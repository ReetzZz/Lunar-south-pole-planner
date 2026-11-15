@echo off
title Lunar South Pole Planner

:: Se siamo nella cartella esterna, entra nella cartella interna
if exist "%~dp0Lunar-South-Pole-Planner-main\src\ui_web\index.html" (
    cd /d "%~dp0Lunar-South-Pole-Planner-main"
) else if exist "%~dp0src\ui_web\index.html" (
    cd /d "%~dp0"
) else (
    cd /d "C:\Users\aless\OneDrive\Desktop\Lunar-South-Pole-Planner-main\Lunar-South-Pole-Planner-main"
)

echo ======================================================
echo       LUNAR SOUTH POLE MISSION PLANNER
echo ======================================================
echo  Cartella attiva: %CD%
echo  Avvio del server sulla porta 8000...
echo.
echo  Per FERMARE il server: chiudi questa finestra nera.
echo ======================================================

start http://localhost:8000/src/ui_web/index.html
python -m http.server 8000
