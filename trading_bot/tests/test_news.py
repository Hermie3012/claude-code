"""Tests für die Nachrichten – mit erfundenen Yahoo-Antworten."""

from datetime import timedelta

import pandas as pd
import pytest

from tradingbot import news


def item(nid, title, hours_ago, tickers=(), fmt="new"):
    """Erzeugt einen Eintrag im Yahoo-Format (neu oder alt)."""
    published = pd.Timestamp(news._now()) - timedelta(hours=hours_ago)
    if fmt == "old":
        return {"uuid": nid, "title": title, "publisher": "Alt-Verlag", "link": f"https://x/{nid}",
                "providerPublishTime": int(published.timestamp()), "relatedTickers": list(tickers)}
    return {"id": nid, "content": {
        "title": title, "summary": "<p>Kurz  und   knapp</p>", "pubDate": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": {"displayName": "Reuters"}, "canonicalUrl": {"url": f"https://x/{nid}"},
        "finance": {"stockTickers": [{"symbol": t} for t in tickers]},
    }}


class FakeFetcher:
    def __init__(self, feeds, fail=()):
        self.feeds, self.fail, self.calls = feeds, set(fail), []

    def __call__(self, ticker):
        self.calls.append(ticker)
        if ticker in self.fail:
            raise RuntimeError("Too Many Requests")
        return self.feeds.get(ticker, [])


@pytest.fixture
def db(tmp_path):
    return tmp_path / "test.db"


def refresh(db, fetcher, tickers, **kw):
    return news.refresh_news(tickers, db_path=db, fetcher=fetcher, sleep=lambda s: None, **kw)


def test_parse_both_formats():
    new = news.parse_item(item("a", "Neu", 1, ["NVDA"]))
    assert new["summary"] == "Kurz und knapp" and new["publisher"] == "Reuters"
    assert new["url"] == "https://x/a" and '"NVDA"' in new["related"]
    old = news.parse_item(item("b", "Alt", 1, ["SAP.DE"], fmt="old"))
    assert old["id"] == "b" and old["publisher"] == "Alt-Verlag" and '"SAP.DE"' in old["related"]
    assert news.parse_item({"content": {"title": ""}}) is None          # kaputte Einträge ignorieren


def test_same_news_from_two_feeds_is_merged(db):
    shared = item("x", "Chips gefragt", 2)
    fetcher = FakeFetcher({"NVDA": [shared], "AMD": [shared, item("y", "Nur AMD", 3)]})
    assert refresh(db, fetcher, ["NVDA", "AMD"]) == {}
    df = news.ranked_news({"NVDA": "watchlist", "AMD": "watchlist"}, db_path=db)
    assert len(df) == 2
    assert df.iloc[0]["title"] == "Chips gefragt" and df.iloc[0]["affected"] == ["AMD", "NVDA"]


def test_related_tickers_count_as_affected(db):
    fetcher = FakeFetcher({"NVDA": [item("x", "Deal", 1, ["NVDA", "MSFT", "OTHER"])]})
    refresh(db, fetcher, ["NVDA"])
    df = news.ranked_news({"NVDA": "watchlist", "MSFT": "scanlist"}, db_path=db)
    assert df.iloc[0]["affected"] == ["NVDA", "MSFT"]                 # OTHER ist nicht in deinen Listen


def test_ranking_prefers_depot_and_fresh_news(db):
    fetcher = FakeFetcher({
        "SAP.DE": [item("depot", "Depot-News", 5)],
        "NVDA": [item("watch", "Watchlist-News", 5)],
        "BAS.DE": [item("scan", "Scan-News", 1)],
        "IFX.DE": [item("old", "Alte Depot-News", 60)],
    })
    refresh(db, fetcher, ["SAP.DE", "NVDA", "BAS.DE", "IFX.DE"])
    roles = news.build_roles(depot=["SAP.DE", "IFX.DE"], watchlist=["NVDA", "SAP.DE"], scanlist=["BAS.DE"], market=False)
    assert roles["SAP.DE"] == "depot"                                  # Depot schlägt Watchlist
    df = news.ranked_news(roles, days=3, db_path=db)
    assert list(df["id"]) == ["depot", "watch", "scan", "old"]
    assert list(news.ranked_news(roles, days=1, db_path=db)["id"]) == ["depot", "watch", "scan"]


def test_cache_and_force(db):
    fetcher = FakeFetcher({"NVDA": [item("a", "A", 1)]})
    refresh(db, fetcher, ["NVDA"])
    refresh(db, fetcher, ["NVDA"])
    assert fetcher.calls == ["NVDA"]                                    # zweites Mal aus dem Cache
    refresh(db, fetcher, ["NVDA"], force=True)
    assert fetcher.calls == ["NVDA", "NVDA"]


def test_errors_are_reported_and_retried(db):
    fetcher = FakeFetcher({"SAP.DE": [item("a", "A", 1)]}, fail={"NVDA"})
    errors = refresh(db, fetcher, ["NVDA", "SAP.DE"])
    assert "Too Many Requests" in errors["NVDA"]
    assert fetcher.calls.count("NVDA") == 1 + len(news.RETRY_WAITS)
    assert len(news.ranked_news({"SAP.DE": "depot"}, db_path=db)) == 1  # andere Ticker trotzdem geladen
    fetcher.fail.clear()
    refresh(db, fetcher, ["NVDA"])
    assert fetcher.calls[-1] == "NVDA"                                  # fehlgeschlagene Ticker gelten als veraltet


def test_old_news_are_deleted(db):
    refresh(db, FakeFetcher({"NVDA": [item("alt", "Alt", 24 * 40), item("neu", "Neu", 1)]}), ["NVDA"])
    df = news.ranked_news({"NVDA": "watchlist"}, days=365, db_path=db)
    assert list(df["id"]) == ["neu"]


def test_market_symbols(db):
    roles = news.build_roles([], [], [], market=True)
    assert set(roles) == set(news.MARKET_SYMBOLS) and set(roles.values()) == {"market"}
    assert news.ranked_news({}, db_path=db).empty
