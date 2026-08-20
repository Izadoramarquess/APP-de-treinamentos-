@echo off
cd /d "%~dp0"
echo Iniciando GeoTrilha LMS...
.\.venv\Scripts\python.exe backend\main.py
pause
