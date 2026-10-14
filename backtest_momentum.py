"""
Momentum-Backtest (Lernprojekt, keine Anlageberatung)

Idee: Alle N Handelstage die Aktien mit dem stärksten Momentum kaufen
(Rendite der letzten LOOKBACK Tage) und gleich gewichtet halten.
Vergleich mit einem Benchmark (alle Aktien gleich gewichtet, Buy & Hold).

Installation:  pip install yfinance pandas numpy matplotlib
Start:         python backtest_momentum.py
"""

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# ---------------- Einstellungen ----------------
TICKERS = [
    "NVDA", "MU", "GOOGL", "MSFT", "AMD", "AVGO", "NOW", "NKE",
    "IFX.DE", "ENR.DE", "SAP.DE", "SIE.DE", "RHM.DE", "ALV.DE",
]
START = "2023-01-01"
END = None            # None = bis heute
LOOKBACK = 60         # Tage für die Momentum-Berechnung
TOP_N = 3             # so viele Aktien gleichzeitig halten
REBALANCE_DAYS = 10   # alle X Handelstage neu sortieren
FEE = 0.001           # 0,1 % Gebühr pro gehandeltem Volumen (anpassen!)
START_CAPITAL = 50_000
# -----------------------------------------------


def load_prices() -> pd.DataFrame:
    data = yf.download(TICKERS, start=START, end=END, auto_adjust=True, progress=False)["Close"]
    data = data.dropna(how="all").ffill().dropna(axis=1)  # Aktien ohne Daten raus
    return data


def run_backtest(prices: pd.DataFrame) -> pd.Series:
    returns = prices.pct_change().fillna(0)
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    current = pd.Series(0.0, index=prices.columns)

    for i in range(LOOKBACK, len(prices)):
        if (i - LOOKBACK) % REBALANCE_DAYS == 0:
            momentum = prices.iloc[i - 1] / prices.iloc[i - 1 - LOOKBACK] - 1
            best = momentum.nlargest(TOP_N).index
            current = pd.Series(0.0, index=prices.columns)
            current[best] = 1 / TOP_N
        weights.iloc[i] = current

    # Gewichte werden erst am Folgetag wirksam (kein Blick in die Zukunft)
    w = weights.shift(1).fillna(0)
    turnover = w.diff().abs().sum(axis=1).fillna(0)
    strat_ret = (w * returns).sum(axis=1) - turnover * FEE
    return (1 + strat_ret).cumprod() * START_CAPITAL


def benchmark(prices: pd.DataFrame) -> pd.Series:
    ret = prices.pct_change().fillna(0).mean(axis=1)
    return (1 + ret).cumprod() * START_CAPITAL


def stats(equity: pd.Series, name: str) -> None:
    ret = equity.pct_change().dropna()
    total = equity.iloc[-1] / equity.iloc[0] - 1
    years = len(equity) / 252
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0
    drawdown = (equity / equity.cummax() - 1).min()
    print(f"{name:<12} Gesamt: {total:7.1%} | pro Jahr: {cagr:6.1%} | "
          f"Sharpe: {sharpe:4.2f} | Max. Drawdown: {drawdown:6.1%}")


def main() -> None:
    prices = load_prices()
    print(f"Daten: {prices.index[0].date()} bis {prices.index[-1].date()}, "
          f"{prices.shape[1]} Aktien\n")

    strat = run_backtest(prices)
    strat = strat.iloc[LOOKBACK:]
    bench = benchmark(prices).iloc[LOOKBACK:]
    bench = bench / bench.iloc[0] * START_CAPITAL

    stats(strat, "Momentum")
    stats(bench, "Benchmark")

    plt.figure(figsize=(10, 5))
    plt.plot(strat, label="Momentum-Strategie")
    plt.plot(bench, label="Benchmark (gleich gewichtet)")
    plt.title("Backtest Momentum")
    plt.ylabel("Depotwert (€)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("backtest.png", dpi=150)
    print("\nChart gespeichert: backtest.png")


if __name__ == "__main__":
    main()
