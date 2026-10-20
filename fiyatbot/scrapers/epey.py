"""epey (fiyat karşılaştırma).

Arama: https://www.epey.com/ara/?ara=...  (şifreli bir /arama/e/... adresine yönlenir)
  Basit, sunucuda üretilmiş HTML: ul.listelegr a.cell
    title özniteliği → ad,  span.fiyat → en düşük fiyat,  span.fiyatsayi → "3 site, 8 fiyat"
  Not: epey ürünleri model düzeyinde listeler ("Apple iPhone 15 Pro"); hafıza/renk başlıkta
  olmadığından "128 GB" gibi gerekli kelimelerde çoğu sonuç elenir.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..matching import garanti_tespit
from ..models import Teklif
from ..price import parse_price
from .base import ParseError, Scraper

BASE = "https://www.epey.com"


def parse_search(html: str) -> list[Teklif]:
    tree = HTMLParser(html)
    if not tree.css_first("ul.listelegr") and "listelegr" not in html:
        raise ParseError("epey: sonuç listesi (ul.listelegr) bulunamadı")
    offers, seen = [], set()
    for card in tree.css("ul.listelegr a.cell"):
        href = card.attributes.get("href") or ""
        price_node = card.css_first(".fiyat")
        if not href or href in seen or not price_node:
            continue
        seen.add(href)
        name_node = card.css_first(".adi")
        title = card.attributes.get("title") or (name_node.text(strip=True) if name_node else "")
        count = card.css_first(".fiyatsayi")
        offers.append(Teklif(
            site="epey", baslik=title, url=href if href.startswith("http") else BASE + href,
            fiyat=parse_price(price_node.text(strip=True)),
            satici=count.text(strip=True) if count else None,
            garanti=garanti_tespit(title),
        ))
    return offers


class Epey(Scraper):
    name = "epey"
    label = "epey"
    enabled_on_ci = False  # Actions IP'leri tüm sitede Cloudflare 403 (2026-10 erişim testi)

    def search(self, query: str) -> list[Teklif]:
        return parse_search(self.http.get(f"{BASE}/ara/?ara={quote_plus(query)}").text)
