"""Tests für die Momentum-Strategie."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.strategy import StrategyParams, momentum, ranking, select, target_weights


def make_prices(daily_returns: dict[str, float], days: int = 30) -> pd.DataFrame:
    """Aktien mit konstanter Tagesrendite, z. B. {'A': 0.01} = +1 % pro Tag."""
    idx = pd.bdate_range("2024-01-01", periods=days)
    return pd.DataFrame({t: 100 * (1 + r) ** np.arange(days) for t, r in daily_returns.items()}, index=idx)


def random_prices(seed=0, days=120, n=6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-01", periods=days)
    rets = rng.normal(0.0005, 0.02, size=(days, n))
    return pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=idx, columns=list("ABCDEF")[:n])


def test_momentum_value():
    prices = make_prices({"A": 0.01}, days=6)
    mom = momentum(prices, lookback=5)
    assert pd.isna(mom.iloc[4, 0])                       # Historie zu kurz
    assert mom.iloc[5, 0] == pytest.approx(1.01 ** 5 - 1)


def test_picks_strongest_stocks():
    prices = make_prices({"A": 0.01, "B": 0.03, "C": -0.01, "D": 0.02})
    w = target_weights(prices, StrategyParams(lookback=5, top_n=2, rebalance_days=5))
    assert w.iloc[-1].to_dict() == {"A": 0.0, "B": 0.5, "C": 0.0, "D": 0.5}


def test_no_weights_before_enough_history():
    prices = make_prices({"A": 0.01, "B": 0.02})
    w = target_weights(prices, StrategyParams(lookback=10, top_n=1, rebalance_days=5))
    assert (w.iloc[:10] == 0).all().all()
    assert w.iloc[10]["B"] == 1.0


def test_weights_only_change_on_rebalance_days():
    prices = random_prices()
    p = StrategyParams(lookback=20, top_n=2, rebalance_days=7)
    w = target_weights(prices, p)
    changed = w.diff().abs().sum(axis=1) > 0
    change_days = [i for i in np.flatnonzero(changed) if i > p.lookback]
    assert all((i - p.lookback) % p.rebalance_days == 0 for i in change_days)
    assert np.allclose(w.iloc[p.lookback:].sum(axis=1), 1.0)   # immer voll investiert


def test_no_look_ahead():
    """Zukünftige Kurse dürfen frühere Entscheidungen nicht beeinflussen."""
    prices = random_prices(seed=1)
    p = StrategyParams(lookback=20, top_n=2, rebalance_days=5)
    cut = 70
    future_changed = prices.copy()
    future_changed.iloc[cut + 1:] *= np.random.default_rng(99).uniform(0.2, 5, size=future_changed.iloc[cut + 1:].shape)
    pd.testing.assert_frame_equal(target_weights(prices, p).iloc[: cut + 1],
                                  target_weights(future_changed, p).iloc[: cut + 1])
    pd.testing.assert_frame_equal(ranking(prices.iloc[: cut + 1], p),
                                  ranking(future_changed.iloc[: cut + 1], p))


def test_only_positive_keeps_cash():
    prices = make_prices({"A": 0.01, "B": -0.01, "C": -0.02})
    p = StrategyParams(lookback=5, top_n=2, rebalance_days=5, only_positive=True)
    last = target_weights(prices, p).iloc[-1]
    assert last.to_dict() == {"A": 0.5, "B": 0.0, "C": 0.0}   # 50 % bleiben Cash
    # ohne Filter wird B trotz negativem Momentum gekauft (wie im Original)
    last_off = target_weights(prices, StrategyParams(lookback=5, top_n=2, rebalance_days=5)).iloc[-1]
    assert last_off["B"] == 0.5


def test_all_negative_means_all_cash():
    prices = make_prices({"A": -0.01, "B": -0.02})
    p = StrategyParams(lookback=5, top_n=1, rebalance_days=5, only_positive=True)
    assert target_weights(prices, p).iloc[-1].sum() == 0


def test_stock_with_short_history_is_skipped():
    prices = make_prices({"A": 0.01, "NEW": 0.05})
    prices.iloc[:20, 1] = np.nan        # NEW erst seit kurzem an der Börse
    assert select(momentum(prices, 15).iloc[-1], top_n=2, only_positive=False) == ["A"]


def test_top_n_larger_than_universe():
    prices = make_prices({"A": 0.01, "B": 0.02})
    w = target_weights(prices, StrategyParams(lookback=5, top_n=5, rebalance_days=5))
    assert w.iloc[-1].sum() == pytest.approx(0.4)   # 2 × 1/5, Rest Cash


def test_ranking_explains_decisions():
    prices = make_prices({"A": 0.01, "B": 0.03, "C": -0.01})
    prices["NEW"] = np.nan
    prices.iloc[-3:, 3] = 100
    table = ranking(prices, StrategyParams(lookback=5, top_n=2, only_positive=True))
    assert list(table.index) == ["B", "A", "C", "NEW"]
    assert table.loc["B", "Im Ziel-Depot"] and table.loc["A", "Im Ziel-Depot"]
    assert "nicht unter den Top 2" in table.loc["C", "Begründung"]
    assert "Zu wenig Kurshistorie" in table.loc["NEW", "Begründung"]


def test_ranking_mentions_positive_filter():
    prices = make_prices({"A": 0.01, "B": -0.01})
    table = ranking(prices, StrategyParams(lookback=5, top_n=2, only_positive=True))
    assert not table.loc["B", "Im Ziel-Depot"]
    assert "nur positiv" in table.loc["B", "Begründung"]


@pytest.mark.parametrize("kwargs", [{"lookback": 0}, {"top_n": 0}, {"rebalance_days": 0}])
def test_invalid_params(kwargs):
    with pytest.raises(ValueError):
        StrategyParams(**kwargs)
