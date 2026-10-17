"""Telegram mesaj şablonları / Message templates (parse_mode=HTML).

Kullanıcıdan/siteden gelen her metin html.escape'ten geçer; başlıklarda geçen <, >, & mesajı bozmaz.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from . import config
from .models import GARANTI_BILINMIYOR, GARANTI_ETIKET, TakipKaydi, Teklif
from .price import format_tl

SITE_LABELS = {
    "trendyol": "Trendyol", "hepsiburada": "Hepsiburada", "amazon": "Amazon", "n11": "n11",
    "pttavm": "PttAVM", "pazarama": "Pazarama", "akakce": "Akakçe", "cimri": "Cimri", "epey": "epey",
}


def esc(text: object) -> str:
    return escape(str(text), quote=False)


def now_tr() -> datetime:
    return datetime.now(config.TZ)


def format_time(dt: datetime | None = None) -> str:
    return (dt or now_tr()).astimezone(config.TZ).strftime("%d.%m.%Y %H:%M")


def format_offer(i: int, t: Teklif, note: str | None = None) -> str:
    price = f"<b>{format_tl(t.fiyat)}</b>" if t.fiyat else "<b>?</b>"
    if t.eski_fiyat and t.fiyat and t.eski_fiyat > t.fiyat:
        price += f" <s>{format_tl(t.eski_fiyat)}</s>"
    if t.indirim_orani:
        price += f" (−%{t.indirim_orani:g})".replace(".", ",")
    if note:
        price += f"  {note}"
    lines = [f"{i}. {price}"]
    if t.sepet_fiyati and (not t.fiyat or t.sepet_fiyati < t.fiyat):
        lines.append(f"   🛒 Sepette <b>{format_tl(t.sepet_fiyati)}</b>")
    lines.append(f"   {esc(t.baslik[:120])}")

    meta = [SITE_LABELS.get(t.site, t.site)]
    if t.satici:
        meta.append(esc(t.satici) + (f" ⭐{t.satici_puani:g}" if t.satici_puani else ""))
    if t.garanti != GARANTI_BILINMIYOR:
        meta.append(f"🛡 {GARANTI_ETIKET[t.garanti]}")
    lines.append("   🏪 " + " · ".join(meta))
    lines.append(f'   <a href="{escape(t.url, quote=True)}">Ürüne git →</a>')
    return "\n".join(lines)


def deal_message(kayit: TakipKaydi, teklifler: list[Teklif], limit: int = config.MAX_RESULTS_PER_MESSAGE,
                 when: datetime | None = None, notes: dict[str, str] | None = None,
                 title: str = "uygun teklif", icon: str = "🔔") -> str:
    """Bir ürün için teklifleri ucuzdan pahalıya, en fazla `limit` tane listeler.

    notes: ilan anahtarı → kısa not (ör. "🆕", "📉 önceki 2.999 TL")
    """
    items = sorted(teklifler, key=lambda t: t.etkin_fiyat or float("inf"))
    shown = items[:limit]
    header = (
        f"{icon} <b>{esc(kayit.sorgu)}</b> (#{kayit.id})\n"
        f"Bütçe ≤ {format_tl(kayit.max_fiyat)} · {len(items)} {title} · {format_time(when)}"
    )
    notes = notes or {}
    body = [format_offer(i, t, notes.get(t.anahtar)) for i, t in enumerate(shown, 1)]
    if len(items) > len(shown):
        body.append(f"… ve {len(items) - len(shown)} teklif daha")
    return "\n\n".join([header, *body])
