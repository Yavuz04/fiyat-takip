"""HTTP katmanı / HTTP layer.

- curl_cffi ile gerçek Chrome TLS parmak izi (Cloudflare/Akamai engellerini azaltır)
- Exponential backoff ile yeniden deneme (ağ hataları, 5xx, 429)
- Aynı siteye istekler arasında bekleme (kibar tarama)
- Bot engeli tespiti (403, captcha, Cloudflare challenge) → BlockedError
"""

from __future__ import annotations

import logging
import random
import time
from urllib.parse import urlparse

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException

from . import config

log = logging.getLogger(__name__)

_BLOCK_MARKERS = (
    "cf-chl", "challenge-platform", "just a moment...", "attention required",
    "captcha", "robot check", "are you a human", "access denied", "erişim engellendi",
    "validatecaptcha", "bm-verify", "/_sec/verify",  # Amazon captcha, Akamai bot doğrulaması
)


class FetchError(Exception):
    """İstek başarısız (ağ hatası, beklenmeyen durum kodu)."""


class BlockedError(FetchError):
    """Site botu engelledi (403 / captcha / Cloudflare)."""


def looks_blocked(status: int, body: str) -> bool:
    if status in (403, 418, 429):
        return True
    # Engel sayfaları küçüktür; büyük gerçek sayfalarda "captcha" kelimesi geçebilir
    if len(body) < 60_000:
        low = body.lower()
        return any(m in low for m in _BLOCK_MARKERS)
    return False


class HttpClient:
    def __init__(
        self,
        timeout: float = config.REQUEST_TIMEOUT,
        retries: int = config.REQUEST_RETRIES,
        min_interval: float = config.MIN_INTERVAL_PER_HOST,
    ):
        self.timeout = timeout
        self.retries = retries
        self.min_interval = min_interval
        self._last_request: dict[str, float] = {}
        self.last_body: dict[str, str] = {}  # host → son yanıt gövdesi (ayrıştırma hatası teşhisi için)
        self.session = requests.Session(impersonate="chrome")
        self.session.headers.update({"Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.6,en;q=0.5"})

    def _wait_turn(self, host: str) -> None:
        elapsed = time.monotonic() - self._last_request.get(host, 0)
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed + random.uniform(0, 0.5))
        self._last_request[host] = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        host = urlparse(url).netloc
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self._wait_turn(host)
            try:
                resp = self.session.get(url, timeout=self.timeout, **kwargs)
            except RequestException as e:
                last_error = FetchError(f"{host}: ağ hatası: {e}")
            else:
                self.last_body[host] = resp.text
                if looks_blocked(resp.status_code, resp.text):
                    # Engel genelde tekrar denemeyle geçmez; siteyi daha fazla yormadan çık
                    raise BlockedError(f"{host}: bot engeli (HTTP {resp.status_code})")
                if resp.status_code < 400:
                    return resp
                last_error = FetchError(f"{host}: HTTP {resp.status_code}")
                if resp.status_code < 500:
                    raise last_error  # 404 vb. tekrar denemeye değmez
            if attempt < self.retries:
                delay = 2 ** attempt + random.uniform(0, 1)
                log.warning("%s (deneme %d/%d), %.1f sn sonra tekrar", last_error, attempt, self.retries, delay)
                time.sleep(delay)
        raise last_error
