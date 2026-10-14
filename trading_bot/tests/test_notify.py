"""Tests für die tägliche E-Mail – ohne Internet und ohne echten Versand."""

import importlib.util
import smtplib
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tradingbot import config, data
from tradingbot.backtest import Costs
from tradingbot.notify import EmailConfig, NotifyError, build_report, load_email_config, send_email
from tradingbot.portfolio import place_order
from tradingbot.signals import load_settings, save_settings
from tradingbot.strategy import StrategyParams
from tradingbot.watchlist import add_ticker, get_watchlist, remove_ticker

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Test-Datenbank mit 3 Aktien (A steigt am stärksten) und Fake-Kursen."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=100)
    trend = {"AAA.DE": 0.004, "BBB.DE": 0.002, "CCC.DE": -0.001}

    def downloader(symbols, start):
        return pd.DataFrame({s: 100 * (1 + trend.get(s, 0.0)) ** np.arange(len(idx)) for s in symbols}, index=idx)

    monkeypatch.setattr(data, "load_prices", partial(data.load_prices, downloader=downloader,
                                                     currency_lookup=lambda t: None, sleep=lambda s: None))
    for name in ("watchlist", "scanlist"):
        for t in get_watchlist(path, name=name):
            remove_ticker(t, path, name=name)
    for t in trend:
        add_ticker(t, path)
    save_settings(StrategyParams(lookback=20, top_n=1), use_scan=False, db_path=path)
    return path


def test_settings_roundtrip(tmp_path):
    p = StrategyParams(lookback=33, top_n=4, rebalance_days=7, only_positive=True)
    save_settings(p, use_scan=False, db_path=tmp_path / "x.db")
    assert load_settings(tmp_path / "x.db") == (p, False)
    assert load_settings(tmp_path / "y.db") == (StrategyParams(), True)   # Standardwerte


def test_report_content(db):
    place_order("CCC.DE", "BUY", 10, 100.0, "2024-01-01", Costs(fee_rate=0), db_path=db)
    subject, body = build_report(db)
    assert "1× KAUFEN, 1× VERKAUFEN" in subject and "Anpassung fällig" in subject
    assert "KEINE ANLAGEBERATUNG" in body
    buy_part = body.split("KAUFEN (1):")[1].split("VERKAUFEN")[0]
    assert "AAA.DE" in buy_part and "Rang   1" in buy_part
    assert "CCC.DE" in body.split("VERKAUFEN (1):")[1].split("HALTEN")[0]
    assert "Gesamtwert" in body and "49." in body          # deutsches Format, z. B. 49.9xx,xx €


def test_report_when_lists_empty(db):
    for t in get_watchlist(db):
        remove_ticker(t, db)
    subject, body = build_report(db)
    assert "konnten nicht berechnet werden" in subject
    assert "Watchlist und Scan-Liste sind leer" in body


def write(tmp_path, text):
    p = tmp_path / "email_config.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_email_config(tmp_path):
    with pytest.raises(NotifyError, match="fehlt"):
        load_email_config(tmp_path / "nope.toml")
    example = (ROOT / "email_config.example.toml").read_text(encoding="utf-8")
    with pytest.raises(NotifyError, match="Platzhalter"):
        load_email_config(write(tmp_path, example))
    with pytest.raises(NotifyError, match="app_password"):
        load_email_config(write(tmp_path, 'sender = "a@gmail.com"\nrecipient = "b@gmail.com"'))
    cfg = load_email_config(write(tmp_path, 'sender = "a@gmail.com"\napp_password = "abcd efgh ijkl mnop"\n'
                                            'recipient = "b@gmail.com"'))
    assert cfg.app_password == "abcdefghijklmnop" and cfg.smtp_host == "smtp.gmail.com"


class FakeSMTP:
    sent = []
    fail_login = False

    def __init__(self, host, port, context=None, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_send_email(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    cfg = EmailConfig("a@gmail.com", "pw", "b@gmail.com")
    send_email(cfg, "Betreff ä", "Text ü")
    msg = FakeSMTP.sent[-1]
    assert msg["To"] == "b@gmail.com" and msg["Subject"] == "Betreff ä"
    FakeSMTP.fail_login = True
    with pytest.raises(NotifyError, match="App-Passwort"):
        send_email(cfg, "x", "y")
    FakeSMTP.fail_login = False


def load_cli():
    spec = importlib.util.spec_from_file_location("notify_cli", ROOT / "notify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_dry_run(db, capsys):
    assert load_cli().main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Betreff: Trading-Bot (Spielgeld)" in out and "nichts gesendet" in out
    assert "ok (dry-run)" in (db.parent / "notify.log").read_text(encoding="utf-8")


def test_cli_missing_config(db, capsys, monkeypatch):
    import tradingbot.notify as n
    monkeypatch.setattr(n, "CONFIG_PATH", db.parent / "fehlt.toml")
    cli = load_cli()
    monkeypatch.setattr(cli, "load_email_config", lambda: n.load_email_config(db.parent / "fehlt.toml"))
    assert cli.main([]) == 1
    assert "email_config.example.toml" in capsys.readouterr().err
