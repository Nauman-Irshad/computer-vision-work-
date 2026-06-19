@echo off
REM Camera + MediaPipe landmarks (Flask). Default is plain HTTP on port 5000.
REM If port 5000 is in use (e.g. Windows services), set: set CAMERA_APP_PORT=5050
cd /d "%~dp0"
echo Starting server — open http://127.0.0.1:5000/ in your browser
echo Close this window to stop.
python app.py
pause
