"""Tarama: bir takip kaydını tüm sitelerde arar, filtreler, adayları zenginleştirir.

Scanning: searches one tracked product on all sites; a failing site never stops the others.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass, field

from . import config
from .http import BlockedError
from .matching import butce_altinda, filtrele
from .models import TakipKaydi, Teklif
from .scrapers.base import ParseError, Scraper

log = logging.getLogger(__name__)

# Site durumları (sağlık kontrolü için)
OK, EMPTY, ERROR, BLOCKED = "ok", "bos", "hata", "engel"


@dataclass
class SiteDurumu:
    site: str
    durum: str
    sonuc: int = 0
    mesaj: str = ""


@dataclass
class TaramaSonucu:
    kayit: TakipKaydi
    eslesen: list[Teklif] = field(default_factory=list)   # filtreyi geçen (bütçe fark etmez)
    firsat: list[Teklif] = field(default_factory=list)    # eşleşen + bütçe altında
    siteler: list[SiteDurumu] = field(default_factory=list)
    elenen: list[tuple[Teklif, str]] = field(default_factory=list)  # (teklif, ret sebebi) — /ekle önizlemesi için
    toplam: int = 0


def _price_key(t: Teklif) -> float:
    return t.etkin_fiyat or float("inf")


def _save_debug(scraper: Scraper) -> None:
    """Ayrıştırılamayan son yanıtı debug/ klasörüne kaydeder (gitignore'da; Actions'ta artifact olarak alınır)."""
    bodies = scraper.http.last_body
    if not bodies:
        return
    host, body = next(((h, b) for h, b in bodies.items() if scraper.name in h), list(bodies.items())[-1])
    path = config.ROOT / "debug" / f"{scraper.name}-{time.strftime('%Y%m%d-%H%M%S')}.html"
    path.parent.mkdir(exist_ok=True)
    path.write_text(body, encoding="utf-8")
    log.info("[%s] ayrıştırılamayan yanıt kaydedildi: %s (%d bayt, %s)", scraper.name, path.name, len(body), host)


def tara(kayit: TakipKaydi, scrapers: list[Scraper], enrich: bool = True) -> TaramaSonucu:
    sonuc = TaramaSonucu(kayit)
    for scraper in scrapers:
        if kayit.siteler and scraper.name not in kayit.siteler:
            continue
        try:
            offers = scraper.search(kayit.sorgu)
        except BlockedError as e:
            log.warning("[%s] #%d: BOT ENGELİ — %s", scraper.name, kayit.id, e)
            sonuc.siteler.append(SiteDurumu(scraper.name, BLOCKED, mesaj=str(e)))
            continue
        except Exception as e:  # noqa: BLE001 — bir site bozulursa diğerleri devam etsin
            log.warning("[%s] #%d: HATA — %s: %s", scraper.name, kayit.id, type(e).__name__, e)
            if isinstance(e, ParseError):
                _save_debug(scraper)
            sonuc.siteler.append(SiteDurumu(scraper.name, ERROR, mesaj=f"{type(e).__name__}: {e}"))
            continue

        matched, reasons = [], Counter()
        for offer in offers:
            reason = filtrele(kayit, offer)
            if reason is None:
                matched.append(offer)
            else:
                reasons[reason.split(":")[0]] += 1
                sonuc.elenen.append((offer, reason))
        sonuc.toplam += len(offers)
        matched.sort(key=_price_key)
        deals = [o for o in matched if butce_altinda(kayit, o)]

        # Detay sayfası sadece bütçe altındaki en ucuz birkaç aday için açılır (az istek)
        if enrich:
            checked = []
            for offer in deals[: config.ENRICH_LIMIT]:
                try:
                    scraper.enrich(offer)
                except Exception as e:  # noqa: BLE001 — detay alınamazsa arama verisiyle devam
                    log.info("[%s] detay alınamadı (%s): %s", scraper.name, type(e).__name__, offer.url)
                if filtrele(kayit, offer) is None:  # stok/garanti detayda değişmiş olabilir
                    checked.append(offer)
            deals = checked + deals[config.ENRICH_LIMIT :]

        log.info(
            "[%s] #%d '%s': %d sonuç, %d eşleşti, %d bütçe altında | elenen: %s",
            scraper.name, kayit.id, kayit.sorgu, len(offers), len(matched), len(deals),
            dict(reasons) or "-",
        )
        sonuc.siteler.append(SiteDurumu(scraper.name, OK if offers else EMPTY, sonuc=len(offers)))
        sonuc.eslesen.extend(matched)
        sonuc.firsat.extend(deals)

    sonuc.eslesen.sort(key=_price_key)
    sonuc.firsat.sort(key=_price_key)
    return sonuc
