"""Fiyat geçmişi / Price history (data/price_history.csv).

Her ürün × site için o çalışmadaki EN UCUZ eşleşen teklif (bütçe fark etmez), sadece fiyat bir
önceki kayda göre değiştiyse yazılır. Böylece dosya ve git geçmişi şişmez.
HISTORY_KEEP_DAYS günden eski satırlar budanır.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from . import config
from .models import Teklif

FIELDS = ["zaman", "urun_id", "site", "fiyat", "satici", "baslik", "url"]


def record(son_fiyat: dict[str, float], urun_id: int, eslesen: list[Teklif], zaman: str) -> list[dict]:
    """Değişen en ucuz fiyatları satır olarak döndürür ve son_fiyat'ı günceller."""
    cheapest: dict[str, Teklif] = {}
    for t in eslesen:
        if t.etkin_fiyat is not None and (t.site not in cheapest or t.etkin_fiyat < cheapest[t.site].etkin_fiyat):
            cheapest[t.site] = t
    rows = []
    for site, t in sorted(cheapest.items()):
        key = f"{urun_id}|{site}"
        if son_fiyat.get(key) == t.etkin_fiyat:
            continue
        son_fiyat[key] = t.etkin_fiyat
        rows.append({"zaman": zaman, "urun_id": urun_id, "site": site, "fiyat": t.etkin_fiyat,
                     "satici": t.satici or "", "baslik": t.baslik[:150], "url": t.url})
    return rows


def read(path: Path | None = None) -> list[dict]:
    path = path or config.HISTORY_FILE
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_all() -> list[dict]:
    """GitHub (bulut) ve PC (ev) profillerinin geçmişini zaman sırasıyla birleştirir."""
    paths = dict.fromkeys([config.HISTORY_FILE, config.EV_HISTORY_FILE])
    rows = [r for p in paths for r in read(p)]
    return sorted(rows, key=lambda r: r["zaman"])


def append(rows: list[dict], now: datetime, path: Path | None = None) -> None:
    """Yeni satırları ekler ve eski satırları budar. Yeni satır yoksa dosyaya dokunmaz."""
    if not rows:
        return
    path = path or config.HISTORY_FILE
    cutoff = (now - timedelta(days=config.HISTORY_KEEP_DAYS)).isoformat(timespec="seconds")
    kept = [r for r in read(path) if r["zaman"] >= cutoff] + rows
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(kept)
