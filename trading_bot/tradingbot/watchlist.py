"""Ticker-Listen, gespeichert in SQLite.

- "watchlist": die Aktien, die du beobachtest (Basis für Backtest und Signale)
- "scanlist":  zusätzliche Kandidaten, die die Signal-Seite optional mit scannt
"""

import re
from datetime import datetime, timezone

from tradingbot import config
from tradingbot.db import connect

# Erlaubt z. B. "NVDA", "SAP.DE", "BRK-B", "^GDAXI"
TICKER_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-]{0,14}$")

# Listenname -> Standardwerte. Der Name ist zugleich der Tabellenname
# (nur diese festen Namen sind erlaubt, nie Benutzereingaben).
LISTS = {
    "watchlist": config.DEFAULT_WATCHLIST,
    "scanlist": config.DEFAULT_SCANLIST,
}


def normalize_ticker(raw: str) -> str:
    """Macht aus Eingaben wie ' sap.de ' ein sauberes 'SAP.DE' oder wirft ValueError."""
    ticker = raw.strip().upper()
    if not TICKER_RE.match(ticker):
        raise ValueError(f"Ungültiges Ticker-Symbol: '{raw}'")
    return ticker


def _table(name: str) -> str:
    if name not in LISTS:
        raise ValueError(f"Unbekannte Liste: {name}")
    return name


def _seed_if_new(conn, name: str) -> None:
    """Füllt beim allerersten Start die Standardwerte ein (nur einmal)."""
    flag = f"{name}_seeded"
    if conn.execute("SELECT 1 FROM meta WHERE key = ?", (flag,)).fetchone():
        return
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        f"INSERT OR IGNORE INTO {_table(name)} (ticker, added_at) VALUES (?, ?)",
        [(t, now) for t in LISTS[name]],
    )
    conn.execute("INSERT INTO meta (key, value) VALUES (?, '1')", (flag,))


def get_watchlist(db_path=None, name: str = "watchlist") -> list[str]:
    with connect(db_path) as conn:
        _seed_if_new(conn, name)
        rows = conn.execute(f"SELECT ticker FROM {_table(name)} ORDER BY rowid").fetchall()
    return [r[0] for r in rows]


def add_ticker(raw: str, db_path=None, name: str = "watchlist") -> bool:
    """Fügt einen Ticker hinzu. Gibt False zurück, wenn er schon drin war."""
    ticker = normalize_ticker(raw)
    with connect(db_path) as conn:
        _seed_if_new(conn, name)
        cur = conn.execute(
            f"INSERT OR IGNORE INTO {_table(name)} (ticker, added_at) VALUES (?, ?)",
            (ticker, datetime.now(timezone.utc).isoformat()),
        )
        return cur.rowcount == 1


def remove_ticker(ticker: str, db_path=None, name: str = "watchlist") -> None:
    with connect(db_path) as conn:
        _seed_if_new(conn, name)
        conn.execute(f"DELETE FROM {_table(name)} WHERE ticker = ?", (ticker,))


def reset_watchlist(db_path=None, name: str = "watchlist") -> None:
    """Stellt die Standardwerte der Liste wieder her."""
    with connect(db_path) as conn:
        conn.execute(f"DELETE FROM {_table(name)}")
        conn.execute("DELETE FROM meta WHERE key = ?", (f"{name}_seeded",))
        _seed_if_new(conn, name)
