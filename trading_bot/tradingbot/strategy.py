"""Momentum-Strategie (Basis: backtest_momentum.py).

Idee: Alle `rebalance_days` Handelstage die `top_n` Aktien mit der höchsten
Rendite der letzten `lookback` Handelstage kaufen und gleich gewichtet halten.

Zeitregel (gegen Look-Ahead-Bias):
    Die Entscheidung an Tag t nutzt NUR Schlusskurse bis einschließlich t.
    Gehandelt wird frühestens zum nächsten Handelstag t+1. Das Verschieben
    um einen Tag passiert im Backtest (Schritt 4), nicht hier.
"""

from dataclasses import dataclass

import pandas as pd

from tradingbot import config


@dataclass(frozen=True)
class StrategyParams:
    lookback: int = config.DEFAULT_LOOKBACK
    top_n: int = config.DEFAULT_TOP_N
    rebalance_days: int = config.DEFAULT_REBALANCE_DAYS
    only_positive: bool = False  # True: nur Aktien mit Momentum > 0, Rest bleibt Cash

    def __post_init__(self):
        if self.lookback < 1:
            raise ValueError("Lookback muss mindestens 1 Tag sein")
        if self.top_n < 1:
            raise ValueError("Top-N muss mindestens 1 sein")
        if self.rebalance_days < 1:
            raise ValueError("Rebalancing-Intervall muss mindestens 1 Tag sein")


def momentum(prices: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Rendite der letzten `lookback` Handelstage für jeden Tag und jede Aktie.

    Wert an Tag t = Kurs(t) / Kurs(t - lookback) - 1. Nutzt nur Vergangenheit.
    NaN, wenn die Historie noch zu kurz ist.
    """
    return prices / prices.shift(lookback) - 1


def select(scores: pd.Series, top_n: int, only_positive: bool) -> list[str]:
    """Wählt die besten Aktien aus einer Momentum-Zeile. NaN wird ignoriert."""
    valid = scores.dropna()
    if only_positive:
        valid = valid[valid > 0]
    return list(valid.nlargest(top_n).index)


def is_rebalance_day(i: int, params: StrategyParams) -> bool:
    """Ist Tag Nummer i (0 = erster Tag der Daten) ein Entscheidungstag?"""
    return i >= params.lookback and (i - params.lookback) % params.rebalance_days == 0


def target_weights(prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
    """Ziel-Gewichte, die am Ende von Tag t feststehen (Zeilen = Tage).

    Zwischen zwei Rebalancing-Tagen bleiben die Gewichte unverändert.
    Jede ausgewählte Aktie bekommt 1/top_n. Werden (mit only_positive)
    weniger als top_n Aktien gewählt, bleibt der Rest als Cash.
    """
    mom = momentum(prices, params.lookback)
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    current = pd.Series(0.0, index=prices.columns)

    for i in range(params.lookback, len(prices)):
        if is_rebalance_day(i, params):
            current = pd.Series(0.0, index=prices.columns)
            current[select(mom.iloc[i], params.top_n, params.only_positive)] = 1 / params.top_n
        weights.iloc[i] = current
    return weights


def ranking(prices: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
    """Momentum-Rangliste für den letzten Tag in `prices`, mit Begründung.

    Grundlage für die Signal-Seite (Schritt 6).
    """
    mom = momentum(prices, params.lookback).iloc[-1]
    chosen = set(select(mom, params.top_n, params.only_positive))
    ranked = mom.dropna().sort_values(ascending=False)
    rank_of = {t: r for r, t in enumerate(ranked.index, start=1)}

    rows = []
    for t in prices.columns:
        m = mom.get(t)
        if pd.isna(m):
            reason = f"Zu wenig Kurshistorie (braucht {params.lookback + 1} Handelstage)"
        elif t in chosen:
            reason = f"Rang {rank_of[t]} von {len(ranked)} – gehört zu den Top {params.top_n}"
        elif params.only_positive and m <= 0 and rank_of[t] <= params.top_n:
            reason = f"Rang {rank_of[t]}, aber Momentum ≤ 0 – Filter 'nur positiv' greift"
        else:
            reason = f"Rang {rank_of[t]} von {len(ranked)} – nicht unter den Top {params.top_n}"
        rows.append({
            "Ticker": t,
            "Momentum": m,
            "Rang": rank_of.get(t),
            "Im Ziel-Depot": t in chosen,
            "Begründung": reason,
        })
    table = pd.DataFrame(rows).set_index("Ticker")
    return table.sort_values("Rang", na_position="last")
