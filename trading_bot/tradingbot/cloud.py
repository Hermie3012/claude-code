"""Einstellungen für den Online-Betrieb (Streamlit Community Cloud, GitHub Actions).

Geheime Werte (Token, Passwörter) stehen NIE im Code. Sie kommen aus:
- Umgebungsvariablen (z. B. GitHub Actions), oder
- st.secrets (Streamlit Community Cloud: App → Settings → Secrets).

Wichtige Namen:
    APP_PASSWORD  Passwort für die App (leer = kein Passwortschutz)
    GIST_TOKEN    GitHub-Token mit Berechtigung "Gists: Read and write"
"""

import hmac
import os
import threading

from tradingbot.storage import GistBackend, Sync

_sync: Sync | None = None
_sync_lock = threading.Lock()


def get_secret(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:  # keine secrets.toml vorhanden o. Ä.
        return None
    return str(value) if value else None


def get_sync() -> Sync | None:
    """Der gemeinsame Abgleich für diesen Server-Prozess (None = kein Online-Speicher)."""
    global _sync
    token = get_secret("GIST_TOKEN")
    if not token:
        return None
    with _sync_lock:
        if _sync is None:
            _sync = Sync(GistBackend(token))
        return _sync


def password_ok(entered: str, expected: str) -> bool:
    # compare_digest: Vergleich dauert immer gleich lang (kein Erraten über die Zeit)
    return hmac.compare_digest(entered.encode(), expected.encode())


def require_password() -> None:
    """Zeigt eine Passwortabfrage, wenn APP_PASSWORD gesetzt ist, und stoppt bis zur Eingabe."""
    import streamlit as st

    expected = get_secret("APP_PASSWORD")
    if not expected or st.session_state.get("auth_ok"):
        return
    st.title("🔒 Trading-Bot")
    st.caption("Lernprojekt – nur Spielgeld. Bitte Passwort eingeben.")
    with st.form("login"):
        entered = st.text_input("Passwort", type="password")
        submitted = st.form_submit_button("Anmelden")
    if submitted:
        if password_ok(entered, expected):
            st.session_state.auth_ok = True
            st.rerun()
        st.error("Falsches Passwort.")
    st.stop()
