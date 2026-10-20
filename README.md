# Fiyat Takip Botu

Türkiye'deki e-ticaret sitelerinde ürün adına göre arama yapan, sonuçları filtreleyen ve fiyat bütçenin
altına düşünce **Telegram'dan bildirim** gönderen kişisel bir bot. GitHub Actions üzerinde ücretsiz çalışır;
GitHub sunucularını engelleyen siteler için isteğe bağlı olarak kendi bilgisayarında da çalışır.

**Siteler:** Trendyol, Hepsiburada, Amazon.com.tr, n11, PttAVM, Pazarama, Akakçe, Cimri, epey

---

## İçindekiler
1. [Nasıl çalışır](#nasıl-çalışır)
2. [Kurulum](#kurulum)
3. [Telegram komutları](#telegram-komutları)
4. [Filtreleme ve bildirim kuralları](#filtreleme-ve-bildirim-kuralları)
5. [Dosyalar ve durum](#dosyalar-ve-durum)
6. [Yeni site eklemek](#yeni-site-eklemek)
7. [Sorun giderme](#sorun-giderme)
8. [Sınırlar ve bilinmesi gerekenler](#sınırlar-ve-bilinmesi-gerekenler)

---

## Nasıl çalışır

```
  GitHub Actions (25 dk'da bir)              Senin PC'n (açıkken, 25 dk'da bir)
  --profil bulut                             --profil ev  (Görev Zamanlayıcı)
  ─────────────────────────────              ─────────────────────────────────
  1. Telegram komutlarını işle               1. git pull (güncel kod + takip listesi)
  2. Amazon, Hepsiburada, n11'i tara         2. Trendyol, Akakçe, Cimri, PttAVM,
  3. Bildirim gönder                            Pazarama, epey'i tara
  4. data/state.json, price_history.csv      3. Bildirim gönder
     → değiştiyse commit + push              4. data/state-ev.json, price_history-ev.csv
                                                → değiştiyse commit + push
```

**Neden iki taraf?** Trendyol, Akakçe, Cimri, PttAVM, Pazarama ve epey, GitHub'ın veri merkezi IP'lerini
Cloudflare ile engelliyor (`tools/erisim_testi.py` ile ölçüldü). Aynı siteler ev internetinden sorunsuz
çalışıyor. Bot bu engelleri aşmaya çalışmaz; bu siteleri senin bilgisayarından tarar. PC kapalıyken bu
siteler taranmaz, açılınca bot kaldığı yerden devam eder.

- İki taraf **ayrı durum dosyalarına** yazar, bu yüzden aynı anda push etseler bile git çakışması olmaz.
- Telegram komutlarını **sadece GitHub** işler; iki taraf birden mesajları okursa birbirinin komutlarını kaçırır.
- Her site ayrı bir eklentidir (`fiyatbot/scrapers/`). Bir site bozulursa diğerleri çalışmaya devam eder.
- Veri önce sitenin sayfaya gömdüğü JSON'dan (`__NEXT_DATA__` benzeri, JSON-LD, hydration verisi) okunur.
  Gömülü JSON yoksa sitenin kararlı öznitelikleri (`data-testid` vb.) kullanılır.

---

## Kurulum

### 1. Yerel ortam
Python 3.12 gerekir.

```powershell
git clone https://github.com/Yavuz04/fiyat-takip
cd fiyat-takip
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q          # testler
```

### 2. Telegram botu oluştur (BotFather)
1. Telegram'da **@BotFather**'ı aç, `/newbot` yaz.
2. Bir görünen ad ver, sonra sonu `bot` ile biten bir kullanıcı adı ver (ör. `benim_fiyat_bot`).
3. BotFather şu mesajı verir:
   ```
   Use this token to access the HTTP API:
   7123456789:AAH...uzun-metin...
   ```
   Alttaki satırın tamamı **token**'dır.
4. `.env.example` dosyasını `.env` olarak kopyala, token'ı yapıştır:
   ```
   TELEGRAM_BOT_TOKEN=7123456789:AAH...
   TELEGRAM_CHAT_ID=
   ```
   `.env` git'e girmez (`.gitignore`). **Token'ı asla koda, commit'e ya da bir sohbete yazma.**

### 3. chat_id'ni öğren
1. Telegram'da kendi botunu aç, **Start** (`/start`) bas.
2. Çalıştır:
   ```powershell
   .\.venv\Scripts\python.exe -m fiyatbot --chat-id-bul
   ```
3. Çıkan `chat_id = 123456789` değerini `.env`'deki `TELEGRAM_CHAT_ID=` satırına yaz.
4. Bağlantı testi:
   ```powershell
   .\.venv\Scripts\python.exe -m fiyatbot --telegram-test
   ```

Bot **sadece bu chat_id'den** gelen komutları kabul eder; başkalarının mesajları yok sayılır.

### 4. Yerelde çalıştırma
```powershell
.\.venv\Scripts\python.exe -m fiyatbot --dry-run            # bildirim göndermez, mesajı ekrana basar, dosya yazmaz
.\.venv\Scripts\python.exe -m fiyatbot --dry-run --site trendyol --urun 1 -v
.\.venv\Scripts\python.exe -m fiyatbot                      # gerçek çalışma
```

| Seçenek | Anlamı |
|---|---|
| `--dry-run` | Bildirim gönderme, dosya yazma, Telegram komutlarını "okundu" sayma |
| `--site X` | Sadece bu site (tekrarlanabilir) |
| `--urun N` | Sadece bu takip id'si |
| `--profil bulut\|ev\|hepsi` | Hangi siteler + hangi durum dosyası (yerelde varsayılan `hepsi`) |
| `--no-enrich` | Satıcı/garanti için ürün sayfalarını açma (daha hızlı) |
| `--no-commands` | Telegram komutlarını işleme |

> Yerelde `--profil hepsi` ile gerçek çalışma yaparsan `data/state.json`'a tüm siteler yazılır. Sürekli
> kullanım için GitHub + PC görevini tercih et; yerel gerçek çalışmayı deneme amaçlı kullan.

### 5. GitHub'a kurulum
1. Repoyu oluştur ve gönder (ör. `gh repo create fiyat-takip --public --source . --push`).
2. **Secrets** ekle: Repo → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

   ya da komut satırından (değer stdin'den okunur, ekrana basılmaz):
   ```powershell
   gh secret set TELEGRAM_BOT_TOKEN
   gh secret set TELEGRAM_CHAT_ID
   ```
3. *Actions* sekmesinde **Fiyat takip** workflow'unu aç. İlk denemeyi *Run workflow* ile elle yapabilirsin
   (isteğe bağlı: `dry_run`, tek `site`).

Workflow'lar:

| Dosya | Ne yapar |
|---|---|
| `.github/workflows/fiyat-takip.yml` | 25 dk'da bir botu çalıştırır, durum değiştiyse commit'ler |
| `.github/workflows/testler.yml` | Kod değişince testleri çalıştırır (botun durum commit'leri tetiklemez) |
| `.github/workflows/erisim-testi.yml` | Elle: sitelerin GitHub IP'lerinden açılıp açılmadığını raporlar |

### 6. PC görevi (GitHub'ı engelleyen siteler için)
```powershell
powershell -ExecutionPolicy Bypass -File tools\ev_gorevi_kur.ps1
```
Bu betik:
- `%USERPROFILE%\fiyat-takip-ev` klasörüne **ayrı bir klon** açar. Geliştirme klasöründeki değişikliklere
  dokunmaz ve henüz göndermediğin commit'leri push etmez.
- `.env`'i oraya kopyalar ve klona özel bir sanal ortam kurar.
- Windows Görev Zamanlayıcı'ya **FiyatTakipBot** görevini ekler: 25 dk'da bir ve oturum açılınca çalışır,
  sadece oturum açıkken çalışır (şifre gerekmez), pencere açmaz, kaçırılan çalışmayı PC açılınca yapar.

| İşlem | Komut |
|---|---|
| Log | `%USERPROFILE%\fiyat-takip-ev\logs\ev-gorevi.log` |
| Hemen çalıştır | `Start-ScheduledTask -TaskName FiyatTakipBot` |
| Geçici durdur | Görev Zamanlayıcı → FiyatTakipBot → Devre Dışı Bırak |
| Kaldır | `Unregister-ScheduledTask -TaskName FiyatTakipBot -Confirm:$false` |

Görev her çalışmada GitHub'dan güncel kodu çeker; `requirements.txt` değişmişse paketleri kendisi günceller.

**Kaynak kullanımı (2 ürünle, yaklaşık):** çalışma başına 30–60 sn, ~60–80 MB RAM, ~2 MB internet.
PC günde 8 saat açıksa ayda ~1,2 GB. Yük takip edilen ürün sayısıyla doğru orantılıdır.

---

## Telegram komutları

Bot sürekli açık değil: komutlar **bir sonraki çalışmada** (en fazla ~25 dk, GitHub yoğunsa daha geç) işlenir.
Tek mesajda alt alta birden fazla komut yazabilirsin.

| Komut | Örnek | Açıklama |
|---|---|---|
| `/ekle <ad> <max fiyat>` | `/ekle Huawei M-Pencil 3 3000` | Yeni takip. Varsayılanlar otomatik; ilk tarama sonucu + elenen örnekler gösterilir |
| `/liste` | | Tüm takipler ve son görülen en ucuz fiyat |
| `/detay <id>` | `/detay 1` | Bir takibin tüm ayarları |
| `/gecmis <id>` | `/gecmis 1` | En düşük fiyat, site başına son fiyatlar, son değişiklikler |
| `/haric <id> <kelime>` | `/haric 1 kılıf, yedek uç` | Başlıkta geçerse ele. Silmek: `/haric 1 -kılıf` |
| `/gerekli <id> <kelime>` | `/gerekli 1 3 nesil` | Başlıkta mutlaka geçsin. Silmek: `-kelime` |
| `/minfiyat <id> <değer>` | `/minfiyat 1 1500` | Altı aksesuar/alakasız sayılır |
| `/maxfiyat <id> <değer>` | `/maxfiyat 1 2750` | Bildirim eşiği (bütçe) |
| `/garanti <id> tr\|hepsi` | `/garanti 1 tr` | `tr`: ithalatçı / yurt dışı garantilileri ele |
| `/siteler <id> <liste>\|hepsi` | `/siteler 1 trendyol,n11` | Sadece bu sitelerde ara |
| `/durdur <id>` / `/devam <id>` | | Takibi duraklat / devam ettir |
| `/sil <id>` | | Takibi sil |
| `/yardim` | | Komut listesi |

**`/ekle` varsayılanları:**
- *gerekli:* sorgudan türetilir. "iPhone 15 128GB" → `iphone 15`, `128 gb`; "MatePad 11.5 S" → `matepad 11 5 s`.
- *hariç:* aksesuar, yenilenmiş, ikinci el ve teşhir kelimeleri. Ayrıca sorguda **geçmeyen** model
  varyantları (pro, plus, max, mini, ultra…) eklenir; "iPhone 15" aramasında "pro" elenir,
  "iPhone 15 Pro" aramasında elenmez.
- *min fiyat:* max fiyatın %40'ı.

---

## Filtreleme ve bildirim kuralları

**Metin eşleştirme**
- Türkçe uyumlu normalizasyon: `KILIF` = `kılıf` = `kilif`, `128 GB` = `128GB` = `128gb`
  (Python'un `.lower()` / `.casefold()` fonksiyonları Türkçe İ/ı'yı yanlış işler, kullanılmaz).
- Kelime sınırlarına bakılır: `15` ile `150` eşleşmez, `cam` ile `camera` eşleşmez.
- 5 harf ve üstü kelimeler Türkçe ekleri yakalar: `kılıf` → `kılıflı`, `kılıfı`.

**Fiyat**
- Türk biçimi doğru okunur: `25.999,00 TL`, `25.999 TL`, `₺25.999`, `1.299,90`.
- Peşin fiyat ve **sepet fiyatı** ayrı tutulur. Bütçe kontrolünde ödenecek en düşük fiyat (sepet dahil)
  kullanılır; mesajda "🛒 Sepette X TL" ayrıca yazılır.
- **Taksit tutarı, kuponlu fiyat** (kupon tıklaması gerekir), üyelik fiyatı (TY Plus) ve takas indirimi fiyat sayılmaz.
- Stokta olmayanlar elenir.

**Garanti:** Başlıktan veya (Trendyol'da) ürün sayfasından okunur: Türkiye/distribütör, ithalatçı, yurt dışı.
Mesajda gösterilir; `/garanti <id> tr` ile filtrelenebilir.

**Spam önleme**
- Bir ilan bütçe altına **ilk kez** düşünce bildirilir (🆕).
- Tekrar bildirim için **son bildirilen** fiyata göre en az **%1 veya 100 TL** (hangisi büyükse) düşmesi gerekir (📉).
- Bütçe üstüne çıkıp tekrar düşen ilan yeniden bildirilir.
- O çalışmada hata veren sitenin kayıtları silinmez; site düzelince her şey yeniden bildirilmez.
- Bir ürünün uygun teklifleri **tek mesajda**, ucuzdan pahalıya, en fazla 10 tane listelenir.

**Site sağlığı**
- Bir site art arda **3 çalışma** boyunca hata verir, engellenir ya da hiç sonuç döndürmezse **tek** uyarı
  gelir ("bot engeli" ya da "site yapısı değişmiş olabilir"). Düzelince **tek** "tekrar çalışıyor" mesajı gelir.
- Uyarı almış bir site her çalışmada değil, ~2 saatte bir denenir (bozuk site çalışmaları yavaşlatmasın).
- Ayrıştırılamayan sayfa `debug/` klasörüne kaydedilir; Actions'ta 7 gün saklanan artifact olarak indirilebilir.

---

## Dosyalar ve durum

GitHub Actions her çalışmada sıfırdan başlar; hatırlanması gereken her şey repodaki dosyalarda tutulur.

| Dosya | İçerik | Yazan |
|---|---|---|
| `data/watchlist.json` | Takip listesi (elle de düzenlenebilir) | Telegram komutları (GitHub) |
| `data/state.json` | Bildirilen fiyatlar, site sağlığı, Telegram offset'i | GitHub |
| `data/price_history.csv` | Fiyat geçmişi (sadece değişince, 90 gün) | GitHub |
| `data/state-ev.json`, `data/price_history-ev.csv` | Aynısı, PC siteleri için | PC görevi |

İçerik değişmediyse dosyalara dokunulmaz, bu yüzden boş commit oluşmaz. Workflow'da `concurrency`
ayarı aynı anda iki GitHub çalışması olmasını engeller.

**Kod yapısı**
```
fiyatbot/
  __main__.py      CLI
  runner.py        bir çalışmanın orkestrasyonu
  scanner.py       bir ürünü tüm sitelerde tara + filtrele
  scrapers/        site eklentileri (base.py arayüz, her site ayrı dosya)
  text.py          Türkçe normalizasyon
  price.py         fiyat ayrıştırma, taksit tespiti
  matching.py      filtreler, garanti tespiti, /ekle varsayılanları
  notify_policy.py spam önleme
  health.py        site sağlığı
  history.py       fiyat geçmişi
  commands.py      Telegram komutları
  telegram.py      Bot API istemcisi
  messages.py      mesaj şablonları (HTML, kaçışlı)
  http.py          oturum, yeniden deneme, bot engeli tespiti
tools/
  ev_gorevi.py         PC görevi
  ev_gorevi_kur.ps1    PC görevi kurulumu
  erisim_testi.py      sitelerin erişilebilirlik testi
tests/               kaydedilmiş gerçek sayfalarla testler (tests/fixtures/<site>/)
```

---

## Yeni site eklemek

1. `fiyatbot/scrapers/<site>.py` oluştur:
   ```python
   class YeniSite(Scraper):
       name = "yenisite"          # /siteler komutunda ve loglarda kullanılır
       label = "Yeni Site"        # mesajlarda görünen ad
       enabled_on_ci = True       # GitHub IP'lerini engelliyorsa False → PC görevinde taranır

       def search(self, query: str) -> list[Teklif]:
           return parse_search(self.http.get(f"https://.../ara?q={quote_plus(query)}").text)
   ```
   Kayıt otomatiktir; başka bir dosyaya dokunmak gerekmez. Mesajdaki ad için `messages.SITE_LABELS`'a eklenebilir.
2. **Seçici tahmin etme.** Önce gerçek sayfayı indir; gömülü JSON, JSON-LD ya da sitenin kendi API'si var mı bak.
   Sayfa beklenen yapıda değilse `ParseError` fırlat; sağlık takibi bunu yakalar.
3. Gerçek sayfadan küçültülmüş bir fixture'ı `tests/fixtures/<site>/` altına koy, `tests/test_scrapers.py`'ye test ekle.
4. Erişimi kontrol et: *Actions → Erişim testi → Run workflow*.

---

## Sorun giderme

| Belirti | Olası sebep / çözüm |
|---|---|
| "⚠️ X … bot engeli" uyarısı | Site o IP'yi engelliyor. GitHub'daysa siteyi `enabled_on_ci = False` yapıp PC'ye taşı |
| "⚠️ X … yapısı değişmiş olabilir" | Site tasarımı değişti. `debug/` (Actions artifact) içindeki sayfaya bakıp scraper'ı güncelle |
| Komutlara yanıt gelmiyor | En fazla ~25 dk bekle. Actions'ta son çalışmanın logunda "Telegram mesajı işlendi" satırına bak |
| Beklenen ürün gelmiyor | `/ekle` önizlemesindeki ve `/detay` çıktısındaki gerekli/hariç kelimeleri kontrol et; `--dry-run -v` ile yerelde dene |
| PC görevi çalışmıyor | `logs\ev-gorevi.log`'a bak; `Get-ScheduledTaskInfo -TaskName FiyatTakipBot` |
| Zamanlanmış çalışma durdu | 60 gün kuralı (aşağıda) ya da *Actions*'tan workflow kapatılmış olabilir |

---

## Sınırlar ve bilinmesi gerekenler

- **Zamanlama:** Cron `0,25,50 * * * *` (UTC, ama dakikalar saat diliminden bağımsız). Aralıklar
  25-25-10 dk olur; GitHub yoğunlukta çalışmaları geciktirebilir ya da atlayabilir. Mesajlardaki saatler Türkiye saatidir.
- **Public repo:** Standart runner dakikaları ücretsiz ve sınırsız. Ama **takip listesi, fiyat geçmişi ve
  Actions logları herkese açıktır**. Token ve chat_id sadece GitHub Secrets'tadır. Private repoda ücretsiz
  dakika ayda 2.000'dir; 25 dk aralıkla ayda ~1.700 çalışma × en az 1 dk bu sınırı zorlar.
- **60 gün kuralı:** Public repoda 60 gün aktivite olmazsa zamanlanmış workflow kapanır. Önlem olarak bot
  her gün bir kez (TR 04:00 civarı) workflow'u API ile yeniden etkinleştirir; durum commit'leri de aktivite sayılır.
- **Engeller:** Siteler bot korumalarını değiştirebilir. Bot engelleri aşmaya çalışmaz (proxy, captcha
  çözme vb. yoktur); tespit eder ve bildirir. İstekler kibar aralıklıdır (aynı siteye en az 2 sn) ve kişisel kullanım içindir.
- **Karşılaştırma siteleri** (Akakçe, Cimri, epey) pazaryerlerindeki ilanları tekrar gösterebilir; aynı teklif
  iki kaynaktan gelebilir. epey ürünleri model düzeyinde listeler (hafıza/renk yok).
