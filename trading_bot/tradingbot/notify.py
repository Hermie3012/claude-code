"""Tägliche E-Mail mit den aktuellen Signalen (gestartet über notify.py).

Versand über Gmail (SMTP). Gmail verlangt dafür ein "App-Passwort" – NICHT
dein normales Passwort. Anleitung im README.

Es werden KEINE Orders ausgeführt – die E-Mail ist nur eine Erinnerung.
"""

import smtplib
import ssl
import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

from tradingbot import config, data
from tradingbot.portfolio import eur, get_state, valuation
from tradingbot.signals import BUY, HOLD, SELL, compute_snapshot, days_since_rebalance, load_settings

CONFIG_PATH = Path(__file__).resolve().parent.parent / "email_config.toml"
PLACEHOLDER = "DEIN"  # Vorlage enthält Platzhalter wie "DEIN_NAME@gmail.com"


class NotifyError(Exception):
    """Fehler mit einer verständlichen Meldung (z. B. falsches Passwort)."""


@dataclass
class EmailConfig:
    sender: str
    app_password: str
    recipient: str
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465


def load_email_config(path: Path = CONFIG_PATH) -> EmailConfig:
    if not path.exists():
        raise NotifyError(
            f"Datei {path.name} fehlt. Kopiere email_config.example.toml nach {path.name} "
            "und trage deine Daten ein (siehe README)."
        )
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise NotifyError(f"{path.name} ist fehlerhaft: {exc}") from exc
    missing = [k for k in ("sender", "app_password", "recipient") if not raw.get(k)]
    if missing:
        raise NotifyError(f"In {path.name} fehlt: {', '.join(missing)}")
    if any(PLACEHOLDER in str(raw[k]) for k in ("sender", "app_password", "recipient")):
        raise NotifyError(f"In {path.name} stehen noch Platzhalter (DEIN_…). Bitte echte Werte eintragen.")
    raw["app_password"] = str(raw["app_password"]).replace(" ", "")  # Google zeigt es mit Leerzeichen an
    known = {k: raw[k] for k in EmailConfig.__dataclass_fields__ if k in raw}
    return EmailConfig(**known)


def _line(ticker: str, row: pd.Series) -> str:
    mom = "–" if pd.isna(row["Momentum"]) else f"{row['Momentum']:+.1%}".replace(".", ",")
    rank = "–" if pd.isna(row["Rang"]) else int(row["Rang"])
    return f"  • {ticker:<10} Rang {rank:>3}   Momentum {mom:>8}"


def build_report(db_path=None) -> tuple[str, str]:
    """Erstellt Betreff und Text der E-Mail."""
    params, use_scan = load_settings(db_path)
    snap = compute_snapshot(params, use_scan, db_path)
    if snap.error:
        return f"Trading-Bot: Signale konnten nicht berechnet werden ({date.today():%d.%m.%Y})", (
            f"{snap.error}\n\n{_errors(snap)}\n\n{config.DISCLAIMER.replace('*', '')}"
        )

    sig = snap.signals
    groups = {s: sig[sig["Signal"] == s] for s in (BUY, SELL, HOLD)}
    days = days_since_rebalance(snap.price_date, db_path)
    due = days is None or days >= params.rebalance_days

    subject = (f"Trading-Bot (Spielgeld) {snap.price_date:%d.%m.%Y}: "
               f"{len(groups[BUY])}× KAUFEN, {len(groups[SELL])}× VERKAUFEN"
               + (" – Anpassung fällig" if due and (len(groups[BUY]) or len(groups[SELL])) else ""))

    lines = [
        "LERNPROJEKT – KEINE ANLAGEBERATUNG. Nur Spielgeld, keine echten Orders.",
        "",
        f"Signale nach Schlusskurs vom {snap.price_date:%d.%m.%Y} "
        f"({len(sig)} Aktien bewertet, Lookback {params.lookback}, Top {params.top_n}"
        + (", nur positives Momentum" if params.only_positive else "") + ")",
        "",
    ]
    for s in (BUY, SELL, HOLD):
        lines.append(f"{s} ({len(groups[s])}):")
        lines += [_line(t, row) for t, row in groups[s].iterrows()] or ["  – keine –"]
        lines.append("")

    if days is None:
        lines.append("Rhythmus: noch keine Anpassung über die Signal-Seite.")
    else:
        lines.append(f"Rhythmus: letzte Anpassung vor {days} Handelstagen, Strategie: alle "
                     f"{params.rebalance_days} → {'Anpassung FÄLLIG' if due else 'noch nicht fällig'}.")
    lines += ["", _depot_summary(snap, db_path), "", _errors(snap),
              "Zum Umsetzen: App starten → Seite 'Signale' → 'Depot an Signale anpassen'.",
              "", config.DISCLAIMER.replace("*", "")]
    return subject, "\n".join(lines).replace("\n\n\n", "\n\n")


def _depot_summary(snap, db_path) -> str:
    state = get_state(db_path)
    prices = snap.loaded.prices.iloc[-1]
    outside = [t for t in state.positions if t not in prices.index]
    if outside:  # Kurse für Depot-Aktien außerhalb von Watchlist/Scan-Liste nachladen
        start = (date.today() - timedelta(days=30)).isoformat()
        extra = data.load_prices(outside, start, db_path=db_path).prices
        if not extra.empty:
            prices = pd.concat([prices, extra.iloc[-1]])
    _, s = valuation(state, prices)
    pct = f"{s['G/V gesamt (%)']:+.2%}".replace(".", ",")
    text = (f"Paper-Depot: Gesamtwert {eur(s['Gesamtwert'])} · Cash {eur(s['Cash'])} · "
            f"Gewinn/Verlust {eur(s['G/V gesamt'], sign=True)} ({pct})")
    if s["missing_prices"]:
        text += f"\n(ohne aktuellen Kurs, mit Einstand bewertet: {', '.join(s['missing_prices'])})"
    return text


def _errors(snap) -> str:
    if snap.loaded is None or not snap.loaded.errors:
        return ""
    return "Ohne Kursdaten (nicht bewertet): " + ", ".join(snap.loaded.errors) + "\n"


def send_email(cfg: EmailConfig, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, cfg.sender, cfg.recipient
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ssl.create_default_context(),
                              timeout=30) as server:
            server.login(cfg.sender, cfg.app_password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise NotifyError(
            "Gmail hat die Anmeldung abgelehnt. Prüfe: (1) Zwei-Faktor-Anmeldung ist aktiv, "
            "(2) du nutzt ein App-Passwort, nicht dein normales Passwort, (3) die Absender-Adresse stimmt."
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise NotifyError(f"E-Mail konnte nicht gesendet werden: {type(exc).__name__}: {exc}") from exc
