"""Genel ayarlar / Global settings."""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
STATE_FILE = DATA_DIR / "state.json"
HISTORY_FILE = DATA_DIR / "price_history.csv"

load_dotenv(ROOT / ".env")  # yerelde .env; Actions'ta Secrets ortam değişkeni olarak gelir

TZ = ZoneInfo("Europe/Istanbul")
IS_CI = os.getenv("GITHUB_ACTIONS") == "true"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# HTTP
REQUEST_TIMEOUT = 20        # saniye
REQUEST_RETRIES = 2         # toplam deneme sayısı (zaman aşımında her deneme 20 sn sürer)
MIN_INTERVAL_PER_HOST = 2.0 # aynı siteye iki istek arası en az bekleme (kibar tarama)

# Tek mesajda en fazla kaç teklif listelensin
MAX_RESULTS_PER_MESSAGE = 10

# Detay sayfası (satıcı/garanti) kaç aday için açılsın — ürün ve site başına
ENRICH_LIMIT = 5

# Spam önleme: önceki bildirime göre en az bu kadar düşerse tekrar bildir (hangisi büyükse)
RENOTIFY_MIN_DROP_PCT = 1.0
RENOTIFY_MIN_DROP_TL = 100.0

# Sağlık kontrolü: bir site art arda bu kadar çalışmada başarısızsa tek uyarı gönder
HEALTH_FAIL_THRESHOLD = 3

# Fiyat geçmişi bu kadar günden eskiyse silinir
HISTORY_KEEP_DAYS = 90
