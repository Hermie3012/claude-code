"""Einstiegspunkt der Streamlit-App.

Start:  streamlit run app.py
Hier wird festgelegt, welche Seiten es gibt und wie sie in der Seitenleiste heißen.
Der Inhalt jeder Seite liegt im Ordner pages/.
"""

import streamlit as st

st.set_page_config(page_title="Trading-Bot (Lernprojekt)", page_icon="📈", layout="wide")

navigation = st.navigation([
    st.Page("pages/0_Start.py", title="Start", icon="📈", default=True),
    st.Page("pages/1_Daten.py", title="Daten", icon="🗂️"),
    st.Page("pages/2_Backtest.py", title="Backtest", icon="🧪"),
])
navigation.run()
