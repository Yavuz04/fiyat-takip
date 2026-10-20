"""Bir çalışmanın orkestrasyonu / One bot run.

  1. Durumu ve takip listesini yükle
  2. Bekleyen Telegram komutlarını işle (sadece yetkili sohbet), yanıtla, Telegram'a onayla
  3. Her aktif ürünü tüm sitelerde tara (bir site bozulursa diğerleri devam eder)
  4. Spam önleme kurallarına göre bildirilecekleri seç → ürün başına tek mesaj
  5. Fiyat geçmişine (sadece değişenleri) yaz
  6. Site sağlığını güncelle → gerekirse tek uyarı / "düzeldi" mesajı
  7. Durumu kaydet (dry-run'da hiçbir dosya yazılmaz, komutlar Telegram'a onaylanmaz)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from . import config, health, history
from .commands import Commands, preview_text
from .http import HttpClient
from .messages import deal_message, now_tr
from .models import TakipKaydi
from .notify_policy import decide
from .price import format_tl
from .scanner import EMPTY, OK, SiteDurumu, TaramaSonucu, tara
from .scrapers import build_scrapers
from .state import State, load_state, save_state
from .storage import load_watchlist, save_watchlist
from .telegram import Telegram, TelegramError

log = logging.getLogger(__name__)


@dataclass
class RunOptions:
    dry_run: bool = False
    sites: list[str] | None = None
    urun_ids: list[int] | None = None
    enrich: bool = True
    commands: bool = True
    profil: str = "hepsi"  # "bulut" (GitHub), "ev" (PC), "hepsi" (yerel deneme)


@dataclass
class _Run:
    """Bir çalışma boyunca biriken veriler."""
    state: State
    scrapers: list
    notifier: object
    zaman: str
    enrich: bool
    durumlar: list[SiteDurumu] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)

    def scan(self, kayit: TakipKaydi) -> tuple[TaramaSonucu, list]:
        """Tarar, spam kurallarını uygular, durumu (bellekte) ve geçmişi günceller."""
        sonuc = tara(kayit, self.scrapers, enrich=self.enrich)
        calisan = {d.site for d in sonuc.siteler if d.durum in (OK, EMPTY)}
        gecmis = self.state.bildirimler.get(str(kayit.id), {})
        bildirimler, yeni = decide(sonuc.firsat, gecmis, calisan, self.zaman)
        self.state.bildirimler[str(kayit.id)] = yeni
        self.durumlar.extend(sonuc.siteler)
        self.rows.extend(history.record(self.state.son_fiyat, kayit.id, sonuc.eslesen, self.zaman))
        return sonuc, bildirimler

    def preview(self, kayit: TakipKaydi) -> str:
        """/ekle sonrası ilk tarama: sonuçlar komut yanıtında gösterilir (ayrı bildirim gitmez)."""
        sonuc, bildirimler = self.scan(kayit)
        return preview_text(sonuc, len(bildirimler))

    def process(self, kayit: TakipKaydi) -> None:
        sonuc, bildirimler = self.scan(kayit)
        if bildirimler:
            self.notifier.send(deal_message(
                kayit, [b.teklif for b in bildirimler], notes=_notes(bildirimler), title="yeni/ucuzlayan teklif"))
        elif sonuc.firsat:
            log.info("#%d: %d fırsat var ama hepsi daha önce bildirildi (fiyat anlamlı düşmedi)",
                     kayit.id, len(sonuc.firsat))
        elif sonuc.eslesen:
            best = sonuc.eslesen[0]
            log.info("#%d: bütçe altında teklif yok; en ucuz eşleşen %s (%s)",
                     kayit.id, format_tl(best.etkin_fiyat), best.site)
        else:
            log.info("#%d: eşleşen teklif yok", kayit.id)


def _notes(bildirimler) -> dict[str, str]:
    return {
        b.teklif.anahtar: "🆕" if b.onceki_fiyat is None else f"📉 önceki {format_tl(b.onceki_fiyat)}"
        for b in bildirimler
    }


def handle_commands(telegram: Telegram, run: _Run, kayitlar: list[TakipKaydi], dry_run: bool) -> Commands | None:
    """Bekleyen Telegram mesajlarını işler. Yetkisiz sohbetlerden gelenler yok sayılır."""
    state = run.state
    try:
        updates = telegram.get_updates(state.telegram_offset)
    except TelegramError as e:
        log.warning("Telegram komutları alınamadı: %s", e)
        return None
    # /liste'de PC'nin (ev profili) gördüğü fiyatlar da görünsün
    son_fiyat = {**load_state(config.EV_STATE_FILE).son_fiyat, **state.son_fiyat}
    cmds = Commands(kayitlar, son_fiyat, preview=run.preview)
    allowed = str(config.TELEGRAM_CHAT_ID).strip()
    for update in updates:
        state.telegram_offset = update["update_id"] + 1
        msg = update.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != allowed or not allowed:
            log.warning("Yetkisiz sohbetten gelen mesaj yok sayıldı")
            continue
        text = msg.get("text") or ""
        log.info("Mesaj: %s", " | ".join(text.splitlines())[:120])
        for reply in cmds.handle_message(text):
            run.notifier.send(reply)
    log.info("%d Telegram mesajı işlendi", len(updates))

    if updates and not dry_run:
        # Hemen kaydet ve Telegram'a onayla: çalışma sonradan çökse bile komutlar iki kez işlenmesin
        if cmds.changed:
            save_watchlist(kayitlar)
        save_state(state)
        try:
            telegram.get_updates(state.telegram_offset)
        except TelegramError as e:
            log.warning("Telegram onayı gönderilemedi: %s", e)
    return cmds


def run(options: RunOptions, notifier, telegram: Telegram | None = None, state: State | None = None) -> State:
    now = now_tr()
    state = state if state is not None else load_state()
    scrapers = build_scrapers(HttpClient(), only=options.sites, profile=options.profil)
    ctx = _Run(state, scrapers, notifier, now.isoformat(timespec="seconds"), options.enrich)
    kayitlar = load_watchlist()
    log.info("Profil: %s", options.profil)

    previewed: set[int] = set()
    # Komutları sadece tek bir taraf okumalı; aksi halde GitHub ile PC birbirinin mesajlarını "çalar"
    if telegram and options.commands and options.profil != "ev":
        cmds = handle_commands(telegram, ctx, kayitlar, options.dry_run)
        if cmds:
            previewed = cmds.previewed

    aktif = [k for k in kayitlar if k.aktif and k.id not in previewed
             and (not options.urun_ids or k.id in options.urun_ids)]
    log.info("%d aktif ürün, %d site: %s", len(aktif), len(scrapers), ", ".join(s.name for s in scrapers))
    for kayit in aktif:
        ctx.process(kayit)

    # Listeden silinen ürünlerin bildirim kayıtlarını temizle (durdurulanlarınki kalır)
    mevcut = {str(k.id) for k in kayitlar}
    for urun_id in list(state.bildirimler):
        if urun_id not in mevcut:
            del state.bildirimler[urun_id]

    ozet = health.summarize(ctx.durumlar)
    for site, d in sorted(ozet.items()):
        log.info("Sağlık: %-12s %s%s", site, d.durum, f" ({d.mesaj[:120]})" if d.mesaj else "")
    for msg in health.update(state.saglik, ozet, ctx.zaman):
        notifier.send(msg)

    if options.dry_run:
        log.info("Dry-run: durum/geçmiş/takip listesi yazılmadı (%d geçmiş satırı yazılacaktı)", len(ctx.rows))
    else:
        history.append(ctx.rows, now)
        save_state(state)
        log.info("Durum kaydedildi; %d yeni fiyat geçmişi satırı", len(ctx.rows))
    return state
