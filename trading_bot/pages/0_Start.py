"""Seite 'Start': Überblick und Hinweis."""

import streamlit as st

from tradingbot.config import DISCLAIMER, START_CAPITAL

st.title("📈 Trading-Bot – Lernprojekt")
st.warning(DISCLAIMER)

capital = f"{START_CAPITAL:,.0f}".replace(",", ".")  # deutsches Format: 50.000

st.markdown(
    f"""
Diese App scannt eine Watchlist von Aktien, berechnet **Momentum-Signale**
und simuliert ein **Paper-Depot** mit {capital} € Spielgeld.

**Seiten (links in der Seitenleiste):**
1. **Daten** – Watchlist bearbeiten, Kurse laden *(Schritt 2)*
2. **Backtest** – Strategie auf historischen Daten testen *(Schritt 4)*
3. **Depot** – virtuelle Orders und Positionen *(Schritt 5)*
4. **Signale** – aktuelle Kaufen/Verkaufen-Liste *(Schritt 6)*
"""
)
