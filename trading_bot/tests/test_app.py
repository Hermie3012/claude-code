"""Prüft, dass die Startseite ohne Fehler lädt und den Hinweis anzeigt."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_home_page_shows_disclaimer():
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert "keine Anlageberatung" in at.warning[0].value
