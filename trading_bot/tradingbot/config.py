"""Zentrale Standardwerte. Übernommen aus backtest_momentum.py."""

from pathlib import Path

# Ordner für die lokale SQLite-Datenbank
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "trading_bot.db"

DEFAULT_WATCHLIST = [
    "NVDA", "MU", "GOOGL", "MSFT", "AMD", "AVGO", "NOW", "NKE",
    "IFX.DE", "ENR.DE", "SAP.DE", "SIE.DE", "RHM.DE", "ALV.DE",
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
