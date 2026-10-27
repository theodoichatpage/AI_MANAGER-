@echo off
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    py -3 server.py
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python 3 is required. Please install Python and try again.
    ) else (
        python server.py
    )
)
pause
