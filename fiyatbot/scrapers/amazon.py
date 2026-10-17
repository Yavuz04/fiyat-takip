"""Amazon.com.tr.

Arama: https://www.amazon.com.tr/s?k=...  (gömülü JSON yok; Amazon'un uzun süredir sabit olan
`data-component-type` / `data-cy` öznitelikleri kullanılır)
  Kart: [data-component-type=s-search-result] (data-asin)
  Fiyat: [data-cy=price-recipe] içindeki ilk .a-price (üstü çizili olmayan) → .a-offscreen
  Eski fiyat: .a-text-price .a-offscreen ("Önceki: ...")
  Kuponlu "indirimli fiyat ... kupon ile" ve takas indirimi KULLANILMAZ (ödeme anında garanti değil).
  Fiyatı olmayan kart (öne çıkan teklif yok / stokta yok) fiyat=None döner ve filtrede elenir.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..matching import garanti_tespit
from ..models import Teklif
from ..price import parse_price
from .base import ParseError, Scraper

BASE = "https://www.amazon.com.tr"
_SPONSORED = re.compile(r"^\s*Sponsorlu( Reklam)?\s*[-–:]\s*", re.I)


def parse_search(html: str) -> list[Teklif]:
    tree = HTMLParser(html)
    cards = tree.css("[data-component-type=s-search-result]")
    if not cards and "s-search-results" not in html and "s-result-list" not in html:
        raise ParseError("Amazon: arama sonuç kartları bulunamadı")

    offers, seen = [], set()
    for card in cards:
        asin = card.attributes.get("data-asin")
        title_node = card.css_first("h2")
        if not asin or asin in seen or not title_node:
            continue
        seen.add(asin)
        title = title_node.attributes.get("aria-label") or title_node.text(strip=True)
        title = _SPONSORED.sub("", title)

        fiyat = eski = None
        recipe = card.css_first("[data-cy=price-recipe]")
        if recipe:
            for price_node in recipe.css(".a-price"):
                if "a-text-price" in (price_node.attributes.get("class") or ""):
                    continue
                shown = price_node.css_first(".a-offscreen")
                fiyat = parse_price(shown.text()) if shown else None
                break
            old = recipe.css_first(".a-text-price .a-offscreen")
            eski = parse_price(old.text()) if old else None
            if eski and fiyat and eski <= fiyat:
                eski = None

        offers.append(Teklif(
            site="amazon", baslik=title, url=f"{BASE}/dp/{asin}", fiyat=fiyat, eski_fiyat=eski,
            garanti=garanti_tespit(title),
        ))
    return offers


class Amazon(Scraper):
    name = "amazon"
    label = "Amazon"

    def search(self, query: str) -> list[Teklif]:
        return parse_search(self.http.get(f"{BASE}/s?k={quote_plus(query)}").text)
