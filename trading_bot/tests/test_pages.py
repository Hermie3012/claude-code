"""Klickt sich durch die Daten-Seite – mit Test-Datenbank und Fake-Kursen."""

from functools import partial
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.fakes import FakeDownloader
from tradingbot import config, data

PAGE = str(Path(__file__).resolve().parent.parent / "pages" / "1_Daten.py")


@pytest.fixture
def page(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    fake_load = partial(data.load_prices, downloader=FakeDownloader(missing={"MSFT"}),
                        currency_lookup=lambda t: None, sleep=lambda s: None)
    monkeypatch.setattr(data, "load_prices", fake_load)
    from tradingbot.watchlist import remove_ticker, get_watchlist
    for t in get_watchlist():
        if t not in ("SAP.DE", "NVDA"):
            remove_ticker(t)
    return AppTest.from_file(PAGE, default_timeout=10).run()


def button(at, label):
    return next(b for b in at.button if label in b.label)


def test_page_renders_with_disclaimer(page):
    assert not page.exception
    assert "keine Anlageberatung" in page.warning[0].value


def test_add_ticker_and_load_prices(page):
    page.text_input(key="new_tickers").input("msft, ungültig!")
    button(page, "Hinzufügen").click().run()
    assert any("MSFT hinzugefügt" in s.value for s in page.success)
    assert any("Ungültiges Ticker-Symbol" in e.value for e in page.error)

    button(page, "Kurse laden").click().run()
    assert not page.exception
    table = page.dataframe[0].value
    assert list(table.index) == ["NVDA", "SAP.DE"]  # Reihenfolge wie in der Watchlist
    assert table.loc["NVDA", "Kurs (EUR)"] == pytest.approx(100.0)
    assert any("MSFT" in e.value for e in page.error)   # Fake liefert für MSFT nichts
    assert len(page.get("plotly_chart")) == 1


BACKTEST = str(Path(__file__).resolve().parent.parent / "pages" / "2_Backtest.py")


def test_backtest_page(tmp_path, monkeypatch):
    """Backtest-Seite mit ~1 Jahr erfundener Kurse: Kennzahlen und Charts erscheinen."""
    import numpy as np
    import pandas as pd

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    idx = pd.bdate_range("2023-01-02", periods=300)
    rng = np.random.default_rng(0)

    def downloader(symbols, start):
        cols = {s: 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, len(idx))) for s in symbols}
        return pd.DataFrame(cols, index=idx)

    monkeypatch.setattr(data, "load_prices", partial(data.load_prices, downloader=downloader,
                                                     currency_lookup=lambda t: None, sleep=lambda s: None))
    at = AppTest.from_file(BACKTEST, default_timeout=20).run()
    assert not at.exception
    assert [m.label for m in at.metric] == ["Gesamtrendite", "Rendite p. a.", "Sharpe-Ratio", "Max. Drawdown"]
    assert len(at.get("plotly_chart")) == 2

    at.sidebar.slider[0].set_value(250).run()     # langer Lookback, 300 Tage reichen noch
    assert not at.exception
    at.sidebar.date_input[0].set_value(pd.Timestamp("2024-01-01").date()).run()  # nur ~50 Tage
    assert any("Zu wenig Kursdaten" in e.value for e in at.error)
