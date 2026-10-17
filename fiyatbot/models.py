"""Veri modelleri / Data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

# Garanti türleri / Warranty types
GARANTI_TR = "tr"                # Türkiye / distribütör garantili
GARANTI_ITHALATCI = "ithalatci"  # İthalatçı garantili
GARANTI_YURTDISI = "yurtdisi"    # Yurt dışı / global versiyon
GARANTI_BILINMIYOR = "bilinmiyor"

GARANTI_ETIKET = {
    GARANTI_TR: "Türkiye garantili",
    GARANTI_ITHALATCI: "İthalatçı garantili",
    GARANTI_YURTDISI: "Yurt dışı",
    GARANTI_BILINMIYOR: "Bilinmiyor",
}


@dataclass
class TakipKaydi:
    """Takip listesindeki bir ürün / A tracked product."""

    id: int
    sorgu: str                                       # sitelerde aranacak metin
    max_fiyat: float                                 # bildirim eşiği
    min_fiyat: float = 0.0                           # altı aksesuar/alakasız sayılır
    gerekli: list[str] = field(default_factory=list)  # hepsi başlıkta geçmeli
    haric: list[str] = field(default_factory=list)    # biri bile geçerse elenir
    aktif: bool = True
    siteler: list[str] | None = None                 # None → tüm siteler
    garanti: str = "hepsi"                           # "hepsi" | "tr" (sadece TR garantili / bilinmeyen)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TakipKaydi":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Teklif:
    """Bir sitede bulunan tek bir ürün teklifi / A single offer from a site."""

    site: str
    baslik: str
    url: str
    fiyat: float | None                  # peşin ödenecek fiyat (indirimli fiyat dahil, sepet hariç)
    sepet_fiyati: float | None = None     # "sepette X TL" fiyatı
    eski_fiyat: float | None = None       # üstü çizili fiyat
    satici: str | None = None
    satici_puani: float | None = None
    garanti: str = GARANTI_BILINMIYOR
    stokta: bool | None = None            # None → bilinmiyor (elenmez)

    @property
    def etkin_fiyat(self) -> float | None:
        """Gerçekte ödenecek en düşük fiyat (sepet indirimi dahil)."""
        prices = [p for p in (self.fiyat, self.sepet_fiyati) if p]
        return min(prices) if prices else None

    @property
    def indirim_orani(self) -> float | None:
        """Eski fiyata göre yüzde indirim (ör. 12.5)."""
        if self.eski_fiyat and self.etkin_fiyat and self.eski_fiyat > self.etkin_fiyat:
            return round((1 - self.etkin_fiyat / self.eski_fiyat) * 100, 1)
        return None

    @property
    def anahtar(self) -> str:
        """Spam önleme için ilan kimliği: site + ilan linki.

        Satıcı adı bilerek anahtara girmez: detay sayfası bazen alınamaz (satıcı None olur) ve
        karşılaştırma sitelerinde "17 fiyat arasında en ucuz" metni değişir — anahtar oynarsa aynı
        ilan tekrar tekrar bildirilirdi. Satıcıyı zaten link belirler (ör. Trendyol'da merchantId).
        """
        return f"{self.site}|{self.url.split('#')[0]}"
