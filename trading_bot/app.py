"""Einstiegspunkt der Streamlit-App.

Start:  streamlit run app.py
Hier wird festgelegt, welche Seiten es gibt und wie sie in der Seitenleiste heißen.
Der Inhalt jeder Seite liegt im Ordner views/.
"""

import streamlit as st

st.set_page_config(page_title="Trading-Bot (Lernprojekt)", page_icon="📈", layout="wide")

navigation = st.navigation([
    st.Page("views/0_Start.py", title="Start", icon="📈", default=True),
    st.Page("views/1_Daten.py", title="Daten", icon="🗂️"),
    st.Page("views/2_Backtest.py", title="Backtest", icon="🧪"),
    st.Page("views/3_Depot.py", title="Depot", icon="💼"),
    st.Page("views/4_Signale.py", title="Signale", icon="🚦"),
])
navigation.run()
