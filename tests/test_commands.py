import pytest

from fiyatbot import config, history, runner
from fiyatbot.commands import Commands
from fiyatbot.matching import yeni_kayit
from fiyatbot.state import load_state
from fiyatbot.storage import load_watchlist, save_watchlist
from tests.test_runner import FakeNotifier, FakeShop


def make(*sorgular):
    return Commands([yeni_kayit(i, s, 3000) for i, s in enumerate(sorgular, 1)])


# --- Komut ayrıştırma ------------------------------------------------------

def test_ekle_with_tl_suffix_gets_next_id():
    c = make("Huawei M-Pencil 3")
    c.handle("/ekle Apple Pencil Pro 4.500 TL")
    assert c.changed and len(c.kayitlar) == 2
    k = c.kayitlar[1]
    assert (k.id, k.sorgu, k.max_fiyat) == (2, "Apple Pencil Pro", 4500)
    assert "pro" not in k.haric  # sorguda geçtiği için hariç tutulmaz


def test_ekle_parses_price_as_last_token():
    c = Commands([])
    c.handle("/ekle Huawei M-Pencil 3 3.000")
    k = c.kayitlar[0]
    assert (k.id, k.sorgu, k.max_fiyat, k.min_fiyat) == (1, "Huawei M-Pencil 3", 3000, 1200)
    assert "pro" in k.haric  # sorguda geçmeyen varyant kelimesi otomatik hariç


@pytest.mark.parametrize("text", ["/ekle", "/ekle 3000", "/ekle Huawei M-Pencil abc"])
def test_ekle_usage_errors(text):
    c = Commands([])
    assert c.handle(text).startswith("⚠️")
    assert c.kayitlar == []


def test_bot_suffix_and_unknown_and_plain_text():
    c = make("x")
    assert "komutlar" in c.handle("/yardim@FiyatBot")
    assert "25 dk" in c.handle("/yardim")
    assert "Bilinmeyen komut" in c.handle("/foo")
    assert c.handle("merhaba") is None


def test_multiline_message_runs_each_command():
    c = make("Huawei M-Pencil 3")
    replies = c.handle_message("/liste\n/detay 1\n\n  /haric 1 kalem ucu, yedek uç\nselam")
    assert len(replies) == 3
    assert replies[0].startswith("📋") and replies[1].startswith("🔎")
    assert c.kayitlar[0].haric[-2:] == ["kalem ucu", "yedek uç"]
    assert c.handle_message("merhaba") == []


def test_haric_add_remove_multi():
    c = make("Huawei M-Pencil 3")
    k = c.kayitlar[0]
    k.haric = ["kılıf"]
    c.handle("/haric 1 uç, ekran koruyucu, kılıf")
    assert k.haric == ["kılıf", "uç", "ekran koruyucu"]  # kılıf zaten vardı
    reply = c.handle("/haric 1 -KILIF")
    assert k.haric == ["uç", "ekran koruyucu"] and "silindi: KILIF" in reply


def test_gerekli_and_amounts():
    c = make("Huawei M-Pencil 3")
    k = c.kayitlar[0]
    c.handle("/gerekli 1 3 nesil")
    assert "3 nesil" in k.gerekli
    c.handle("/minfiyat 1 1500")
    c.handle("/maxfiyat #1 2.750")
    assert (k.min_fiyat, k.max_fiyat) == (1500, 2750)
    assert "büyük olamaz" in c.handle("/minfiyat 1 5000")


def test_durdur_devam_sil_and_missing_id():
    c = make("a", "b")
    c.handle("/durdur 2")
    assert c.kayitlar[1].aktif is False
    c.handle("/devam 2")
    assert c.kayitlar[1].aktif is True
    c.handle("/sil 1")
    assert [k.id for k in c.kayitlar] == [2]
    assert "bulunamadı" in c.handle("/sil 9")
    assert "Geçersiz id" in c.handle("/sil abc")


def test_garanti_siteler():
    c = make("x")
    c.handle("/garanti 1 tr")
    assert c.kayitlar[0].garanti == "tr"
    c.handle("/siteler 1 trendyol, n11")
    assert c.kayitlar[0].siteler == ["trendyol", "n11"]
    assert "Bilinmeyen site" in c.handle("/siteler 1 gittigidiyor")
    c.handle("/siteler 1 hepsi")
    assert c.kayitlar[0].siteler is None


def test_liste_shows_cheapest_and_escapes():
    c = Commands([yeni_kayit(1, "Kalem <Pro> & Co", 3000)], son_fiyat={"1|trendyol": 2899.0, "1|n11": 3100.0})
    out = c.handle("/liste")
    assert "Kalem &lt;Pro&gt; &amp; Co" in out and "2.899 TL (Trendyol)" in out


def test_gecmis(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "h.csv")
    from datetime import datetime
    now = datetime.fromisoformat("2026-10-18T12:00:00+03:00")
    history.append([
        {"zaman": "2026-10-17T10:00:00+03:00", "urun_id": 1, "site": "trendyol", "fiyat": 3199.0,
         "satici": "", "baslik": "x", "url": "u"},
        {"zaman": "2026-10-18T10:00:00+03:00", "urun_id": 1, "site": "trendyol", "fiyat": 2899.0,
         "satici": "", "baslik": "x", "url": "u"},
        {"zaman": "2026-10-18T10:00:00+03:00", "urun_id": 1, "site": "n11", "fiyat": 3518.76,
         "satici": "", "baslik": "x", "url": "u"},
    ], now)
    out = make("Huawei M-Pencil 3").handle("/gecmis 1")
    assert "En düşük: <b>2.899 TL</b> · Trendyol" in out
    assert "3.199 TL → 2.899 TL 📉" in out
    assert "n11: 3.518,76 TL" in out
    assert "henüz fiyat geçmişi yok" in make("a", "b").handle("/gecmis 2")


# --- Runner entegrasyonu (sahte Telegram) ----------------------------------

class FakeTelegram:
    def __init__(self, updates):
        self.updates = updates
        self.calls = []

    def get_updates(self, offset=None):
        self.calls.append(offset)
        return [u for u in self.updates if offset is None or u["update_id"] >= offset]


def msg(update_id, text, chat_id):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr(config, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.csv")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "111")
    save_watchlist([])
    return tmp_path


def test_commands_end_to_end(env, monkeypatch):
    shop = FakeShop("shop", [[2899, 3500], [2899, 3500]])
    monkeypatch.setattr(runner, "build_scrapers", lambda *a, **kw: [shop])
    tg = FakeTelegram([
        msg(10, "/sil 1", chat_id=999),                          # yabancı → yok sayılır
        msg(11, "/ekle Huawei M-Pencil 3 Nesil 3000", chat_id=111),
    ])
    notifier = FakeNotifier()
    runner.run(runner.RunOptions(enrich=False), notifier, telegram=tg)

    assert len(load_watchlist()) == 1
    assert len(notifier.sent) == 1  # sadece /ekle yanıtı (önizleme dahil); ayrıca fırsat bildirimi yok
    reply = notifier.sent[0]
    assert "#1 eklendi" in reply and "İlk tarama" in reply and "2.899 TL" in reply
    assert load_state().telegram_offset == 12
    assert tg.calls == [None, 12]  # al + Telegram'a onayla

    # Sonraki çalışma: yeni komut yok, fiyat aynı → sessiz (önizlemede bildirildi sayıldı)
    notifier2 = FakeNotifier()
    runner.run(runner.RunOptions(enrich=False), notifier2, telegram=FakeTelegram([]))
    assert notifier2.sent == []


def test_dry_run_does_not_confirm_or_save(env, monkeypatch):
    monkeypatch.setattr(runner, "build_scrapers", lambda *a, **kw: [FakeShop("shop", [[2899]])])
    tg = FakeTelegram([msg(5, "/ekle Huawei M-Pencil 3 Nesil 3000", chat_id=111)])
    notifier = FakeNotifier()
    runner.run(runner.RunOptions(dry_run=True, enrich=False), notifier, telegram=tg)
    assert "eklendi" in notifier.sent[0]
    assert tg.calls == [None]                 # onay yok → gerçek çalışmada tekrar işlenecek
    assert load_watchlist() == []             # dosyaya yazılmadı
    assert not (env / "state.json").exists()


def test_empty_chat_id_rejects_everything(env, monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "")
    monkeypatch.setattr(runner, "build_scrapers", lambda *a, **kw: [])
    tg = FakeTelegram([msg(1, "/ekle x 100", chat_id="")])
    notifier = FakeNotifier()
    runner.run(runner.RunOptions(), notifier, telegram=tg)
    assert notifier.sent == [] and load_watchlist() == []
