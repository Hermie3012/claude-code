"""Paper-Depot: virtuelle Orders mit Spielgeld. KEINE echten Orders.

Gespeichert werden nur die Orders (Tabelle `orders`). Cash, Positionen und
Gewinn/Verlust werden jedes Mal aus allen Orders neu berechnet ("Orderbuch").
So können Kontostand und Historie nie auseinanderlaufen.

Einstandskurs: Durchschnitt aller Käufe INKLUSIVE Kaufgebühren. Beim Verkauf
wird der Einstand anteilig abgezogen (Durchschnittskosten-Methode).
"""

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from tradingbot import config
from tradingbot.backtest import Costs
from tradingbot.db import connect


def eur(x: float, sign: bool = False) -> str:
    """Deutsches Geldformat: 1234.5 -> '1.234,50 €' (mit sign=True: '+1.234,50 €')."""
    text = f"{x:{'+' if sign else ''},.2f} €"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


class OrderError(ValueError):
    """Order nicht möglich (z. B. zu wenig Cash). Die Meldung ist für Menschen gedacht."""


@dataclass
class Position:
    shares: int
    cost_basis: float  # Einstand gesamt in EUR (inkl. Kaufgebühren)

    @property
    def avg_cost(self) -> float:
        return self.cost_basis / self.shares


@dataclass
class DepotState:
    start_capital: float
    cash: float
    positions: dict[str, Position]
    realized_pnl: float   # Gewinn/Verlust aus bereits verkauften Aktien (nach Gebühren)
    fees_paid: float


# ---------------------------------------------------------------- Einstellungen

def get_settings(db_path=None) -> tuple[float, Costs]:
    """Startkapital und Gebühren des Depots (gespeichert in der Tabelle meta)."""
    with connect(db_path) as conn:
        rows = dict(conn.execute("SELECT key, value FROM meta WHERE key LIKE 'depot_%'").fetchall())
    capital = float(rows.get("depot_start_capital", config.START_CAPITAL))
    costs = Costs(fee_rate=float(rows.get("depot_fee_rate", config.DEFAULT_FEE)),
                  fixed_fee=float(rows.get("depot_fixed_fee", 0.0)))
    return capital, costs


def save_fees(costs: Costs, db_path=None) -> None:
    with connect(db_path) as conn:
        conn.executemany("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                         [("depot_fee_rate", str(costs.fee_rate)), ("depot_fixed_fee", str(costs.fixed_fee))])


def reset_depot(start_capital: float = config.START_CAPITAL, db_path=None) -> None:
    """Löscht alle Orders und beginnt neu mit `start_capital` Spielgeld."""
    if start_capital <= 0:
        raise ValueError("Startkapital muss größer als 0 sein")
    with connect(db_path) as conn:
        conn.execute("DELETE FROM orders")
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('depot_start_capital', ?)",
                     (str(start_capital),))


# ---------------------------------------------------------------- Zustand berechnen

def _replay(orders: pd.DataFrame, start_capital: float) -> DepotState:
    """Spielt alle Orders der Reihe nach durch und berechnet den Depotstand."""
    cash, realized, fees = start_capital, 0.0, 0.0
    positions: dict[str, Position] = {}
    for o in orders.itertuples():
        volume = o.shares * o.price
        fees += o.fee
        if o.side == "BUY":
            cash -= volume + o.fee
            pos = positions.setdefault(o.ticker, Position(0, 0.0))
            pos.shares += o.shares
            pos.cost_basis += volume + o.fee
        else:
            pos = positions[o.ticker]
            cost_sold = pos.avg_cost * o.shares
            cash += volume - o.fee
            realized += volume - o.fee - cost_sold
            pos.shares -= o.shares
            pos.cost_basis -= cost_sold
            if pos.shares == 0:
                del positions[o.ticker]
    return DepotState(start_capital, cash, positions, realized, fees)


def _orders(conn) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM orders ORDER BY id", conn)


def get_state(db_path=None) -> DepotState:
    capital, _ = get_settings(db_path)
    with connect(db_path) as conn:
        return _replay(_orders(conn), capital)


def order_history(db_path=None) -> pd.DataFrame:
    with connect(db_path) as conn:
        return _orders(conn)


# ---------------------------------------------------------------- Orders

def max_affordable(cash: float, price: float, costs: Costs) -> int:
    """Wie viele ganze Aktien kann ich mir inklusive Gebühren leisten?"""
    if price <= 0 or cash <= costs.fixed_fee:
        return 0
    return max(0, math.floor((cash - costs.fixed_fee) / (price * (1 + costs.fee_rate)) + 1e-9))


def place_order(ticker: str, side: str, shares: int, price: float, price_date: str,
                costs: Costs | None = None, note: str = "", db_path=None) -> dict:
    """Führt eine virtuelle Order zum angegebenen Kurs (EUR) aus.

    side: "BUY" (Kaufen) oder "SELL" (Verkaufen). Nur ganze Aktien.
    Wirft OrderError, wenn die Order nicht möglich ist.
    """
    if side not in ("BUY", "SELL"):
        raise OrderError(f"Unbekannte Orderart: {side}")
    if isinstance(shares, float) and not shares.is_integer():
        raise OrderError("Es sind nur ganze Aktien erlaubt.")
    shares = int(shares)
    if shares <= 0:
        raise OrderError("Die Stückzahl muss mindestens 1 sein.")
    if not price or price <= 0 or math.isnan(price):
        raise OrderError(f"Kein gültiger Kurs für {ticker} vorhanden.")

    capital, saved_costs = get_settings(db_path)
    costs = costs or saved_costs
    volume = shares * price
    fee = round(costs.for_order(volume), 2)

    with connect(db_path) as conn:
        state = _replay(_orders(conn), capital)
        if side == "BUY" and volume + fee > state.cash + 1e-6:
            raise OrderError(
                f"Nicht genug Cash: benötigt {eur(volume + fee)} (inkl. {eur(fee)} Gebühr), "
                f"verfügbar {eur(state.cash)}. Maximal möglich: "
                f"{max_affordable(state.cash, price, costs)} Stück."
            )
        held = state.positions.get(ticker, Position(0, 0.0)).shares
        if side == "SELL" and shares > held:
            raise OrderError(f"Du hast nur {held} Stück {ticker} im Depot.")
        order = {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ticker": ticker, "side": side, "shares": shares, "price": price,
            "price_date": price_date, "fee": fee, "note": note,
        }
        conn.execute(
            "INSERT INTO orders (created_at, ticker, side, shares, price, price_date, fee, note) "
            "VALUES (:created_at, :ticker, :side, :shares, :price, :price_date, :fee, :note)", order,
        )
    return order


# ---------------------------------------------------------------- Bewertung

def valuation(state: DepotState, last_prices: pd.Series) -> tuple[pd.DataFrame, dict]:
    """Bewertet die Positionen mit aktuellen Kursen (EUR).

    Gibt (Positionstabelle, Summen) zurück. Fehlt ein Kurs, wird die Position
    mit dem Einstand bewertet und in `missing_prices` gemeldet.
    """
    rows, missing = [], []
    for t, pos in state.positions.items():
        price = last_prices.get(t)
        if price is None or pd.isna(price):
            missing.append(t)
            price = pos.avg_cost
        value = pos.shares * price
        rows.append({"Ticker": t, "Stück": pos.shares, "Einstand/Stück": pos.avg_cost, "Kurs": price,
                     "Wert": value, "G/V (EUR)": value - pos.cost_basis,
                     "G/V (%)": value / pos.cost_basis - 1})
    table = pd.DataFrame(rows, columns=["Ticker", "Stück", "Einstand/Stück", "Kurs", "Wert",
                                        "G/V (EUR)", "G/V (%)"]).set_index("Ticker")
    invested = float(table["Wert"].sum())
    total = state.cash + invested
    if total > 0:
        table["Anteil"] = table["Wert"] / total
    summary = {
        "Gesamtwert": total,
        "Cash": state.cash,
        "Investiert": invested,
        "G/V gesamt": total - state.start_capital,
        "G/V gesamt (%)": total / state.start_capital - 1,
        "G/V realisiert": state.realized_pnl,
        "G/V unrealisiert": float(table["G/V (EUR)"].sum()),
        "Gebühren": state.fees_paid,
        "missing_prices": missing,
    }
    return table, summary
