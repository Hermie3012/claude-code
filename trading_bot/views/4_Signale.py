"""Seite 'Signale': aktuelle Kaufen/Verkaufen-Liste und Depot-Anpassung."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from tradingbot import config, data
from tradingbot.portfolio import eur, get_settings, get_state
from tradingbot.signals import BUY, HOLD, NONE, SELL, build_signals, execute_plan, last_rebalance, plan_rebalance
from tradingbot.strategy import StrategyParams
from tradingbot.watchlist import get_watchlist

LABEL = {BUY: "🟢 KAUFEN", SELL: "🔴 VERKAUFEN", HOLD: "🔵 HALTEN", NONE: "–"}

st.set_page_config(page_title="Signale", page_icon="🚦", layout="wide")
st.title("🚦 Signale")
st.warning(config.DISCLAIMER)

state = st.session_state
state.setdefault("flash", [])
for level, msg in state.flash:
    getattr(st, level)(msg)
state.flash = []

# ---------------------------------------------------------------- Einstellungen
with st.sidebar:
    st.header("Strategie")
    lookback = st.slider("Lookback (Handelstage)", 5, 250, config.DEFAULT_LOOKBACK)
    top_n = st.slider("Top-N (Anzahl Aktien)", 1, 10, config.DEFAULT_TOP_N)
    rebalance = st.slider("Umschichten alle … Handelstage", 1, 60, config.DEFAULT_REBALANCE_DAYS)
    only_positive = st.checkbox("Nur positives Momentum kaufen (sonst Cash)")
    st.header("Scan")
    use_scan = st.checkbox("Scan-Liste einbeziehen", value=True,
                           help="Zusätzlich zur Watchlist auch die Aktien der Scan-Liste bewerten "
                                "(bearbeitbar auf der Seite Daten).")

params = StrategyParams(lookback=lookback, top_n=top_n, rebalance_days=rebalance, only_positive=only_positive)

# ---------------------------------------------------------------- Daten
universe = get_watchlist()
if use_scan:
    universe = list(dict.fromkeys(universe + get_watchlist(name="scanlist")))
if not universe:
    st.info("Watchlist und Scan-Liste sind leer. Füge auf der Seite **Daten** Aktien hinzu.")
    st.stop()

# Lookback zählt Handelstage; in Kalendertagen etwa 1,5-mal so viel plus Puffer
start = date.today() - timedelta(days=int(lookback * 1.5) + 30)
with st.spinner(f"Lade Kurse für {len(universe)} Aktien …"):
    loaded = data.load_prices(universe, start.isoformat())
for w in loaded.warnings:
    st.warning(w)
if loaded.errors:
    with st.expander(f"⚠️ {len(loaded.errors)} Aktien ohne Daten (werden nicht bewertet)"):
        st.write("\n".join(f"- **{t}**: {msg}" for t, msg in loaded.errors.items()))
prices = loaded.prices
if len(prices) < lookback + 1:
    st.error(f"Zu wenig Kursdaten ({len(prices)} Tage) für einen Lookback von {lookback} Tagen.")
    st.stop()

price_date = prices.index[-1].date()
depot = get_state()
_, costs = get_settings()
signals = build_signals(prices, params, held=set(depot.positions))

# ---------------------------------------------------------------- Rhythmus
last = last_rebalance()
st.write(f"Signale nach Schlusskurs vom **{price_date:%d.%m.%Y}** · {prices.shape[1]} Aktien bewertet")
if last is None:
    st.info(f"Noch keine Anpassung über diese Seite. Die Strategie sieht vor, alle {rebalance} Handelstage umzuschichten.")
else:
    days_since = int(np.busday_count(date.fromisoformat(last), price_date))
    text = f"Letzte Anpassung: Kurse vom **{date.fromisoformat(last):%d.%m.%Y}** – vor {days_since} Handelstagen."
    if days_since >= rebalance:
        st.warning(f"{text} Laut Strategie (alle {rebalance} Handelstage) wäre eine Anpassung fällig.")
    else:
        st.info(f"{text} Nächste Anpassung laut Strategie in {rebalance - days_since} Handelstagen.")
if (date.today() - price_date).days > 4:
    st.warning(f"Die neuesten Kurse sind vom {price_date:%d.%m.%Y} – evtl. veraltet.")

# ---------------------------------------------------------------- Signale
counts = signals["Signal"].value_counts()
c = st.columns(3)
for col, sig in zip(c, [BUY, SELL, HOLD]):
    col.metric(LABEL[sig], int(counts.get(sig, 0)))

view = signals.assign(Signal=signals["Signal"].map(LABEL))
column_config = {
    "Momentum": st.column_config.NumberColumn(format="percent", help=f"Rendite der letzten {lookback} Handelstage"),
    "Rang": st.column_config.NumberColumn(format="%d"),
    "Im Depot": st.column_config.CheckboxColumn(),
    "Begründung": st.column_config.TextColumn(width="large"),
}
st.subheader("Handlungsliste")
actions = view[signals["Signal"] != NONE]
if actions.empty:
    st.write("Keine Signale – das Ziel-Depot ist leer (z. B. weil alle Momentum-Werte negativ sind "
             "und 'nur positives Momentum' aktiv ist).")
else:
    st.dataframe(actions, column_config=column_config)
with st.expander(f"📊 Komplette Rangliste ({len(view)} Aktien)"):
    st.dataframe(view, column_config=column_config)

outside = sorted(set(depot.positions) - set(universe))
if outside:
    st.info("Im Depot, aber nicht in Watchlist/Scan-Liste (keine Signale, werden nicht angepasst): "
            + ", ".join(outside))

# ---------------------------------------------------------------- Depot anpassen
st.subheader("Depot an Signale anpassen")
st.caption(f"Ziel: je 1/{top_n} des Depotwerts in jede Aktie des Ziel-Depots, ganze Aktien, "
           f"Ausführung zum Schlusskurs vom {price_date:%d.%m.%Y}. Spielgeld – keine echten Orders.")
adjust_held = st.toggle("Gehaltene Positionen auf 1/N angleichen", value=True,
                        help="Aus: Es wird nur gekauft und verkauft, was neu ins Ziel-Depot kommt "
                             "oder herausfällt. Spart Gebühren für kleine Ausgleichsorders.")
# Ziel-Depot nach Rang sortiert: bei knappem Cash wird der Beste zuerst gekauft
targets = list(signals[signals["Signal"].isin([BUY, HOLD])].sort_values("Rang").index)
plan, notes = plan_rebalance(depot, prices.iloc[-1], targets, top_n, costs, set(universe), adjust_held)

if st.button("🔍 Vorschau der Orders anzeigen"):
    state.show_plan = True
if state.get("show_plan"):
    for n in notes:
        st.info(n)
    if not plan:
        st.success("Dein Depot entspricht bereits den Signalen – keine Orders nötig.")
    else:
        table = pd.DataFrame([{
            "Art": "Kauf" if o.side == "BUY" else "Verkauf", "Ticker": o.ticker, "Stück": o.shares,
            "Kurs": o.price, "Volumen": o.shares * o.price,
            "Gebühr": round(costs.for_order(o.shares * o.price), 2), "Grund": o.reason,
        } for o in plan])
        money = st.column_config.NumberColumn(format="euro")
        st.dataframe(table, hide_index=True, column_config={"Kurs": money, "Volumen": money, "Gebühr": money})
        cash_after = (depot.cash + (table["Volumen"] * np.where(table["Art"] == "Kauf", -1, 1)).sum()
                      - table["Gebühr"].sum())
        st.write(f"{len(plan)} Orders · Gebühren **{eur(table['Gebühr'].sum())}** · "
                 f"Cash danach ca. **{eur(cash_after)}**")
        b1, b2, _ = st.columns([2, 1, 3])
        if b1.button("✅ Orders ausführen (Spielgeld)", type="primary"):
            errors = execute_plan(plan, price_date.isoformat(), costs)
            state.show_plan = False
            if errors:
                state.flash.append(("error", "Nicht alle Orders ausgeführt:\n\n" + "\n".join(f"- {e}" for e in errors)))
            else:
                state.flash.append(("success", f"{len(plan)} Orders ausgeführt. Details auf der Seite **Depot**."))
            st.rerun()
        if b2.button("Abbrechen"):
            state.show_plan = False
            st.rerun()
