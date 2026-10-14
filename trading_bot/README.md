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
├── app.py              # Einstieg: legt die Seiten und ihre Namen fest
├── views/              # die Seiten (Start, Daten, Backtest, später Depot, Signale)
├── tradingbot/         # die eigentliche Logik (ohne Oberfläche)
│   ├── config.py       # Standardwerte (Watchlist, Lookback, Gebühren …)
│   ├── db.py           # SQLite-Datenbank (Tabellen anlegen, Verbindung)
│   ├── data.py         # Kurse laden, cachen, in EUR umrechnen
│   ├── strategy.py     # Momentum-Signale
│   ├── backtest.py     # Backtest-Simulation und Kennzahlen
│   ├── portfolio.py    # Paper-Depot (virtuelle Orders)
│   ├── signals.py      # Signale und Depot-Anpassung
│   └── watchlist.py    # Watchlist und Scan-Liste
├── tests/              # automatische Tests
├── data/               # lokale SQLite-Datenbank (wird nicht ins Git übernommen)
├── requirements.txt    # benötigte Python-Pakete
└── pytest.ini          # Test-Einstellungen
```

Die Trennung zwischen `views/` (Oberfläche) und `tradingbot/` (Logik) sorgt
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

## Die Strategie (Momentum)

1. Für jede Aktie wird die Rendite der letzten **Lookback** Handelstage berechnet
   (Standard: 60). Das ist das „Momentum“.
2. Alle **Rebalancing-Tage** (Standard: 10) werden die **Top-N** Aktien
   (Standard: 3) gekauft und gleich gewichtet (je 1/N des Depots).
3. Option **„nur positives Momentum“** (Standard: aus): Aktien mit Momentum ≤ 0
   werden nicht gekauft, ihr Anteil bleibt als Cash liegen.

**Kein Blick in die Zukunft:** Die Entscheidung an Tag t nutzt nur Kurse bis
einschließlich Tag t; gehandelt wird erst am nächsten Handelstag. Ein Test
(`test_no_look_ahead`) verändert absichtlich alle späteren Kurse und prüft, dass
sich frühere Entscheidungen dadurch nicht ändern.

## Der Backtest

- **Zeitablauf:** Entscheidung nach Börsenschluss an Tag t → Order zum Schlusskurs
  an Tag t+1 → Gewinn/Verlust ab Tag t+2. So nutzt die Strategie nie Kurse, die
  sie bei der Entscheidung noch nicht kennen konnte.
- **Drift:** Zwischen zwei Umschichtungen verändern sich die Anteile mit den
  Kursen (wie in echt). Beim Umschichten wird wieder auf je 1/N gebracht.
- **Gebühren:** prozentual vom Ordervolumen und/oder fix pro Order.
- **Benchmark:** alle Aktien der Watchlist zu gleichen Teilen kaufen und liegen lassen.
- **Kennzahlen:** Gesamtrendite, Rendite p. a., Volatilität, Sharpe-Ratio
  (ohne risikolosen Zins), maximaler Drawdown.

## Das Paper-Depot

- Startkapital **50.000 € Spielgeld** (beim Zurücksetzen änderbar).
- Orders werden zum **letzten verfügbaren Schlusskurs** (in €) ausgeführt,
  nur **ganze Aktien**. Gebühren wie im Backtest einstellbar.
- Gespeichert werden nur die Orders. Cash, Positionen und Gewinn/Verlust
  werden daraus jedes Mal neu berechnet – so passen Kontostand und Historie
  immer zusammen.
- **Einstandskurs** = Durchschnittspreis inklusive Kaufgebühren.
  **Realisiert** = Gewinn/Verlust aus Verkäufen, **unrealisiert** = nur auf dem Papier.

## Signale

- **Universum:** Watchlist plus (abschaltbar) die **Scan-Liste**. Die Scan-Liste
  ist mit deutschen Standardwerten (DAX) vorbelegt – Stand beim Erstellen der
  App, Indizes ändern sich. Bearbeiten auf der Seite **Daten**.
- **KAUFEN** = im Ziel-Depot (Top-N), aber nicht in deinem Depot ·
  **VERKAUFEN** = in deinem Depot, aber nicht mehr im Ziel-Depot ·
  **HALTEN** = in beiden. Jede Zeile hat eine Begründung (Rang, Momentum).
- **Depot anpassen:** zeigt erst eine **Vorschau** der Orders, ausgeführt wird
  erst nach Bestätigung. Ziel: je 1/N des Depotwerts, ganze Aktien. Gehaltene
  Positionen werden nur angeglichen, wenn sie mehr als 2 % vom Ziel abweichen
  (abschaltbar). Aktien außerhalb von Watchlist/Scan-Liste bleiben unverändert.
- Die Seite zeigt, wann zuletzt angepasst wurde und ob laut Strategie
  (alle N Handelstage) wieder eine Anpassung fällig ist.

## Fahrplan

1. ✅ Projektstruktur, requirements.txt, README
2. ✅ Daten-Modul: Kurse laden und in SQLite cachen, Watchlist editierbar
3. ✅ Strategie-Modul: Momentum-Signale (Lookback, Top-N einstellbar)
4. ✅ Backtest-Seite: Rendite, Sharpe, max. Drawdown, Chart, Gebühren
5. ✅ Paper-Depot: 50.000 € Spielgeld, Orders, Positionen, G/V, Historie
6. ✅ Signal-Seite: Kaufen/Verkaufen-Liste mit Begründung
7. ⬜ Optional: tägliche E-Mail-Benachrichtigung
