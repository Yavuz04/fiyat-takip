"""Hepsiburada.

Arama: https://www.hepsiburada.com/ara?q=...
  Sayfadaki `<script id="reduxStore">` JSON'u → voltranState.fragmentsMap.*.ProductList.html
  Bu HTML parçasının içinde `'STATE': {...}` JSON'u var → data.products[].variantList[]
  Her varyant (renk) ayrı bir ilan:
    listing.priceInfo.price           → satış fiyatı
    listing.priceInfo.originalPrice   → liste fiyatı (sadece discountType != NoDiscount ise eski fiyat sayılır;
                                        aksi halde sitede üstü çizili gösterilmiyor)
    listing.merchantName              → satıcı (çoğunlukla sadece varsayılan varyantta dolu)
    procurable                        → satın alınabilir (stok)
  Taksit ("Peşin fiyatına 3 x ...") ve kuponlar ayrı etiketlerde durur, fiyata karışmaz.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from ..embedded import json_after, script_json
from ..matching import garanti_tespit
from ..models import Teklif
from ..price import parse_price
from ..text import fold
from .base import ParseError, Scraper

BASE = "https://www.hepsiburada.com"
_BASKET = re.compile(r"sepette\D*([\d.,]+)")


def _basket_price(listing: dict) -> float | None:
    """Kampanya etiketlerinde 'Sepette 54.999 TL' gibi bir metin varsa o fiyatı döndürür."""
    labels = (listing.get("categorizedLabels") or {}).values()
    for group in labels:
        for label in group or []:
            m = _BASKET.search(fold(str(label.get("text", ""))).replace(" ", "")) if isinstance(label, dict) else None
            if m:
                return parse_price(m.group(1))
    return None


def _product_state(html: str) -> dict:
    store = script_json(html, "reduxStore")
    if not store:
        raise ParseError("Hepsiburada: reduxStore bulunamadı")
    for fragment in ((store.get("voltranState") or {}).get("fragmentsMap") or {}).values():
        product_list = (fragment or {}).get("ProductList")
        if product_list and product_list.get("html"):
            state = json_after(product_list["html"], "'STATE':")
            if state and "data" in state:
                return state["data"]
    raise ParseError("Hepsiburada: ProductList STATE bulunamadı")


def parse_search(html: str) -> list[Teklif]:
    data = _product_state(html)
    offers, seen = [], set()
    for product in data.get("products") or []:
        for v in product.get("variantList") or []:
            sku = v.get("sku")
            if not sku or sku in seen or not v.get("url"):
                continue
            seen.add(sku)
            listing = v.get("listing") or {}
            info = listing.get("priceInfo") or {}
            fiyat = parse_price(info.get("price"))
            original = parse_price(info.get("originalPrice"))
            discounted = info.get("discountType") not in (None, "", "NoDiscount") or (info.get("discountRate") or 0) > 0
            eski = original if discounted and original and fiyat and original > fiyat else None
            sepet = _basket_price(listing)
            if sepet and fiyat and sepet >= fiyat:
                sepet = None
            title = v.get("name", "")
            offers.append(Teklif(
                site="hepsiburada", baslik=title, url=BASE + v["url"], fiyat=fiyat, sepet_fiyati=sepet,
                eski_fiyat=eski, satici=listing.get("merchantName") or None,
                garanti=garanti_tespit(title), stokta=bool(v.get("procurable", True)),
            ))
    return offers


class Hepsiburada(Scraper):
    name = "hepsiburada"
    label = "Hepsiburada"

    def search(self, query: str) -> list[Teklif]:
        return parse_search(self.http.get(f"{BASE}/ara?q={quote_plus(query)}").text)
