"""Uçtan uca: sahte scraper + sahte bildirici ile ardışık çalışmalar (ağ yok, geçici klasör)."""

from datetime import datetime

import pytest

from fiyatbot import config, history, runner
from fiyatbot.http import BlockedError
from fiyatbot.models import Teklif
from fiyatbot.scrapers.base import Scraper
from fiyatbot.state import load_state
from fiyatbot.storage import save_watchlist
from fiyatbot.matching import yeni_kayit


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)


class FakeShop(Scraper):
    name = ""  # kayda girmesin
    label = "Fake"

    def __init__(self, site, prices):
        super().__init__(http=None)
        self.name = site
        self.prices = prices  # her çağrıda sıradaki değer: fiyat listesi ya da Exception

    def search(self, query):
        value = self.prices.pop(0)
        if isinstance(value, Exception):
            raise value
        return [Teklif(site=self.name, baslik=f"Huawei M-Pencil 3. Nesil {i}", url=f"https://{self.name}/p/{i}",
                       fiyat=p) for i, p in enumerate(value)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr(config, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.csv")
    k = yeni_kayit(1, "Huawei M-Pencil 3", 3000)
    k.gerekli = ["huawei", "m pencil", "3 nesil"]
    save_watchlist([k])
    return tmp_path


def run_once(monkeypatch, shops, dry_run=False):
    monkeypatch.setattr(runner, "build_scrapers", lambda *a, **kw: shops)
    notifier = FakeNotifier()
    runner.run(runner.RunOptions(dry_run=dry_run, enrich=False), notifier)
    return notifier.sent


def test_full_cycle(env, monkeypatch):
    shop = FakeShop("shop", [[2899, 3500], [2899, 3500], [2780], [3100], [2899]])
    # 1) ilk kez bütçe altında → bildir
    sent = run_once(monkeypatch, [shop])
    assert len(sent) == 1 and "2.899 TL" in sent[0] and "🆕" in sent[0] and "3.500" not in sent[0]
    # 2) aynı fiyat → sessiz
    assert run_once(monkeypatch, [shop]) == []
    # 3) yeterince düştü → bildir (önceki fiyatla)
    sent = run_once(monkeypatch, [shop])
    assert len(sent) == 1 and "📉 önceki 2.899 TL" in sent[0]
    # 4) bütçe üstüne çıktı → sessiz;  5) tekrar düştü → yeniden bildir
    assert run_once(monkeypatch, [shop]) == []
    sent = run_once(monkeypatch, [shop])
    assert len(sent) == 1 and "🆕" in sent[0]

    rows = history.read()
    assert [float(r["fiyat"]) for r in rows] == [2899, 2780, 3100, 2899]  # sadece değişince yazıldı


def test_dry_run_writes_nothing(env, monkeypatch):
    sent = run_once(monkeypatch, [FakeShop("shop", [[2899]])], dry_run=True)
    assert len(sent) == 1
    assert not (env / "state.json").exists() and not (env / "history.csv").exists()


def test_site_failure_isolated_and_health_alert(env, monkeypatch):
    # Bozuk siteler ~2 saatte bir denenir; test saati deneme penceresine sabitlenir
    monkeypatch.setattr(runner, "now_tr", lambda: datetime.fromisoformat("2026-10-21T14:05:00+03:00"))
    good = FakeShop("good", [[2899]] * 4)
    bad = FakeShop("bad", [BlockedError("bad: bot engeli (HTTP 403)")] * 3 + [[2950]])
    sent = run_once(monkeypatch, [bad, good])
    assert len(sent) == 1 and "2.899" in sent[0]  # kötü site diğerini durdurmadı
    assert run_once(monkeypatch, [bad, good]) == []
    sent = run_once(monkeypatch, [bad, good])
    assert len(sent) == 1 and "bot engeli" in sent[0]  # 3. başarısızlıkta tek uyarı
    sent = run_once(monkeypatch, [bad, good])
    assert any("tekrar çalışıyor" in m for m in sent) and any("2.950" in m for m in sent)
    assert load_state().saglik["bad"]["uyarildi"] is False


def test_profiles_split_sites():
    from fiyatbot.scrapers import build_scrapers
    names = lambda p: [s.name for s in build_scrapers(None, profile=p)]  # noqa: E731
    assert names("bulut") == ["amazon", "hepsiburada", "n11"]
    assert names("ev") == ["akakce", "cimri", "epey", "pazarama", "pttavm", "trendyol"]
    assert len(names("hepsi")) == 9
    assert [s.name for s in build_scrapers(None, only=["trendyol"], profile="bulut")] == ["trendyol"]


def test_ev_profile_skips_commands_and_uses_own_files(env, monkeypatch):
    from tests.test_commands import FakeTelegram, msg
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "111")
    monkeypatch.setattr(runner, "build_scrapers", lambda *a, **kw: [FakeShop("shop", [[2899]])])
    config.use_profile("ev")  # conftest'in geçici EV yollarını etkinleştirir
    tg = FakeTelegram([msg(1, "/sil 1", chat_id=111)])
    notifier = FakeNotifier()
    runner.run(runner.RunOptions(enrich=False, profil="ev"), notifier, telegram=tg)
    assert tg.calls == []                       # PC komutlara dokunmaz (GitHub'ın işi)
    assert len(notifier.sent) == 1              # ama fırsatı bildirir
    assert config.STATE_FILE == config.EV_STATE_FILE and config.EV_STATE_FILE.exists()
    assert not (env / "state.json").exists()


def test_unhealthy_site_skipped_until_retry_window(env, monkeypatch):
    from fiyatbot.http import FetchError
    good = FakeShop("good", [[2899]] * 5)
    bad = FakeShop("bad", [FetchError("timeout")] * 3 + [[2950]])
    monkeypatch.setattr(runner, "now_tr", lambda: datetime.fromisoformat("2026-10-21T13:30:00+03:00"))
    for _ in range(3):
        run_once(monkeypatch, [bad, good])          # 3. hatada uyarı → bozuk işaretli
    assert load_state().saglik["bad"]["uyarildi"] is True
    run_once(monkeypatch, [bad, good])              # 13:30 → deneme penceresi dışı, atlanır
    assert len(bad.prices) == 1                     # çağrılmadı
    monkeypatch.setattr(runner, "now_tr", lambda: datetime.fromisoformat("2026-10-21T14:05:00+03:00"))
    sent = run_once(monkeypatch, [bad, good])       # 14:05 → denenir, düzelmiş → "tekrar çalışıyor"
    assert any("tekrar çalışıyor" in m for m in sent)


def test_unchanged_state_not_rewritten(env, monkeypatch):
    # Aynı sonuç → state.json'a hiç dokunulmamalı (Actions'ta boş/anlamsız commit oluşmasın)
    shop = FakeShop("shop", [[2899], [2899]])
    run_once(monkeypatch, [shop])
    path = env / "state.json"
    before = path.read_bytes(), path.stat().st_mtime_ns
    run_once(monkeypatch, [shop])
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_repeated_timeouts_do_not_change_state(env, monkeypatch):
    from fiyatbot.http import FetchError
    errors = [FetchError(f"epey: timed out after {ms} milliseconds") for ms in (20012, 20007, 20019)]
    good = FakeShop("good", [[2899]] * 3)
    bad = FakeShop("bad", errors)
    run_once(monkeypatch, [bad, good])
    run_once(monkeypatch, [bad, good])
    first = load_state().saglik["bad"]["son_hata"]
    run_once(monkeypatch, [bad, good])
    assert load_state().saglik["bad"]["son_hata"] == first  # milisaniye farkı state'i değiştirmez
