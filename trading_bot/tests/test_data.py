"""Tests für das Daten-Modul – ohne Internet, mit einem Fake-Downloader."""

from datetime import timedelta

import pandas as pd
import pytest

from tests.fakes import DATES, FakeDownloader
from tradingbot import data

def no_lookup(ticker):
    return None


@pytest.fixture
def db(tmp_path):
    return tmp_path / "test.db"


def load(db, dl, tickers=("SAP.DE", "NVDA"), **kw):
    return data.load_prices(list(tickers), "2024-01-01", db_path=db, downloader=dl,
                            currency_lookup=no_lookup, sleep=lambda s: None, **kw)


def test_currency_detection():
    assert data.detect_currency("SAP.DE", no_lookup) == "EUR"
    assert data.detect_currency("NVDA", no_lookup) == "USD"
    assert data.detect_currency("VOD.L", no_lookup) == "GBp"
    assert data.detect_currency("BTC-EUR", no_lookup) == "EUR"
    assert data.detect_currency("BRK-B", no_lookup) == "USD"
    assert data.detect_currency("XYZ.UNKNOWN", no_lookup) is None


def test_usd_and_pence_are_converted_to_eur(db):
    res = load(db, FakeDownloader(), tickers=("SAP.DE", "NVDA", "VOD.L"))
    last = res.prices.iloc[-1]
    assert last["SAP.DE"] == pytest.approx(100.0)
    assert last["NVDA"] == pytest.approx(100.0)   # 110 USD / 1,10
    assert last["VOD.L"] == pytest.approx(100.0)  # 7000 Pence = 70 GBP / 0,70
    assert res.prices_local.iloc[-1]["NVDA"] == pytest.approx(110.0)
    assert res.errors == {}


def test_second_call_uses_cache(db):
    dl = FakeDownloader()
    load(db, dl)
    assert len(dl.calls) == 1
    res = load(db, dl)
    assert len(dl.calls) == 1          # kein neuer Download
    assert res.downloaded == []
    assert len(res.prices) == len(DATES)


def test_force_and_expired_cache_reload(db, monkeypatch):
    dl = FakeDownloader()
    load(db, dl)
    load(db, dl, force=True)
    assert len(dl.calls) == 2
    later = data._now() + timedelta(hours=data.MAX_AGE_HOURS + 1)
    monkeypatch.setattr(data, "_now", lambda: later)
    load(db, dl)
    assert len(dl.calls) == 3


def test_earlier_start_date_triggers_download(db):
    dl = FakeDownloader()
    data.load_prices(["SAP.DE"], "2024-01-05", db_path=db, downloader=dl, currency_lookup=no_lookup)
    load(db, dl, tickers=("SAP.DE",))
    assert len(dl.calls) == 2


def test_rate_limit_is_retried(db):
    waits = []
    dl = FakeDownloader(fail_times=2)
    res = data.load_prices(["SAP.DE"], "2024-01-01", db_path=db, downloader=dl,
                           currency_lookup=no_lookup, sleep=waits.append)
    assert res.errors == {}
    assert waits == list(data.RETRY_WAITS)
    assert len(dl.calls) == 3


def test_permanent_failure_does_not_crash(db):
    res = load(db, FakeDownloader(fail_times=99))
    assert set(res.errors) >= {"SAP.DE", "NVDA"}
    assert "RuntimeError" in res.errors["SAP.DE"]
    assert res.prices.empty


def test_unknown_ticker_reported_others_still_load(db):
    dl = FakeDownloader(missing={"NVDA"})
    res = load(db, dl)
    assert "NVDA" in res.errors
    assert list(res.prices.columns) == ["SAP.DE"]
    # nur das fehlende Symbol wird erneut versucht
    assert dl.calls[1:] == [["NVDA"], ["NVDA"]]


def test_missing_fx_rate_is_an_error(db):
    res = load(db, FakeDownloader(missing={"EURUSD=X"}))
    assert "Wechselkurs" in res.errors["NVDA"]
    assert "SAP.DE" in res.prices.columns


def test_failed_refresh_falls_back_to_cache(db):
    load(db, FakeDownloader())
    res = load(db, FakeDownloader(fail_times=99), force=True)
    assert res.errors == {}
    assert any("gespeicherte Daten" in w for w in res.warnings)
    assert res.prices.iloc[-1]["NVDA"] == pytest.approx(100.0)


def test_fx_uses_only_past_rates():
    """Am 3. Tag fehlt der Wechselkurs -> der vom Vortag wird genommen, nicht der vom Folgetag."""
    idx = pd.bdate_range("2024-01-01", periods=4)
    local = pd.Series([110.0] * 4, index=idx)
    fx = pd.Series([1.10, 1.10, 1.25], index=idx[[0, 1, 3]])
    eur = data.to_eur(local, "USD", fx)
    assert eur.iloc[2] == pytest.approx(100.0)
    assert eur.iloc[3] == pytest.approx(88.0)


def test_cache_status_and_clear(db):
    load(db, FakeDownloader())
    status = data.cache_status(db)
    assert set(status["Ticker"]) == {"SAP.DE", "NVDA", "EURUSD=X"}
    data.clear_cache(db)
    assert data.cache_status(db).empty
