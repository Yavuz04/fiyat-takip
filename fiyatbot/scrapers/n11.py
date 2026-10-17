"""n11.

Arama: https://www.n11.com/arama?q=...  (sunucu tarafında üretilmiş Vue HTML)
  - Kartlar: `a.product-item` → başlık `h2.product-item-title`, son fiyat `h3.price-currency`,
    üstü çizili fiyat `.old-price .price`, rozet `.price-badge` ("SEPETTE" ise son fiyat sepet fiyatıdır
    ve üstü çizili görünen fiyat aslında peşin satış fiyatıdır).
  - Stok: JSON-LD ItemList → offers.availability (karta URL ile eşlenir).
  - Satıcı adı arama sayfasında yok.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..embedded import ld_products
from ..matching import garanti_tespit
from ..models import Teklif
from ..price import parse_price
from ..text import fold
from .base import ParseError, Scraper

BASE = "https://www.n11.com"


def _text(node, selector: str) -> str:
    found = node.css_first(selector)
    return found.text(strip=True) if found else ""


def parse_search(html: str) -> list[Teklif]:
    tree = HTMLParser(html)
    cards = tree.css("a.product-item")
    if not cards and "searchResultContainer" not in html:
        raise ParseError("n11: ürün kartları (a.product-item) bulunamadı")

    stock = {}
    for prod in ld_products(html):
        offer = prod.get("offers") or {}
        if prod.get("url"):
            stock[prod["url"].split("?")[0]] = "InStock" in str(offer.get("availability", ""))

    offers, seen = [], set()
    for card in cards:
        href = (card.attributes.get("href") or "").split("?")[0]
        if not href or href in seen:
            continue
        seen.add(href)
        url = href if href.startswith("http") else BASE + href
        title = _text(card, ".product-item-title")
        final = parse_price(_text(card, ".price-currency"))
        old = parse_price(_text(card, ".old-price .price"))
        is_basket = "sepette" in fold(_text(card, ".price-badge"))

        fiyat, sepet, eski = final, None, old
        if is_basket and old and final and final < old:
            fiyat, sepet, eski = old, final, None
        offers.append(Teklif(
            site="n11", baslik=title, url=url, fiyat=fiyat, sepet_fiyati=sepet, eski_fiyat=eski,
            garanti=garanti_tespit(title), stokta=stock.get(url),
        ))
    return offers


class N11(Scraper):
    name = "n11"
    label = "n11"

    def search(self, query: str) -> list[Teklif]:
        return parse_search(self.http.get(f"{BASE}/arama?q={quote_plus(query)}").text)
