"""Telegram komutları / Bot commands.

Bot sürekli açık değil: her çalışmada (≈25 dk'da bir) bekleyen mesajlar getUpdates ile alınır,
burada işlenir ve yanıtlanır. Sadece config.TELEGRAM_CHAT_ID sohbetinden gelen mesajlar kabul edilir.

Komutların çoğu saf fonksiyon gibi çalışır: takip listesini (bellekte) değiştirir ve yanıt metni
döndürür. Kaydetme ve gönderme işini runner yapar.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from html import escape

from . import config, history
from .matching import yeni_kayit
from .messages import SITE_LABELS, esc
from .models import TakipKaydi
from .price import format_tl, parse_price
from .scrapers import scraper_classes
from .text import fold

log = logging.getLogger(__name__)

HELP = """🤖 <b>Fiyat takip botu — komutlar</b>

<b>Ürün ekle / listele</b>
/ekle &lt;ürün adı&gt; &lt;max fiyat&gt; — ör. <code>/ekle Huawei M-Pencil 3 3000</code>
/liste — tüm takipler
/detay &lt;id&gt; — bir takibin tüm ayarları
/gecmis &lt;id&gt; — fiyat geçmişi özeti

<b>Düzenle</b>
/haric &lt;id&gt; &lt;kelime&gt; — başlıkta geçerse ele (sil: <code>-kelime</code>, çoklu: virgülle)
/gerekli &lt;id&gt; &lt;kelime&gt; — başlıkta mutlaka geçsin (sil: <code>-kelime</code>)
/minfiyat &lt;id&gt; &lt;değer&gt; — altı aksesuar/alakasız sayılır
/maxfiyat &lt;id&gt; &lt;değer&gt; — bildirim eşiği (bütçe)
/garanti &lt;id&gt; tr|hepsi — tr: ithalatçı/yurt dışı garantilileri ele
/siteler &lt;id&gt; trendyol,n11|hepsi — sadece bu sitelerde ara

<b>Durum</b>
/durdur &lt;id&gt;, /devam &lt;id&gt;, /sil &lt;id&gt;
/yardim — bu mesaj

⏱ Bot sürekli açık değil; komutlar bir sonraki çalışmada (<b>en fazla ~25 dk, GitHub yoğunsa daha geç</b>) işlenir."""


class CommandError(Exception):
    """Kullanıcıya gösterilecek hata (yanlış kullanım vb.)."""


def _parse_id(arg: str) -> int:
    try:
        return int(arg.lstrip("#"))
    except ValueError:
        raise CommandError(f"Geçersiz id: <code>{esc(arg)}</code> (ör. /liste ile bak)") from None


def _parse_amount(arg: str) -> float:
    value = parse_price(arg)
    if value is None:
        raise CommandError(f"Geçersiz tutar: <code>{esc(arg)}</code>")
    return value


def _words(text: str) -> list[str]:
    return [w.strip() for w in text.split(",") if w.strip()]


def _fmt_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(config.TZ).strftime("%d.%m %H:%M")
    except ValueError:
        return iso


class Commands:
    def __init__(
        self,
        kayitlar: list[TakipKaydi],
        son_fiyat: dict[str, float] | None = None,
        preview: Callable[[TakipKaydi], str] | None = None,
    ):
        self.kayitlar = kayitlar
        self.son_fiyat = son_fiyat or {}
        self.preview = preview          # /ekle sonrası ilk tarama (runner verir)
        self.changed = False            # takip listesi değişti mi
        self.previewed: set[int] = set()  # bu çalışmada zaten taranmış ürünler

    # --- yardımcılar -------------------------------------------------------

    def _get(self, arg: str) -> TakipKaydi:
        urun_id = _parse_id(arg)
        for k in self.kayitlar:
            if k.id == urun_id:
                return k
        raise CommandError(f"#{urun_id} bulunamadı. /liste ile bak.")

    def _need(self, args: list[str], n: int, usage: str) -> None:
        if len(args) < n:
            raise CommandError(f"Kullanım: {usage}")

    def _cheapest(self, k: TakipKaydi) -> tuple[float, str] | None:
        prices = [(p, key.split("|", 1)[1]) for key, p in self.son_fiyat.items() if key.split("|", 1)[0] == str(k.id)]
        return min(prices) if prices else None

    # --- giriş noktası -----------------------------------------------------

    def handle_message(self, text: str) -> list[str]:
        """Bir Telegram mesajını işler. Alt alta yazılmış birden fazla komut desteklenir:
        '/' ile başlayan her satır ayrı bir komuttur; diğer satırlar yok sayılır."""
        commands = [line.strip() for line in (text or "").splitlines() if line.strip().startswith("/")]
        replies = [self.handle(c) for c in commands]
        return [r for r in replies if r]

    def handle(self, text: str) -> str | None:
        """Bir mesajı işler, yanıt metnini döndürür (komut değilse None)."""
        text = (text or "").strip()
        if not text.startswith("/"):
            return None
        head, _, rest = text.partition(" ")
        name = head[1:].split("@", 1)[0].lower()  # /ekle@BotAdi → ekle
        handler = getattr(self, f"cmd_{name}", None)
        if handler is None:
            return f"Bilinmeyen komut: <code>{esc(head)}</code>\n/yardim ile komutları gör."
        try:
            return handler(rest.strip())
        except CommandError as e:
            return f"⚠️ {e}"

    # --- komutlar ----------------------------------------------------------

    def cmd_start(self, rest: str) -> str:
        return HELP

    cmd_yardim = cmd_help = cmd_start

    def cmd_ekle(self, rest: str) -> str:
        parts = rest.split()
        if parts and parts[-1].lower() in ("tl", "₺", "try"):  # "/ekle ... 3000 TL"
            parts = parts[:-1]
        self._need(parts, 2, "/ekle &lt;ürün adı&gt; &lt;max fiyat&gt;  (ör. /ekle Huawei M-Pencil 3 3000)")
        max_fiyat = _parse_amount(parts[-1])
        sorgu = " ".join(parts[:-1])
        new_id = max((k.id for k in self.kayitlar), default=0) + 1
        kayit = yeni_kayit(new_id, sorgu, max_fiyat)
        self.kayitlar.append(kayit)
        self.changed = True
        text = (
            f"✅ <b>#{kayit.id} eklendi:</b> {esc(kayit.sorgu)}\n"
            f"Bütçe ≤ {format_tl(kayit.max_fiyat)} · min {format_tl(kayit.min_fiyat)}\n"
            f"Gerekli: {esc(', '.join(kayit.gerekli))}\n"
            f"Hariç: {len(kayit.haric)} kelime (aksesuar, yenilenmiş, model varyantları…) — /detay {kayit.id}"
        )
        if self.preview:
            self.previewed.add(kayit.id)
            text += "\n\n" + self.preview(kayit)
        return text

    def cmd_liste(self, rest: str) -> str:
        if not self.kayitlar:
            return "Takip listesi boş. /ekle ile ürün ekle."
        lines = ["📋 <b>Takip listesi</b>"]
        for k in sorted(self.kayitlar, key=lambda k: k.id):
            durum = "✅" if k.aktif else "⏸"
            line = f"{durum} <b>#{k.id}</b> {esc(k.sorgu)} — ≤ {format_tl(k.max_fiyat)}"
            best = self._cheapest(k)
            if best:
                line += f"\n      en ucuz son görülen: {format_tl(best[0])} ({esc(SITE_LABELS.get(best[1], best[1]))})"
            lines.append(line)
        return "\n".join(lines)

    def cmd_detay(self, rest: str) -> str:
        self._need(rest.split(), 1, "/detay &lt;id&gt;")
        k = self._get(rest.split()[0])
        siteler = ", ".join(k.siteler) if k.siteler else "hepsi"
        return (
            f"🔎 <b>#{k.id} {esc(k.sorgu)}</b> ({'aktif' if k.aktif else 'durduruldu'})\n"
            f"Bütçe (max): {format_tl(k.max_fiyat)}\nMin fiyat: {format_tl(k.min_fiyat)}\n"
            f"Gerekli: {esc(', '.join(k.gerekli) or '-')}\n"
            f"Hariç: {esc(', '.join(k.haric) or '-')}\n"
            f"Garanti: {'sadece TR/bilinmeyen' if k.garanti == 'tr' else 'hepsi'}\nSiteler: {esc(siteler)}"
        )

    def _set_active(self, rest: str, active: bool) -> str:
        self._need(rest.split(), 1, f"/{'devam' if active else 'durdur'} &lt;id&gt;")
        k = self._get(rest.split()[0])
        k.aktif = active
        self.changed = True
        return f"{'▶️' if active else '⏸'} #{k.id} {esc(k.sorgu)} {'tekrar takipte' if active else 'durduruldu'}."

    def cmd_durdur(self, rest: str) -> str:
        return self._set_active(rest, False)

    def cmd_devam(self, rest: str) -> str:
        return self._set_active(rest, True)

    def cmd_sil(self, rest: str) -> str:
        self._need(rest.split(), 1, "/sil &lt;id&gt;")
        k = self._get(rest.split()[0])
        self.kayitlar.remove(k)
        self.changed = True
        return f"🗑 #{k.id} {esc(k.sorgu)} silindi."

    def _edit_words(self, rest: str, attr: str, usage: str) -> str:
        urun, _, words = rest.partition(" ")
        self._need([urun, words] if words.strip() else [urun], 2, usage)
        k = self._get(urun)
        current: list[str] = getattr(k, attr)
        added, removed = [], []
        # Karşılaştırma Türkçe uyumlu fold() ile: "KILIF" = "kılıf" (str.casefold bunu bilmez)
        for w in _words(words):
            if w.startswith("-"):
                target = fold(w[1:])
                before = len(current)
                current[:] = [c for c in current if fold(c) != target]
                if len(current) < before:
                    removed.append(w[1:].strip())
            elif fold(w) not in (fold(c) for c in current):
                current.append(w)
                added.append(w)
        self.changed = self.changed or bool(added or removed)
        parts = []
        if added:
            parts.append("eklendi: " + esc(", ".join(added)))
        if removed:
            parts.append("silindi: " + esc(", ".join(removed)))
        label = "Hariç" if attr == "haric" else "Gerekli"
        return f"✏️ #{k.id} {label.lower()} — {'; '.join(parts) or 'değişiklik yok'}\n{label}: {esc(', '.join(current) or '-')}"

    def cmd_haric(self, rest: str) -> str:
        return self._edit_words(rest, "haric", "/haric &lt;id&gt; &lt;kelime&gt;  (sil: -kelime)")

    def cmd_gerekli(self, rest: str) -> str:
        return self._edit_words(rest, "gerekli", "/gerekli &lt;id&gt; &lt;kelime&gt;  (sil: -kelime)")

    def _set_amount(self, rest: str, attr: str, usage: str) -> str:
        parts = rest.split()
        self._need(parts, 2, usage)
        k = self._get(parts[0])
        value = _parse_amount(parts[1])
        setattr(k, attr, value)
        if k.min_fiyat > k.max_fiyat:
            raise CommandError(f"Min fiyat ({format_tl(k.min_fiyat)}) max fiyattan ({format_tl(k.max_fiyat)}) büyük olamaz.")
        self.changed = True
        return f"✏️ #{k.id} {'min' if attr == 'min_fiyat' else 'max'} fiyat: {format_tl(value)}"

    def cmd_minfiyat(self, rest: str) -> str:
        return self._set_amount(rest, "min_fiyat", "/minfiyat &lt;id&gt; &lt;değer&gt;")

    def cmd_maxfiyat(self, rest: str) -> str:
        return self._set_amount(rest, "max_fiyat", "/maxfiyat &lt;id&gt; &lt;değer&gt;")

    def cmd_garanti(self, rest: str) -> str:
        parts = rest.split()
        self._need(parts, 2, "/garanti &lt;id&gt; tr|hepsi")
        k = self._get(parts[0])
        if parts[1].lower() not in ("tr", "hepsi"):
            raise CommandError("Değer <code>tr</code> ya da <code>hepsi</code> olmalı.")
        k.garanti = parts[1].lower()
        self.changed = True
        return f"✏️ #{k.id} garanti filtresi: {'sadece TR/bilinmeyen' if k.garanti == 'tr' else 'hepsi'}"

    def cmd_siteler(self, rest: str) -> str:
        urun, _, value = rest.partition(" ")
        self._need([urun, value] if value.strip() else [urun], 2, "/siteler &lt;id&gt; trendyol,n11|hepsi")
        k = self._get(urun)
        known = sorted(scraper_classes())
        if value.strip().lower() == "hepsi":
            k.siteler = None
        else:
            sites = [s.lower() for s in _words(value.replace(" ", ","))]
            unknown = [s for s in sites if s not in known]
            if unknown:
                raise CommandError(f"Bilinmeyen site: {esc(', '.join(unknown))}\nGeçerli: {', '.join(known)}")
            k.siteler = sites
        self.changed = True
        return f"✏️ #{k.id} siteler: {esc(', '.join(k.siteler) if k.siteler else 'hepsi')}"

    def cmd_gecmis(self, rest: str) -> str:
        self._need(rest.split(), 1, "/gecmis &lt;id&gt;")
        k = self._get(rest.split()[0])
        rows = [r for r in history.read() if r["urun_id"] == str(k.id)]
        if not rows:
            return f"#{k.id} için henüz fiyat geçmişi yok."
        lowest = min(rows, key=lambda r: float(r["fiyat"]))
        last_by_site: dict[str, dict] = {}
        changes = []
        for r in rows:
            prev = last_by_site.get(r["site"])
            if prev:
                changes.append((r, float(prev["fiyat"])))
            last_by_site[r["site"]] = r
        site = lambda s: esc(SITE_LABELS.get(s, s))  # noqa: E731
        lines = [
            f"📈 <b>#{k.id} {esc(k.sorgu)}</b> — son {config.HISTORY_KEEP_DAYS} gün",
            f"En düşük: <b>{format_tl(float(lowest['fiyat']))}</b> · {site(lowest['site'])} · {_fmt_time(lowest['zaman'])}",
            "",
            "<b>Son görülen (site başına):</b>",
        ]
        for s, r in sorted(last_by_site.items(), key=lambda x: float(x[1]["fiyat"])):
            lines.append(f"  {site(s)}: {format_tl(float(r['fiyat']))} ({_fmt_time(r['zaman'])})")
        if changes:
            lines += ["", "<b>Son değişiklikler:</b>"]
            for r, prev in changes[-8:][::-1]:
                arrow = "📉" if float(r["fiyat"]) < prev else "📈"
                lines.append(f"  {_fmt_time(r['zaman'])} {site(r['site'])}: "
                             f"{format_tl(prev)} → {format_tl(float(r['fiyat']))} {arrow}")
        return "\n".join(lines)


def preview_text(sonuc, firsat_bildirildi: int, limit: int = 5) -> str:
    """/ekle sonrası ilk tarama özeti: eşleşenler + filtre kontrolü için elenen örnekler."""
    sites_ok = sum(1 for d in sonuc.siteler if d.durum in ("ok", "bos"))
    sites_bad = [d.site for d in sonuc.siteler if d.durum not in ("ok", "bos")]
    lines = [
        f"🔍 <b>İlk tarama:</b> {sites_ok} site, {sonuc.toplam} sonuç → {len(sonuc.eslesen)} eşleşti, "
        f"{len(sonuc.firsat)} bütçe altında"
    ]
    if sites_bad:
        lines.append(f"(taranamayan: {esc(', '.join(sites_bad))})")
    if sonuc.eslesen:
        lines.append("\n<b>En ucuz eşleşenler:</b>")
        for t in sonuc.eslesen[:limit]:
            mark = "✅" if t in sonuc.firsat else "▫️"
            lines.append(f"{mark} {format_tl(t.etkin_fiyat)} · {esc(SITE_LABELS.get(t.site, t.site))} · "
                         f"<a href=\"{escape(t.url, quote=True)}\">{esc(t.baslik[:70])}</a>")
    else:
        lines.append("\nEşleşen sonuç yok — gerekli kelimeler fazla katı olabilir.")
    # Filtre kontrolü: "gerekli yok" çoğunlukla alakasız ürünlerdir; diğer sebepler daha öğreticidir
    samples = [(t, r) for t, r in sonuc.elenen if not r.startswith("gerekli")][:limit]
    samples += [(t, r) for t, r in sonuc.elenen if r.startswith("gerekli")][: max(0, limit - len(samples))]
    if samples:
        lines.append("\n<b>Elenen örnekler (filtre kontrolü):</b>")
        for t, r in samples:
            price = format_tl(t.etkin_fiyat) if t.etkin_fiyat else "?"
            lines.append(f"✖️ {esc(t.baslik[:60])} ({price}) → <i>{esc(r)}</i>")
    if firsat_bildirildi:
        lines.append(f"\nBütçe altındaki {firsat_bildirildi} teklif bildirildi sayıldı; fiyat düşmedikçe tekrar gelmez.")
    return "\n".join(lines)
