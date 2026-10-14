"""Signale: das Ziel-Depot der Strategie mit deinem Paper-Depot vergleichen.

KAUFEN    = im Ziel-Depot, aber (noch) nicht in deinem Depot
VERKAUFEN = in deinem Depot, aber nicht mehr im Ziel-Depot
HALTEN    = in beiden

plan_rebalance() rechnet aus, welche Orders nötig wären, damit dein Depot
wieder dem Ziel entspricht (je 1/Top-N des Depotwerts, nur ganze Aktien).
Ausgeführt wird erst mit execute_plan() – die Seite zeigt vorher eine Vorschau.
"""

import json
import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from tradingbot import data
from tradingbot.backtest import Costs
from tradingbot.db import connect
from tradingbot.portfolio import DepotState, OrderError, get_state, max_affordable, place_order
from tradingbot.strategy import StrategyParams, ranking
from tradingbot.watchlist import get_watchlist

BUY, SELL, HOLD, NONE = "KAUFEN", "VERKAUFEN", "HALTEN", "–"
SIGNAL_ORDER = {BUY: 0, SELL: 1, HOLD: 2, NONE: 3}

# Gehaltene Aktien werden nur angepasst, wenn sie mehr als 2 % vom Zielwert
# abweichen. Sonst entstünden ständig Mini-Orders, die nur Gebühren kosten.
REBALANCE_TOLERANCE = 0.02

ORDER_NOTE = "Signal-Anpassung"


def build_signals(prices: pd.DataFrame, params: StrategyParams, held: set[str]) -> pd.DataFrame:
    """Signal-Tabelle für alle Aktien in `prices` (= das gescannte Universum)."""
    table = ranking(prices, params)
    table["Im Depot"] = [t in held for t in table.index]

    signals, reasons = [], []
    for t, row in table.iterrows():
        if row["Im Ziel-Depot"] and not row["Im Depot"]:
            signals.append(BUY)
            reasons.append(f"Neu im Ziel-Depot: {row['Begründung']}")
        elif row["Im Ziel-Depot"]:
            signals.append(HOLD)
            reasons.append(f"Weiter im Ziel-Depot: {row['Begründung']}")
        elif row["Im Depot"]:
            signals.append(SELL)
            reasons.append(f"Nicht mehr im Ziel-Depot: {row['Begründung']}")
        else:
            signals.append(NONE)
            reasons.append(row["Begründung"])
    table["Signal"] = signals
    table["Begründung"] = reasons
    table["_order"] = table["Signal"].map(SIGNAL_ORDER)
    table = table.sort_values(["_order", "Rang"], na_position="last").drop(columns="_order")
    return table[["Signal", "Rang", "Momentum", "Im Depot", "Begründung"]]


@dataclass
class PlannedOrder:
    ticker: str
    side: str        # "BUY" oder "SELL"
    shares: int
    price: float
    reason: str


def plan_rebalance(state: DepotState, last_prices: pd.Series, targets: list[str], top_n: int,
                   costs: Costs, universe: set[str], adjust_held: bool = True
                   ) -> tuple[list[PlannedOrder], list[str]]:
    """Plant die Orders, um das Depot an das Ziel anzupassen.

    - Nur Aktien aus `universe` werden angefasst; andere Positionen bleiben.
    - Zielwert je Aktie = (Cash + Wert der verwalteten Positionen) / top_n.
    - Erst Verkäufe (bringt Cash), dann Käufe in Rang-Reihenfolge.
    Gibt (Orders, Hinweise) zurück.
    """
    notes: list[str] = []

    def price_of(t):
        p = last_prices.get(t)
        return None if p is None or pd.isna(p) or p <= 0 else float(p)

    managed = {t: pos for t, pos in state.positions.items() if t in universe}
    missing = [t for t in set(managed) | set(targets) if price_of(t) is None]
    for t in missing:
        notes.append(f"{t}: kein aktueller Kurs – wird übersprungen.")
    investable = state.cash + sum(pos.shares * price_of(t) for t, pos in managed.items() if price_of(t))
    target_value = investable / top_n

    orders: list[PlannedOrder] = []
    cash = state.cash

    # 1. Verkäufe
    for t, pos in managed.items():
        price = price_of(t)
        if price is None:
            continue
        n, why = 0, ""
        if t not in targets:
            n, why = pos.shares, "nicht mehr im Ziel-Depot"
        elif adjust_held and pos.shares * price > target_value * (1 + REBALANCE_TOLERANCE):
            n, why = pos.shares - math.floor(target_value / price), "Anteil zu groß – zurück auf 1/N"
        if n > 0:
            orders.append(PlannedOrder(t, "SELL", n, price, why))
            cash += n * price - costs.for_order(n * price)

    # 2. Käufe
    for t in targets:
        price = price_of(t)
        if price is None:
            continue
        held = managed[t].shares if t in managed else 0
        if held and not adjust_held:
            continue
        if held and held * price >= target_value * (1 - REBALANCE_TOLERANCE):
            continue
        wanted = math.floor(target_value / price) - held
        n = min(wanted, max_affordable(cash, price, costs))
        if wanted > 0 and n < wanted:
            notes.append(f"{t}: Cash reicht nur für {n} statt {wanted} Stück (Gebühren).")
        if n > 0:
            orders.append(PlannedOrder(t, "BUY", n, price,
                                       "neu im Ziel-Depot" if not held else "Anteil zu klein – auf 1/N auffüllen"))
            cash -= n * price + costs.for_order(n * price)

    outside = sorted(set(state.positions) - universe)
    if outside:
        notes.append("Nicht in Watchlist/Scan-Liste, bleiben unverändert: " + ", ".join(outside))
    return orders, notes


def execute_plan(orders: list[PlannedOrder], price_date: str, costs: Costs, db_path=None) -> list[str]:
    """Führt geplante Orders nacheinander aus. Gibt Fehlermeldungen zurück (leer = alles ok)."""
    errors = []
    for o in orders:
        try:
            place_order(o.ticker, o.side, o.shares, o.price, price_date, costs,
                        note=f"{ORDER_NOTE}: {o.reason}", db_path=db_path)
        except OrderError as exc:
            errors.append(f"{o.ticker}: {exc}")
    with connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_rebalance', ?)", (price_date,))
    return errors


def last_rebalance(db_path=None) -> str | None:
    """Datum (Kursdatum) der letzten Anpassung über die Signal-Seite."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = 'last_rebalance'").fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------- Einstellungen & Berechnung
# Die Signal-Seite speichert ihre Einstellungen, damit die tägliche E-Mail
# (notify.py) mit genau denselben Werten rechnet.

def save_settings(params: StrategyParams, use_scan: bool, db_path=None) -> None:
    value = json.dumps({**asdict(params), "use_scan": use_scan})
    with connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('signal_settings', ?)", (value,))


def load_settings(db_path=None) -> tuple[StrategyParams, bool]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = 'signal_settings'").fetchone()
    if not row:
        return StrategyParams(), True
    values = json.loads(row[0])
    use_scan = values.pop("use_scan", True)
    return StrategyParams(**values), use_scan


@dataclass
class Snapshot:
    """Alles, was Signal-Seite und E-Mail für den aktuellen Stand brauchen."""
    universe: list[str]
    loaded: "data.LoadResult | None"
    signals: pd.DataFrame | None
    price_date: date | None
    error: str | None = None


def compute_snapshot(params: StrategyParams, use_scan: bool, db_path=None) -> Snapshot:
    universe = get_watchlist(db_path)
    if use_scan:
        universe = list(dict.fromkeys(universe + get_watchlist(db_path, name="scanlist")))
    if not universe:
        return Snapshot(universe, None, None, None,
                        "Watchlist und Scan-Liste sind leer. Füge auf der Seite Daten Aktien hinzu.")

    # Lookback zählt Handelstage; in Kalendertagen etwa 1,5-mal so viel plus Puffer
    start = date.today() - timedelta(days=int(params.lookback * 1.5) + 30)
    loaded = data.load_prices(universe, start.isoformat(), db_path=db_path)
    prices = loaded.prices
    if len(prices) < params.lookback + 1:
        return Snapshot(universe, loaded, None, None,
                        f"Zu wenig Kursdaten ({len(prices)} Tage) für einen Lookback von {params.lookback} Tagen.")
    held = set(get_state(db_path).positions)
    return Snapshot(universe, loaded, build_signals(prices, params, held), prices.index[-1].date())


def days_since_rebalance(price_date: date, db_path=None) -> int | None:
    """Handelstage seit der letzten Anpassung (None = noch nie angepasst)."""
    last = last_rebalance(db_path)
    return None if last is None else int(np.busday_count(date.fromisoformat(last), price_date))
