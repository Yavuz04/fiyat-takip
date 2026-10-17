from pathlib import Path

import pytest

from fiyatbot.matching import filtrele
from fiyatbot.models import GARANTI_TR, GARANTI_YURTDISI, TakipKaydi, Teklif
from fiyatbot.scrapers.base import ParseError
from fiyatbot.scrapers.trendyol import parse_detail, parse_search

FIX = Path(__file__).parent / "fixtures" / "trendyol"


@pytest.fixture(scope="module")
def offers() -> dict[str, Teklif]:
    return {o.baslik: o for o in parse_search((FIX / "search.html").read_text(encoding="utf-8"))}


def test_parses_all_products(offers):
    assert len(offers) == 7
    assert all(o.site == "trendyol" and o.url.startswith("https://www.trendyol.com/") for o in offers.values())
    assert all(o.stokta for o in offers.values())


def test_regular_price(offers):
    o = offers["Apple iPhone 15 128 GB Siyah"]
    assert o.fiyat == 59499
    assert o.sepet_fiyati is None and o.eski_fiyat is None


def test_basket_price_kept_separate(offers):
    o = offers["Apple Yenilenmiş iPhone 15 128 GB Mavi Cep Telefonu (12 Ay Garantili) - A Kalite"]
    assert o.fiyat == 47915          # peşin fiyat
    assert o.sepet_fiyati == 45519.25  # "Sepette %5 indirim"
    assert o.etkin_fiyat == 45519.25
    assert o.indirim_orani is None   # sepet indirimi "eski fiyat" sayılmaz


def test_warranty_from_title(offers):
    o = offers["Apple iPhone 16 128GB Teal 5G With FaceTime - International Version"]
    assert o.garanti == GARANTI_YURTDISI


def test_filter_on_real_data(offers):
    k = TakipKaydi(id=1, sorgu="iPhone 15 128GB", max_fiyat=60000, min_fiyat=15000,
                   gerekli=["iphone 15", "128"], haric=["pro", "plus", "yenilenmiş"])
    kept = sorted(o.baslik for o in offers.values() if filtrele(k, o) is None)
    assert kept == ["Apple iPhone 15 128 GB Mavi", "Apple iPhone 15 128 GB Siyah"]


def test_detail_enrich():
    t = Teklif(site="trendyol", baslik="Apple iPhone 15 128 GB Mavi", url="u", fiyat=59799)
    parse_detail((FIX / "detail.html").read_text(encoding="utf-8"), t)
    assert t.satici == "Trendyol"
    assert t.satici_puani == 9.3
    assert t.garanti == GARANTI_TR
    assert t.stokta is True


def test_structure_change_raises():
    with pytest.raises(ParseError):
        parse_search("<html><body>yeni tasarım</body></html>")
