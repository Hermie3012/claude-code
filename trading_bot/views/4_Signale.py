"""Seite 'Signale': aktuelle Kaufen/Verkaufen-Liste und Depot-Anpassung."""

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from tradingbot import config
from tradingbot.portfolio import eur, get_settings, get_state
from tradingbot.signals import (BUY, HOLD, NONE, SELL, compute_snapshot, days_since_rebalance, execute_plan,
                                last_rebalance, load_settings, plan_rebalance, save_settings)
from tradingbot.strategy import StrategyParams

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
# Startwerte aus der Datenbank (gespeichert vom letzten Besuch), danach merkt
# sich Streamlit die Werte über die `key`s.
saved, saved_scan = load_settings()
for key, value in [("sig_lookback", saved.lookback), ("sig_top_n", saved.top_n),
                   ("sig_rebalance", saved.rebalance_days), ("sig_positive", saved.only_positive),
                   ("sig_scan", saved_scan)]:
    state.setdefault(key, value)

with st.sidebar:
    st.header("Strategie")
    lookback = st.slider("Lookback (Handelstage)", 5, 250, key="sig_lookback")
    top_n = st.slider("Top-N (Anzahl Aktien)", 1, 10, key="sig_top_n")
    rebalance = st.slider("Umschichten alle … Handelstage", 1, 60, key="sig_rebalance")
    only_positive = st.checkbox("Nur positives Momentum kaufen (sonst Cash)", key="sig_positive")
    st.header("Scan")
    use_scan = st.checkbox("Scan-Liste einbeziehen", key="sig_scan",
                           help="Zusätzlich zur Watchlist auch die Aktien der Scan-Liste bewerten "
                                "(bearbeitbar auf der Seite Daten).")
    st.caption("Diese Einstellungen werden gespeichert und auch für die tägliche E-Mail verwendet.")

params = StrategyParams(lookback=lookback, top_n=top_n, rebalance_days=rebalance, only_positive=only_positive)
if (params, use_scan) != (saved, saved_scan):
    save_settings(params, use_scan)

# ---------------------------------------------------------------- Daten
with st.spinner("Lade Kurse …"):
    snap = compute_snapshot(params, use_scan)
if snap.loaded is not None:
    for w in snap.loaded.warnings:
        st.warning(w)
    if snap.loaded.errors:
        with st.expander(f"⚠️ {len(snap.loaded.errors)} Aktien ohne Daten (werden nicht bewertet)"):
            st.write("\n".join(f"- **{t}**: {msg}" for t, msg in snap.loaded.errors.items()))
if snap.error:
    st.error(snap.error)
    st.stop()

universe, prices, signals, price_date = snap.universe, snap.loaded.prices, snap.signals, snap.price_date
depot = get_state()
_, costs = get_settings()

# ---------------------------------------------------------------- Rhythmus
days_since = days_since_rebalance(price_date)
st.write(f"Signale nach Schlusskurs vom **{price_date:%d.%m.%Y}** · {prices.shape[1]} Aktien bewertet")
if days_since is None:
    st.info(f"Noch keine Anpassung über diese Seite. Die Strategie sieht vor, alle {rebalance} Handelstage umzuschichten.")
else:
    last = date.fromisoformat(last_rebalance())
    text = f"Letzte Anpassung: Kurse vom **{last:%d.%m.%Y}** – vor {days_since} Handelstagen."
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
