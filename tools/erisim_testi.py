"""Erişim testi: her sitenin birkaç herkese açık sayfasını botun normal HTTP istemcisiyle BİR KEZ ister,
durum kodunu ve engel olup olmadığını raporlar. Siteleri yormamak için istekler arası bekleme vardır.

Kullanım:  python tools/erisim_testi.py
Amaç: Actions IP'lerinde engelin sitenin tamamına mı yoksa sadece belirli sayfalara mı uygulandığını görmek.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fiyatbot.http import BlockedError, FetchError, HttpClient  # noqa: E402

Q = "huawei+m+pencil+3"
URLS = {
    "trendyol": ["https://www.trendyol.com/", f"https://www.trendyol.com/sr?q={Q}"],
    "akakce": ["https://www.akakce.com/", f"https://www.akakce.com/arama/?q={Q}"],
    "cimri": ["https://www.cimri.com/", f"https://www.cimri.com/arama?q={Q}"],
    "pttavm": ["https://www.pttavm.com/", f"https://www.pttavm.com/arama?q={Q}"],
    "pazarama": ["https://www.pazarama.com/", f"https://www.pazarama.com/arama?q={Q}"],
    "epey": ["https://www.epey.com/", f"https://www.epey.com/ara/?ara={Q}"],
    "amazon": ["https://www.amazon.com.tr/", f"https://www.amazon.com.tr/s?k={Q}"],
    "hepsiburada": ["https://www.hepsiburada.com/", f"https://www.hepsiburada.com/ara?q={Q}"],
    "n11": ["https://www.n11.com/", f"https://www.n11.com/arama?q={Q}"],
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    http = HttpClient(retries=1, min_interval=2.0)
    for site, urls in URLS.items():
        for url in urls:
            try:
                resp = http.get(url)
                title = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.S)
                result = f"OK {resp.status_code} ({len(resp.text) // 1024} KB) {title.group(1).strip()[:50] if title else ''}"
            except BlockedError as e:
                body = http.last_body.get(url.split("/")[2], "")
                title = re.search(r"<title[^>]*>(.*?)</title>", body, re.S)
                result = f"ENGEL {e} — sayfa: {title.group(1).strip()[:60] if title else '?'}"
            except FetchError as e:
                result = f"HATA {e}"
            print(f"{site:12} {url[:60]:60} {result}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
