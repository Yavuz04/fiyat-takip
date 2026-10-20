"""Komut satırı / CLI.

Örnekler:
  python -m fiyatbot --dry-run                    # tüm aktif ürünler, tüm siteler, bildirim yok
  python -m fiyatbot --dry-run --site trendyol    # tek site
  python -m fiyatbot --dry-run --urun 1 -v        # tek ürün, ayrıntılı log
  python -m fiyatbot                              # gerçek çalışma: komutlar + tarama + bildirim + durum kaydı
  python -m fiyatbot --profil ev                  # PC görevi: sadece GitHub'ı engelleyen siteler
  python -m fiyatbot --chat-id-bul                # bota yazdıktan sonra chat_id'ni gösterir
  python -m fiyatbot --telegram-test              # .env ayarlarıyla deneme mesajı gönderir
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import config, runner
from .messages import esc, format_time
from .notifier import make_notifier
from .runner import RunOptions
from .telegram import Telegram

log = logging.getLogger("fiyatbot")


def find_chat_id() -> int:
    updates = Telegram(config.TELEGRAM_BOT_TOKEN, "").get_updates()
    chats = {(u["message"]["chat"]["id"], u["message"]["chat"].get("first_name") or u["message"]["chat"].get("title"))
             for u in updates if "message" in u}
    if not chats:
        print("Mesaj bulunamadı. Telegram'da botuna /start yaz ve tekrar dene.")
        return 1
    for chat_id, name in chats:
        print(f"chat_id = {chat_id}   ({name})")
    print("Bu değeri .env içindeki TELEGRAM_CHAT_ID'ye yaz.")
    return 0


def run(args) -> int:
    profil = args.profil or ("bulut" if config.IS_CI else "hepsi")
    config.use_profile(profil)
    options = RunOptions(dry_run=args.dry_run, sites=args.site, urun_ids=args.urun,
                         enrich=not args.no_enrich, commands=not args.no_commands, profil=profil)
    telegram = None
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        telegram = Telegram(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    elif not args.dry_run:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanımlı değil (.env veya GitHub Secrets)")
        return 2
    runner.run(options, make_notifier(args.dry_run), telegram=telegram)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fiyatbot", description="Fiyat takip botu")
    parser.add_argument("--dry-run", action="store_true", help="bildirim gönderme, ekrana bas")
    parser.add_argument("--site", action="append", help="sadece bu site(ler) (tekrarlanabilir)")
    parser.add_argument("--urun", type=int, action="append", help="sadece bu ürün id(leri)")
    parser.add_argument("--no-enrich", action="store_true", help="detay sayfalarını açma")
    parser.add_argument("--no-commands", action="store_true", help="Telegram komutlarını işleme")
    parser.add_argument("--profil", choices=config.PROFILES,
                        help="bulut: GitHub'da çalışan siteler (Actions'ta varsayılan); "
                             "ev: GitHub'ı engelleyen siteler, ayrı durum dosyası, komut yok (PC görevi); "
                             "hepsi: tüm siteler (yerelde varsayılan)")
    parser.add_argument("--chat-id-bul", action="store_true", help="bota gelen mesajlardan chat_id'yi göster")
    parser.add_argument("--telegram-test", action="store_true", help="deneme mesajı gönder")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("curl_cffi").setLevel(logging.WARNING)

    if args.chat_id_bul:
        return find_chat_id()
    if args.telegram_test:
        make_notifier(dry_run=False).send(f"✅ Fiyat botu bağlantı testi · {esc(format_time())}")
        print("Deneme mesajı gönderildi.")
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
