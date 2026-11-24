@echo off
rem VishasBody tracker on CPU (MediaPipe). Same as BodyTracker.bat --backend mediapipe
rem Use when ONNX models are missing or the GPU is busy. Extra args are passed through (e.g. --debug, --camera 1)
call "%~dp0BodyTracker.bat" --backend mediapipe %*
