import pytest

from fiyatbot import config


@pytest.fixture(autouse=True)
def _isolated_data(tmp_path, monkeypatch):
    """Hiçbir test gerçek data/ dosyalarını okuyup yazmasın."""
    for name, filename in [("WATCHLIST_FILE", "watchlist.json"), ("STATE_FILE", "state.json"),
                           ("HISTORY_FILE", "history.csv"), ("EV_STATE_FILE", "state-ev.json"),
                           ("EV_HISTORY_FILE", "history-ev.csv")]:
        monkeypatch.setattr(config, name, tmp_path / filename)
