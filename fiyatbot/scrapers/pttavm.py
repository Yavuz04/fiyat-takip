"""PttAVM.

Arama: https://www.pttavm.com/arama?q=...
  `window.__staticRouterHydrationData = JSON.parse("...")` (React Router) →
  loaderData.*.dehydratedState.queries[].state.data.products[]
    priceInfo.discountedPrice → ödenecek fiyat;  priceInfo.originalPrice → eski fiyat
    shop.shop_name / shop.rating (100 üzerinden; 10'luk ölçeğe çevrilir)
"""

from __future__ import annotations

from urllib.parse import quote

from ..embedded import window_json
from ..matching import garanti_tespit
from ..models import Teklif
from ..price import parse_price
from .base import ParseError, Scraper

BASE = "https://www.pttavm.com"


def _products(data: dict) -> list[dict] | None:
    for loader in (data.get("loaderData") or {}).values():
        queries = ((loader or {}).get("dehydratedState") or {}).get("queries") or []
        for q in queries:
            result = (q.get("state") or {}).get("data")
            if isinstance(result, dict) and isinstance(result.get("products"), list):
                return result["products"]
    return None


def parse_search(html: str) -> list[Teklif]:
    data = window_json(html, "__staticRouterHydrationData")
    products = _products(data) if data else None
    if products is None:
        raise ParseError("PttAVM: hydration verisinde ürün listesi bulunamadı")

    offers = []
    for p in products:
        if not p.get("url"):
            continue
        info = p.get("priceInfo") or {}
        fiyat = parse_price(info.get("discountedPrice")) or parse_price(info.get("regularPrice"))
        eski = parse_price(info.get("originalPrice"))
        if eski and fiyat and eski <= fiyat:
            eski = None
        shop = p.get("shop") or {}
        rating = shop.get("rating")
        title = p.get("name", "")
        offers.append(Teklif(
            site="pttavm", baslik=title, url=p["url"], fiyat=fiyat, eski_fiyat=eski,
            satici=shop.get("shop_name") or None,
            # 0 = henüz puanı yok
            satici_puani=round(float(rating) / 10, 1) if isinstance(rating, (int, float)) and rating > 0 else None,
            garanti=garanti_tespit(title),
        ))
    return offers


class PttAVM(Scraper):
    name = "pttavm"
    label = "PttAVM"
    enabled_on_ci = False  # Actions IP'leri tüm sitede Cloudflare 403 (2026-10 erişim testi)

    def search(self, query: str) -> list[Teklif]:
        return parse_search(self.http.get(f"{BASE}/arama?q={quote(query)}").text)
