"""Börsennachrichten von Yahoo Finance: laden, zwischenspeichern, nach Wichtigkeit sortieren.

Yahoo liefert zu jedem Ticker die neuesten Nachrichten. Dieselbe Nachricht
taucht oft bei mehreren Aktien auf – wir speichern sie einmal und merken uns
alle betroffenen Aktien.

Wichtigkeit (score) einer Nachricht:
    Summe der Gewichte aller betroffenen Aktien (Depot 3, Watchlist 2,
    Gesamtmarkt 2, Scan-Liste 1) × Alterungsfaktor (nach 24 h nur noch halb so viel).
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

import pandas as pd

from tradingbot.db import connect

MAX_AGE_HOURS = 2         # so lange gelten gespeicherte Nachrichten als aktuell
REQUEST_PAUSE = 0.3       # Sekunden Pause zwischen zwei Tickern (schont das Rate-Limit)
RETRY_WAITS = (2, 5)      # Pausen vor dem 2. und 3. Versuch
KEEP_DAYS = 30            # ältere Nachrichten werden gelöscht
HALF_LIFE_HOURS = 24

MARKET_SYMBOLS = {"^GDAXI": "DAX", "^GSPC": "S&P 500"}
ROLE_WEIGHTS = {"depot": 3, "watchlist": 2, "market": 2, "scanlist": 1}
ROLE_LABELS = {"depot": "Depot", "watchlist": "Watchlist", "market": "Gesamtmarkt", "scanlist": "Scan-Liste"}

Fetcher = Callable[[str], list[dict]]


def yfinance_fetcher(ticker: str) -> list[dict]:
    import yfinance as yf

    return yf.Ticker(ticker).get_news(count=20) or []


# ---------------------------------------------------------------- Rohdaten lesen

def _clean(text: str) -> str:
    """Entfernt HTML-Reste und überflüssige Leerzeichen."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def parse_item(raw: dict) -> dict | None:
    """Macht aus einem Yahoo-Eintrag ein einheitliches dict (neues und altes Format)."""
    c = raw.get("content") if isinstance(raw.get("content"), dict) else raw
    title = _clean(c.get("title", ""))
    if not title:
        return None

    if c.get("pubDate"):
        published = pd.Timestamp(c["pubDate"])
    elif raw.get("providerPublishTime"):
        published = pd.Timestamp(raw["providerPublishTime"], unit="s")
    else:
        return None
    published = published.tz_localize("UTC") if published.tzinfo is None else published.tz_convert("UTC")

    url = ((c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url")
           or raw.get("link") or "")
    related = raw.get("relatedTickers") or [
        s.get("symbol") for s in ((c.get("finance") or {}).get("stockTickers") or []) if s.get("symbol")
    ]
    return {
        "id": str(raw.get("id") or raw.get("uuid") or c.get("id") or url or title),
        "title": title,
        "summary": _clean(c.get("summary") or c.get("description") or ""),
        "publisher": (c.get("provider") or {}).get("displayName") or raw.get("publisher") or "",
        "url": url,
        "published_at": published.isoformat(),
        "related": json.dumps(sorted(set(related))),
    }


# ---------------------------------------------------------------- Laden & Cache

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stale(conn, ticker: str, force: bool) -> bool:
    row = conn.execute("SELECT fetched_at FROM news_fetch WHERE ticker = ?", (ticker,)).fetchone()
    return force or row is None or _now() - datetime.fromisoformat(row[0]) > timedelta(hours=MAX_AGE_HOURS)


def _fetch_with_retry(ticker, fetcher, sleep) -> list[dict]:
    for attempt in range(len(RETRY_WAITS) + 1):
        if attempt:
            sleep(RETRY_WAITS[attempt - 1])
        try:
            return fetcher(ticker)
        except Exception as exc:  # z. B. Rate-Limit oder kein Internet
            error = exc
    raise error


def refresh_news(tickers: list[str], force: bool = False, db_path=None,
                 fetcher: Fetcher = yfinance_fetcher, sleep=time.sleep) -> dict[str, str]:
    """Lädt Nachrichten für veraltete Ticker nach. Gibt Fehler je Ticker zurück."""
    errors: dict[str, str] = {}
    with connect(db_path) as conn:
        todo = [t for t in tickers if _stale(conn, t, force)]
        for i, t in enumerate(todo):
            if i:
                sleep(REQUEST_PAUSE)
            try:
                raw_items = _fetch_with_retry(t, fetcher, sleep)
            except Exception as exc:
                errors[t] = f"{type(exc).__name__}: {exc}"
                continue
            for item in filter(None, map(parse_item, raw_items)):
                conn.execute(
                    "INSERT OR REPLACE INTO news (id, title, summary, publisher, url, published_at, related) "
                    "VALUES (:id, :title, :summary, :publisher, :url, :published_at, :related)", item)
                conn.execute("INSERT OR IGNORE INTO news_links (news_id, ticker) VALUES (?, ?)", (item["id"], t))
            conn.execute("INSERT OR REPLACE INTO news_fetch (ticker, fetched_at) VALUES (?, ?)",
                         (t, _now().isoformat()))
            conn.commit()  # Zwischenstand sichern, falls später etwas abbricht

        cutoff = (_now() - timedelta(days=KEEP_DAYS)).isoformat()
        conn.execute("DELETE FROM news_links WHERE news_id IN (SELECT id FROM news WHERE published_at < ?)", (cutoff,))
        conn.execute("DELETE FROM news WHERE published_at < ?", (cutoff,))
    return errors


# ---------------------------------------------------------------- Auswerten

def ranked_news(roles: dict[str, str], days: int = 3, db_path=None) -> pd.DataFrame:
    """Nachrichten der letzten `days` Tage zu den Tickern in `roles`, wichtigste zuerst.

    roles: Ticker -> "depot" | "watchlist" | "scanlist" | "market"
    """
    columns = ["id", "title", "summary", "publisher", "url", "published", "affected", "score"]
    if not roles:
        return pd.DataFrame(columns=columns)
    marks = ",".join("?" * len(roles))
    cutoff = (_now() - timedelta(days=days)).isoformat()
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""SELECT n.id, n.title, n.summary, n.publisher, n.url, n.published_at, n.related,
                       GROUP_CONCAT(l.ticker)
                FROM news n JOIN news_links l ON l.news_id = n.id
                WHERE l.ticker IN ({marks}) AND n.published_at >= ?
                GROUP BY n.id""",
            [*roles, cutoff],
        ).fetchall()

    now = pd.Timestamp(_now())
    records = []
    for nid, title, summary, publisher, url, published_at, related, linked in rows:
        mentioned = set(linked.split(",")) | set(json.loads(related or "[]"))
        affected = sorted((t for t in mentioned if t in roles),
                          key=lambda t: (-ROLE_WEIGHTS[roles[t]], t))
        published = pd.Timestamp(published_at)
        age_hours = max((now - published).total_seconds() / 3600, 0)
        weight = sum(ROLE_WEIGHTS[roles[t]] for t in affected)
        records.append({
            "id": nid, "title": title, "summary": summary, "publisher": publisher, "url": url,
            "published": published, "affected": affected,
            "score": weight * 0.5 ** (age_hours / HALF_LIFE_HOURS),
        })
    df = pd.DataFrame(records, columns=columns)
    return df.sort_values(["score", "published"], ascending=False, ignore_index=True)


def build_roles(depot: list[str], watchlist: list[str], scanlist: list[str], market: bool) -> dict[str, str]:
    """Ticker -> wichtigste Rolle (Depot schlägt Watchlist schlägt Scan-Liste)."""
    roles: dict[str, str] = {}
    for role, tickers in [("scanlist", scanlist), ("watchlist", watchlist), ("depot", depot)]:
        roles.update({t: role for t in tickers})
    if market:
        roles.update({t: "market" for t in MARKET_SYMBOLS})
    return roles
