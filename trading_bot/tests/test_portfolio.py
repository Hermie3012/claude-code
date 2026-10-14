"""Tests für das Paper-Depot."""

import pandas as pd
import pytest

from tradingbot import config
from tradingbot.backtest import Costs
from tradingbot.portfolio import (OrderError, eur, get_settings, get_state, max_affordable, order_history,
                                  place_order, reset_depot, save_fees, valuation)

NO_FEES = Costs(fee_rate=0, fixed_fee=0)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "test.db"


def buy(db, ticker, shares, price, costs=NO_FEES):
    return place_order(ticker, "BUY", shares, price, "2024-01-02", costs, db_path=db)


def sell(db, ticker, shares, price, costs=NO_FEES):
    return place_order(ticker, "SELL", shares, price, "2024-01-03", costs, db_path=db)


def test_new_depot_has_50000_cash(db):
    state = get_state(db)
    assert state.cash == config.START_CAPITAL == 50_000
    assert state.positions == {}


def test_buy_reduces_cash_and_creates_position(db):
    buy(db, "SAP.DE", 10, 200.0, Costs(fee_rate=0.001, fixed_fee=1))
    state = get_state(db)
    assert state.cash == pytest.approx(50_000 - 2000 - 3)      # Gebühr: 2 € + 1 €
    assert state.positions["SAP.DE"].shares == 10
    assert state.positions["SAP.DE"].avg_cost == pytest.approx(200.3)  # inkl. Gebühr


def test_average_cost_over_two_buys(db):
    buy(db, "A", 10, 100.0)
    buy(db, "A", 10, 200.0)
    assert get_state(db).positions["A"].avg_cost == pytest.approx(150.0)


def test_sell_realizes_profit(db):
    buy(db, "A", 10, 100.0)
    sell(db, "A", 4, 150.0, Costs(fee_rate=0, fixed_fee=2))
    state = get_state(db)
    assert state.positions["A"].shares == 6
    assert state.positions["A"].avg_cost == pytest.approx(100.0)
    assert state.realized_pnl == pytest.approx(4 * 50 - 2)
    sell(db, "A", 6, 90.0)
    assert "A" not in get_state(db).positions                  # Position geschlossen


def test_not_enough_cash(db):
    with pytest.raises(OrderError, match="Nicht genug Cash"):
        buy(db, "A", 501, 100.0)
    assert order_history(db).empty                             # nichts gespeichert


def test_cannot_sell_more_than_held(db):
    buy(db, "A", 5, 100.0)
    with pytest.raises(OrderError, match="nur 5 Stück"):
        sell(db, "A", 6, 100.0)
    with pytest.raises(OrderError, match="nur 0 Stück"):
        sell(db, "B", 1, 100.0)


@pytest.mark.parametrize("shares", [0, -3, 1.5])
def test_only_whole_positive_shares(db, shares):
    with pytest.raises(OrderError):
        buy(db, "A", shares, 100.0)


@pytest.mark.parametrize("price", [0, -1, float("nan"), None])
def test_invalid_price(db, price):
    with pytest.raises(OrderError, match="Kein gültiger Kurs"):
        buy(db, "A", 1, price)


def test_max_affordable():
    assert max_affordable(1000, 100, NO_FEES) == 10
    assert max_affordable(1000, 100, Costs(fee_rate=0.001, fixed_fee=1)) == 9   # 10 Stück = 1002 €
    assert max_affordable(0.5, 100, Costs(fixed_fee=1)) == 0


def test_buying_max_affordable_never_fails(db):
    costs = Costs(fee_rate=0.0025, fixed_fee=4.9)
    n = max_affordable(50_000, 123.45, costs)
    buy(db, "A", n, 123.45, costs)
    with pytest.raises(OrderError):
        buy(db, "A", max_affordable(get_state(db).cash, 123.45, costs) + 1, 123.45, costs)


def test_pnl_adds_up(db):
    """Realisiert + unrealisiert = Gesamtwert - Startkapital (kein Cent geht verloren)."""
    costs = Costs(fee_rate=0.001, fixed_fee=1)
    buy(db, "A", 100, 50.0, costs)
    buy(db, "B", 30, 120.0, costs)
    sell(db, "A", 40, 61.0, costs)
    buy(db, "A", 10, 58.0, costs)
    sell(db, "B", 30, 99.0, costs)
    table, s = valuation(get_state(db), pd.Series({"A": 64.0}))
    assert s["G/V realisiert"] + s["G/V unrealisiert"] == pytest.approx(s["G/V gesamt"])
    assert s["Gesamtwert"] == pytest.approx(s["Cash"] + 70 * 64.0)
    assert table.loc["A", "Stück"] == 70


def test_missing_price_is_reported(db):
    buy(db, "A", 10, 100.0)
    table, s = valuation(get_state(db), pd.Series(dtype=float))
    assert s["missing_prices"] == ["A"]
    assert table.loc["A", "Wert"] == pytest.approx(1000)       # Notlösung: Einstand


def test_reset_and_settings(db):
    buy(db, "A", 10, 100.0)
    save_fees(Costs(fee_rate=0.002, fixed_fee=3), db)
    reset_depot(10_000, db)
    capital, costs = get_settings(db)
    assert capital == 10_000 and costs == Costs(fee_rate=0.002, fixed_fee=3)
    assert get_state(db).cash == 10_000 and order_history(db).empty
    place_order("A", "BUY", 1, 100.0, "2024-01-02", db_path=db)   # nutzt gespeicherte Gebühren
    assert order_history(db)["fee"].iloc[0] == pytest.approx(3.2)


def test_eur_format():
    assert eur(1234.5) == "1.234,50 €"
    assert eur(-19.4, sign=True) == "-19,40 €"
    assert eur(5, sign=True) == "+5,00 €"
