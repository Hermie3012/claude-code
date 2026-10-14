"""Signale: das Ziel-Depot der Strategie mit deinem Paper-Depot vergleichen.

KAUFEN    = im Ziel-Depot, aber (noch) nicht in deinem Depot
VERKAUFEN = in deinem Depot, aber nicht mehr im Ziel-Depot
HALTEN    = in beiden

plan_rebalance() rechnet aus, welche Orders nötig wären, damit dein Depot
wieder dem Ziel entspricht (je 1/Top-N des Depotwerts, nur ganze Aktien).
Ausgeführt wird erst mit execute_plan() – die Seite zeigt vorher eine Vorschau.
"""

import math
from dataclasses import dataclass

import pandas as pd

from tradingbot.backtest import Costs
from tradingbot.db import connect
from tradingbot.portfolio import DepotState, OrderError, max_affordable, place_order
from tradingbot.strategy import StrategyParams, ranking

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
