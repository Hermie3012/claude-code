"""Tests für Signale und die Depot-Anpassung."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.backtest import Costs
from tradingbot.portfolio import get_state, order_history, place_order
from tradingbot.signals import (BUY, HOLD, NONE, SELL, build_signals, execute_plan, last_rebalance,
                                plan_rebalance)
from tradingbot.strategy import StrategyParams

NO_FEES = Costs(fee_rate=0, fixed_fee=0)
P = StrategyParams(lookback=5, top_n=2, rebalance_days=5)


def trending(returns: dict[str, float], days=10) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-01", periods=days)
    return pd.DataFrame({t: 100 * (1 + r) ** np.arange(days) for t, r in returns.items()}, index=idx)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "test.db"


def test_signal_categories():
    prices = trending({"A": 0.03, "B": 0.02, "C": 0.01, "D": -0.01})
    table = build_signals(prices, P, held={"B", "C"})
    assert table["Signal"].to_dict() == {"A": BUY, "C": SELL, "B": HOLD, "D": NONE}
    assert table.loc["A", "Begründung"].startswith("Neu im Ziel-Depot: Rang 1")
    assert table.loc["C", "Begründung"].startswith("Nicht mehr im Ziel-Depot")


def test_plan_from_cash_only(db):
    prices = pd.Series({"A": 100.0, "B": 30.0})
    orders, notes = plan_rebalance(get_state(db), prices, ["A", "B"], 2, NO_FEES, {"A", "B"})
    assert [(o.ticker, o.side, o.shares) for o in orders] == [("A", "BUY", 250), ("B", "BUY", 833)]
    assert notes == []


def test_plan_sells_first_then_buys(db):
    place_order("C", "BUY", 100, 100.0, "2024-01-01", NO_FEES, db_path=db)
    prices = pd.Series({"A": 100.0, "B": 100.0, "C": 100.0})
    orders, _ = plan_rebalance(get_state(db), prices, ["A", "B"], 2, NO_FEES, {"A", "B", "C"})
    assert [(o.ticker, o.side, o.shares) for o in orders] == [("C", "SELL", 100), ("A", "BUY", 250), ("B", "BUY", 250)]


def test_plan_rebalances_held_positions(db):
    place_order("A", "BUY", 400, 100.0, "2024-01-01", NO_FEES, db_path=db)   # 40.000 € in A
    prices = pd.Series({"A": 100.0, "B": 100.0})
    orders, _ = plan_rebalance(get_state(db), prices, ["A", "B"], 2, NO_FEES, {"A", "B"})
    assert [(o.ticker, o.side, o.shares) for o in orders] == [("A", "SELL", 150), ("B", "BUY", 250)]

    orders, _ = plan_rebalance(get_state(db), prices, ["A", "B"], 2, NO_FEES, {"A", "B"}, adjust_held=False)
    assert [(o.ticker, o.side, o.shares) for o in orders] == [("B", "BUY", 100)]   # nur restliches Cash


def test_small_deviation_is_ignored(db):
    place_order("A", "BUY", 250, 100.0, "2024-01-01", NO_FEES, db_path=db)
    place_order("B", "BUY", 250, 100.0, "2024-01-01", NO_FEES, db_path=db)
    prices = pd.Series({"A": 101.0, "B": 99.0})        # 1 % Abweichung: unter der Toleranz
    orders, _ = plan_rebalance(get_state(db), prices, ["A", "B"], 2, NO_FEES, {"A", "B"})
    assert orders == []


def test_positions_outside_universe_untouched(db):
    place_order("X", "BUY", 10, 100.0, "2024-01-01", NO_FEES, db_path=db)
    prices = pd.Series({"A": 100.0, "X": 100.0})
    orders, notes = plan_rebalance(get_state(db), prices, ["A"], 1, NO_FEES, {"A"})
    assert [(o.ticker, o.side) for o in orders] == [("A", "BUY")]
    assert orders[0].shares == 490                     # nur das Cash, X bleibt
    assert any("bleiben unverändert: X" in n for n in notes)


def test_fees_reduce_last_buy(db):
    costs = Costs(fee_rate=0.01, fixed_fee=0)
    prices = pd.Series({"A": 100.0})
    orders, notes = plan_rebalance(get_state(db), prices, ["A"], 1, costs, {"A"})
    assert orders[0].shares == 495                     # 500 Stück wären mit 1 % Gebühr zu teuer
    assert any("Cash reicht nur" in n for n in notes)


def test_missing_price_skipped(db):
    orders, notes = plan_rebalance(get_state(db), pd.Series({"A": 100.0}), ["A", "B"], 2, NO_FEES, {"A", "B"})
    assert [o.ticker for o in orders] == ["A"]
    assert any("B: kein aktueller Kurs" in n for n in notes)


def test_execute_plan_places_orders(db):
    prices = pd.Series({"A": 100.0, "B": 50.0})
    orders, _ = plan_rebalance(get_state(db), prices, ["A", "B"], 2, NO_FEES, {"A", "B"})
    assert execute_plan(orders, "2024-01-05", NO_FEES, db_path=db) == []
    state = get_state(db)
    assert state.positions["A"].shares == 250 and state.positions["B"].shares == 500
    assert order_history(db)["note"].str.startswith("Signal-Anpassung").all()
    assert last_rebalance(db) == "2024-01-05"


def test_execute_plan_reports_errors(db):
    from tradingbot.signals import PlannedOrder
    errors = execute_plan([PlannedOrder("A", "SELL", 1, 100.0, "Test")], "2024-01-05", NO_FEES, db_path=db)
    assert "nur 0 Stück" in errors[0]
