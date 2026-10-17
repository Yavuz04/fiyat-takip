"""Türkçe metin normalizasyonu / Turkish-aware text normalization.

Karşılaştırma için tüm metinler "katlanmış" (folded) forma çevrilir:
  - Türkçe büyük/küçük harf doğru işlenir (İ→i, I→ı; Python'un .lower()'ı bunu bilmez)
  - Aksanlar ve Türkçe harfler ASCII'ye indirgenir (ş→s, ı→i, ğ→g ...)
  - Noktalama boşluğa dönüşür
  - Harf/rakam sınırları ayrılır: "128GB" → "128 gb", "iPhone15" → "iphone 15"
Böylece "128 GB" = "128GB" = "128gb" ve "KILIF" = "kılıf" = "kilif" olur.
"""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ALPHA_DIGIT = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")


def tr_lower(text: str) -> str:
    """Türkçe kurallarına göre küçük harf (İ→i, I→ı)."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def fold(text: str) -> str:
    """Metni karşılaştırma formuna çevirir. Örn: 'Apple iPhone 15 (128 GB) Kılıf' → 'apple iphone 15 128 gb kilif'."""
    if not text:
        return ""
    s = tr_lower(text).replace("ı", "i")
    # Aksanları (ş, ğ, ü, ö, ç, â ...) ayır ve at / strip combining marks
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = _NON_ALNUM.sub(" ", s)
    s = _ALPHA_DIGIT.sub(" ", s)
    return " ".join(s.split())


def tokens(text: str) -> list[str]:
    return fold(text).split()
