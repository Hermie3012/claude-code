"""Watchlist: welche Aktien die App beobachtet. Gespeichert in SQLite."""

import re
from datetime import datetime, timezone

from tradingbot import config
from tradingbot.db import connect

# Erlaubt z. B. "NVDA", "SAP.DE", "BRK-B", "^GDAXI"
TICKER_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-]{0,14}$")


def normalize_ticker(raw: str) -> str:
    """Macht aus Eingaben wie ' sap.de ' ein sauberes 'SAP.DE' oder wirft ValueError."""
    ticker = raw.strip().upper()
    if not TICKER_RE.match(ticker):
        raise ValueError(f"Ungültiges Ticker-Symbol: '{raw}'")
    return ticker


def _seed_if_new(conn) -> None:
    """Füllt beim allerersten Start die Standard-Watchlist ein (nur einmal)."""
    seeded = conn.execute("SELECT 1 FROM meta WHERE key = 'watchlist_seeded'").fetchone()
    if seeded:
        return
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT OR IGNORE INTO watchlist (ticker, added_at) VALUES (?, ?)",
        [(t, now) for t in config.DEFAULT_WATCHLIST],
    )
    conn.execute("INSERT INTO meta (key, value) VALUES ('watchlist_seeded', '1')")


def get_watchlist(db_path=None) -> list[str]:
    with connect(db_path) as conn:
        _seed_if_new(conn)
        rows = conn.execute("SELECT ticker FROM watchlist ORDER BY rowid").fetchall()
    return [r[0] for r in rows]


def add_ticker(raw: str, db_path=None) -> bool:
    """Fügt einen Ticker hinzu. Gibt False zurück, wenn er schon drin war."""
    ticker = normalize_ticker(raw)
    with connect(db_path) as conn:
        _seed_if_new(conn)
        cur = conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, added_at) VALUES (?, ?)",
            (ticker, datetime.now(timezone.utc).isoformat()),
        )
        return cur.rowcount == 1


def remove_ticker(ticker: str, db_path=None) -> None:
    with connect(db_path) as conn:
        _seed_if_new(conn)
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))


def reset_watchlist(db_path=None) -> None:
    """Stellt die Standard-Watchlist aus config.py wieder her."""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM watchlist")
        conn.execute("DELETE FROM meta WHERE key = 'watchlist_seeded'")
        _seed_if_new(conn)
