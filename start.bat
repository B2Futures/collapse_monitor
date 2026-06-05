@echo off
cd /d "%~dp0"
echo.
echo  Collapse Monitor
echo  ----------------
echo.

:: Install / update dependencies
echo  Checking dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo  [ERROR] pip install failed. Make sure Python is installed and in PATH.
    pause
    exit /b 1
)

:: Check python works
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Python not found. Install from python.org and check "Add to PATH".
    pause
    exit /b 1
)

:: Start server minimized — this window MUST stay running
echo  Starting server (minimized in taskbar)...
start "Collapse Monitor Server — DO NOT CLOSE" /min python server.py

:: Give server a moment to bind to port 5000
echo  Waiting for server to start...
timeout /t 3 /noisy >nul

:: Verify server actually started
curl -s http://localhost:5000/status >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [WARNING] Server may not have started yet — opening browser anyway.
    echo  If the page shows an error, wait 5 seconds and refresh.
)

:: Open browser
start http://localhost:5000

echo.
echo  Done. The minimized "Collapse Monitor Server" window in your taskbar
echo  must stay open while you use the app. Close it to shut down the server.
echo.
timeout /t 5 /noisy >nul
exit
