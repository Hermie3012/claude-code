@echo off
rem ================================================================
rem  Trading-Bot (Lernprojekt) - Start per Doppelklick unter Windows
rem  Beim ersten Start wird alles automatisch eingerichtet.
rem ================================================================
setlocal
cd /d "%~dp0"
title Trading-Bot (Lernprojekt - nur Spielgeld)

echo.
echo  ==================================================
echo   Trading-Bot - Lernprojekt (nur Spielgeld)
echo   Keine Anlageberatung, keine echten Orders.
echo  ==================================================
echo.

rem --- Python suchen: zuerst den Windows-Starter "py", dann "python" ---
set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY goto nopython

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto oldpython

rem --- Erster Start: eigene Python-Umgebung im Ordner .venv anlegen ---
if not exist ".venv\Scripts\python.exe" (
    echo Erster Start: Die App wird eingerichtet. Das dauert ein paar Minuten ...
    echo.
    %PY% -m venv .venv
    if errorlevel 1 goto error
)

rem --- Pakete installieren, wenn requirements.txt neu oder geaendert ist ---
fc /b requirements.txt ".venv\requirements.installed" >nul 2>&1
if errorlevel 1 (
    echo Installiere die benoetigten Pakete ...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 goto error
    copy /y requirements.txt ".venv\requirements.installed" >nul
    echo.
)

echo Die App startet. Der Browser oeffnet sich gleich von selbst.
echo Falls nicht: im Browser http://localhost:8501 eingeben.
echo.
echo ZUM BEENDEN: dieses Fenster schliessen.
echo.
".venv\Scripts\python.exe" -m streamlit run app.py
goto end

:nopython
echo FEHLER: Python wurde nicht gefunden.
echo.
echo So geht's:
echo  1. https://www.python.org/downloads/ oeffnen und Python herunterladen.
echo  2. Beim Installieren unbedingt "Add python.exe to PATH" ankreuzen.
echo  3. Danach diese Datei erneut doppelklicken.
goto end

:oldpython
echo FEHLER: Deine Python-Version ist zu alt. Benoetigt wird Python 3.11 oder neuer.
%PY% --version
echo Neue Version: https://www.python.org/downloads/
goto end

:error
echo.
echo FEHLER: Die Einrichtung hat nicht geklappt (siehe Meldungen oben).
echo Tipp: Internetverbindung pruefen. Hilft das nicht, den Ordner ".venv"
echo loeschen und diese Datei erneut doppelklicken.

:end
echo.
pause
