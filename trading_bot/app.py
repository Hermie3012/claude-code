"""Einstiegspunkt der Streamlit-App.

Start:  streamlit run app.py
Hier wird festgelegt, welche Seiten es gibt und wie sie in der Seitenleiste heißen.
Der Inhalt jeder Seite liegt im Ordner views/.

Online-Betrieb (z. B. für das iPad): siehe README, Abschnitt "Online nutzen".
Dann schützt ein Passwort die App, und deine Daten werden in einem secret
GitHub Gist gesichert (tradingbot/storage.py).
"""

import streamlit as st

from tradingbot import cloud

st.set_page_config(page_title="Trading-Bot (Lernprojekt)", page_icon="📈", layout="wide")

cloud.require_password()

sync = cloud.get_sync()
if sync is not None:
    sync.ensure_pulled()
    if sync.error:
        st.error(sync.error)

navigation = st.navigation([
    st.Page("views/0_Start.py", title="Start", icon="📈", default=True),
    st.Page("views/1_Daten.py", title="Daten", icon="🗂️"),
    st.Page("views/2_Backtest.py", title="Backtest", icon="🧪"),
    st.Page("views/3_Depot.py", title="Depot", icon="💼"),
    st.Page("views/4_Signale.py", title="Signale", icon="🚦"),
    st.Page("views/5_Nachrichten.py", title="Nachrichten", icon="📰"),
])
try:
    navigation.run()
finally:
    # Auch wenn eine Seite mit st.stop()/st.rerun() endet: Änderungen sichern
    if sync is not None:
        sync.push_if_changed()
