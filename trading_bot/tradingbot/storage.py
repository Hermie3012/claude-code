"""Online-Speicher für deine Daten (für den Betrieb im Internet, z. B. auf dem iPad).

Auf Streamlit Community Cloud wird die lokale Datenbank bei jedem Neustart des
Servers gelöscht. Deshalb werden deine eigenen Daten – Watchlist, Scan-Liste,
Orders und Einstellungen – zusätzlich als JSON-Datei in einem "secret"
GitHub Gist gespeichert. Der ist nirgends öffentlich gelistet, aber wer den
genauen Link kennt, kann ihn lesen – also keine echten Geheimnisse hineinlegen.
Kurse und Nachrichten werden nicht gespeichert, die werden neu geladen.

Ablauf:
- Beim Start des Servers: Daten aus dem Gist in die lokale Datenbank laden.
- Nach jeder Aktion: hat sich etwas geändert? Dann ins Gist speichern.
- Schlägt das Laden fehl, wird NICHT gespeichert – sonst könnte eine leere
  Standard-Watchlist deine echten Daten überschreiben.

Ohne GIST_TOKEN (z. B. lokal auf dem Computer) ist all das abgeschaltet.
"""

import hashlib
import json
import threading
from datetime import datetime, timezone

import requests

from tradingbot.db import connect

USER_TABLES = ("watchlist", "scanlist", "orders", "meta")  # nur deine Daten, keine Caches
FORMAT_VERSION = 1

GITHUB_API = "https://api.github.com"
GIST_FILENAME = "trading_bot_data.json"
GIST_DESCRIPTION = "Trading-Bot (Lernprojekt) – gespeicherte Daten"


class StorageError(Exception):
    """Fehler beim Online-Speicher, mit verständlicher Meldung."""


# ---------------------------------------------------------------- Export / Import

def export_user_data(db_path=None) -> dict:
    with connect(db_path) as conn:
        tables = {}
        for table in USER_TABLES:
            cur = conn.execute(f"SELECT * FROM {table} ORDER BY rowid")
            cols = [c[0] for c in cur.description]
            tables[table] = [dict(zip(cols, row)) for row in cur.fetchall()]
    return {"version": FORMAT_VERSION, "saved_at": datetime.now(timezone.utc).isoformat(), "tables": tables}


def import_user_data(data: dict, db_path=None) -> None:
    """Ersetzt deine Daten in der lokalen Datenbank durch die aus `data`."""
    if data.get("version") != FORMAT_VERSION:
        raise StorageError(f"Unbekanntes Datenformat (Version {data.get('version')}).")
    tables = data.get("tables", {})
    with connect(db_path) as conn:
        for table in USER_TABLES:
            allowed = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            conn.execute(f"DELETE FROM {table}")
            for row in tables.get(table, []):
                cols = [c for c in row if c in allowed]   # unbekannte Spalten ignorieren
                if cols:
                    conn.execute(
                        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                        [row[c] for c in cols],
                    )
        # Eine geladene Liste gilt genau so – keine Standardwerte nachträglich untermischen
        for name in ("watchlist", "scanlist"):
            if name in tables:
                conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES (?, '1')", (f"{name}_seeded",))


def fingerprint(data: dict) -> str:
    """Prüfsumme nur über die Tabellen (ohne Zeitstempel) – erkennt Änderungen."""
    return hashlib.sha256(json.dumps(data["tables"], sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------- GitHub Gist

class GistBackend:
    """Liest und schreibt die Datei trading_bot_data.json in einem secret (nicht öffentlichen) Gist."""

    def __init__(self, token: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self.gist_id: str | None = None

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            resp = self.session.request(method, f"{GITHUB_API}{path}", timeout=15, **kwargs)
        except requests.RequestException as exc:
            raise StorageError(f"GitHub nicht erreichbar: {type(exc).__name__}") from exc
        if resp.status_code == 401:
            raise StorageError("GitHub lehnt den Token ab (GIST_TOKEN ungültig oder abgelaufen).")
        if resp.status_code in (403, 404):
            raise StorageError("Der Token hat keine Berechtigung für Gists (Gists: Read and write).")
        if not resp.ok:
            raise StorageError(f"GitHub-Fehler {resp.status_code}.")
        return resp.json()

    def _find(self) -> str | None:
        for page in range(1, 6):
            gists = self._request("GET", "/gists", params={"per_page": 100, "page": page})
            for g in gists:
                if GIST_FILENAME in g.get("files", {}):
                    return g["id"]
            if len(gists) < 100:
                return None
        return None

    def load(self) -> dict | None:
        self.gist_id = self.gist_id or self._find()
        if not self.gist_id:
            return None   # noch nie gespeichert
        file = self._request("GET", f"/gists/{self.gist_id}")["files"].get(GIST_FILENAME)
        if file is None:
            return None
        content = file.get("content", "")
        if file.get("truncated"):
            try:
                resp = self.session.get(file["raw_url"], timeout=15)
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise StorageError(f"Gist-Datei konnte nicht geladen werden: {type(exc).__name__}") from exc
            content = resp.text
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise StorageError("Die gespeicherte Datei im Gist ist beschädigt.") from exc

    def save(self, data: dict) -> None:
        files = {GIST_FILENAME: {"content": json.dumps(data, ensure_ascii=False, indent=1)}}
        if self.gist_id:
            self._request("PATCH", f"/gists/{self.gist_id}", json={"files": files})
        else:
            created = self._request("POST", "/gists",
                                    json={"description": GIST_DESCRIPTION, "public": False, "files": files})
            self.gist_id = created["id"]


# ---------------------------------------------------------------- Abgleich

class Sync:
    """Hält lokale Datenbank und Online-Speicher abgeglichen (einmal pro Server-Prozess)."""

    def __init__(self, backend, db_path=None):
        self.backend = backend
        self.db_path = db_path
        self.pulled = False
        self.last_saved: str | None = None
        self.error: str | None = None
        self._lock = threading.Lock()

    def ensure_pulled(self) -> bool:
        """Lädt beim ersten Aufruf die Daten aus dem Online-Speicher. True = bereit."""
        with self._lock:
            if self.pulled:
                return True
            try:
                data = self.backend.load()
                if data is not None:
                    import_user_data(data, self.db_path)
                    self.last_saved = fingerprint(export_user_data(self.db_path))
            except StorageError as exc:
                self.error = f"Online-Speicher nicht erreichbar – Änderungen werden NICHT gespeichert. ({exc})"
                return False
            self.pulled, self.error = True, None
            return True

    def push_if_changed(self) -> None:
        with self._lock:
            if not self.pulled:
                return   # nie speichern, bevor erfolgreich geladen wurde
            data = export_user_data(self.db_path)
            fp = fingerprint(data)
            if fp == self.last_saved:
                return
            try:
                self.backend.save(data)
                self.last_saved, self.error = fp, None
            except StorageError as exc:
                self.error = f"Speichern im Online-Speicher fehlgeschlagen – wird erneut versucht. ({exc})"
