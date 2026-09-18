@echo off
title SC Downloader
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

echo Avvio di SC Downloader...
echo Chiudi la finestra dell'app per uscire.
echo.

"%PYTHON%" gui.py %*

if errorlevel 1 (
    echo.
    echo Qualcosa non ha funzionato, l'errore e' scritto qui sopra.
    pause
)
