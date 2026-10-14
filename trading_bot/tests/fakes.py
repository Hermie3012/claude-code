"""Gemeinsame Test-Helfer: erfundene Kursdaten statt Internet."""

import pandas as pd

DATES = pd.bdate_range("2024-01-01", "2024-01-10")  # 8 Handelstage


class FakeDownloader:
    """Liefert feste Kurse und zählt, welche Symbole angefragt wurden."""

    def __init__(self, prices=None, fail_times=0, missing=()):
        self.prices = prices or {
            "SAP.DE": 100.0,      # EUR
            "NVDA": 110.0,        # USD
            "EURUSD=X": 1.10,     # 1 EUR = 1,10 USD
            "VOD.L": 7000.0,      # Pence
            "EURGBP=X": 0.70,     # 1 EUR = 0,70 GBP
        }
        self.fail_times = fail_times
        self.missing = set(missing)
        self.calls: list[list[str]] = []

    def __call__(self, symbols, start):
        self.calls.append(list(symbols))
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("Too Many Requests")  # simuliertes Rate-Limit
        dates = DATES[DATES >= pd.Timestamp(start)]
        cols = {s: [self.prices[s]] * len(dates) for s in symbols if s not in self.missing}
        return pd.DataFrame(cols, index=dates)
