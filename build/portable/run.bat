@echo off
REM Reach - Windows Runner
REM This script runs the reach client using the bundled Python

setlocal enabledelayedexpansion

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM Set up Python environment
set "PYTHONHOME=%SCRIPT_DIR%\python"
set "PYTHONPATH=%SCRIPT_DIR%\app;%SCRIPT_DIR%\packages"
set "PATH=%SCRIPT_DIR%\python;%SCRIPT_DIR%\python\Scripts;%PATH%"

REM Disable Python's user site-packages to ensure isolation
set "PYTHONNOUSERSITE=1"

REM Config directory (in user's home)
if not defined REACH_CONFIG_DIR (
    set "REACH_CONFIG_DIR=%USERPROFILE%\.reach"
)

REM Run the client
"%SCRIPT_DIR%\python\python.exe" -m client.reach %*

endlocal
