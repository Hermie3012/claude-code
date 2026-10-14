"""Tests für den Online-Speicher – mit einem Fake-Gist statt GitHub."""

from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from tradingbot import cloud, config
from tradingbot.backtest import Costs
from tradingbot.portfolio import get_state, place_order
from tradingbot.storage import (GIST_FILENAME, GistBackend, StorageError, Sync, export_user_data,
                                import_user_data)
from tradingbot.watchlist import add_ticker, get_watchlist

APP = str(Path(__file__).resolve().parent.parent / "app.py")


class FakeBackend:
    def __init__(self, data=None, fail_load=False, fail_save=False):
        self.data, self.fail_load, self.fail_save, self.saves = data, fail_load, fail_save, 0

    def load(self):
        if self.fail_load:
            raise StorageError("kein Netz")
        return self.data

    def save(self, data):
        if self.fail_save:
            raise StorageError("kein Netz")
        self.data, self.saves = data, self.saves + 1


@pytest.fixture
def db(tmp_path):
    return tmp_path / "a.db"


def test_export_import_roundtrip(db, tmp_path):
    add_ticker("TSLA", db)
    place_order("TSLA", "BUY", 3, 100.0, "2024-01-02", Costs(fee_rate=0), db_path=db)
    data = export_user_data(db)
    other = tmp_path / "b.db"
    import_user_data(data, other)
    assert get_watchlist(other) == get_watchlist(db)
    assert get_state(other).positions["TSLA"].shares == 3
    assert "prices" not in data["tables"]                    # Caches werden nicht gespeichert


def test_import_rejects_unknown_version(db):
    with pytest.raises(StorageError):
        import_user_data({"version": 99, "tables": {}}, db)


def test_first_start_creates_gist_after_change(db):
    backend = FakeBackend(data=None)
    sync = Sync(backend, db)
    assert sync.ensure_pulled()
    get_watchlist(db)                                         # erster Besuch: Standardliste
    sync.push_if_changed()
    assert backend.saves == 1
    sync.push_if_changed()
    assert backend.saves == 1                                 # nichts geändert -> nicht speichern


def test_restart_restores_data(db, tmp_path):
    backend = FakeBackend()
    sync = Sync(backend, db)
    sync.ensure_pulled()
    add_ticker("TSLA", db)
    sync.push_if_changed()

    fresh = tmp_path / "neustart.db"                          # Server-Neustart: leere Datenbank
    sync2 = Sync(backend, fresh)
    assert sync2.ensure_pulled()
    assert "TSLA" in get_watchlist(fresh)
    sync2.push_if_changed()
    assert backend.saves == 1                                 # Laden allein speichert nichts


def test_failed_load_never_overwrites(db):
    backend = FakeBackend(data={"version": 1, "tables": {"watchlist": [{"ticker": "ECHT", "added_at": "x"}]}},
                          fail_load=True)
    sync = Sync(backend, db)
    assert not sync.ensure_pulled()
    assert "NICHT gespeichert" in sync.error
    get_watchlist(db)
    sync.push_if_changed()
    assert backend.saves == 0                                 # echte Daten bleiben unangetastet
    backend.fail_load = False
    assert sync.ensure_pulled()                               # nächster Versuch klappt
    assert get_watchlist(db) == ["ECHT"]


def test_failed_save_is_retried(db):
    backend = FakeBackend(fail_save=True)
    sync = Sync(backend, db)
    sync.ensure_pulled()
    add_ticker("TSLA", db)
    sync.push_if_changed()
    assert "fehlgeschlagen" in sync.error and backend.saves == 0
    backend.fail_save = False
    sync.push_if_changed()
    assert backend.saves == 1 and sync.error is None


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload
        self.ok = status < 400

    def json(self):
        return self._payload


class FakeSession(requests.Session):
    """Simuliert die GitHub-Gist-API."""

    def __init__(self, status=200):
        super().__init__()
        self.status, self.gists, self.calls = status, {}, []

    def request(self, method, url, **kw):
        self.calls.append((method, url.replace("https://api.github.com", "")))
        if self.status != 200:
            return FakeResponse(self.status, {})
        path = url.replace("https://api.github.com", "")
        if method == "GET" and path == "/gists":
            return FakeResponse(200, [{"id": i, "files": g} for i, g in self.gists.items()])
        if method == "POST":
            self.gists["g1"] = {GIST_FILENAME: {"content": kw["json"]["files"][GIST_FILENAME]["content"]}}
            assert kw["json"]["public"] is False                 # immer privat
            return FakeResponse(201, {"id": "g1"})
        gid = path.split("/")[-1]
        if method == "PATCH":
            self.gists[gid].update(kw["json"]["files"])
            return FakeResponse(200, {"id": gid})
        return FakeResponse(200, {"files": self.gists[gid]})


def test_gist_backend_create_find_update():
    session = FakeSession()
    backend = GistBackend("tok", session)
    assert backend.load() is None
    backend.save({"version": 1, "tables": {"x": [1]}})
    backend.save({"version": 1, "tables": {"x": [2]}})
    assert [m for m, _ in session.calls].count("POST") == 1     # nur einmal anlegen
    assert GistBackend("tok", session).load()["tables"]["x"] == [2]
    assert session.headers["Authorization"] == "Bearer tok"


@pytest.mark.parametrize("status,text", [(401, "Token ab"), (403, "Berechtigung"), (500, "500")])
def test_gist_backend_errors(status, text):
    with pytest.raises(StorageError, match=text):
        GistBackend("tok", FakeSession(status)).load()


def test_get_secret_prefers_environment(monkeypatch):
    monkeypatch.setenv("GIST_TOKEN", "aus-env")
    assert cloud.get_secret("GIST_TOKEN") == "aus-env"
    monkeypatch.delenv("GIST_TOKEN")
    assert cloud.get_secret("GIST_TOKEN") is None


def test_password_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    at = AppTest.from_file(APP, default_timeout=10)
    at.secrets["APP_PASSWORD"] = "geheim"
    at.run()
    assert at.title[0].value == "🔒 Trading-Bot" and not at.warning   # App-Inhalt verborgen
    at.text_input[0].input("falsch")
    at.button[0].click().run()
    assert any("Falsches Passwort" in e.value for e in at.error)
    at.text_input[0].input("geheim")
    at.button[0].click().run()
    assert not at.exception
    assert "keine Anlageberatung" in at.warning[0].value                 # Startseite sichtbar


def test_app_without_password_and_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    at = AppTest.from_file(APP, default_timeout=10).run()
    assert not at.exception and "keine Anlageberatung" in at.warning[0].value


def test_notify_env_email_config(monkeypatch, tmp_path):
    from tradingbot.notify import load_email_config
    for k, v in {"SMTP_SENDER": "a@gmail.com", "SMTP_APP_PASSWORD": "ab cd", "SMTP_RECIPIENT": "b@gmail.com"}.items():
        monkeypatch.setenv(k, v)
    cfg = load_email_config(tmp_path / "gibtsnicht.toml")
    assert (cfg.sender, cfg.app_password, cfg.recipient) == ("a@gmail.com", "abcd", "b@gmail.com")


def test_app_syncs_changes_to_gist(tmp_path, monkeypatch):
    """Ganze App: Laden aus dem Gist beim Start, Speichern nach einer Änderung."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    saved = {"version": 1, "tables": {"watchlist": [{"ticker": "SAP.DE", "added_at": "x"}],
                                      "meta": [{"key": "watchlist_seeded", "value": "1"}]}}
    backend = FakeBackend(data=saved)
    monkeypatch.setattr(cloud, "_sync", None)
    monkeypatch.setattr(cloud, "GistBackend", lambda token: backend)

    at = AppTest.from_file(APP, default_timeout=10)
    at.secrets["GIST_TOKEN"] = "tok"
    at.run()
    assert not at.exception and backend.saves == 0             # nur geladen, nichts geändert
    at.switch_page("views/1_Daten.py").run()
    assert any("SAP.DE" in m.value for m in at.markdown)        # Watchlist aus dem Gist angezeigt
    at.text_input(key="watchlist_new").input("TSLA")
    next(b for b in at.button if "Hinzufügen" in b.label).click().run()
    assert backend.saves >= 1
    tickers = [r["ticker"] for r in backend.data["tables"]["watchlist"]]
    assert tickers == ["SAP.DE", "TSLA"]
