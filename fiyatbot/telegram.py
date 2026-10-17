"""Telegram Bot API istemcisi / Minimal Telegram Bot API client.

Token hiçbir zaman loglanmaz; hata mesajlarında maskelenir.
"""

from __future__ import annotations

import logging
import time

from curl_cffi import requests

log = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 4096


class TelegramError(Exception):
    pass


class Telegram:
    def __init__(self, token: str, chat_id: str, timeout: float = 20):
        if not token:
            raise TelegramError("TELEGRAM_BOT_TOKEN tanımlı değil (.env veya GitHub Secrets)")
        self._token = token
        self.chat_id = str(chat_id)
        self.timeout = timeout

    def _call(self, method: str, payload: dict, retries: int = 3) -> object:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                data = resp.json()
            except Exception as e:  # noqa: BLE001
                error = f"{method}: bağlantı hatası: {str(e).replace(self._token, '***')}"
            else:
                if data.get("ok"):
                    return data["result"]
                retry_after = (data.get("parameters") or {}).get("retry_after")
                error = f"{method}: {data.get('error_code')} {data.get('description')}"
                if retry_after and attempt < retries:  # 429: Telegram ne kadar bekleneceğini söyler
                    time.sleep(min(int(retry_after), 30))
                    continue
                if resp.status_code < 500:
                    raise TelegramError(error)
            if attempt < retries:
                time.sleep(2 ** attempt)
        raise TelegramError(error)

    def send(self, text: str, chat_id: str | None = None) -> None:
        for chunk in split_message(text):
            self._call("sendMessage", {
                "chat_id": chat_id or self.chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })

    def get_updates(self, offset: int | None = None) -> list[dict]:
        payload = {"timeout": 0, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", payload)


def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Uzun mesajı boş satırlardan (teklif sınırları) bölerek parçalara ayırır; HTML etiketi bölünmez."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = block if len(block) <= limit else block[: limit - 1] + "…"
    if current:
        chunks.append(current)
    return chunks
