@echo off
REM Build PyInstaller executable for Windows
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..\..
set BUILD_DIR=%PROJECT_DIR%\dist

echo === Building ET Phone Home for Windows ===
echo Project: %PROJECT_DIR%
echo.

REM Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: python not found
    exit /b 1
)

REM Create/activate virtual environment
set VENV_DIR=%PROJECT_DIR%\.venv-build
if not exist "%VENV_DIR%" (
    echo Creating build virtual environment...
    python -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"

REM Install dependencies
echo Installing dependencies...
pip install --upgrade pip wheel
pip install pyinstaller
pip install -e "%PROJECT_DIR%"

REM Build
echo Building executable...
cd /d "%PROJECT_DIR%"
pyinstaller --clean --noconfirm build\pyinstaller\phonehome.spec

REM Verify
if exist "%BUILD_DIR%\phonehome.exe" (
    echo.
    echo === Build Successful ===
    dir "%BUILD_DIR%\phonehome.exe"
    echo.
    echo Test with: %BUILD_DIR%\phonehome.exe --help
) else (
    echo Error: Build failed
    exit /b 1
)

endlocal
