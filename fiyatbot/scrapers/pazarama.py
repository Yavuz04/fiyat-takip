"""Pazarama.

Arama: https://www.pazarama.com/arama?q=...
  `window.__NUXT__` bir JS fonksiyonu (JSON değil), bu yüzden sunucuda üretilmiş kart HTML'i okunur.
  Kararlı `data-testid` öznitelikleri kullanılır:
    [data-testid=listing-product-card-grid]          → kart
    [data-testid=product-card-title]                 → başlık
    [data-testid=base-product-card-price-container]  → fiyat alanı
  Fiyat alanında "Sepette" yazısı varsa: önceki fiyat peşin, sonraki fiyat sepet fiyatıdır.
  "Son 10 Günün En Düşük Fiyatı" gibi bilgi metinleri (TL içermez) atlanır.
"""

from __future__ import annotations

from urllib.parse import quote

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..matching import garanti_tespit
from ..models import Teklif
from ..price import parse_price
from ..text import fold
from .base import ParseError, Scraper

BASE = "https://www.pazarama.com"


def _price_parts(container) -> tuple[list[float], int | None]:
    """Fiyat alanındaki fiyatlar (sırayla) ve 'Sepette' etiketinin kaç fiyattan sonra geldiği."""
    prices, basket_at = [], None
    for node in container.traverse():
        if node.tag == "-text":
            continue
        text = node.text(deep=False, strip=True)
        if not text:
            continue
        if fold(text) == "sepette":
            basket_at = len(prices)
        elif "TL" in text:
            price = parse_price(text)
            if price:
                prices.append(price)
    return prices, basket_at


def parse_search(html: str) -> list[Teklif]:
    tree = HTMLParser(html)
    cards = tree.css("[data-testid=listing-product-card-grid]")
    if not cards and "product-card" not in html:
        raise ParseError("Pazarama: ürün kartları bulunamadı")

    offers, seen = [], set()
    for card in cards:
        link = card.css_first("a[href]")
        title_node = card.css_first("[data-testid=product-card-title]")
        price_node = card.css_first("[data-testid=base-product-card-price-container]")
        if not link or not title_node or not price_node:
            continue
        href = link.attributes.get("href", "").split("?")[0]
        if not href or href in seen:
            continue
        seen.add(href)

        prices, basket_at = _price_parts(price_node)
        fiyat = sepet = eski = None
        if basket_at is not None and 0 < basket_at < len(prices):
            fiyat, sepet = prices[basket_at - 1], prices[basket_at]
        elif len(prices) >= 2:
            fiyat, eski = min(prices[:2]), max(prices[:2])
        elif prices:
            fiyat = prices[0]
        if sepet and fiyat and sepet >= fiyat:
            sepet = None

        title = " ".join(title_node.text(strip=True).split())
        offers.append(Teklif(
            site="pazarama", baslik=title, url=href if href.startswith("http") else BASE + href,
            fiyat=fiyat, sepet_fiyati=sepet, eski_fiyat=eski, garanti=garanti_tespit(title),
        ))
    return offers


class Pazarama(Scraper):
    name = "pazarama"
    label = "Pazarama"

    def search(self, query: str) -> list[Teklif]:
        return parse_search(self.http.get(f"{BASE}/arama?q={quote(query)}").text)
