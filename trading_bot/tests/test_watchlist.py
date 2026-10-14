import pytest

from tradingbot import config
from tradingbot.watchlist import add_ticker, get_watchlist, normalize_ticker, remove_ticker, reset_watchlist


@pytest.fixture
def db(tmp_path):
    return tmp_path / "test.db"


def test_first_start_uses_default_watchlist(db):
    assert get_watchlist(db) == config.DEFAULT_WATCHLIST


def test_add_and_remove(db):
    assert add_ticker(" tsla ", db) is True
    assert add_ticker("TSLA", db) is False  # schon vorhanden
    assert "TSLA" in get_watchlist(db)
    remove_ticker("TSLA", db)
    assert "TSLA" not in get_watchlist(db)


def test_empty_watchlist_stays_empty(db):
    for t in get_watchlist(db):
        remove_ticker(t, db)
    assert get_watchlist(db) == []  # Standardliste kommt NICHT ungefragt zurück
    reset_watchlist(db)
    assert get_watchlist(db) == config.DEFAULT_WATCHLIST


@pytest.mark.parametrize("raw", ["", "  ", "SAP DE", "x" * 20, "DROP;TABLE"])
def test_invalid_tickers_are_rejected(raw):
    with pytest.raises(ValueError):
        normalize_ticker(raw)


@pytest.mark.parametrize("raw,expected", [("sap.de", "SAP.DE"), ("brk-b", "BRK-B"), ("^gdaxi", "^GDAXI")])
def test_valid_tickers(raw, expected):
    assert normalize_ticker(raw) == expected
