"""Bildirim gönderici / Notifier: gerçek Telegram ya da dry-run (ekrana basar)."""

from __future__ import annotations

import html
import logging
import re

from . import config
from .telegram import Telegram

log = logging.getLogger(__name__)


class DryRunNotifier:
    """Bildirim göndermez; mesajı (HTML etiketleri sadeleştirilmiş) ekrana basar."""

    def send(self, text: str) -> None:
        plain = re.sub(r'<a href="([^"]+)">[^<]*</a>', r"\1", text)
        plain = html.unescape(re.sub(r"</?(b|s|i|code)>", "", plain))
        print("\n┌── [DRY-RUN] Telegram mesajı " + "─" * 30)
        for line in plain.splitlines():
            print("│ " + line)
        print("└" + "─" * 60)


class TelegramNotifier:
    def __init__(self, telegram: Telegram):
        self.telegram = telegram

    def send(self, text: str) -> None:
        self.telegram.send(text)
        log.info("Telegram mesajı gönderildi (%d karakter)", len(text))


def make_notifier(dry_run: bool):
    if dry_run:
        return DryRunNotifier()
    return TelegramNotifier(Telegram(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID))
