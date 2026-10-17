"""Eşleştirme ve filtreleme / Matching and filtering.

Kelime eşleşmesi token bazlıdır: "15" kelimesi "150" ile eşleşmez, "cam" kelimesi "camera" ile
eşleşmez. Uzun (≥5 harf) kelimeler Türkçe ekleri yakalamak için önek olarak eşleşir:
"kılıf" → "kılıflı", "kılıfı" da yakalanır.
"""

from __future__ import annotations

from .models import (
    GARANTI_BILINMIYOR,
    GARANTI_ITHALATCI,
    GARANTI_TR,
    GARANTI_YURTDISI,
    TakipKaydi,
    Teklif,
)
from .text import fold, tokens

# /ekle ile eklenen ürünlere varsayılan olarak uygulanan hariç kelimeler
GENEL_HARIC = [
    "kılıf", "kapak", "cam", "koruyucu", "ekran koruyucu", "yenilenmiş", "ikinci el", "2 el",
    "teşhir", "vitrin", "outlet", "kutusuz", "aksesuar", "şarj aleti", "şarj cihazı", "kablo",
    "adaptör", "tutucu", "sticker", "yedek parça", "kordon", "kayış", "silikon",
]
# Model varyantları: sorguda GEÇMİYORSA hariç tutulur ("iPhone 15" aramasında "pro" elenir,
# "iPhone 15 Pro" aramasında elenmez)
VARYANT_KELIMELER = ["pro", "plus", "max", "mini", "ultra", "lite", "air", "fe"]

_UNITS = {"gb", "tb", "mb", "mah", "w", "hz", "inc", "inch", "cm", "mm", "kg", "lt", "ml"}
_PREFIX_MIN_LEN = 5


def _token_eq(word: str, title_token: str) -> bool:
    if word == title_token:
        return True
    return word.isalpha() and len(word) >= _PREFIX_MIN_LEN and title_token.startswith(word)


def contains_phrase(title_tokens: list[str], phrase: str) -> bool:
    """Kelime/öbek başlıkta ardışık token'lar olarak geçiyor mu?"""
    words = tokens(phrase)
    if not words:
        return True
    n = len(words)
    for i in range(len(title_tokens) - n + 1):
        if all(_token_eq(w, t) for w, t in zip(words, title_tokens[i : i + n])):
            return True
    return False


def garanti_tespit(text: str) -> str:
    """Başlık/açıklama metninden garanti türünü tahmin eder."""
    t = fold(text)
    if "ithalatci" in t:
        return GARANTI_ITHALATCI
    if any(k in t for k in ("distributor", "turkiye garanti", "tr garanti", "apple turkiye", "resmi garanti")):
        return GARANTI_TR
    if any(k in t for k in ("yurt disi", "yurtdisi", "global versiyon", "global surum", "import",
                            "international version")):
        return GARANTI_YURTDISI
    return GARANTI_BILINMIYOR


def filtrele(kayit: TakipKaydi, teklif: Teklif) -> str | None:
    """Teklif kriterlere uyuyorsa None, uymuyorsa ret sebebini döndürür.

    Not: max_fiyat burada kontrol edilmez — bütçe üstü ama eşleşen sonuçlar da fiyat geçmişi
    ve /ekle önizlemesi için gereklidir. Bütçe kontrolü: butce_altinda().
    """
    if teklif.stokta is False:
        return "stok yok"
    fiyat = teklif.etkin_fiyat
    if fiyat is None:
        return "fiyat yok"
    if fiyat < kayit.min_fiyat:
        return "min fiyat altı"

    title = tokens(teklif.baslik)
    for word in kayit.gerekli:
        if not contains_phrase(title, word):
            return f"gerekli yok: {word}"
    for word in kayit.haric:
        if contains_phrase(title, word):
            return f"hariç: {word}"

    if kayit.garanti == "tr" and teklif.garanti in (GARANTI_ITHALATCI, GARANTI_YURTDISI):
        return f"garanti: {teklif.garanti}"
    return None


def butce_altinda(kayit: TakipKaydi, teklif: Teklif) -> bool:
    fiyat = teklif.etkin_fiyat
    return fiyat is not None and fiyat <= kayit.max_fiyat


def varsayilan_gerekli(sorgu: str) -> list[str]:
    """Sorgudan zorunlu kelimeler türetir. 'iPhone 15 128GB' → ['iphone 15', '128 gb'].

    Kurallar:
      - bir sayı, önündeki kelimeyle birleşir (model numarası: 'iphone 15', 's 24')
      - ondalıklı model numarası bölünmez: 'MatePad 11.5' → 'matepad 11 5'
      - sayıdan sonraki tek harf model ekidir: '11.5 S' → '... 11 5 s', 'iPhone 16e' → 'iphone 16 e'
      - bir birim, önündeki sayıyla birleşir ('128 gb')
    """
    toks = tokens(sorgu)
    groups: list[list[str]] = []
    for i, tok in enumerate(toks):
        prev = groups[-1] if groups else None
        next_is_unit = i + 1 < len(toks) and toks[i + 1] in _UNITS
        is_model_group = bool(prev) and prev[0].isalpha() and prev[0] not in _UNITS
        if (prev and tok.isdigit() and not next_is_unit and len(prev) == 1
                and prev[-1].isalpha() and prev[-1] not in _UNITS):
            prev.append(tok)
        elif is_model_group and len(prev) >= 2 and prev[-1].isdigit() and tok.isdigit() and not next_is_unit:
            prev.append(tok)  # ondalık: 11 . 5
        elif is_model_group and len(prev) >= 2 and prev[-1].isdigit() and len(tok) == 1 and tok.isalpha():
            prev.append(tok)  # model eki: 11.5 S, 16e
        elif prev and tok in _UNITS and prev[-1].isdigit():
            prev.append(tok)
        else:
            groups.append([tok])
    return [" ".join(g) for g in groups]


def varsayilan_haric(sorgu: str) -> list[str]:
    query = set(tokens(sorgu))
    return GENEL_HARIC + [v for v in VARYANT_KELIMELER if v not in query]


def yeni_kayit(id: int, sorgu: str, max_fiyat: float) -> TakipKaydi:
    """/ekle komutu için mantıklı varsayılanlarla yeni kayıt."""
    return TakipKaydi(
        id=id,
        sorgu=sorgu.strip(),
        max_fiyat=max_fiyat,
        min_fiyat=round(max_fiyat * 0.4),
        gerekli=varsayilan_gerekli(sorgu),
        haric=varsayilan_haric(sorgu),
    )
