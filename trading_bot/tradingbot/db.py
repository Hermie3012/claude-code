"""SQLite-Datenbank: eine einzige lokale Datei (data/trading_bot.db).

Tabellen:
- watchlist:   die beobachteten Ticker
- prices:      Schlusskurse je Ticker und Tag (in Originalwährung)
- fetch_log:   wann und ab welchem Datum ein Ticker zuletzt geladen wurde
- ticker_info: Währung je Ticker
- orders:      alle virtuellen Orders des Paper-Depots
- meta:        sonstige Einstellungen (z. B. "Watchlist wurde schon befüllt")
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from tradingbot import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    ticker   TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    close  REAL NOT NULL,
    PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS fetch_log (
    ticker       TEXT PRIMARY KEY,
    fetched_from TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticker_info (
    ticker   TEXT PRIMARY KEY,
    currency TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,      -- wann die Order aufgegeben wurde (UTC)
    ticker     TEXT NOT NULL,
    side       TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    shares     INTEGER NOT NULL CHECK (shares > 0),
    price      REAL NOT NULL,      -- Ausführungskurs in EUR
    price_date TEXT NOT NULL,      -- Datum des verwendeten Schlusskurses
    fee        REAL NOT NULL,
    note       TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def connect(db_path: str | Path | None = None):
    """Öffnet die Datenbank, legt fehlende Tabellen an und speichert am Ende.

    Verwendung:
        with connect() as conn:
            conn.execute(...)
    """
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()
