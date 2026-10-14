"""Minimaltest: Projekt lässt sich importieren und Standardwerte sind plausibel."""

from tradingbot import config


def test_defaults_are_sane():
    assert config.START_CAPITAL == 50_000
    assert 0 < config.DEFAULT_TOP_N <= len(config.DEFAULT_WATCHLIST)
    assert config.DEFAULT_LOOKBACK > 0
    assert 0 <= config.DEFAULT_FEE < 0.05
