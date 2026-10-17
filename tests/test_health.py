from fiyatbot import health
from fiyatbot.scanner import BLOCKED, EMPTY, ERROR, OK, SiteDurumu

Z = "2026-10-18T12:00:00+03:00"


def step(saglik, **site_states):
    ozet = {s: SiteDurumu(s, d, sonuc=5 if d == OK else 0, mesaj="" if d == OK else "HTTP 403")
            for s, d in site_states.items()}
    return health.update(saglik, ozet, Z)


def test_single_alert_after_threshold_then_single_recovery():
    saglik = {}
    assert step(saglik, epey=ERROR) == []
    assert step(saglik, epey=ERROR) == []
    msgs = step(saglik, epey=ERROR)
    assert len(msgs) == 1 and "epey" in msgs[0] and "3 çalışmadır" in msgs[0]
    for _ in range(5):  # uyarıdan sonra spam yok
        assert step(saglik, epey=ERROR) == []
    msgs = step(saglik, epey=OK)
    assert len(msgs) == 1 and "tekrar çalışıyor" in msgs[0]
    assert step(saglik, epey=OK) == []
    assert saglik["epey"]["ardisik_hata"] == 0


def test_blocked_message_mentions_bot_block():
    saglik = {}
    for _ in range(2):
        step(saglik, amazon=BLOCKED)
    msgs = step(saglik, amazon=BLOCKED)
    assert "bot engeli" in msgs[0]


def test_recovery_before_threshold_resets_counter():
    saglik = {}
    step(saglik, n11=EMPTY)
    step(saglik, n11=EMPTY)
    step(saglik, n11=OK)
    assert step(saglik, n11=EMPTY) == []
    assert saglik["n11"]["ardisik_hata"] == 1


def test_summarize_any_success_means_healthy():
    durumlar = [SiteDurumu("n11", EMPTY), SiteDurumu("n11", OK, sonuc=4), SiteDurumu("amazon", EMPTY),
                SiteDurumu("amazon", BLOCKED, mesaj="403"), SiteDurumu("cimri", EMPTY)]
    ozet = health.summarize(durumlar)
    assert ozet["n11"].durum == OK  # niş bir ürün için 0 sonuç normal
    assert ozet["amazon"].durum == BLOCKED  # engel boştan önceliklidir
    assert ozet["cimri"].durum == EMPTY
