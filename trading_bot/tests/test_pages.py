"""Klickt sich durch die Daten-Seite – mit Test-Datenbank und Fake-Kursen."""

from functools import partial
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.fakes import FakeDownloader
from tradingbot import config, data

PAGE = str(Path(__file__).resolve().parent.parent / "views" / "1_Daten.py")


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
    page.text_input(key="watchlist_new").input("msft, ungültig!")
    button(page, "Hinzufügen").click().run()
    assert any("MSFT zur Watchlist hinzugefügt" in s.value for s in page.success)
    assert any("Ungültiges Ticker-Symbol" in e.value for e in page.error)

    button(page, "Kurse laden").click().run()
    assert not page.exception
    table = page.dataframe[0].value
    assert list(table.index) == ["NVDA", "SAP.DE"]  # Reihenfolge wie in der Watchlist
    assert table.loc["NVDA", "Kurs (EUR)"] == pytest.approx(100.0)
    assert any("MSFT" in e.value for e in page.error)   # Fake liefert für MSFT nichts
    assert len(page.get("plotly_chart")) == 1


BACKTEST = str(Path(__file__).resolve().parent.parent / "views" / "2_Backtest.py")


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


DEPOT = str(Path(__file__).resolve().parent.parent / "views" / "3_Depot.py")


@pytest.fixture
def depot_page(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=20)

    def downloader(symbols, start):
        prices = {"NVDA": 110.0, "EURUSD=X": 1.10, "SAP.DE": 200.0}
        return pd.DataFrame({s: [prices.get(s, 50.0)] * len(idx) for s in symbols}, index=idx)

    monkeypatch.setattr(data, "load_prices", partial(data.load_prices, downloader=downloader,
                                                     currency_lookup=lambda t: None, sleep=lambda s: None))
    from tradingbot.watchlist import get_watchlist, remove_ticker
    for t in get_watchlist():
        if t not in ("NVDA", "SAP.DE"):
            remove_ticker(t)
    return AppTest.from_file(DEPOT, default_timeout=10).run()


def test_depot_buy_sell_and_reset(depot_page):
    at = depot_page
    assert not at.exception
    assert at.metric[0].value == "50.000,00 €"

    at.selectbox[0].set_value("NVDA")
    at.number_input[0].set_value(10)
    at.run()
    button(at, "Kaufen (Spielgeld)").click().run()
    assert any("10 × NVDA" in s.value for s in at.success)
    assert at.metric[1].value == "48.999,00 €"     # 50.000 - 10 × 100 € (= 110 USD) - 1 € Gebühr (0,1 %)
    assert at.dataframe[0].value.loc["NVDA", "Stück"] == 10

    at.radio[0].set_value("Verkaufen").run()
    at.number_input[0].set_value(11).run()
    button(at, "Verkaufen (Spielgeld)").click().run()
    assert any("nur 10 Stück" in e.value for e in at.error)

    at.checkbox[0].check().run()
    button(at, "Depot zurücksetzen").click().run()
    assert at.metric[1].value == "50.000,00 €"


SIGNALS = str(Path(__file__).resolve().parent.parent / "views" / "4_Signale.py")


def test_signals_page_preview_and_execute(tmp_path, monkeypatch):
    import numpy as np
    import pandas as pd

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=120)
    trend = {"NVDA": 0.004, "SAP.DE": 0.003, "SIE.DE": 0.002, "EURUSD=X": 0.0}

    def downloader(symbols, start):
        return pd.DataFrame({s: (1.1 if s == "EURUSD=X" else 100) * (1 + trend.get(s, -0.001)) ** np.arange(len(idx))
                             for s in symbols}, index=idx)

    monkeypatch.setattr(data, "load_prices", partial(data.load_prices, downloader=downloader,
                                                     currency_lookup=lambda t: None, sleep=lambda s: None))
    from tradingbot.watchlist import add_ticker, get_watchlist, remove_ticker
    for name in ("watchlist", "scanlist"):
        for t in get_watchlist(name=name):
            remove_ticker(t, name=name)
    add_ticker("NVDA")
    add_ticker("SAP.DE")
    add_ticker("SIE.DE", name="scanlist")
    add_ticker("BAS.DE", name="scanlist")

    at = AppTest.from_file(SIGNALS, default_timeout=20).run()
    assert not at.exception
    actions = at.dataframe[0].value
    assert list(actions.index) == ["NVDA", "SAP.DE", "SIE.DE"]          # Top 3, alle KAUFEN
    assert set(actions["Signal"]) == {"🟢 KAUFEN"}

    button(at, "Vorschau").click().run()
    plan = at.dataframe[2].value
    assert list(plan["Ticker"]) == ["NVDA", "SAP.DE", "SIE.DE"]
    button(at, "Orders ausführen").click().run()
    assert any("3 Orders ausgeführt" in s.value for s in at.success)
    assert set(at.dataframe[0].value["Signal"]) == {"🔵 HALTEN"}       # jetzt im Depot

    at.sidebar.checkbox[1].uncheck().run()                              # ohne Scan-Liste
    actions = at.dataframe[0].value
    assert "SIE.DE" not in actions.index                                # nicht mehr bewertet …
    assert any("SIE.DE" in i.value for i in at.info)                    # … und als "außerhalb" gemeldet
