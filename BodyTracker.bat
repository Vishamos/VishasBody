@echo off
rem VishasBody tracker launcher. Extra args are passed to main.py (e.g. --debug, --camera 1)
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
) else (
    rem Do not call bare "python": on a PC without it, Windows auto-installs the latest Python.
    py -3.12 main.py %*
)

echo.
pause
