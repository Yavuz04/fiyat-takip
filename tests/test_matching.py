import pytest

from fiyatbot.matching import (
    butce_altinda,
    contains_phrase,
    filtrele,
    garanti_tespit,
    varsayilan_gerekli,
    varsayilan_haric,
    yeni_kayit,
)
from fiyatbot.models import GARANTI_ITHALATCI, GARANTI_TR, GARANTI_YURTDISI, TakipKaydi, Teklif
from fiyatbot.text import tokens


def kayit(**kw) -> TakipKaydi:
    base = dict(
        id=1,
        sorgu="iPhone 15 128GB",
        max_fiyat=45000,
        min_fiyat=15000,
        gerekli=["iphone 15", "128"],
        haric=["kılıf", "pro", "plus", "yenilenmiş", "ikinci el", "teşhir", "cam", "koruyucu"],
    )
    base.update(kw)
    return TakipKaydi(**base)


def teklif(baslik, fiyat=42000.0, **kw) -> Teklif:
    return Teklif(site="test", baslik=baslik, url="https://x/1", fiyat=fiyat, **kw)


# --- contains_phrase -------------------------------------------------------

def test_phrase_word_boundaries():
    t = tokens("Apple iPhone 150 Kamera Lensi")
    assert not contains_phrase(t, "iphone 15")
    assert not contains_phrase(tokens("Camera Lens"), "cam")
    assert contains_phrase(tokens("Ekran Koruyucu Cam"), "cam")


def test_phrase_unit_spacing():
    assert contains_phrase(tokens("iPhone 15 128 GB"), "128GB")
    assert contains_phrase(tokens("iPhone 15 128GB"), "128 gb")
    assert contains_phrase(tokens("iPhone 15 128GB"), "128")


def test_phrase_turkish_suffix_prefix_match():
    assert contains_phrase(tokens("iPhone 15 Kılıflı Set"), "kılıf")
    assert contains_phrase(tokens("Yenilenmiş iPhone"), "yenilenmis")
    # kısa kelimeler önek olarak eşleşmez
    assert not contains_phrase(tokens("Profesyonel Kamera"), "pro")


# --- filtrele --------------------------------------------------------------

@pytest.mark.parametrize(
    "baslik",
    [
        "Apple iPhone 15 128 GB Siyah",
        "APPLE İPHONE 15 128GB MAVİ (Apple Türkiye Garantili)",
        "iPhone 15 Siyah 128 GB Cep Telefonu",
    ],
)
def test_filter_accepts(baslik):
    assert filtrele(kayit(), teklif(baslik)) is None


@pytest.mark.parametrize(
    "baslik, reason_start",
    [
        ("Apple iPhone 15 Pro 128 GB", "hariç: pro"),
        ("Apple iPhone 15 Plus 128GB", "hariç: plus"),
        ("iPhone 15 128 GB Yenilenmiş", "hariç: yenilenmiş"),
        ("iPhone 15 128GB İkinci El", "hariç: ikinci el"),
        ("iPhone 15 Uyumlu Kılıf Şeffaf", "gerekli yok: 128"),
        ("Apple iPhone 15 256 GB", "gerekli yok: 128"),
        ("Apple iPhone 14 128 GB", "gerekli yok: iphone 15"),
    ],
)
def test_filter_rejects(baslik, reason_start):
    assert filtrele(kayit(), teklif(baslik)).startswith(reason_start)


def test_filter_min_price_and_stock():
    assert filtrele(kayit(), teklif("iPhone 15 128GB", fiyat=499)) == "min fiyat altı"
    assert filtrele(kayit(), teklif("iPhone 15 128GB", stokta=False)) == "stok yok"
    assert filtrele(kayit(), teklif("iPhone 15 128GB", stokta=None)) is None
    assert filtrele(kayit(), teklif("iPhone 15 128GB", fiyat=None)) == "fiyat yok"


def test_filter_uses_basket_price():
    t = teklif("iPhone 15 128GB", fiyat=46000, sepet_fiyati=44000)
    assert t.etkin_fiyat == 44000
    assert filtrele(kayit(), t) is None
    assert butce_altinda(kayit(), t)
    assert not butce_altinda(kayit(), teklif("iPhone 15 128GB", fiyat=46000))


def test_filter_warranty():
    k = kayit(garanti="tr")
    assert filtrele(k, teklif("iPhone 15 128GB", garanti=GARANTI_ITHALATCI)) == "garanti: ithalatci"
    assert filtrele(k, teklif("iPhone 15 128GB", garanti=GARANTI_TR)) is None
    assert filtrele(k, teklif("iPhone 15 128GB")) is None  # bilinmiyor → elenmez
    assert filtrele(kayit(), teklif("iPhone 15 128GB", garanti=GARANTI_YURTDISI)) is None


# --- garanti / varsayılanlar ----------------------------------------------

def test_garanti_tespit():
    assert garanti_tespit("iPhone 15 (İthalatçı Garantili)") == GARANTI_ITHALATCI
    assert garanti_tespit("Apple Türkiye Garantili") == GARANTI_TR
    assert garanti_tespit("Distribütör Garantili") == GARANTI_TR
    assert garanti_tespit("Yurt Dışı Versiyon") == GARANTI_YURTDISI
    assert garanti_tespit("iPhone 15 128GB") == "bilinmiyor"


def test_default_required():
    assert varsayilan_gerekli("iPhone 15 128GB") == ["iphone 15", "128 gb"]
    assert varsayilan_gerekli("Samsung Galaxy S24 Ultra 256 GB") == ["samsung", "galaxy", "s 24", "ultra", "256 gb"]
    assert varsayilan_gerekli("PlayStation 5") == ["playstation 5"]
    assert varsayilan_gerekli("Huawei MatePad 11.5 S") == ["huawei", "matepad 11 5 s"]
    assert varsayilan_gerekli("iPhone 16e 128GB") == ["iphone 16 e", "128 gb"]
    assert varsayilan_gerekli("Huawei M-Pencil 3") == ["huawei", "m", "pencil 3"]


def test_default_required_matches_real_titles():
    k = yeni_kayit(2, "Huawei MatePad 11.5 S", 15000)
    assert filtrele(k, teklif('Huawei MatePad 11.5" S PaperMatte 8GB 256GB Tablet', fiyat=17000)) is None
    assert filtrele(k, teklif("Huawei MatePad 11.5 8GB 128GB Tablet", fiyat=12000)) is not None  # S değil


def test_default_excluded_variants():
    assert "pro" in varsayilan_haric("iPhone 15 128GB")
    assert "pro" not in varsayilan_haric("iPhone 15 Pro 128GB")
    assert "max" in varsayilan_haric("iPhone 15 Pro 128GB")


@pytest.mark.parametrize("baslik", ["Apple iPhone 15 128 GB Mavi 2.EL", "APPLE IPHONE 15 128GB MAVİ VİTRİN"])
def test_default_excludes_used_and_display(baslik):
    # PttAVM'de canlı görülen başlıklar
    assert filtrele(yeni_kayit(1, "iPhone 15 128GB", 60000), teklif(baslik)) is not None


def test_new_record_end_to_end():
    k = yeni_kayit(7, "iPhone 15 128GB", 45000)
    assert k.min_fiyat == 18000
    assert filtrele(k, teklif("Apple iPhone 15 128 GB Siyah")) is None
    assert filtrele(k, teklif("Apple iPhone 15 Pro Max 128 GB")) is not None
    assert filtrele(k, teklif("iPhone 15 128GB Uyumlu Ekran Koruyucu Cam", fiyat=19000)) is not None


def test_record_roundtrip():
    k = yeni_kayit(3, "PlayStation 5", 20000)
    assert TakipKaydi.from_dict({**k.to_dict(), "bilinmeyen_alan": 1}) == k
