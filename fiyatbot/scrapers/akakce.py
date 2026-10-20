"""Akakçe (fiyat karşılaştırma).

Arama: https://www.akakce.com/arama/?q=...
  CSS sınıfları sürümlü/kısaltılmış (pt_v8 vb.) ve kırılgan; bunun yerine Astro bileşeninin
  `<astro-island component-url=".../SearchWrapper..." props="...">` özniteliğindeki JSON kullanılır:
    searchData.productList.products[]: name, url, price (tüm satıcılar arasında en düşük), countOfPrices
  price == 0 → sadece ikinci el teklifi var (minOfNonNewPrice) → atlanır.
  Satıcı adı arama sayfasında yok; "N fiyat arasında en ucuz" bilgisi verilir.
"""

from __future__ import annotations

import json
from urllib.parse import quote_plus

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..embedded import astro_revive
from ..matching import garanti_tespit
from ..models import Teklif
from ..price import parse_price
from .base import ParseError, Scraper

BASE = "https://www.akakce.com"


def _search_data(html: str) -> dict:
    for island in HTMLParser(html).css("astro-island"):
        props = island.attributes.get("props")
        if props and "searchData" in props:
            data = astro_revive(json.loads(props))
            if isinstance(data.get("searchData"), dict):
                return data["searchData"]
    raise ParseError("Akakçe: SearchWrapper props (searchData) bulunamadı")


def parse_search(html: str) -> list[Teklif]:
    products = (_search_data(html).get("productList") or {}).get("products") or []
    offers = []
    for p in products:
        fiyat = parse_price(p.get("price"))
        if not fiyat or not p.get("url"):
            continue
        count = p.get("countOfPrices") or 0
        brand = p.get("mkName") or ""
        name = p.get("name", "")
        title = name if brand in ("", "-") or name.lower().startswith(brand.lower()) else f"{brand} {name}"
        offers.append(Teklif(
            site="akakce", baslik=title, url=BASE + p["url"], fiyat=fiyat,
            satici=f"{count} fiyat arasında en ucuz" if count > 1 else None,
            garanti=garanti_tespit(name),
        ))
    return offers


class Akakce(Scraper):
    name = "akakce"
    label = "Akakçe"
    enabled_on_ci = False  # Actions IP'leri tüm sitede Cloudflare 403 (2026-10 erişim testi)

    def search(self, query: str) -> list[Teklif]:
        return parse_search(self.http.get(f"{BASE}/arama/?q={quote_plus(query)}").text)
