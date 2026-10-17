"""Her site için kaydedilmiş (küçültülmüş) gerçek yanıtlarla ayrıştırma testleri.

Fixture'lar 2026-10 tarihli gerçek arama sayfalarından üretildi ("iphone 15 128gb").
"""

from pathlib import Path

import pytest

from fiyatbot.matching import filtrele
from fiyatbot.models import GARANTI_ITHALATCI, GARANTI_TR, TakipKaydi
from fiyatbot.scrapers import akakce, amazon, cimri, epey, hepsiburada, n11, pazarama, pttavm
from fiyatbot.scrapers.base import ParseError

FIX = Path(__file__).parent / "fixtures"
KAYIT = TakipKaydi(id=1, sorgu="iPhone 15 128GB", max_fiyat=60000, min_fiyat=15000,
                   gerekli=["iphone 15", "128"],
                   haric=["kılıf", "pro", "plus", "yenilenmiş", "ikinci el", "teşhir", "cam", "koruyucu", "flash bellek"])


def load(module, site: str):
    return module.parse_search((FIX / site / "search.html").read_text(encoding="utf-8"))


def by_title(offers):
    return {o.baslik: o for o in offers}


def matched_titles(offers):
    return sorted(o.baslik for o in offers if filtrele(KAYIT, o) is None)


# --- Hepsiburada -----------------------------------------------------------

def test_hepsiburada():
    offers = load(hepsiburada, "hepsiburada")
    assert len(offers) == 5  # renk varyantları ayrı ilan, sku ile tekilleştirilir
    o = by_title(offers)["Apple iPhone 15 128 GB Mavi"]
    assert o.fiyat == 60469.16 and o.satici == "Alsambunu" and o.stokta is True
    # originalPrice var ama discountType=NoDiscount → sitede üstü çizili gösterilmiyor, eski fiyat sayılmaz
    assert by_title(offers)["Apple iPhone 15 128 GB Siyah"].eski_fiyat is None
    assert all(o.url.startswith("https://www.hepsiburada.com/") for o in offers)


# --- Amazon ----------------------------------------------------------------

def test_amazon():
    offers = by_title(load(amazon, "amazon"))
    assert offers["Apple iPhone 15 (128 GB) - Siyah"].fiyat is None  # öne çıkan teklif yok
    assert offers["Apple iPhone 16 (128 GB) - Siyah"].fiyat == 72999
    assert offers["Apple iPhone 16 (128 GB) - Siyah"].url == "https://www.amazon.com.tr/dp/B0DGJJZWQX"
    adapter = next(o for t, o in offers.items() if t.startswith("Type-c Girişli"))
    assert adapter.fiyat == 280 and adapter.eski_fiyat == 325
    # Sponsorlu öneki temizlenir; kuponlu "indirimli fiyat" kullanılmaz
    sponsored = next(o for t, o in offers.items() if "Magsafe" in t)
    assert sponsored.baslik.startswith("Ehr.") and sponsored.fiyat == 299.9


def test_amazon_no_price_is_filtered():
    offers = load(amazon, "amazon")
    assert matched_titles(offers) == []  # iPhone 15 128GB fiyatsız, diğerleri başka model/aksesuar


# --- n11 -------------------------------------------------------------------

def test_n11_basket_price():
    offers = by_title(load(n11, "n11"))
    o = offers["Yenilenmiş Apple iPhone 15 128 GB A Kalite (12 Ay Garantili)"]
    assert o.fiyat == 51999 and o.sepet_fiyati == 46499  # "SEPETTE" rozeti
    new = offers["Apple iPhone 15 128 GB (Apple Türkiye Garantili)"]
    assert new.fiyat == 60000 and new.sepet_fiyati is None
    assert new.garanti == GARANTI_TR and new.stokta is True


def test_n11_filter():
    assert matched_titles(load(n11, "n11")) == ["Apple iPhone 15 128 GB (Apple Türkiye Garantili)"]


# --- PttAVM ----------------------------------------------------------------

def test_pttavm():
    offers = by_title(load(pttavm, "pttavm"))
    o = offers["Apple iPhone 15 128 6 GB RAM 5G (Apple Türkiye Garantili) SİYAH"]
    assert o.fiyat == 60672.85 and o.eski_fiyat == 63799
    assert o.satici == "CepHane Teknoloji" and o.satici_puani == 9.5  # 94.6/100 → 9.5/10
    assert o.garanti == GARANTI_TR
    assert offers["iPhone 15 Pro 128 GB Siyah Titanyum (İthalatçı Garantili)"].garanti == GARANTI_ITHALATCI
    assert offers["Apple iPhone 15 128 GB Siyah (Apple Türkiye Garantili)"].satici_puani is None  # puan 0


def test_pttavm_filter():
    assert matched_titles(load(pttavm, "pttavm")) == [
        "Apple iPhone 15 128 6 GB RAM 5G (Apple Türkiye Garantili) SİYAH",
        "Apple iPhone 15 128 GB Siyah (Apple Türkiye Garantili)",
        "Apple iPhone 15 128 GB Siyah Akıllı Cep Telefonu",
    ]


# --- Pazarama --------------------------------------------------------------

def test_pazarama():
    offers = by_title(load(pazarama, "pazarama"))
    o = offers["Yenilenmiş iPhone 15 128 GB Siyah B Kalite Cep Telefonu"]
    assert o.fiyat == 43999 and o.sepet_fiyati == 43559.01
    # "Son 10 Günün En Düşük Fiyatı" metnindeki 10 fiyat sanılmaz
    plus = offers["Yenilenmiş IPHONE 15 PLUS 128GB -A Kalite- Mavi"]
    assert plus.fiyat == 59429 and plus.sepet_fiyati == 58834.72
    assert offers["Apple iPhone 15 Siyah 128 GB 6 GB Ram Akıllı Telefon (Apple Türkiye Garantili)"].fiyat == 60000


# --- Akakçe ----------------------------------------------------------------

def test_akakce():
    offers = by_title(load(akakce, "akakce"))
    o = offers["Apple iPhone 15 128 GB Siyah"]
    assert o.fiyat == 57999.05 and o.satici == "38 fiyat arasında en ucuz"
    assert "Apple iPhone 15 Plus 128 GB" not in offers  # sadece ikinci el teklifi (price=0) → atlanır
    # Pro ve flash bellekler elenir, 5 renk kalır (bütçe kontrolü filtrede değil, ayrı yapılır)
    assert matched_titles(offers.values()) == [f"Apple iPhone 15 128 GB {c}" for c in
                                               ("Mavi", "Pembe", "Sarı", "Siyah", "Yeşil")]


# --- Cimri -----------------------------------------------------------------

def test_cimri():
    offers = by_title(load(cimri, "cimri"))
    o = offers["Apple iPhone 15 128 GB Siyah"]
    assert o.fiyat == 56999.04
    assert o.satici == "Vatan Bilgisayar (20 fiyat arasında en ucuz)"
    assert o.url.startswith("https://www.cimri.com/cep-telefonlari/")


def test_cimri_unmatched_listing_is_kept():
    # isFakeProduct=true ilanlar kataloğa eşlenmemiş gerçek tekliflerdir; url boş gelir
    # (M-Pencil aramasında sonuçların hepsi böyleydi) → ilan adıyla Cimri araması link olarak verilir
    html = (FIX / "cimri" / "search.html").read_text(encoding="utf-8")
    html = html.replace('"isFakeProduct": false', '"isFakeProduct": true', 1)
    html = html.replace('"url": "/cep-telefonlari/en-ucuz-apple-iphone-15-5g-128gb-siyah-fiyatlari,2237451716"',
                        '"url": ""', 1)
    offers = cimri.parse_search(html)
    assert len(offers) == 8
    assert offers[0].url == "https://www.cimri.com/arama?q=Apple+iPhone+15+128+GB+Siyah"
    assert offers[0].satici.startswith("Vatan Bilgisayar")


# --- epey ------------------------------------------------------------------

def test_epey():
    offers = load(epey, "epey")
    assert len(offers) == 7
    assert offers[0].baslik == "Apple iPhone 15 Pro" and offers[0].fiyat == 75036.9
    assert offers[0].satici == "3 site, 8 fiyat"


# --- Yapı değişikliği → ParseError -----------------------------------------

@pytest.mark.parametrize("module", [hepsiburada, amazon, n11, pttavm, pazarama, akakce, cimri, epey])
def test_structure_change_raises(module):
    with pytest.raises(ParseError):
        module.parse_search("<html><body><h1>Yeni tasarım</h1></body></html>")
