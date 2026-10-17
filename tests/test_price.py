import pytest

from fiyatbot.price import format_tl, looks_like_installment, parse_price


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("25.999,00 TL", 25999.0),
        ("25.999 TL", 25999.0),
        ("₺25.999", 25999.0),
        ("25.999,90TL", 25999.9),
        ("1.299,90", 1299.9),
        ("1.299.999,00 TL", 1299999.0),
        ("899 TL", 899.0),
        ("899,99 TL", 899.99),
        ("25999.0", 25999.0),        # JSON tarzı ondalık
        ("25,999.00", 25999.0),      # İngilizce format
        ("Sepette 24.500 TL", 24500.0),
        (25999, 25999.0),
        (25999.5, 25999.5),
        ("  ₺ 54.999,00  ", 54999.0),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "Fiyat yok", "0 TL", 0, -5, True])
def test_parse_price_invalid(raw):
    assert parse_price(raw) is None


@pytest.mark.parametrize(
    "text",
    ["12 x 2.166,58 TL", "Aylık 2.166 TL", "3 Taksit", "2.166 TL/ay", "Peşin fiyatına 6 taksit", "x12 2.166 TL"],
)
def test_installment_detected(text):
    assert looks_like_installment(text)


@pytest.mark.parametrize("text", ["25.999 TL", "Sepette 24.500 TL", "İndirimli fiyat 23.999,00 TL"])
def test_not_installment(text):
    assert not looks_like_installment(text)


def test_format_tl():
    assert format_tl(25999.0) == "25.999 TL"
    assert format_tl(1299.9) == "1.299,90 TL"
    assert format_tl(899.999) == "900 TL"
