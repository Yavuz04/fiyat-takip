"""Site sağlık takibi / Per-site health tracking.

Bir site art arda HEALTH_FAIL_THRESHOLD çalışma boyunca hiç sonuç döndürmezse ya da hata/engel
verirse TEK bir uyarı gönderilir; site tekrar sonuç döndürünce TEK bir "düzeldi" mesajı gönderilir.
Arada her çalışmada mesaj atılmaz.

Bir çalışmada site için durum, tüm ürünlerin sonuçlarından çıkarılır: en az bir üründe sonuç
geldiyse site sağlıklıdır (niş bir ürün için 0 sonuç normal olabilir).
"""

from __future__ import annotations

import re
from collections import defaultdict

from . import config
from .messages import SITE_LABELS, esc
from .scanner import BLOCKED, EMPTY, ERROR, OK, SiteDurumu

_REASON = {
    BLOCKED: "bot engeli (403 / captcha / Cloudflare) — Actions IP'si engellenmiş olabilir",
    ERROR: "hata veriyor — site yapısı değişmiş olabilir",
    EMPTY: "hiç sonuç döndürmüyor — site yapısı değişmiş olabilir",
}


def summarize(durumlar: list[SiteDurumu]) -> dict[str, SiteDurumu]:
    """Ürün bazındaki site durumlarını site bazında tek duruma indirger."""
    by_site: dict[str, list[SiteDurumu]] = defaultdict(list)
    for d in durumlar:
        by_site[d.site].append(d)
    result = {}
    for site, items in by_site.items():
        oks = [d for d in items if d.durum == OK]
        if oks:
            result[site] = SiteDurumu(site, OK, sonuc=sum(d.sonuc for d in oks))
            continue
        # Öncelik: engel > hata > boş
        for kind in (BLOCKED, ERROR, EMPTY):
            bad = [d for d in items if d.durum == kind]
            if bad:
                result[site] = SiteDurumu(site, kind, mesaj=bad[0].mesaj)
                break
    return result


def _stable(message: str) -> str:
    """Hata metnindeki değişken sayıları atar ("timed out after 20012 ms" → "... after # ms"):
    durum dosyası her çalışmada gereksiz yere değişip commit üretmesin."""
    return re.sub(r"\d+", "#", message)[:200]


def update(saglik: dict[str, dict], ozet: dict[str, SiteDurumu], zaman: str) -> list[str]:
    """Sağlık durumunu günceller, gönderilmesi gereken mesajları döndürür.

    Durum sadece anlamlı değişikliklerde değişir (sayaç, uyarı bayrağı, hata türü); her çalışmada
    değişen zaman damgası tutulmaz, böylece sağlıklı çalışmalar commit üretmez.
    """
    messages = []
    for site, d in sorted(ozet.items()):
        s = saglik.setdefault(site, {"ardisik_hata": 0, "uyarildi": False})
        label = SITE_LABELS.get(site, site)
        s.pop("son_basari", None)  # eski sürümden kalan alan
        s["son_durum"] = d.durum
        if d.durum == OK:
            if s.get("uyarildi"):
                messages.append(f"✅ <b>{esc(label)}</b> tekrar çalışıyor ({d.sonuc} sonuç).")
                s["duzeldi"] = zaman
            s.update(ardisik_hata=0, uyarildi=False)
            s.pop("son_hata", None)
            continue
        s["ardisik_hata"] = s.get("ardisik_hata", 0) + 1
        s["son_hata"] = _stable(d.mesaj) if d.mesaj else d.durum
        if s["ardisik_hata"] >= config.HEALTH_FAIL_THRESHOLD and not s.get("uyarildi"):
            s["uyarildi"] = True
            detail = f"\n<code>{esc(d.mesaj[:200])}</code>" if d.mesaj else ""
            messages.append(
                f"⚠️ <b>{esc(label)}</b> {s['ardisik_hata']} çalışmadır {_REASON[d.durum]}.{detail}\n"
                f"Düzelince haber vereceğim; o zamana kadar bu site için tekrar uyarmayacağım."
            )
    return messages
