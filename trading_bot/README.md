# 📈 Trading-Bot (Lernprojekt)

> ⚠️ **Keine Anlageberatung.** Dieses Projekt dient nur zum Lernen.
> Es wird ausschließlich mit **Spielgeld** gehandelt (Paper-Trading),
> es gibt **keine** Verbindung zu einem echten Broker.

Die App scannt eine Watchlist von Aktien, berechnet Momentum-Signale
(Basis: `../backtest_momentum.py`), testet die Strategie auf historischen
Daten und simuliert ein Depot mit 50.000 € Startkapital.

## Voraussetzungen

- Python **3.11 oder neuer** (`python --version` prüfen)
- Internetzugang (Kursdaten kommen von Yahoo Finance über `yfinance`)

## Installation

Im Terminal in diesen Ordner wechseln (`trading_bot/`) und dann:

```bash
# 1. Virtuelle Umgebung anlegen (hält die Pakete vom restlichen System getrennt)
python -m venv .venv

# 2. Aktivieren
#    macOS/Linux:
source .venv/bin/activate
#    Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 3. Pakete installieren
pip install -r requirements.txt
```

## Starten

```bash
streamlit run app.py
```

Der Browser öffnet sich automatisch (sonst: <http://localhost:8501>).

## Tests ausführen

```bash
pytest
```

## Projektstruktur

```
trading_bot/
├── app.py              # Startseite der Streamlit-App
├── pages/              # weitere Seiten (Daten, Backtest, Depot, Signale)
├── tradingbot/         # die eigentliche Logik (ohne Oberfläche)
│   ├── config.py       # Standardwerte (Watchlist, Lookback, Gebühren …)
│   ├── db.py           # SQLite-Datenbank (Tabellen anlegen, Verbindung)
│   ├── watchlist.py    # Watchlist lesen/ändern
│   └── data.py         # Kurse laden, cachen, in EUR umrechnen
├── tests/              # automatische Tests
├── data/               # lokale SQLite-Datenbank (wird nicht ins Git übernommen)
├── requirements.txt    # benötigte Python-Pakete
└── pytest.ini          # Test-Einstellungen
```

Die Trennung zwischen `pages/` (Oberfläche) und `tradingbot/` (Logik) sorgt
dafür, dass sich die Logik ohne Browser testen lässt.

## Kursdaten – wie funktioniert der Cache?

- Kurse werden in `data/trading_bot.db` gespeichert und **12 Stunden** lang
  wiederverwendet. Danach (oder mit „Alles neu laden“) wird neu geladen.
- Es werden **bereinigte Kurse** verwendet (Dividenden/Splits herausgerechnet).
  Deshalb wird beim Aktualisieren die ganze Historie neu geladen, nicht nur der
  letzte Tag – sonst entstünden künstliche Kurssprünge.
- **Währungen:** Alle Kurse werden in Euro umgerechnet, mit dem Wechselkurs
  des jeweiligen Tages (z. B. `EURUSD=X`). Die Währung wird an der Börsen-Endung
  erkannt: ohne Endung = USD, `.DE` = EUR, `.L` = Pence usw.
- **Fehler / Rate-Limits:** Schlägt ein Abruf fehl, wird er zweimal mit
  Pause wiederholt. Klappt es dann nicht, zeigt die App eine Meldung und nutzt –
  falls vorhanden – die zuletzt gespeicherten Kurse.

## Fahrplan

1. ✅ Projektstruktur, requirements.txt, README
2. ✅ Daten-Modul: Kurse laden und in SQLite cachen, Watchlist editierbar
3. ⬜ Strategie-Modul: Momentum-Signale (Lookback, Top-N einstellbar)
4. ⬜ Backtest-Seite: Rendite, Sharpe, max. Drawdown, Chart, Gebühren
5. ⬜ Paper-Depot: 50.000 € Spielgeld, Orders, Positionen, G/V, Historie
6. ⬜ Signal-Seite: Kaufen/Verkaufen-Liste mit Begründung
7. ⬜ Optional: tägliche E-Mail-Benachrichtigung
