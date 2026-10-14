#!/usr/bin/env bash
# ================================================================
#  Trading-Bot (Lernprojekt) – Start per Doppelklick (macOS)
#  Linux: im Terminal "bash start.command" ausführen.
#  Beim ersten Start wird alles automatisch eingerichtet.
# ================================================================
cd "$(dirname "$0")" || exit 1

pause_and_exit() {
    echo
    read -r -p "Zum Schließen Enter drücken … " _
    exit "${1:-1}"
}

echo
echo " =================================================="
echo "  Trading-Bot – Lernprojekt (nur Spielgeld)"
echo "  Keine Anlageberatung, keine echten Orders."
echo " =================================================="
echo

# --- Python 3.11 oder neuer suchen ---
PY=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "FEHLER: Python 3.11 oder neuer wurde nicht gefunden."
    echo
    echo "So geht's:"
    echo " 1. https://www.python.org/downloads/ öffnen und Python herunterladen und installieren."
    echo "    (Das vorinstallierte Python auf dem Mac ist zu alt.)"
    echo " 2. Danach diese Datei erneut doppelklicken."
    pause_and_exit 1
fi

# --- Erster Start: eigene Python-Umgebung im Ordner .venv anlegen ---
if [ ! -x .venv/bin/python ]; then
    echo "Erster Start: Die App wird eingerichtet. Das dauert ein paar Minuten …"
    echo
    if ! "$PY" -m venv .venv; then
        echo "FEHLER: Die Python-Umgebung konnte nicht angelegt werden."
        echo "Linux-Tipp: Paket 'python3-venv' installieren (z. B. sudo apt install python3-venv)."
        rm -rf .venv
        pause_and_exit 1
    fi
fi

# --- Pakete installieren, wenn requirements.txt neu oder geändert ist ---
if ! cmp -s requirements.txt .venv/requirements.installed; then
    echo "Installiere die benötigten Pakete …"
    if ! .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt; then
        echo
        echo "FEHLER: Die Installation hat nicht geklappt (siehe Meldungen oben)."
        echo "Tipp: Internetverbindung prüfen. Hilft das nicht, den Ordner .venv löschen und neu starten."
        pause_and_exit 1
    fi
    cp requirements.txt .venv/requirements.installed
    echo
fi

echo "Die App startet. Der Browser öffnet sich gleich von selbst."
echo "Falls nicht: im Browser http://localhost:8501 eingeben."
echo
echo "ZUM BEENDEN: dieses Fenster schließen (oder Strg+C)."
echo
.venv/bin/python -m streamlit run app.py
