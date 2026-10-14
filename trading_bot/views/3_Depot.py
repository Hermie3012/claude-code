"""Seite 'Depot': Paper-Trading mit Spielgeld."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from tradingbot import config, data
from tradingbot.backtest import Costs
from tradingbot.portfolio import (OrderError, eur, get_settings, get_state, max_affordable, order_history,
                                  place_order, reset_depot, save_fees, valuation)
from tradingbot.watchlist import get_watchlist

PRICE_WINDOW_DAYS = 45   # für den aktuellen Kurs reichen die letzten Wochen
STALE_AFTER_DAYS = 4     # ältere Kurse werden markiert (Wochenende/Feiertage einkalkuliert)

st.set_page_config(page_title="Depot", page_icon="💼", layout="wide")
st.title("💼 Paper-Depot")
st.warning(config.DISCLAIMER)
st.info("🎲 **Spielgeld:** Alle Orders sind virtuell und werden zum letzten verfügbaren "
        "Schlusskurs ausgeführt. Es wird nichts an einen Broker gesendet.")

state = st.session_state
state.setdefault("flash", [])
for level, msg in state.flash:
    getattr(st, level)(msg)
state.flash = []

# ---------------------------------------------------------------- Kurse
depot = get_state()
capital, costs = get_settings()
tickers = list(dict.fromkeys(get_watchlist() + list(depot.positions)))  # ohne Doppelte
loaded = None
if tickers:
    with st.spinner("Lade aktuelle Kurse …"):
        loaded = data.load_prices(tickers, (date.today() - timedelta(days=PRICE_WINDOW_DAYS)).isoformat())
    for w in loaded.warnings:
        st.warning(w)
last_prices = loaded.prices.iloc[-1] if loaded is not None and not loaded.prices.empty else pd.Series(dtype=float)
price_date = loaded.prices.index[-1].date() if not last_prices.empty else None

# ---------------------------------------------------------------- Übersicht
positions, summary = valuation(depot, last_prices)
c = st.columns(4)
c[0].metric("Gesamtwert", eur(summary["Gesamtwert"]))
c[1].metric("Cash", eur(summary["Cash"]))
c[2].metric("Gewinn/Verlust gesamt", eur(summary["G/V gesamt"], sign=True),
            delta=f"{summary['G/V gesamt (%)']:+.2%}".replace(".", ","))
c[3].metric("davon realisiert", eur(summary["G/V realisiert"], sign=True),
            help="Gewinn/Verlust aus bereits verkauften Aktien (nach Gebühren). "
                 "Der Rest ist 'unrealisiert', also nur auf dem Papier.")
st.caption(f"Startkapital {eur(capital)} · Gezahlte Gebühren {eur(summary['Gebühren'])}"
           + (f" · Kurse vom {price_date:%d.%m.%Y}" if price_date else ""))
if price_date and (date.today() - price_date).days > STALE_AFTER_DAYS:
    st.warning(f"Die neuesten Kurse sind vom {price_date:%d.%m.%Y} – evtl. veraltet "
               "(kein Internet oder Rate-Limit?).")
if summary["missing_prices"]:
    st.warning("Kein aktueller Kurs für " + ", ".join(summary["missing_prices"])
               + " – diese Positionen sind mit dem Einstandskurs bewertet.")

st.subheader("Positionen")
if positions.empty:
    st.write("Noch keine Positionen. Kaufe unten deine erste Aktie.")
else:
    money = st.column_config.NumberColumn(format="euro")
    st.dataframe(positions, column_config={
        "Einstand/Stück": money, "Kurs": money, "Wert": money, "G/V (EUR)": money,
        "G/V (%)": st.column_config.NumberColumn(format="percent"),
        "Anteil": st.column_config.NumberColumn(format="percent"),
    })

# ---------------------------------------------------------------- Order aufgeben
st.subheader("Neue Order")
if not tickers:
    st.info("Füge auf der Seite **Daten** Aktien zur Watchlist hinzu, um handeln zu können.")
else:
    tradable = [t for t in tickers if t in last_prices.index and pd.notna(last_prices[t])]
    if not tradable:
        st.error("Für keine Aktie liegt ein Kurs vor – Handeln ist gerade nicht möglich.")
    else:
        col1, col2, col3 = st.columns(3)
        side_label = col1.radio("Art", ["Kaufen", "Verkaufen"], horizontal=True)
        side = "BUY" if side_label == "Kaufen" else "SELL"
        choices = tradable if side == "BUY" else [t for t in tradable if t in depot.positions]
        if not choices:
            st.info("Du hast keine Aktien, die du verkaufen könntest.")
        else:
            ticker = col2.selectbox("Aktie", choices)
            price = float(last_prices[ticker])
            limit = (max_affordable(depot.cash, price, costs) if side == "BUY"
                     else depot.positions[ticker].shares)
            shares = col3.number_input(f"Stück (max. {limit})", min_value=1, step=1, value=1)
            volume = shares * price
            fee = round(costs.for_order(volume), 2)
            sign = 1 if side == "BUY" else -1
            st.write(f"Kurs: **{eur(price)}** (Schlusskurs {price_date:%d.%m.%Y}) · "
                     f"Ordervolumen **{eur(volume)}** · Gebühr **{eur(fee)}** · "
                     f"Cash danach **{eur(depot.cash - sign * volume - fee)}**")
            if st.button(f"✅ {side_label} (Spielgeld)", type="primary"):
                try:
                    place_order(ticker, side, int(shares), price, price_date.isoformat(), costs)
                    state.flash.append(("success", f"{side_label}: {int(shares)} × {ticker} zu {eur(price)} ausgeführt."))
                    st.rerun()
                except OrderError as exc:
                    st.error(str(exc))

# ---------------------------------------------------------------- Historie
st.subheader("Orderhistorie")
history = order_history()
if history.empty:
    st.write("Noch keine Orders.")
else:
    view = pd.DataFrame({
        "Zeitpunkt": pd.to_datetime(history["created_at"]).dt.tz_convert("Europe/Berlin").dt.strftime("%d.%m.%Y %H:%M"),
        "Art": history["side"].map({"BUY": "Kauf", "SELL": "Verkauf"}),
        "Ticker": history["ticker"],
        "Stück": history["shares"],
        "Kurs": history["price"],
        "Kurs vom": pd.to_datetime(history["price_date"]).dt.strftime("%d.%m.%Y"),
        "Volumen": history["shares"] * history["price"],
        "Gebühr": history["fee"],
        "Notiz": history["note"],
    }).iloc[::-1]  # neueste zuerst
    money = st.column_config.NumberColumn(format="euro")
    st.dataframe(view, hide_index=True, column_config={"Kurs": money, "Volumen": money, "Gebühr": money})

# ---------------------------------------------------------------- Einstellungen
with st.expander("⚙️ Depot-Einstellungen"):
    st.markdown("**Gebühren** (gelten für neue Orders)")
    f1, f2 = st.columns(2)
    fee_pct = f1.number_input("Prozentual pro Order (%)", 0.0, 5.0, costs.fee_rate * 100, step=0.05, format="%.2f")
    fixed = f2.number_input("Fix pro Order (€)", 0.0, 50.0, costs.fixed_fee, step=0.5)
    if st.button("Gebühren speichern"):
        save_fees(Costs(fee_rate=fee_pct / 100, fixed_fee=fixed))
        state.flash.append(("success", "Gebühren gespeichert."))
        st.rerun()

    st.divider()
    st.markdown("**Depot zurücksetzen** – löscht alle Orders und Positionen.")
    new_capital = st.number_input("Neues Startkapital (€)", 1000.0, 10_000_000.0, config.START_CAPITAL, step=1000.0)
    confirm = st.checkbox("Ja, ich möchte wirklich alles löschen")
    if st.button("🗑️ Depot zurücksetzen", disabled=not confirm):
        reset_depot(new_capital)
        state.flash.append(("success", f"Depot zurückgesetzt – Startkapital {eur(new_capital)}."))
        st.rerun()
