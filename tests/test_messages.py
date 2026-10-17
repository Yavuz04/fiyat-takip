from datetime import datetime, timezone

from fiyatbot.messages import deal_message, format_time
from fiyatbot.models import GARANTI_TR, TakipKaydi, Teklif
from fiyatbot.telegram import split_message

KAYIT = TakipKaydi(id=3, sorgu="iPhone 15 <128GB> & co", max_fiyat=60000)


def t(fiyat, **kw) -> Teklif:
    return Teklif(site="trendyol", baslik=kw.pop("baslik", f"Ürün {fiyat}"),
                  url=kw.pop("url", f"https://x.com/p?a=1&b={fiyat}"), fiyat=fiyat, **kw)


def test_html_escaping():
    msg = deal_message(KAYIT, [t(50000, baslik="Kılıf <script> & Cam", satici="A&B <Store>")])
    assert "iPhone 15 &lt;128GB&gt; &amp; co" in msg
    assert "Kılıf &lt;script&gt; &amp; Cam" in msg
    assert "A&amp;B &lt;Store&gt;" in msg
    assert 'href="https://x.com/p?a=1&amp;b=50000"' in msg
    assert "<script>" not in msg


def test_sorted_cheapest_first_and_limited():
    offers = [t(p) for p in (59000, 51000, 55000, 52000)]
    msg = deal_message(KAYIT, offers, limit=3)
    assert msg.index("51.000 TL") < msg.index("52.000 TL") < msg.index("55.000 TL")
    assert "59.000 TL</b>" not in msg
    assert "… ve 1 teklif daha" in msg
    assert "4 uygun teklif" in msg


def test_sorting_uses_basket_price():
    msg = deal_message(KAYIT, [t(53000), t(54000, sepet_fiyati=50000, baslik="Sepetli")])
    assert msg.index("Sepetli") < msg.index("53.000 TL")
    assert "🛒 Sepette <b>50.000 TL</b>" in msg


def test_offer_details():
    msg = deal_message(KAYIT, [t(54000, eski_fiyat=60000, satici="Trendyol", satici_puani=9.3, garanti=GARANTI_TR)])
    assert "<b>54.000 TL</b> <s>60.000 TL</s> (−%10)" in msg
    assert "Trendyol ⭐9.3" in msg
    assert "🛡 Türkiye garantili" in msg


def test_time_is_istanbul():
    # 12:00 UTC = 15:00 Türkiye
    assert format_time(datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)) == "16.10.2026 15:00"


def test_split_long_message():
    text = "\n\n".join(f"blok {i} " + "x" * 300 for i in range(40))
    chunks = split_message(text, limit=1000)
    assert all(len(c) <= 1000 for c in chunks)
    assert "\n\n".join(chunks) == text
