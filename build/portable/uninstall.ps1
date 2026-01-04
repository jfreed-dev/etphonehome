# ET Phone Home - Windows Uninstaller
# Removes phonehome from user profile

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\phonehome",
    [string]$ConfigDir = "$env:USERPROFILE\.etphonehome",
    [switch]$Force  # Uninstall without prompting
)

$ErrorActionPreference = "Stop"

Write-Host "=== ET Phone Home Uninstaller ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $InstallDir)) {
    Write-Host "phonehome does not appear to be installed at $InstallDir"
    exit 0
}

Write-Host "This will remove:"
Write-Host "  - $InstallDir"
Write-Host ""
Write-Host "Note: Config directory $ConfigDir will NOT be removed" -ForegroundColor Yellow
Write-Host ""

if (-not $Force) {
    $response = Read-Host "Continue with uninstall? [y/N]"
    if ($response -notmatch '^[Yy]') {
        Write-Host "Uninstall cancelled."
        exit 0
    }
}

Write-Host "Removing phonehome..."

# Remove from user PATH
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -like "*$InstallDir*") {
    $paths = $userPath -split ";" | Where-Object { $_ -ne $InstallDir -and $_ -ne "" }
    $newPath = $paths -join ";"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    Write-Host "  Removed from user PATH" -ForegroundColor Green
}

# Remove installation directory
if (Test-Path $InstallDir) {
    Remove-Item -Path $InstallDir -Recurse -Force
    Write-Host "  Removed $InstallDir" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Uninstall Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Config and keys preserved at: $ConfigDir"
Write-Host "To remove config: Remove-Item -Recurse $ConfigDir"
Write-Host ""
