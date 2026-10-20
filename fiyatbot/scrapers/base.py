"""Scraper eklenti arayüzü / Scraper plugin interface.

Yeni site eklemek: bu klasöre bir dosya ekle, Scraper'dan türeyen bir sınıf yaz,
`name` ve `label` ver, `search()` metodunu doldur. Kayıt otomatiktir.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..http import HttpClient
from ..models import Teklif


class ParseError(Exception):
    """Sayfa beklenen yapıda değil — site yapısı değişmiş olabilir."""


class Scraper(ABC):
    name: str = ""            # kısa kimlik, ör. "trendyol" (watchlist'teki site kısıtında kullanılır)
    label: str = ""           # mesajlarda görünen ad, ör. "Trendyol"
    # False → GitHub Actions IP'lerini engelliyor; sadece "ev" profilinde (PC'de) taranır
    enabled_on_ci: bool = True

    def __init__(self, http: HttpClient):
        self.http = http

    @abstractmethod
    def search(self, query: str) -> list[Teklif]:
        """Arama yapıp teklifleri döndürür. Hata durumunda FetchError/ParseError fırlatır."""

    def enrich(self, teklif: Teklif) -> Teklif:
        """(Opsiyonel) Detay sayfasından satıcı/garanti/stok bilgisini tamamlar."""
        return teklif
