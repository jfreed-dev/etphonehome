@echo off
REM ET Phone Home - First-time Setup (Windows)
REM Generates SSH keys and creates initial configuration

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "CONFIG_DIR=%USERPROFILE%\.etphonehome"

echo === ET Phone Home Setup ===
echo.

REM Create config directory
if not exist "%CONFIG_DIR%" (
    mkdir "%CONFIG_DIR%"
    echo Config directory created: %CONFIG_DIR%
) else (
    echo Config directory: %CONFIG_DIR%
)

REM Generate SSH keypair if not exists
set "KEY_FILE=%CONFIG_DIR%\id_ed25519"
if exist "%KEY_FILE%" (
    echo SSH key already exists: %KEY_FILE%
) else (
    echo Generating SSH keypair...
    call "%SCRIPT_DIR%\run.bat" --generate-key
)

REM Create config file if not exists
set "CONFIG_FILE=%CONFIG_DIR%\config.yaml"
if exist "%CONFIG_FILE%" (
    echo Config file already exists: %CONFIG_FILE%
) else (
    echo Creating default config...
    call "%SCRIPT_DIR%\run.bat" --init
)

echo.
echo === Setup Complete ===
echo.
echo Next steps:
echo 1. Edit %CONFIG_FILE% with your server details
echo 2. Add your public key to the server's authorized_keys
echo 3. Run: run.bat
echo.
echo Quick connect (bypassing config file):
echo   run.bat -s YOUR_SERVER -p 2222 -u etphonehome
echo.

REM Show public key if it exists
if exist "%KEY_FILE%.pub" (
    echo Your public key:
    type "%KEY_FILE%.pub"
    echo.
)

endlocal
pause
