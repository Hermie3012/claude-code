"""Backtest: Wie hätte sich die Strategie in der Vergangenheit geschlagen?

Zeitablauf (wir haben nur Schlusskurse):
    Tag t   : nach Börsenschluss wird entschieden (Kurse bis einschließlich t)
    Tag t+1 : die Orders werden zum Schlusskurs ausgeführt
    ab t+2  : die neuen Positionen machen Gewinn oder Verlust
So kann die Strategie nie einen Kurs nutzen, den sie bei der Entscheidung
noch nicht kannte (kein Look-Ahead-Bias).

Zwischen zwei Umschichtungen "driften" die Anteile mit den Kursen: Steigt
eine Aktie, wird ihr Anteil am Depot größer – genau wie in echt.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tradingbot import config
from tradingbot.strategy import StrategyParams, is_rebalance_day, target_weights

TRADING_DAYS = 252   # Handelstage pro Jahr (für Volatilität und Sharpe)
MIN_ORDER_EUR = 0.01


@dataclass(frozen=True)
class Costs:
    fee_rate: float = config.DEFAULT_FEE  # Anteil vom Ordervolumen, 0.001 = 0,1 %
    fixed_fee: float = 0.0                # Euro pro Order

    def __post_init__(self):
        if self.fee_rate < 0 or self.fixed_fee < 0:
            raise ValueError("Gebühren dürfen nicht negativ sein")

    def for_orders(self, amounts: np.ndarray) -> float:
        """Gebühr für eine Liste von Orderbeträgen (Kauf und Verkauf positiv)."""
        return float(amounts.sum() * self.fee_rate + len(amounts) * self.fixed_fee)

    def for_order(self, volume: float) -> float:
        """Gebühr für eine einzelne Order."""
        return self.for_orders(np.array([volume]))


@dataclass
class BacktestResult:
    equity: pd.Series        # Depotwert der Strategie pro Tag
    benchmark: pd.Series     # Depotwert Benchmark (alle Aktien kaufen und halten)
    trades: pd.DataFrame     # jede einzelne Order
    rebalances: pd.DataFrame # jede Umschichtung mit den gewählten Aktien
    fees_paid: float


def run_backtest(prices: pd.DataFrame, params: StrategyParams, costs: Costs = Costs(),
                 start_capital: float = config.START_CAPITAL) -> BacktestResult:
    prices = prices.ffill()
    start = params.lookback  # erster Entscheidungstag: ab hier zählt das Kapital
    if len(prices) < start + 2:
        raise ValueError(
            f"Zu wenig Kursdaten: {len(prices)} Tage, für Lookback {params.lookback} "
            f"werden mindestens {start + 2} gebraucht. Früheres Startdatum wählen."
        )

    targets = target_weights(prices, params).to_numpy()
    rets = prices.pct_change(fill_method=None).fillna(0.0).to_numpy()
    dates, tickers = prices.index, prices.columns

    cash, hold = start_capital, np.zeros(len(tickers))  # hold = Euro-Wert je Aktie
    pending = None   # Entscheidung, die am nächsten Tag ausgeführt wird
    equity, trades, rebalances, fees_paid = [], [], [], 0.0

    for i in range(start, len(prices)):
        hold = hold * (1 + rets[i])  # Kursbewegung des Tages

        if pending is not None:      # Ausführung zum heutigen Schlusskurs
            decided_on, target = pending
            total = cash + hold.sum()
            diff = target * total - hold
            orders = np.abs(diff) >= MIN_ORDER_EUR
            fee = costs.for_orders(np.abs(diff[orders]))
            new_hold = target * (total - fee)   # Gebühren schmälern das Depot
            for j in np.flatnonzero(orders):
                amount = new_hold[j] - hold[j]
                trades.append({"Datum": dates[i], "Ticker": tickers[j],
                               "Aktion": "Kauf" if amount > 0 else "Verkauf",
                               "Betrag (EUR)": abs(amount)})
            rebalances.append({"Entschieden am": decided_on, "Ausgeführt am": dates[i],
                               "Aktien": ", ".join(tickers[target > 0]) or "– nur Cash –",
                               "Gebühren (EUR)": fee})
            fees_paid += fee
            cash, hold = total - fee - new_hold.sum(), new_hold
            pending = None

        if is_rebalance_day(i, params):
            pending = (dates[i], targets[i])
        equity.append(cash + hold.sum())

    equity = pd.Series(equity, index=dates[start:], name="Strategie")
    bench = buy_and_hold(prices.iloc[start:], costs, start_capital)
    return BacktestResult(equity, bench, pd.DataFrame(trades), pd.DataFrame(rebalances), fees_paid)


def buy_and_hold(prices: pd.DataFrame, costs: Costs, start_capital: float) -> pd.Series:
    """Benchmark: am 2. Tag (gleiches Timing wie die Strategie) alle Aktien mit
    Kurs zu gleichen Teilen kaufen und bis zum Ende liegen lassen."""
    buy_row = prices.iloc[1]
    available = buy_row.dropna().index
    fee = costs.for_orders(np.full(len(available), start_capital / max(len(available), 1)))
    per_stock = (start_capital - fee) / max(len(available), 1)
    growth = prices[available].iloc[1:] / buy_row[available]
    values = (growth * per_stock).sum(axis=1)
    first = pd.Series([start_capital], index=prices.index[:1])
    return pd.concat([first, values]).rename("Benchmark")


# ---------------------------------------------------------------- Kennzahlen

def drawdown(equity: pd.Series) -> pd.Series:
    """Abstand zum bisherigen Höchststand, z. B. -0,25 = 25 % unter dem Hoch."""
    return equity / equity.cummax() - 1


def metrics(equity: pd.Series) -> dict[str, float]:
    """Kennzahlen einer Depotwert-Kurve.

    Sharpe-Ratio: Rendite pro Risiko-Einheit (Risiko = Schwankung), hier ohne
    risikolosen Zins gerechnet. Faustregel: > 1 gut, < 0,5 eher schwach.
    """
    daily = equity.pct_change().dropna()
    total = equity.iloc[-1] / equity.iloc[0] - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    std = daily.std()
    return {
        "Gesamtrendite": total,
        "Rendite p. a.": (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else np.nan,
        "Volatilität p. a.": std * np.sqrt(TRADING_DAYS) if len(daily) > 1 else np.nan,
        "Sharpe-Ratio": daily.mean() / std * np.sqrt(TRADING_DAYS) if std > 0 else np.nan,
        "Max. Drawdown": drawdown(equity).min(),
        "Endwert (EUR)": equity.iloc[-1],
    }
