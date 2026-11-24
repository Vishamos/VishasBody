@echo off
rem VishasBody tracker launcher. Extra args are passed to src\main.py (e.g. --debug, --camera 1)
cd /d "%~dp0"

rem Do not call bare "python": on a PC without it, Windows auto-installs the latest Python.
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=py -3.12")

rem Install packages with the same Python that runs the tracker, only when something is missing.
%PY% -c "import mediapipe, cv2, websockets, onnxruntime" 2>nul || (
    echo [setup] Installing packages from requirements.txt ...
    %PY% -m pip install -r requirements.txt || (
        echo [setup] Install failed. See the messages above.
        pause
        exit /b 1
    )
)

%PY% src\main.py %*

echo.
pause
