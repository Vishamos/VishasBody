@echo off
rem VishasBody tracker on GPU (ONNX Runtime DirectML). Same as BodyTracker.bat --backend onnx
rem Extra args are passed through (e.g. --debug, --camera 1)
call "%~dp0BodyTracker.bat" --backend onnx %*
