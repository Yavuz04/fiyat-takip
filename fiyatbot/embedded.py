"""Sayfa içine gömülü JSON'u çıkarma yardımcıları / Helpers for embedded page JSON."""

from __future__ import annotations

import json
import re

_decoder = json.JSONDecoder()
_LD_JSON = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def ld_json(html: str) -> list[dict]:
    """Sayfadaki tüm JSON-LD nesneleri (liste/@graph açılmış halde). Bozuk bloklar atlanır."""
    items = []
    for m in _LD_JSON.finditer(html):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict):
                items.extend(item["@graph"] if isinstance(item.get("@graph"), list) else [item])
    return items


def ld_products(html: str) -> list[dict]:
    """JSON-LD ItemList içindeki Product nesneleri."""
    products = []
    for item in ld_json(html):
        if item.get("@type") == "ItemList":
            for el in item.get("itemListElement") or []:
                prod = el.get("item", el) if isinstance(el, dict) else None
                if isinstance(prod, dict) and prod.get("@type") == "Product":
                    products.append(prod)
    return products


def window_json(html: str, key: str):
    """`window["key"]={...}`, `window.key = {...}` veya `window.key = JSON.parse("...")` atamasındaki
    JSON'u döndürür; yoksa None."""
    for marker in (f'window["{key}"]=', f'window["{key}"] =', f"window.{key}=", f"window.{key} ="):
        idx = html.find(marker)
        if idx != -1:
            start = idx + len(marker)
            while html[start].isspace():
                start += 1
            if html.startswith("JSON.parse(", start):
                text = _decoder.raw_decode(html, start + len("JSON.parse("))[0]
                return json.loads(text)
            return _decoder.raw_decode(html, start)[0]
    return None


def script_json(html: str, script_id: str):
    """`<script id="script_id">{...}</script>` içeriğini JSON olarak döndürür; yoksa None."""
    m = re.search(r'<script[^>]*\bid="%s"[^>]*>(.*?)</script>' % re.escape(script_id), html, re.S)
    return json.loads(m.group(1)) if m else None


def json_after(text: str, marker: str):
    """Metinde `marker`'dan hemen sonra başlayan JSON değerini döndürür; yoksa None."""
    idx = text.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    while text[start].isspace():
        start += 1
    return _decoder.raw_decode(text, start)[0]


def astro_revive(value):
    """Astro island `props` serileştirmesini çözer: [0, x] → x, [1, [...]] → liste."""
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
        kind, inner = value
        if kind == 1 and isinstance(inner, list):
            return [astro_revive(v) for v in inner]
        return astro_revive(inner) if isinstance(inner, (dict, list)) else inner
    if isinstance(value, dict):
        return {k: astro_revive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [astro_revive(v) for v in value]
    return value
