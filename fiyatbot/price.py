"""Türk fiyat formatı ayrıştırma / Turkish price parsing.

Desteklenen örnekler:
  "25.999,00 TL" → 25999.0     "25.999 TL" → 25999.0     "₺25.999" → 25999.0
  "1.299,90"     → 1299.9      "25999.0"   → 25999.0     25999      → 25999.0
  "Sepette 24.500 TL" → 24500.0
"""

from __future__ import annotations

import re

from .text import fold

_NUMBER = re.compile(r"\d[\d.,]*")

# Taksit metinleri: "12 x 2.166 TL", "Aylık 2.166 TL", "3 taksit", "2.166 TL/ay"
_INSTALLMENT = re.compile(r"taksit|aylik|\b\d+\s*x\b|\bx\s*\d+\b|\bay\b")


def _to_float(num: str) -> float | None:
    num = num.rstrip(".,")
    if not num:
        return None
    has_dot, has_comma = "." in num, "," in num

    if has_dot and has_comma:
        # Sonda olan ayraç ondalıktır: "25.999,00" (TR) veya "25,999.00" (EN)
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif has_comma or has_dot:
        sep = "," if has_comma else "."
        parts = num.split(sep)
        # Birden fazla ayraç ya da tam 3 haneli son grup → binlik ayracı ("25.999", "1.299.000")
        if len(parts) > 2 or len(parts[-1]) == 3:
            num = num.replace(sep, "")
        else:
            num = num.replace(sep, ".")  # ondalık: "25999,5", "25999.0"
    try:
        return float(num)
    except ValueError:
        return None


def parse_price(value) -> float | None:
    """Metin ya da sayıdan fiyat çıkarır; bulunamazsa / sıfır veya negatifse None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    match = _NUMBER.search(str(value))
    if not match:
        return None
    result = _to_float(match.group())
    return result if result and result > 0 else None


def looks_like_installment(text: str) -> bool:
    """Metin bir taksit tutarı mı? Taksit tutarı asla ürün fiyatı olarak kullanılmamalı."""
    return bool(_INSTALLMENT.search(fold(text)))


def format_tl(amount: float) -> str:
    """25999.5 → '25.999,50 TL', 25999.0 → '25.999 TL'."""
    whole = int(amount)
    kurus = round((amount - whole) * 100)
    if kurus == 100:
        whole, kurus = whole + 1, 0
    text = f"{whole:,}".replace(",", ".")
    return f"{text},{kurus:02d} TL" if kurus else f"{text} TL"
