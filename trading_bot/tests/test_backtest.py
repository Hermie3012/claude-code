"""Tests für den Backtest – mit Beispielen, die man im Kopf nachrechnen kann."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.backtest import Costs, buy_and_hold, drawdown, metrics, run_backtest
from tradingbot.strategy import StrategyParams

NO_FEES = Costs(fee_rate=0, fixed_fee=0)


def frame(**cols) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    return pd.DataFrame(cols, index=pd.bdate_range("2024-01-01", periods=n), dtype=float)


def test_follows_single_stock_with_two_day_lag():
    # Entscheidung an Tag 2, Kauf zum Schluss von Tag 3, Gewinn ab Tag 4
    prices = frame(A=[100, 100, 100, 110, 121, 133.1])
    res = run_backtest(prices, StrategyParams(lookback=2, top_n=1, rebalance_days=100), NO_FEES, 1000)
    assert res.equity.tolist() == pytest.approx([1000, 1000, 1100, 1210])
    assert res.trades["Datum"].iloc[0] == prices.index[3]


def test_jump_on_decision_day_is_not_captured():
    """B springt genau am Entscheidungstag um 100 %. Den Sprung darf die
    Strategie nicht mitnehmen – sie erfährt ihn erst zum Schlusskurs."""
    prices = frame(A=[100, 101, 102, 103, 104, 105],
                   B=[100, 100, 200, 200, 200, 200])
    res = run_backtest(prices, StrategyParams(lookback=2, top_n=1, rebalance_days=100), NO_FEES, 1000)
    assert res.rebalances["Aktien"].iloc[0] == "B"
    assert res.equity.iloc[-1] == pytest.approx(1000)   # kein Gewinn aus dem Sprung


def test_percentage_and_fixed_fees():
    prices = frame(A=[100.0] * 6)
    costs = Costs(fee_rate=0.01, fixed_fee=5)
    res = run_backtest(prices, StrategyParams(lookback=2, top_n=1, rebalance_days=100), costs, 1000)
    assert res.fees_paid == pytest.approx(1000 * 0.01 + 5)
    assert res.equity.iloc[-1] == pytest.approx(1000 - 15)


def test_weights_drift_between_rebalances():
    prices = frame(A=[100, 100, 100, 100, 200, 200], B=[100] * 6)
    res = run_backtest(prices, StrategyParams(lookback=2, top_n=2, rebalance_days=100), NO_FEES, 1000)
    # 500 € in A verdoppeln sich, 500 € in B bleiben: 1500 €
    assert res.equity.iloc[-1] == pytest.approx(1500)


def test_rebalance_with_unchanged_stocks_restores_equal_weights():
    prices = frame(A=[100, 100, 100, 100, 200, 200, 200, 200], B=[100] * 8)
    p = StrategyParams(lookback=2, top_n=2, rebalance_days=3)
    res = run_backtest(prices, p, Costs(fee_rate=0.01), 1000)
    second = res.trades[res.trades["Datum"] == prices.index[6]]
    assert set(second["Aktion"]) == {"Kauf", "Verkauf"}       # A verkaufen, B kaufen
    assert second["Betrag (EUR)"].sum() == pytest.approx(500, rel=0.02)


def test_only_positive_stays_in_cash():
    prices = frame(A=[100, 99, 98, 97, 96, 95])
    p = StrategyParams(lookback=2, top_n=1, rebalance_days=1, only_positive=True)
    res = run_backtest(prices, p, Costs(fee_rate=0.01, fixed_fee=1), 1000)
    assert res.equity.tolist() == pytest.approx([1000] * 4)
    assert res.trades.empty and res.fees_paid == 0


def test_no_look_ahead_in_equity():
    rng = np.random.default_rng(3)
    prices = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.02, (150, 5)), axis=0),
                          index=pd.bdate_range("2024-01-01", periods=150), columns=list("ABCDE"))
    p = StrategyParams(lookback=20, top_n=2, rebalance_days=5)
    changed = prices.copy()
    changed.iloc[101:] *= 3
    a = run_backtest(prices, p).equity.loc[: prices.index[100]]
    b = run_backtest(changed, p).equity.loc[: prices.index[100]]
    pd.testing.assert_series_equal(a, b)


def test_too_little_data():
    with pytest.raises(ValueError, match="Zu wenig Kursdaten"):
        run_backtest(frame(A=[100] * 5), StrategyParams(lookback=10))


def test_benchmark_buy_and_hold():
    prices = frame(A=[100, 100, 200], B=[100, 100, 100])
    bench = buy_and_hold(prices, NO_FEES, 1000)
    assert bench.tolist() == pytest.approx([1000, 1000, 1500])


def test_drawdown_and_metrics():
    eq = pd.Series([100, 120, 90, 130], index=pd.bdate_range("2024-01-01", periods=4))
    assert drawdown(eq).min() == pytest.approx(-0.25)
    m = metrics(eq)
    assert m["Gesamtrendite"] == pytest.approx(0.30)
    assert m["Max. Drawdown"] == pytest.approx(-0.25)


def test_metrics_one_year_doubling():
    idx = pd.date_range("2024-01-01", "2025-01-01", freq="D")
    eq = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    assert metrics(eq)["Rendite p. a."] == pytest.approx(1.0, abs=0.01)


def test_negative_fees_rejected():
    with pytest.raises(ValueError):
        Costs(fee_rate=-0.01)
