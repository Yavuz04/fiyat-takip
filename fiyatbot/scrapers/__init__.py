"""Scraper kaydı: bu paketteki her modülün Scraper alt sınıfları otomatik bulunur.

Registry: every Scraper subclass in this package is discovered automatically.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from ..http import HttpClient
from .base import Scraper

log = logging.getLogger(__name__)


def scraper_classes() -> dict[str, type[Scraper]]:
    for mod in pkgutil.iter_modules(__path__):
        if mod.name == "base":
            continue
        try:
            importlib.import_module(f"{__name__}.{mod.name}")
        except Exception:  # bozuk bir modül diğerlerini durdurmasın
            log.exception("Scraper modülü yüklenemedi: %s", mod.name)
    return {cls.name: cls for cls in Scraper.__subclasses__() if cls.name}


def build_scrapers(http: HttpClient, only: list[str] | None = None, profile: str = "hepsi") -> list[Scraper]:
    """profile: "bulut" → GitHub'da çalışan siteler, "ev" → GitHub'ı engelleyen siteler, "hepsi" → tümü.
    `only` verilirse profil yok sayılır (elle tek site denemek için)."""
    result = []
    for name, cls in sorted(scraper_classes().items()):
        if only:
            if name not in only:
                continue
        elif profile == "bulut" and not cls.enabled_on_ci:
            continue
        elif profile == "ev" and cls.enabled_on_ci:
            continue
        result.append(cls(http))
    return result
