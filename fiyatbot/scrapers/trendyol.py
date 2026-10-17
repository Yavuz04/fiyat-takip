"""Trendyol.

Arama: https://www.trendyol.com/sr?q=...  → sayfada gömülü `window["__single-search-result__PROPS"]`
       JSON'u, `data.products` listesi (sayfa başına ~36 kart, alaka sıralı; cardType PRODUCT/ADS).
       Fiyat alanları:
         price.current            → satış (peşin) fiyatı
         price.discountedPrice    → binaryPrice.discountType == "basketPromotion" ise SEPETTE fiyat
         price.old                → üstü çizili eski fiyat (0 = yok)
       appPrice (sadece mobil uygulama kuponu) ve "TY Plus" (üyelik) fiyatları kullanılmaz.
Detay: ürün sayfasında `window["__envoy__SHARED_PROPS"].product`:
         merchantListing.merchant.name / sellerScore.value → satıcı ve puanı
         attributes[key.name == "Garanti Tipi"]           → garanti
         inStock                                          → stok
"""

from __future__ import annotations

from urllib.parse import quote

from ..embedded import window_json
from ..matching import garanti_tespit
from ..models import GARANTI_BILINMIYOR, Teklif
from ..price import parse_price
from .base import ParseError, Scraper

BASE = "https://www.trendyol.com"
SEARCH_KEY = "__single-search-result__PROPS"
DETAIL_KEY = "__envoy__SHARED_PROPS"


def parse_search(html: str) -> list[Teklif]:
    data = window_json(html, SEARCH_KEY)
    if not data or "data" not in data:
        raise ParseError(f"Trendyol: {SEARCH_KEY} bulunamadı")
    products = data["data"].get("products")
    if products is None:
        raise ParseError("Trendyol: data.products yok")

    offers, seen = [], set()
    for p in products:
        # ADS = sponsorlu ilan; gerçek bir teklif olduğu için alınır, organik kopyası tekilleştirilir
        if p.get("cardType", "PRODUCT") not in ("PRODUCT", "ADS") or not p.get("url"):
            continue
        path = p["url"].split("?")[0]
        if path in seen:
            continue
        seen.add(path)
        price = p.get("price") or {}
        current = parse_price(price.get("current"))
        discounted = parse_price(price.get("discountedPrice"))
        discount_type = (p.get("binaryPrice") or {}).get("discountType")

        fiyat, sepet = current, None
        if discounted and current and discounted < current:
            if discount_type == "basketPromotion":
                sepet = discounted
            else:
                fiyat = discounted  # doğrudan indirim: ödenecek fiyat zaten düşük olan
        eski = parse_price(price.get("old"))
        if eski is None and fiyat != current:
            eski = current
        if eski is not None and fiyat is not None and eski <= fiyat:
            eski = None

        name = p.get("name", "")
        brand = p.get("brand") or ""
        title = name if name.lower().startswith(brand.lower()) else f"{brand} {name}".strip()
        offers.append(
            Teklif(
                site="trendyol",
                baslik=title,
                url=BASE + p["url"],
                fiyat=fiyat,
                sepet_fiyati=sepet,
                eski_fiyat=eski,
                garanti=garanti_tespit(name),
                stokta=not (p.get("tagStockBar") or {}).get("isSoldOut", False),
            )
        )
    return offers


def parse_detail(html: str, teklif: Teklif) -> Teklif:
    data = window_json(html, DETAIL_KEY)
    product = (data or {}).get("product")
    if not product:
        raise ParseError(f"Trendyol detay: {DETAIL_KEY}.product bulunamadı")
    merchant = (product.get("merchantListing") or {}).get("merchant") or {}
    if merchant.get("name"):
        teklif.satici = merchant["name"]
    score = (merchant.get("sellerScore") or {}).get("value")
    if isinstance(score, (int, float)):
        teklif.satici_puani = float(score)
    if "inStock" in product:
        teklif.stokta = bool(product["inStock"])
    for attr in product.get("attributes") or []:
        if (attr.get("key") or {}).get("name") == "Garanti Tipi":
            garanti = garanti_tespit((attr.get("value") or {}).get("name", ""))
            if garanti != GARANTI_BILINMIYOR:
                teklif.garanti = garanti
            break
    return teklif


class Trendyol(Scraper):
    name = "trendyol"
    label = "Trendyol"

    def search(self, query: str) -> list[Teklif]:
        resp = self.http.get(f"{BASE}/sr?q={quote(query)}")
        return parse_search(resp.text)

    def enrich(self, teklif: Teklif) -> Teklif:
        resp = self.http.get(teklif.url)
        return parse_detail(resp.text, teklif)
