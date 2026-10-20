"""Cimri (fiyat karşılaştırma).

Arama: https://www.cimri.com/arama?q=...
  Cloudflare, çerezsiz doğrudan /arama isteğini 403 ile engelliyor; önce ana sayfa açılıp
  `_cfuvid` çerezi alınınca arama çalışıyor (oturum başına bir kez yapılır).
  Veri: `<script id="__OCTOPUS_DATA__" type="application/json">` →
    props.pageProps.data.search.products[]: title, url, offerCount,
    topOffers[0]: price, originalPrice, merchant.name (en ucuz teklifin mağazası)
  isFakeProduct=true: kataloğa eşlenmemiş ilan (gerçek teklif; örn. M-Pencil aramasının tamamı).
    Bunlarda url boş gelir (mağaza linki tıklamada JS ile üretilir); link olarak ilan adıyla Cimri araması verilir.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ..embedded import script_json
from ..matching import garanti_tespit
from ..models import Teklif
from ..price import parse_price
from .base import ParseError, Scraper

BASE = "https://www.cimri.com"


def parse_search(html: str) -> list[Teklif]:
    data = script_json(html, "__OCTOPUS_DATA__")
    try:
        search = data["props"]["pageProps"]["data"]["search"]
    except (TypeError, KeyError):
        raise ParseError("Cimri: __OCTOPUS_DATA__ içinde search verisi bulunamadı") from None

    offers = []
    for p in search.get("products") or []:
        if p.get("isDeletedProduct") or p.get("isAllOffersPassive"):
            continue
        title = p.get("title", "")
        if p.get("url"):
            url = BASE + p["url"]
        elif title:
            # isFakeProduct: ürün sayfası yok, mağaza linki JS ile üretiliyor → ilan adıyla Cimri araması
            url = f"{BASE}/arama?q={quote_plus(title)}"
        else:
            continue
        top = (p.get("topOffers") or [None])[0] or {}
        fiyat = parse_price(top.get("price"))
        eski = parse_price(top.get("originalPrice"))
        if eski and fiyat and eski <= fiyat:
            eski = None
        merchant = (top.get("merchant") or {}).get("name")
        count = p.get("offerCount") or 0
        satici = f"{merchant} ({count} fiyat arasında en ucuz)" if merchant and count > 1 else merchant
        offers.append(Teklif(
            site="cimri", baslik=title, url=url, fiyat=fiyat, eski_fiyat=eski,
            satici=satici, garanti=garanti_tespit(title),
        ))
    return offers


class Cimri(Scraper):
    name = "cimri"
    label = "Cimri"
    enabled_on_ci = False  # Actions IP'leri tüm sitede Cloudflare 403 (2026-10 erişim testi)

    def __init__(self, http):
        super().__init__(http)
        self._warmed_up = False

    def search(self, query: str) -> list[Teklif]:
        if not self._warmed_up:
            self.http.get(f"{BASE}/")  # Cloudflare çerezi
            self._warmed_up = True
        resp = self.http.get(f"{BASE}/arama?q={quote_plus(query)}", headers={"Referer": f"{BASE}/"})
        return parse_search(resp.text)
