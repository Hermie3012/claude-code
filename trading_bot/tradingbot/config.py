"""Zentrale Standardwerte. Übernommen aus backtest_momentum.py."""

from pathlib import Path

# Ordner für die lokale SQLite-Datenbank
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "trading_bot.db"

DEFAULT_WATCHLIST = [
    "NVDA", "MU", "GOOGL", "MSFT", "AMD", "AVGO", "NOW", "NKE",
    "IFX.DE", "ENR.DE", "SAP.DE", "SIE.DE", "RHM.DE", "ALV.DE",
]
# Scan-Liste: zusätzliche Kandidaten für die Signal-Seite (deutsche Standardwerte).
# ACHTUNG: Stand meines Wissens – Indizes ändern sich. In der App bearbeitbar.
DEFAULT_SCANLIST = [
    "ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE", "BNR.DE",
    "CBK.DE", "CON.DE", "DB1.DE", "DBK.DE", "DHL.DE", "DTE.DE", "DTG.DE", "ENR.DE",
    "EOAN.DE", "FME.DE", "FRE.DE", "G1A.DE", "HEI.DE", "HEN3.DE", "HNR1.DE", "IFX.DE",
    "MBG.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "P911.DE", "PAH3.DE", "QIA.DE", "RHM.DE",
    "RWE.DE", "SAP.DE", "SHL.DE", "SIE.DE", "SRT3.DE", "SY1.DE", "VNA.DE", "VOW3.DE",
    "ZAL.DE",
]
DEFAULT_START = "2023-01-01"
DEFAULT_LOOKBACK = 60        # Tage für die Momentum-Berechnung
DEFAULT_TOP_N = 3            # so viele Aktien gleichzeitig halten
DEFAULT_REBALANCE_DAYS = 10  # alle X Handelstage neu sortieren
DEFAULT_FEE = 0.001          # 0,1 % Gebühr pro gehandeltem Volumen
START_CAPITAL = 50_000.0     # Spielgeld in Euro

DISCLAIMER = (
    "⚠️ **Lernprojekt – keine Anlageberatung.** Alle Signale und Ergebnisse "
    "dienen nur zu Lernzwecken. Es wird ausschließlich mit Spielgeld "
    "gehandelt, es gibt keine Verbindung zu einem echten Broker. "
    "Vergangene Wertentwicklung ist kein Indikator für die Zukunft."
)
