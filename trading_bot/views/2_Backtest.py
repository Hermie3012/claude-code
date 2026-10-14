"""Seite 'Backtest': Strategie auf historischen Kursen testen."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tradingbot import config, data
from tradingbot.backtest import Costs, drawdown, metrics, run_backtest
from tradingbot.strategy import StrategyParams
from tradingbot.watchlist import get_watchlist

COLORS = {"Strategie": "#2a78d6", "Benchmark": "#eb6834"}

st.set_page_config(page_title="Backtest", page_icon="🧪", layout="wide")
st.title("🧪 Backtest")
st.warning(config.DISCLAIMER)
st.caption("Ein Backtest zeigt, wie die Regeln in der Vergangenheit funktioniert *hätten*. "
           "Das sagt nichts darüber, wie sie in Zukunft funktionieren.")

# ---------------------------------------------------------------- Einstellungen
with st.sidebar:
    st.header("Einstellungen")
    start = st.date_input("Startdatum der Kursdaten", value=date.fromisoformat(config.DEFAULT_START),
                          max_value=date.today(), format="DD.MM.YYYY")
    lookback = st.slider("Lookback (Handelstage)", 5, 250, config.DEFAULT_LOOKBACK,
                         help="Über wie viele Tage die Rendite (Momentum) gemessen wird.")
    top_n = st.slider("Top-N (Anzahl Aktien)", 1, 10, config.DEFAULT_TOP_N)
    rebalance = st.slider("Umschichten alle … Handelstage", 1, 60, config.DEFAULT_REBALANCE_DAYS)
    only_positive = st.checkbox("Nur positives Momentum kaufen (sonst Cash)")
    st.subheader("Gebühren")
    fee_pct = st.number_input("Prozentual pro Order (%)", 0.0, 5.0, config.DEFAULT_FEE * 100,
                              step=0.05, format="%.2f")
    fixed_fee = st.number_input("Fix pro Order (€)", 0.0, 50.0, 0.0, step=0.5)
    capital = st.number_input("Startkapital (€)", 1000.0, 10_000_000.0, config.START_CAPITAL, step=1000.0)

# ---------------------------------------------------------------- Daten
tickers = get_watchlist()
if not tickers:
    st.info("Die Watchlist ist leer. Füge auf der Seite **Daten** Aktien hinzu.")
    st.stop()

with st.spinner("Lade Kurse (aus dem Cache, falls vorhanden) …"):
    loaded = data.load_prices(tickers, start.isoformat())
for w in loaded.warnings:
    st.warning(w)
if loaded.errors:
    st.error("Ohne Daten (nicht im Backtest): " + ", ".join(f"**{t}**" for t in loaded.errors))
if loaded.prices.empty:
    st.stop()

params = StrategyParams(lookback=lookback, top_n=top_n, rebalance_days=rebalance, only_positive=only_positive)
costs = Costs(fee_rate=fee_pct / 100, fixed_fee=fixed_fee)
try:
    res = run_backtest(loaded.prices, params, costs, capital)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

first, last = res.equity.index[0], res.equity.index[-1]
st.write(f"Zeitraum: **{first:%d.%m.%Y} – {last:%d.%m.%Y}** · {loaded.prices.shape[1]} Aktien · "
         f"Die ersten {lookback} Handelstage ab Startdatum dienen nur zum Berechnen des ersten Momentums.")

# ---------------------------------------------------------------- Kennzahlen
m_s, m_b = metrics(res.equity), metrics(res.benchmark)


def pct(x, sign=True):
    return "–" if pd.isna(x) else f"{x:{'+' if sign else ''}.1%}".replace(".", ",")


def num(x):
    return "–" if pd.isna(x) else f"{x:.2f}".replace(".", ",")


def eur(x):
    return f"{x:,.0f} €".replace(",", ".")


FORMAT = {"Gesamtrendite": pct, "Rendite p. a.": pct, "Volatilität p. a.": lambda x: pct(x, sign=False),
          "Sharpe-Ratio": num, "Max. Drawdown": pct, "Endwert (EUR)": eur}

cols = st.columns(4)
for col, key in zip(cols, ["Gesamtrendite", "Rendite p. a.", "Sharpe-Ratio", "Max. Drawdown"]):
    fmt = FORMAT[key]
    delta = m_s[key] - m_b[key] if pd.notna(m_s[key]) and pd.notna(m_b[key]) else None
    col.metric(key, fmt(m_s[key]),
               delta=None if delta is None else f"{fmt(delta)} vs. Benchmark",
               delta_color="off" if delta is None else "normal")

st.dataframe(pd.DataFrame({name: {k: FORMAT[k](v) for k, v in m.items()}
                           for name, m in [("Strategie", m_s), ("Benchmark", m_b)]}).T)
st.caption(f"Gezahlte Gebühren: **{eur(res.fees_paid)}** bei {len(res.trades)} Orders "
           f"({len(res.rebalances)} Umschichtungen). Benchmark: alle Aktien zu gleichen Teilen "
           "kaufen und liegen lassen. Sharpe ohne risikolosen Zins.")

with st.expander("❓ Was bedeuten die Kennzahlen?"):
    st.markdown("""
- **Gesamtrendite**: Gewinn/Verlust über den ganzen Zeitraum.
- **Rendite p. a.**: auf ein Jahr umgerechnet – macht unterschiedlich lange Zeiträume vergleichbar.
- **Sharpe-Ratio**: Rendite geteilt durch Schwankung. Höher = mehr Rendite pro eingegangenem Risiko.
  Faustregel: über 1 gut, unter 0,5 schwach.
- **Max. Drawdown**: der größte Verlust vom letzten Höchststand bis zum Tiefpunkt.
  –30 % heißt: zwischendurch war ein Drittel des Depots weg. Wichtig, um zu prüfen, ob man das aushalten würde.
""")

# ---------------------------------------------------------------- Charts
def line_chart(series: dict[str, pd.Series], y_title: str, y_format: str, height: int):
    fig = go.Figure()
    for name, s in series.items():
        fig.add_trace(go.Scatter(x=s.index, y=s, name=name, mode="lines",
                                 line=dict(width=2, color=COLORS[name]),
                                 hovertemplate=f"%{{y:{y_format}}}"))
    fig.update_layout(hovermode="x unified", height=height, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                      yaxis_title=y_title, separators=",.")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)", tickformat=y_format)
    return fig


st.subheader("Depotwert")
st.plotly_chart(line_chart({"Strategie": res.equity, "Benchmark": res.benchmark},
                           "Depotwert (€)", ",.0f", 420), width="stretch")
st.subheader("Drawdown (Abstand zum Höchststand)")
st.plotly_chart(line_chart({"Strategie": drawdown(res.equity) * 100, "Benchmark": drawdown(res.benchmark) * 100},
                           "Drawdown (%)", ".1f", 260), width="stretch")

# ---------------------------------------------------------------- Details
with st.expander(f"📋 Umschichtungen ({len(res.rebalances)})"):
    if not res.rebalances.empty:
        st.dataframe(res.rebalances, hide_index=True, column_config={
            "Entschieden am": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "Ausgeführt am": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "Gebühren (EUR)": st.column_config.NumberColumn(format="euro"),
        })
with st.expander(f"🧾 Alle Orders ({len(res.trades)})"):
    if not res.trades.empty:
        st.dataframe(res.trades, hide_index=True, column_config={
            "Datum": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "Betrag (EUR)": st.column_config.NumberColumn(format="euro"),
        })
