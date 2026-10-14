"""Kursdaten: von Yahoo Finance laden, in SQLite zwischenspeichern, in Euro umrechnen.

Ablauf von load_prices():
1. Währung jedes Tickers bestimmen (z. B. NVDA -> USD, SAP.DE -> EUR).
2. Prüfen, welche Ticker (und Wechselkurse) im Cache fehlen oder veraltet sind.
3. Nur diese herunterladen, mit Wiederholungen bei Fehlern (z. B. Rate-Limit).
4. Alles aus der Datenbank lesen und in Euro umrechnen.

Warum beim Aktualisieren die ganze Historie neu geladen wird:
Wir nutzen "bereinigte" Kurse (auto_adjust), die Dividenden und Aktiensplits
herausrechnen. Bei jeder Dividende ändert Yahoo dadurch auch ALLE älteren Kurse.
Würden wir nur neue Tage anhängen, entstünde ein künstlicher Kurssprung.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

import pandas as pd

from tradingbot.db import connect

MAX_AGE_HOURS = 12      # so lange gelten gespeicherte Kurse als aktuell
RETRY_WAITS = (2, 5)    # Sekunden Pause vor dem 2. und 3. Versuch

# Börsen-Endung -> Währung. Ticker ohne Endung sind US-Aktien (USD).
SUFFIX_CURRENCY = {
    "DE": "EUR", "F": "EUR", "PA": "EUR", "AS": "EUR", "MI": "EUR", "MC": "EUR",
    "BR": "EUR", "VI": "EUR", "HE": "EUR", "LS": "EUR", "IR": "EUR",
    "L": "GBp",   # London notiert in Pence (1/100 Pfund)
    "SW": "CHF", "TO": "CAD", "T": "JPY", "HK": "HKD",
    "ST": "SEK", "CO": "DKK", "OL": "NOK",
}
KNOWN_CURRENCIES = {"EUR", "USD", "GBP", "CHF", "CAD", "JPY", "HKD", "SEK", "DKK", "NOK"}

# Ein Downloader bekommt Symbole + Startdatum und liefert eine Tabelle mit
# Schlusskursen (Zeilen = Tage, Spalten = Symbole). In Tests wird er ersetzt.
Downloader = Callable[[list[str], str], pd.DataFrame]


@dataclass
class LoadResult:
    prices: pd.DataFrame                # Schlusskurse in EUR (Spalten = Ticker)
    prices_local: pd.DataFrame          # Schlusskurse in Originalwährung
    currencies: dict[str, str]          # Ticker -> Währung
    errors: dict[str, str] = field(default_factory=dict)   # Ticker ohne Daten
    warnings: list[str] = field(default_factory=list)      # z. B. veralteter Cache
    downloaded: list[str] = field(default_factory=list)    # frisch geladene Symbole


# ---------------------------------------------------------------- Download

def yfinance_downloader(symbols: list[str], start: str) -> pd.DataFrame:
    """Lädt bereinigte Schlusskurse von Yahoo Finance.

    Achtung: yf.download wirft bei Fehlern meist KEINE Exception, sondern
    liefert leere Spalten. Deshalb prüft _download_with_retry jede Spalte.
    """
    import yfinance as yf

    data = yf.download(symbols, start=start, auto_adjust=True, progress=False, threads=False)
    if data is None or data.empty:
        return pd.DataFrame()
    close = data["Close"]
    if isinstance(close, pd.Series):  # ältere yfinance-Versionen bei 1 Ticker
        close = close.to_frame(symbols[0])
    return close


def _download_with_retry(symbols, start, downloader, sleep):
    """Lädt Symbole; fehlende werden nach einer Pause erneut versucht.

    Gibt (gefundene Kursreihen, Fehlermeldungen) zurück und stürzt nie ab.
    """
    found: dict[str, pd.Series] = {}
    last_error: dict[str, str] = {}
    remaining = list(symbols)

    for attempt in range(len(RETRY_WAITS) + 1):
        if attempt > 0:
            sleep(RETRY_WAITS[attempt - 1])
        try:
            frame = downloader(remaining, start)
        except Exception as exc:  # z. B. YFRateLimitError oder Netzwerkfehler
            for s in remaining:
                last_error[s] = f"{type(exc).__name__}: {exc}"
            continue

        for s in remaining:
            series = frame[s].dropna() if s in frame.columns else pd.Series(dtype=float)
            if series.empty:
                last_error[s] = "Keine Daten erhalten (Ticker falsch, Rate-Limit oder kein Internet)"
            else:
                found[s] = series
        remaining = [s for s in remaining if s not in found]
        if not remaining:
            break

    return found, {s: last_error[s] for s in remaining}


# ---------------------------------------------------------------- Währungen

def yfinance_currency_lookup(ticker: str) -> str | None:
    """Fragt die Währung bei Yahoo ab (nur für unbekannte Börsen-Endungen)."""
    try:
        import yfinance as yf

        return yf.Ticker(ticker).fast_info["currency"]
    except Exception:
        return None


def detect_currency(ticker: str, lookup=yfinance_currency_lookup) -> str | None:
    if "." in ticker:
        suffix = ticker.rsplit(".", 1)[1]
        return SUFFIX_CURRENCY.get(suffix) or lookup(ticker)
    if "-" in ticker:  # Krypto wie BTC-EUR
        tail = ticker.rsplit("-", 1)[1]
        if tail in KNOWN_CURRENCIES:
            return tail
    if ticker.startswith("^"):  # Indizes: Währung unterschiedlich
        return lookup(ticker)
    return "USD"


def fx_symbol(currency: str) -> str | None:
    """Yahoo-Symbol für den Wechselkurs: EURUSD=X = wie viele USD für 1 EUR."""
    if currency == "EUR":
        return None
    if currency == "GBp":
        return "EURGBP=X"
    return f"EUR{currency}=X"


def to_eur(local: pd.Series, currency: str, fx: pd.Series | None) -> pd.Series:
    """Rechnet eine Kursreihe in Euro um.

    Für jeden Handelstag wird der letzte BEKANNTE Wechselkurs genommen
    (nie einer aus der Zukunft).
    """
    if currency == "EUR":
        return local
    if currency == "GBp":
        local = local / 100  # Pence -> Pfund
    fx_aligned = fx.reindex(fx.index.union(local.index)).ffill().reindex(local.index)
    return local / fx_aligned


# ---------------------------------------------------------------- Cache

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_stale(conn, symbol, start, force, max_age_hours) -> bool:
    row = conn.execute(
        "SELECT fetched_from, fetched_at FROM fetch_log WHERE ticker = ?", (symbol,)
    ).fetchone()
    if force or row is None:
        return True
    fetched_from, fetched_at = row
    if fetched_from > start:  # Cache beginnt später als gewünscht
        return True
    return _now() - datetime.fromisoformat(fetched_at) > timedelta(hours=max_age_hours)


def _store(conn, symbol: str, series: pd.Series, fetched_from: str) -> None:
    rows = [(symbol, pd.Timestamp(d).strftime("%Y-%m-%d"), float(v)) for d, v in series.items()]
    conn.execute("DELETE FROM prices WHERE ticker = ?", (symbol,))
    conn.executemany("INSERT INTO prices (ticker, date, close) VALUES (?, ?, ?)", rows)
    conn.execute(
        "INSERT OR REPLACE INTO fetch_log (ticker, fetched_from, fetched_at) VALUES (?, ?, ?)",
        (symbol, fetched_from, _now().isoformat()),
    )


def _read(conn, symbols: list[str], start: str) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    marks = ",".join("?" * len(symbols))
    df = pd.read_sql_query(
        f"SELECT ticker, date, close FROM prices WHERE ticker IN ({marks}) AND date >= ?",
        conn, params=[*symbols, start],
    )
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    return df.pivot(index="date", columns="ticker", values="close").sort_index()


def _currency(conn, ticker, lookup) -> str | None:
    row = conn.execute("SELECT currency FROM ticker_info WHERE ticker = ?", (ticker,)).fetchone()
    if row:
        return row[0]
    cur = detect_currency(ticker, lookup)
    if cur:
        conn.execute("INSERT INTO ticker_info (ticker, currency) VALUES (?, ?)", (ticker, cur))
    return cur


# ---------------------------------------------------------------- Hauptfunktion

def load_prices(
    tickers: list[str],
    start: str,
    force: bool = False,
    max_age_hours: float = MAX_AGE_HOURS,
    db_path=None,
    downloader: Downloader = yfinance_downloader,
    currency_lookup=yfinance_currency_lookup,
    sleep=time.sleep,
) -> LoadResult:
    """Liefert Schlusskurse ab `start` (Format 'YYYY-MM-DD') in Euro.

    force=True lädt alles neu, auch wenn der Cache noch frisch ist.
    """
    errors: dict[str, str] = {}
    warnings: list[str] = []
    downloaded: list[str] = []

    with connect(db_path) as conn:
        # 1. Währungen
        currencies: dict[str, str] = {}
        for t in tickers:
            cur = _currency(conn, t, currency_lookup)
            if cur:
                currencies[t] = cur
            else:
                errors[t] = "Währung konnte nicht bestimmt werden"

        fx_needed = {fx_symbol(c) for c in currencies.values()} - {None}
        symbols = list(currencies) + sorted(fx_needed)

        # 2. Was muss neu geladen werden? Gruppiert nach Startdatum,
        #    damit möglichst wenige Anfragen an Yahoo gehen.
        groups: dict[str, list[str]] = {}
        for s in symbols:
            if _is_stale(conn, s, start, force, max_age_hours):
                row = conn.execute("SELECT fetched_from FROM fetch_log WHERE ticker = ?", (s,)).fetchone()
                dl_start = min(start, row[0]) if row else start
                groups.setdefault(dl_start, []).append(s)

        # 3. Herunterladen und speichern
        for dl_start, group in groups.items():
            found, failed = _download_with_retry(group, dl_start, downloader, sleep)
            for s, series in found.items():
                _store(conn, s, series, dl_start)
                downloaded.append(s)
            for s, msg in failed.items():
                has_cache = conn.execute("SELECT 1 FROM prices WHERE ticker = ? LIMIT 1", (s,)).fetchone()
                if has_cache:
                    warnings.append(f"{s}: Aktualisierung fehlgeschlagen ({msg}) – nutze gespeicherte Daten.")
                else:
                    errors[s] = msg

        # 4. Aus der Datenbank lesen
        raw = _read(conn, symbols, start)

    # 5. In Euro umrechnen
    local_cols, eur_cols = {}, {}
    for t, cur in currencies.items():
        if t not in raw.columns or raw[t].dropna().empty:
            errors.setdefault(t, "Keine Kursdaten im gewünschten Zeitraum")
            continue
        local = raw[t].dropna()
        fx_sym = fx_symbol(cur)
        fx = raw[fx_sym].dropna() if fx_sym and fx_sym in raw.columns else None
        if fx_sym and (fx is None or fx.empty):
            errors[t] = f"Wechselkurs {fx_sym} fehlt – Umrechnung in EUR nicht möglich"
            continue
        local_cols[t] = local
        eur_cols[t] = to_eur(local, cur, fx)

    # Börsen haben unterschiedliche Feiertage: Lücken mit dem letzten Kurs füllen
    prices = pd.DataFrame(eur_cols).sort_index().ffill()
    prices_local = pd.DataFrame(local_cols).sort_index().ffill()
    return LoadResult(prices, prices_local, currencies, errors, warnings, downloaded)


def cache_status(db_path=None) -> pd.DataFrame:
    """Übersicht für die Oberfläche: was liegt im Cache?"""
    with connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT p.ticker AS Ticker, i.currency AS Währung,
                   MIN(p.date) AS von, MAX(p.date) AS bis, COUNT(*) AS Tage,
                   f.fetched_at AS "geladen am (UTC)"
            FROM prices p
            LEFT JOIN fetch_log f ON f.ticker = p.ticker
            LEFT JOIN ticker_info i ON i.ticker = p.ticker
            GROUP BY p.ticker ORDER BY p.ticker
            """,
            conn,
        )


def clear_cache(db_path=None) -> None:
    """Löscht alle gespeicherten Kurse (die Watchlist bleibt erhalten)."""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM prices")
        conn.execute("DELETE FROM fetch_log")
