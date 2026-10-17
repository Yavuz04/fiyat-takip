"""JSON dosya okuma/yazma / JSON file I/O (atomik yazma)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import config
from .models import TakipKaydi


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    """Önce geçici dosyaya yazıp sonra yer değiştirir; yarıda kesilirse dosya bozulmaz."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_watchlist(path: Path | None = None) -> list[TakipKaydi]:
    return [TakipKaydi.from_dict(d) for d in read_json(path or config.WATCHLIST_FILE, [])]


def save_watchlist(kayitlar: list[TakipKaydi], path: Path | None = None) -> None:
    write_json(path or config.WATCHLIST_FILE, [k.to_dict() for k in kayitlar])
