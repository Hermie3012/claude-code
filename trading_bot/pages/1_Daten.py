"""Seite 'Daten': Watchlist bearbeiten, Kurse laden, Cache ansehen."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tradingbot import config, data
from tradingbot.watchlist import add_ticker, get_watchlist, normalize_ticker, remove_ticker, reset_watchlist

# Feste Farbreihenfolge (geprüft auf Farbsehschwäche). Max. 8 Linien im Chart.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                 "#e87ba4", "#008300", "#6250d6", "#e34948"]
MAX_LINES = len(SERIES_COLORS)

st.set_page_config(page_title="Daten", page_icon="🗂️", layout="wide")
st.title("🗂️ Daten & Watchlist")
st.warning(config.DISCLAIMER)

state = st.session_state
state.setdefault("flash", [])          # Meldungen, die nach einem Klick angezeigt werden
state.setdefault("color_of", {})       # Ticker -> Farbe (bleibt stabil)


# ---------------------------------------------------------------- Aktionen
def on_add():
    raw = state.get("new_tickers", "")
    for part in raw.replace(";", ",").split(","):
        if not part.strip():
            continue
        try:
            t = normalize_ticker(part)
            if add_ticker(t):
                state.flash.append(("success", f"{t} hinzugefügt."))
            else:
                state.flash.append(("info", f"{t} ist schon in der Watchlist."))
        except ValueError as exc:
            state.flash.append(("error", str(exc)))
    state.new_tickers = ""


def on_remove():
    for t in state.get("to_remove", []):
        remove_ticker(t)
    state.to_remove = []


def on_reset():
    reset_watchlist()
    state.flash.append(("success", "Standard-Watchlist wiederhergestellt."))


for level, msg in state.flash:
    getattr(st, level)(msg)
state.flash = []

# ---------------------------------------------------------------- Watchlist
st.header("1. Watchlist")
watchlist = get_watchlist()
st.write(f"**{len(watchlist)} Ticker:** " + (", ".join(watchlist) or "– leer –"))

col_add, col_remove = st.columns(2)
with col_add:
    st.text_input(
        "Ticker hinzufügen (mehrere mit Komma)",
        key="new_tickers",
        placeholder="z. B. TSLA, BAS.DE",
        help="Yahoo-Finance-Symbole: US-Aktien ohne Endung, Xetra mit .DE, London mit .L",
    )
    st.button("➕ Hinzufügen", on_click=on_add)
with col_remove:
    st.multiselect("Ticker entfernen", watchlist, key="to_remove")
    c1, c2 = st.columns(2)
    c1.button("🗑️ Entfernen", on_click=on_remove, disabled=not state.get("to_remove"))
    c2.button("↺ Standardliste", on_click=on_reset)

# ---------------------------------------------------------------- Kurse laden
st.header("2. Kurse laden")
c1, c2 = st.columns([1, 2])
start = c1.date_input("Startdatum", value=date.fromisoformat(config.DEFAULT_START),
                      max_value=date.today(), format="DD.MM.YYYY")
force = c2.checkbox("Alles neu laden (Cache ignorieren)",
                    help=f"Normalerweise werden gespeicherte Kurse {data.MAX_AGE_HOURS} Stunden lang wiederverwendet.")

if st.button("📥 Kurse laden", type="primary", disabled=not watchlist):
    with st.spinner("Lade Kurse … bei Rate-Limits wird automatisch kurz gewartet und erneut versucht."):
        state.load_result = data.load_prices(watchlist, start.isoformat(), force=force)

res: data.LoadResult | None = state.get("load_result")
if res is None:
    st.info("Klicke auf **Kurse laden**. Bereits gespeicherte Kurse werden aus dem Cache genommen.")
else:
    if res.downloaded:
        st.caption(f"Neu heruntergeladen: {', '.join(res.downloaded)}")
    else:
        st.caption("Alle Kurse kamen aus dem Cache (kein Download nötig).")
    for w in res.warnings:
        st.warning(w)
    if res.errors:
        st.error("**Für diese Symbole gibt es keine Daten:**\n\n"
                 + "\n".join(f"- **{t}**: {msg}" for t, msg in res.errors.items()))

    if not res.prices.empty:
        # Tabelle: letzter Kurs je Aktie
        last_date = res.prices_local.apply(lambda s: s.last_valid_index())
        table = pd.DataFrame({
            "Währung": pd.Series(res.currencies),
            "Kurs (Original)": res.prices_local.ffill().iloc[-1],
            "Kurs (EUR)": res.prices.iloc[-1],
            "Änderung 1 Tag": res.prices.pct_change(fill_method=None).iloc[-1],
            "Stand": last_date.dt.strftime("%d.%m.%Y"),
        }).loc[res.prices.columns]
        st.subheader("Letzte Kurse")
        st.dataframe(
            table,
            column_config={
                "Kurs (Original)": st.column_config.NumberColumn(format="%.2f"),
                "Kurs (EUR)": st.column_config.NumberColumn(format="%.2f €"),
                "Änderung 1 Tag": st.column_config.NumberColumn(format="percent"),
            },
        )

        # Chart: Wertentwicklung, alle Kurse am ersten Tag auf 100 gesetzt
        st.subheader("Wertentwicklung (Start = 100, in EUR)")
        choices = list(res.prices.columns)
        selected = st.multiselect(f"Aktien im Chart (max. {MAX_LINES})", choices,
                                  default=choices[:4], max_selections=MAX_LINES)
        # Jede Aktie behält ihre Farbe, auch wenn andere ab-/zugewählt werden
        for t in list(state.color_of):
            if t not in selected:
                del state.color_of[t]
        for t in selected:
            if t not in state.color_of:
                free = [c for c in SERIES_COLORS if c not in state.color_of.values()]
                state.color_of[t] = free[0]

        if selected:
            fig = go.Figure()
            for t in selected:
                s = res.prices[t].dropna()
                fig.add_trace(go.Scatter(
                    x=s.index, y=s / s.iloc[0] * 100, name=t, mode="lines",
                    line=dict(width=2, color=state.color_of[t]),
                    hovertemplate="%{y:.1f}",
                ))
            fig.add_hline(y=100, line_width=1, line_color="rgba(128,128,128,0.6)")
            fig.update_layout(hovermode="x unified", height=420, margin=dict(l=10, r=10, t=10, b=10),
                              legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                              yaxis_title="Index (Start = 100)")
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
            st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- Cache
with st.expander("🗄️ Gespeicherte Daten (Cache)"):
    status = data.cache_status()
    if status.empty:
        st.write("Noch keine Kurse gespeichert.")
    else:
        st.dataframe(status, hide_index=True)
    if st.button("Cache leeren"):
        data.clear_cache()
        state.pop("load_result", None)
        st.rerun()
