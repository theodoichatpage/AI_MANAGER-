@echo off
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m automation_agent.bootstrap
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python 3.10 or later is required. Install Python and open this file again.
    ) else (
        python -m automation_agent.bootstrap
    )
)
pause
