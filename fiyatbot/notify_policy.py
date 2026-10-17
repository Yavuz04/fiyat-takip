"""Tekrarlayan bildirim (spam) önleme / Deduplication of notifications.

Kurallar:
  1. Bütçe altındaki bir ilan ilk kez görülürse → bildir ("yeni").
  2. Daha önce bildirilmişse, sadece son BİLDİRİLEN fiyata göre anlamlı ölçüde düştüyse tekrar bildir
     (en az %1 veya 100 TL, hangisi büyükse) ("düştü").
  3. Bütçe üstüne çıkan / listeden kalkan ilan unutulur → tekrar bütçe altına inerse yine bildirilir.
     Ama o çalışmada HATA veren sitenin kayıtları silinmez (site çöktü diye herkes yeniden bildirilmesin).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config
from .models import Teklif


@dataclass
class Bildirim:
    teklif: Teklif
    onceki_fiyat: float | None  # None → ilk kez


def min_drop(previous: float) -> float:
    return max(previous * config.RENOTIFY_MIN_DROP_PCT / 100, config.RENOTIFY_MIN_DROP_TL)


def decide(
    firsatlar: list[Teklif],
    gecmis: dict[str, dict],
    calisan_siteler: set[str],
    zaman: str,
) -> tuple[list[Bildirim], dict[str, dict]]:
    """Bir ürünün bu çalışmadaki fırsatlarından hangilerinin bildirileceğine karar verir.

    gecmis: bu ürün için {ilan anahtarı: {"fiyat": son bildirilen fiyat, "zaman": ...}}
    calisan_siteler: bu çalışmada başarıyla taranan siteler
    Dönüş: (bildirilecekler, yeni geçmiş)
    """
    bildirimler: list[Bildirim] = []
    yeni: dict[str, dict] = {}

    for teklif in firsatlar:
        key, fiyat = teklif.anahtar, teklif.etkin_fiyat
        if fiyat is None or key in yeni:
            continue
        onceki = gecmis.get(key)
        if onceki is None:
            bildirimler.append(Bildirim(teklif, None))
            yeni[key] = {"fiyat": fiyat, "zaman": zaman}
        elif fiyat <= onceki["fiyat"] - min_drop(onceki["fiyat"]):
            bildirimler.append(Bildirim(teklif, onceki["fiyat"]))
            yeni[key] = {"fiyat": fiyat, "zaman": zaman}
        else:
            yeni[key] = onceki  # son BİLDİRİLEN fiyat korunur; küçük dalgalanmalar birikip spam yapmaz

    # Bu çalışmada taranamayan sitelerin eski kayıtlarını koru
    for key, value in gecmis.items():
        if key not in yeni and key.split("|", 1)[0] not in calisan_siteler:
            yeni[key] = value

    return bildirimler, yeni
