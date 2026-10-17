"""Kalıcı durum / Persistent state (data/state.json).

GitHub Actions her çalışmada sıfırdan başlar; hatırlanması gereken her şey bu dosyada tutulur
ve workflow sonunda değiştiyse repoya commit'lenir.

Yapı:
{
  "bildirimler": {"<urun_id>": {"<ilan anahtarı>": {"fiyat": 2899.0, "zaman": "..."}}},
  "son_fiyat":   {"<urun_id>|<site>": 2899.0},     # fiyat geçmişine sadece değişince yazmak için
  "saglik":      {"<site>": {"ardisik_hata": 0, "uyarildi": false, "son_durum": "ok", ...}},
  "telegram_offset": null
}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .storage import read_json, write_json


@dataclass
class State:
    bildirimler: dict[str, dict[str, dict]] = field(default_factory=dict)
    son_fiyat: dict[str, float] = field(default_factory=dict)
    saglik: dict[str, dict] = field(default_factory=dict)
    telegram_offset: int | None = None

    def to_dict(self) -> dict:
        return {
            "bildirimler": self.bildirimler,
            "son_fiyat": self.son_fiyat,
            "saglik": self.saglik,
            "telegram_offset": self.telegram_offset,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        return cls(
            bildirimler=data.get("bildirimler") or {},
            son_fiyat=data.get("son_fiyat") or {},
            saglik=data.get("saglik") or {},
            telegram_offset=data.get("telegram_offset"),
        )


def load_state(path: Path | None = None) -> State:
    return State.from_dict(read_json(path or config.STATE_FILE, {}))


def save_state(state: State, path: Path | None = None) -> None:
    """İçerik değişmediyse dosyaya dokunmaz (boş commit oluşmasın)."""
    path = path or config.STATE_FILE
    new = state.to_dict()
    if read_json(path, None) != new:
        write_json(path, new)
