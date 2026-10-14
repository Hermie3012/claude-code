"""Tägliche Signal-E-Mail verschicken.

    python notify.py             # Signale berechnen und E-Mail senden
    python notify.py --dry-run   # nur anzeigen, nichts senden (zum Testen)

Für den täglichen automatischen Start siehe README ("Tägliche E-Mail").
Jeder Lauf wird in data/notify.log protokolliert.
"""

import argparse
import logging
import sys
from pathlib import Path

# Damit das Skript auch aus einem anderen Ordner (z. B. per Aufgabenplanung) startet
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tradingbot import config  # noqa: E402
from tradingbot.notify import NotifyError, build_report, load_email_config, send_email  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tägliche Signal-E-Mail (Lernprojekt, Spielgeld)")
    parser.add_argument("--dry-run", action="store_true", help="E-Mail nur anzeigen, nicht senden")
    args = parser.parse_args(argv)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("notify")
    log.setLevel(logging.INFO)
    handler = logging.FileHandler(config.DATA_DIR / "notify.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    try:
        email_cfg = None if args.dry_run else load_email_config()
        subject, body = build_report()
        if args.dry_run:
            print(f"Betreff: {subject}\n\n{body}\n\n(--dry-run: nichts gesendet)")
        else:
            send_email(email_cfg, subject, body)
            print(f"E-Mail gesendet an {email_cfg.recipient}: {subject}")
        log.info("ok%s: %s", " (dry-run)" if args.dry_run else "", subject)
        return 0
    except NotifyError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        log.error("%s", exc)
        return 1
    except Exception:
        log.exception("Unerwarteter Fehler")
        raise
    finally:
        log.removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    sys.exit(main())
