from fiyatbot.notify_policy import decide, min_drop
from fiyatbot.models import Teklif


def t(fiyat, url="https://www.trendyol.com/p/1", site="trendyol", **kw) -> Teklif:
    return Teklif(site=site, baslik="Huawei M-Pencil 3. Nesil", url=url, fiyat=fiyat, **kw)


ALL = {"trendyol", "akakce", "n11"}


def run(offers, gecmis, calisan=ALL):
    bildirimler, yeni = decide(offers, gecmis, calisan, "2026-10-18T12:00:00+03:00")
    return [(b.teklif.etkin_fiyat, b.onceki_fiyat) for b in bildirimler], yeni


def test_first_time_notifies():
    sent, state = run([t(2899)], {})
    assert sent == [(2899, None)]
    assert state["trendyol|https://www.trendyol.com/p/1"]["fiyat"] == 2899


def test_same_price_not_repeated():
    _, state = run([t(2899)], {})
    sent, state2 = run([t(2899)], state)
    assert sent == [] and state2 == state


def test_small_drop_ignored_big_drop_notified():
    _, state = run([t(2899)], {})
    assert min_drop(2899) == 100  # %1 = 29 TL < 100 TL → 100 TL
    sent, state = run([t(2850)], state)
    assert sent == []  # 49 TL düşüş anlamsız
    assert state["trendyol|https://www.trendyol.com/p/1"]["fiyat"] == 2899  # son BİLDİRİLEN fiyat korunur
    sent, state = run([t(2799)], state)
    assert sent == [(2799, 2899)]


def test_percent_threshold_for_expensive_items():
    _, state = run([t(60000)], {})
    assert min_drop(60000) == 600  # %1 > 100 TL
    assert run([t(59500)], state)[0] == []
    assert run([t(59400)], state)[0] == [(59400, 60000)]


def test_slow_creep_does_not_accumulate():
    # 2899 → 2850 → 2810: her adım küçük ama toplam 89 TL < 100 → bildirilmez; 2799 → bildirilir
    _, state = run([t(2899)], {})
    for p in (2850, 2810):
        sent, state = run([t(p)], state)
        assert sent == []
    assert run([t(2799)], state)[0] == [(2799, 2899)]


def test_rising_above_budget_then_back_renotifies():
    _, state = run([t(2899)], {})
    _, state = run([], state)  # bütçe üstüne çıktı → firsat listesinde yok → unutulur
    assert state == {}
    assert run([t(2899)], state)[0] == [(2899, None)]


def test_failed_site_keeps_its_history():
    _, state = run([t(2899), t(2899, url="https://www.akakce.com/x", site="akakce")], {})
    # akakce bu çalışmada hata verdi → fırsat listesinde yok ama kaydı silinmemeli
    sent, state2 = run([t(2899)], state, calisan={"trendyol"})
    assert sent == []
    assert "akakce|https://www.akakce.com/x" in state2
    # akakce düzelip aynı fiyatı gösterince tekrar bildirilmez
    assert run([t(2899), t(2899, url="https://www.akakce.com/x", site="akakce")], state2)[0] == []


def test_basket_price_counts_and_key_ignores_seller_text():
    _, state = run([t(3000, sepet_fiyati=2899, satici="17 fiyat arasında en ucuz")], {})
    # Satıcı metni değişti (karşılaştırma sitesi) → aynı ilan, tekrar bildirilmez
    assert run([t(3000, sepet_fiyati=2899, satici="18 fiyat arasında en ucuz")], state)[0] == []


def test_duplicate_offers_in_one_run_counted_once():
    sent, _ = run([t(2899), t(2899)], {})
    assert len(sent) == 1
