# 📈 Trading-Bot (Lernprojekt)

> ⚠️ **Keine Anlageberatung.** Dieses Projekt dient nur zum Lernen.
> Es wird ausschließlich mit **Spielgeld** gehandelt (Paper-Trading),
> es gibt **keine** Verbindung zu einem echten Broker.

Die App scannt eine Watchlist von Aktien, berechnet Momentum-Signale
(Basis: `../backtest_momentum.py`), testet die Strategie auf historischen
Daten und simuliert ein Depot mit 50.000 € Startkapital.

## 🚀 Schnellstart (ohne Vorkenntnisse)

1. **Python installieren** (einmalig): <https://www.python.org/downloads/>
   herunterladen und installieren. **Windows:** im Installer unbedingt
   „Add python.exe to PATH“ ankreuzen.
2. **Code herunterladen:** auf GitHub den grünen Knopf **„Code“ → „Download ZIP“**
   wählen und die ZIP-Datei entpacken. (Solange die App noch nicht in `main`
   übernommen ist: <https://github.com/Hermie3012/claude-code/archive/refs/heads/trading-bot-app.zip>)
3. Im entpackten Ordner in den Unterordner **`trading_bot`** wechseln und
   **doppelklicken**:
   - **Windows:** `start.bat`
   - **Mac:** `start.command` – beim allerersten Mal ggf. **Rechtsklick → Öffnen**,
     weil macOS Dateien aus dem Internet zunächst blockiert.
   - **Linux:** im Terminal `bash start.command`
4. Beim ersten Start werden die Pakete installiert (ein paar Minuten, Internet nötig).
   Danach öffnet sich die App im Browser. Ab dem zweiten Start geht es schnell.
5. **Beenden:** das schwarze Fenster (Terminal) schließen.

Deine Daten (Watchlist, Depot, Kurse) liegen in `trading_bot/data/` auf deinem
Computer. Wenn du eine neue Version herunterlädst, kopiere diesen Ordner mit,
damit dein Depot erhalten bleibt.

## 📱 Online nutzen (z. B. auf dem iPad)

Die App kann kostenlos bei **Streamlit Community Cloud** laufen. Dann öffnest du
sie einfach in Safari – kein Computer nötig. Alle Schritte gehen im iPad-Browser.

**So funktioniert es:** Streamlit holt den Code aus deinem GitHub-Repository.
Deine Daten (Watchlist, Depot, Orders, Einstellungen) werden zusätzlich in
einem „secret“ **GitHub Gist** gespeichert – sonst wären sie nach jedem
Neustart des Servers weg. Ein Passwort schützt die App.

### Schritt 1: Code nach `main` übernehmen

Auf GitHub den Pull Request „Trading-Bot-App …“ öffnen → **Merge pull request**
→ **Confirm merge**. (Die tägliche E-Mail funktioniert nur von `main` aus.)

### Schritt 2: GitHub-Token für den Daten-Speicher erstellen

1. <https://github.com/settings/personal-access-tokens/new> öffnen
   (oder: Profilbild → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token).
2. **Token name:** `trading-bot` · **Expiration:** z. B. 1 Jahr.
3. **Repository access:** „Public repositories“ genügt.
4. **Permissions → Account permissions → Gists:** „Read and write“.
5. **Generate token** → den Token (beginnt mit `github_pat_`) kopieren und
   sicher aufbewahren (z. B. in der Notizen-App). Er wird nur einmal angezeigt.

### Schritt 3: App bei Streamlit veröffentlichen

1. <https://share.streamlit.io> öffnen → **Continue with GitHub** → Zugriff erlauben.
2. **Create app** → „Deploy a public app from GitHub“ wählen.
3. Eintragen:
   - **Repository:** `Hermie3012/claude-code`
   - **Branch:** `main`
   - **Main file path:** `trading_bot/app.py`
   - **App URL:** ein Name nach Wahl, z. B. `mein-trading-bot`
4. **Advanced settings** öffnen:
   - **Python version:** 3.12
   - **Secrets:** folgendes eintragen (eigene Werte einsetzen):
     ```toml
     APP_PASSWORD = "ein-passwort-das-du-dir-ausdenkst"
     GIST_TOKEN = "github_pat_..."
     ```
5. **Save** → **Deploy**. Die erste Einrichtung dauert ein paar Minuten.

### Schritt 4: Auf dem iPad benutzen

Die App-Adresse (z. B. `https://mein-trading-bot.streamlit.app`) in Safari
öffnen und das Passwort eingeben. Tipp: Teilen-Knopf → **„Zum Home-Bildschirm“**
– dann hast du ein App-Symbol.

### Schritt 5 (optional): Tägliche E-Mail ohne Computer

Läuft über **GitHub Actions** (`.github/workflows/trading-bot-notify.yml`),
Montag–Freitag um 22:45 Uhr (Sommerzeit) bzw. 21:45 Uhr (Winterzeit).

1. Gmail-App-Passwort erstellen (siehe „Tägliche E-Mail“ → Schritt 1 weiter unten).
2. Auf GitHub im Repository: **Settings → Secrets and variables → Actions →
   New repository secret**, vier Secrets anlegen:
   `GIST_TOKEN` (wie oben), `SMTP_SENDER` (deine Gmail-Adresse),
   `SMTP_APP_PASSWORD` (Gmail-App-Passwort), `SMTP_RECIPIENT` (Empfänger).
3. Tab **Actions** öffnen. Falls GitHub fragt: Workflows aktivieren
   („I understand my workflows, go ahead and enable them“).
4. Testen: **Trading-Bot Signal-E-Mail → Run workflow**. Nach 1–2 Minuten sollte
   die E-Mail ankommen; bei einem roten ❌ zeigt das Protokoll den Grund.

### Gut zu wissen

- **Einschlafen:** Nach ca. 12 Stunden ohne Besuch schläft die App ein. Beim
  nächsten Öffnen auf **„Yes, get this app back up!“** tippen – das dauert
  1–2 Minuten. Deine Daten bleiben erhalten (Gist).
- **Rate-Limits:** Yahoo bremst Anfragen von Cloud-Servern manchmal aus. Dann
  zeigt die App eine Meldung – einfach später erneut versuchen.
- **Datenschutz:** Ein „secret“ Gist ist nirgends öffentlich gelistet, aber wer
  den genauen Link kennt, kann ihn lesen. Für ein Spielgeld-Depot unkritisch.
  Den Token niemals weitergeben; falls doch passiert: auf GitHub löschen und neu erstellen.
- **Speichern:** Jede Änderung wird automatisch gesichert. Ist der Speicher
  nicht erreichbar, zeigt die App eine rote Meldung – dann lieber nichts ändern
  und später neu laden.
- Lokal auf einem Computer (ohne diese Secrets) läuft die App wie gehabt, ohne
  Passwort und ohne Gist.

## Voraussetzungen

- Python **3.11 oder neuer** (`python --version` prüfen)
- Internetzugang (Kursdaten kommen von Yahoo Finance über `yfinance`)

## Installation (manuell, für Fortgeschrittene)

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
├── notify.py           # tägliche Signal-E-Mail (separat starten)
├── start.bat           # Start per Doppelklick (Windows)
├── start.command       # Start per Doppelklick (Mac) bzw. bash start.command (Linux)
├── .streamlit/         # Streamlit-Einstellungen (z. B. keine E-Mail-Abfrage beim Start)
├── email_config.example.toml  # Vorlage für die E-Mail-Zugangsdaten
├── views/              # die Seiten (Start, Daten, Backtest, später Depot, Signale)
├── tradingbot/         # die eigentliche Logik (ohne Oberfläche)
│   ├── config.py       # Standardwerte (Watchlist, Lookback, Gebühren …)
│   ├── db.py           # SQLite-Datenbank (Tabellen anlegen, Verbindung)
│   ├── data.py         # Kurse laden, cachen, in EUR umrechnen
│   ├── strategy.py     # Momentum-Signale
│   ├── backtest.py     # Backtest-Simulation und Kennzahlen
│   ├── portfolio.py    # Paper-Depot (virtuelle Orders)
│   ├── signals.py      # Signale und Depot-Anpassung
│   ├── notify.py       # E-Mail-Text bauen und senden
│   ├── news.py         # Börsennachrichten laden und gewichten
│   ├── cloud.py        # Online-Betrieb: Secrets, Passwort, Abgleich
│   ├── storage.py      # Daten im GitHub Gist sichern/laden
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

## Nachrichten

Die Seite **Nachrichten** sammelt die neuesten Meldungen von Yahoo Finance
(meist auf Englisch) zu deinen Depot-Aktien, der Watchlist, optional der
Scan-Liste und zum Gesamtmarkt (DAX, S&P 500).

- Taucht dieselbe Nachricht bei mehreren Aktien auf, erscheint sie **einmal**
  mit allen betroffenen Aktien.
- **Wichtigste zuerst:** jede betroffene Aktie bringt Punkte (Depot 3,
  Watchlist 2, Gesamtmarkt 2, Scan-Liste 1); nach 24 Stunden zählt eine
  Nachricht nur noch halb so viel.
- Neben jeder Aktie steht ihre **Kursänderung am letzten Handelstag** – ein
  Hinweis, aber kein Beweis, dass die Nachricht der Grund war.
- Nachrichten werden 2 Stunden zwischengespeichert („Neu laden“ holt sofort
  neue); Nachrichten älter als 30 Tage werden gelöscht.

## Tägliche E-Mail

`notify.py` berechnet die Signale (mit den Einstellungen, die du zuletzt auf
der Seite **Signale** gewählt hast) und schickt dir eine E-Mail mit der
KAUFEN/VERKAUFEN-Liste, dem Depotwert und ob eine Anpassung fällig ist.
Es werden **keine Orders ausgeführt** – das machst du selbst in der App.

### 1. Gmail-App-Passwort erstellen

Gmail lässt Programme nicht mit deinem normalen Passwort senden. Du brauchst
ein **App-Passwort**:

1. Unter <https://myaccount.google.com/security> die
   **Bestätigung in zwei Schritten** einschalten (falls noch nicht aktiv).
2. <https://myaccount.google.com/apppasswords> öffnen, einen Namen eingeben
   (z. B. „Trading-Bot“) und auf **Erstellen** klicken.
3. Das angezeigte 16-stellige Passwort kopieren (Leerzeichen sind egal).

### 2. Zugangsdaten eintragen

Im Ordner `trading_bot/` die Datei `email_config.example.toml` **kopieren**,
die Kopie `email_config.toml` nennen und darin die Platzhalter `DEIN_…`
ersetzen. Diese Datei wird **nicht** ins Git übernommen – gib sie niemandem.

### 3. Testen

Terminal öffnen, in den Ordner `trading_bot/` wechseln, virtuelle Umgebung
aktivieren (siehe „Installation“) und dann:

```bash
python notify.py --dry-run   # zeigt die E-Mail nur an
python notify.py             # sendet sie wirklich
```

Bei Problemen steht eine verständliche Fehlermeldung im Terminal und in
`data/notify.log`.

### 4. Täglich automatisch starten

Welches Betriebssystem hast du?
- **Windows**: Startmenü-Knopf mit dem Fenster-Logo unten links.
- **macOS**: Apfel-Logo oben links.
- **Linux**: wenn du es nicht weißt, hast du es wahrscheinlich nicht 🙂
- Oder im Terminal: `python -c "import platform; print(platform.system())"`
  (gibt `Windows`, `Darwin` = macOS oder `Linux` aus).

Vorschlag: **Montag bis Freitag um 22:45 Uhr** – dann sind auch die
US-Börsen (Schluss 22:00 Uhr deutscher Zeit) geschlossen. Der Computer muss
zu dieser Zeit eingeschaltet sein (nicht im Ruhezustand).

In den Befehlen unten `PFAD` durch den echten Pfad zum Ordner `trading_bot`
ersetzen (z. B. `C:\Users\Max\claude-code\trading_bot` oder
`/Users/max/claude-code/trading_bot`).

**Windows** – PowerShell öffnen und eingeben (eine Zeile):

```powershell
schtasks /Create /SC WEEKLY /D MO,TUE,WED,THU,FRI /ST 22:45 /TN "TradingBot-Signale" /TR "\"PFAD\.venv\Scripts\python.exe\" \"PFAD\notify.py\""
```

Prüfen/ändern/löschen in der **Aufgabenplanung** (Startmenü → „Aufgabenplanung“
suchen) unter „TradingBot-Signale“. Zum sofortigen Testen:
`schtasks /Run /TN "TradingBot-Signale"`.

**macOS und Linux** – Terminal öffnen, `crontab -e` eingeben und diese Zeile
am Ende einfügen (speichern und schließen):

```
45 22 * * 1-5 PFAD/.venv/bin/python PFAD/notify.py
```

`crontab -l` zeigt die eingetragenen Aufgaben. Auf macOS fragt das System beim
ersten Lauf evtl. nach Berechtigungen; falls nichts passiert, unter
*Systemeinstellungen → Datenschutz & Sicherheit → Festplattenvollzugriff*
das Programm `cron` (unter `/usr/sbin/cron`) hinzufügen.

## Fahrplan

1. ✅ Projektstruktur, requirements.txt, README
2. ✅ Daten-Modul: Kurse laden und in SQLite cachen, Watchlist editierbar
3. ✅ Strategie-Modul: Momentum-Signale (Lookback, Top-N einstellbar)
4. ✅ Backtest-Seite: Rendite, Sharpe, max. Drawdown, Chart, Gebühren
5. ✅ Paper-Depot: 50.000 € Spielgeld, Orders, Positionen, G/V, Historie
6. ✅ Signal-Seite: Kaufen/Verkaufen-Liste mit Begründung
7. ✅ Optional: tägliche E-Mail-Benachrichtigung
8. ✅ Nachrichten-Seite mit betroffenen Aktien
9. ✅ Start per Doppelklick (Computer) und Online-Betrieb (iPad)
