"""PC görevi (Windows Görev Zamanlayıcı ile 25 dk'da bir): GitHub IP'lerini engelleyen siteleri tarar.

Akış:  git pull → python -m fiyatbot --profil ev → (değiştiyse) state-ev/geçmiş-ev commit + push

- Sadece bu iş için ayrılmış bir klonda çalışır (ör. C:\\Users\\MSI\\fiyat-takip-ev); geliştirme
  klasöründeki değişikliklere dokunmaz. Her çalışmada güncel kodu ve takip listesini GitHub'dan alır.
- Sadece data/state-ev.json ve data/price_history-ev.csv commit'lenir; GitHub'daki bot başka dosyalara
  yazdığı için iki tarafın push'ları çakışmaz.
- Aynı anda iki görev çalışmasın diye kilit dosyası kullanılır.
- Çıktı logs/ev-gorevi.log dosyasına yazılır (1 MB'ta döner).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "logs" / "ev-gorevi.lock"
LOG = REPO / "logs" / "ev-gorevi.log"
EV_FILES = ["data/state-ev.json", "data/price_history-ev.csv"]
STALE_LOCK_SECONDS = 30 * 60

log = logging.getLogger("ev-gorevi")


def git(*args: str, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.stdout.strip():
        log.info("git %s: %s", args[0], result.stdout.strip()[-500:])
    if result.returncode != 0 and not quiet:
        log.warning("git %s başarısız: %s", " ".join(args), result.stderr.strip()[-500:])
        if check:
            raise RuntimeError(f"git {args[0]} başarısız")
    return result


def acquire_lock() -> bool:
    LOCK.parent.mkdir(exist_ok=True)
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < STALE_LOCK_SECONDS:
        return False
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def ensure_requirements() -> None:
    """Çekilen kodda requirements.txt değiştiyse paketleri günceller."""
    req = REPO / "requirements.txt"
    stamp = REPO / "logs" / "requirements.installed"
    current = req.read_text(encoding="utf-8")
    if stamp.exists() and stamp.read_text(encoding="utf-8") == current:
        return
    log.info("requirements.txt değişmiş, paketler güncelleniyor")
    result = subprocess.run([str(_python()), "-m", "pip", "install", "-q", "-r", str(req)], cwd=REPO,
                            capture_output=True, text=True, encoding="utf-8",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode == 0:
        stamp.write_text(current, encoding="utf-8")
    else:
        log.warning("pip install başarısız: %s", result.stderr.strip()[-500:])


def _python() -> Path:
    # pythonw ile başlatılsa bile alt süreçler python.exe ile (konsolsuz) çalışır
    exe = Path(sys.executable)
    return exe.with_name("python.exe") if exe.name.lower() == "pythonw.exe" else exe


def run_bot() -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    result = subprocess.run([str(_python()), "-m", "fiyatbot", "--profil", "ev"], cwd=REPO, env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=20 * 60,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in (result.stdout + result.stderr).splitlines():
        log.info("bot | %s", line)
    return result.returncode


def push_state() -> None:
    git("add", "--", *[f for f in EV_FILES if (REPO / f).exists()])
    # diff --quiet: 0 = değişiklik yok, 1 = değişiklik var (hata değil)
    if git("diff", "--cached", "--quiet", check=False, quiet=True).returncode == 0:
        log.info("Durum değişmedi, commit yok.")
        return
    git("commit", "-m", f"ev durum: {datetime.now():%Y-%m-%d %H:%M}")
    for attempt in range(1, 4):
        if git("pull", "--rebase", "--autostash", check=False).returncode == 0 and \
                git("push", check=False).returncode == 0:
            log.info("Push tamam.")
            return
        log.warning("Push başarısız (deneme %d), tekrar denenecek", attempt)
        time.sleep(attempt * 10)
    log.error("Push yapılamadı; bir sonraki çalışmada tekrar denenecek.")


def main() -> int:
    LOG.parent.mkdir(exist_ok=True)
    handler = RotatingFileHandler(LOG, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    if not acquire_lock():
        log.info("Önceki görev hâlâ çalışıyor, atlandı.")
        return 0
    try:
        log.info("===== PC görevi başladı =====")
        if git("pull", "--rebase", "--autostash", check=False).returncode != 0:
            log.warning("git pull yapılamadı (internet yok?); yerel kopya ile devam")
        ensure_requirements()
        code = run_bot()
        log.info("Bot çıkış kodu: %d", code)
        push_state()
        return code
    except Exception:  # noqa: BLE001 — görev zamanlayıcıda sessizce ölmesin, loga yazsın
        log.exception("PC görevi hata verdi")
        return 1
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
