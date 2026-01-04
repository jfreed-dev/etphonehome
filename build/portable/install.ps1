# ET Phone Home - Windows User Installation
# Installs phonehome to user profile (no admin required)

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\phonehome",
    [string]$ConfigDir = "$env:USERPROFILE\.etphonehome",
    [switch]$Force  # Overwrite without prompting
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== ET Phone Home Installer ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installation directory: $InstallDir"
Write-Host "Config directory: $ConfigDir"
Write-Host ""

# Check if already installed
if (Test-Path $InstallDir) {
    if (-not $Force) {
        Write-Host "Warning: phonehome is already installed at $InstallDir" -ForegroundColor Yellow
        $response = Read-Host "Overwrite existing installation? [y/N]"
        if ($response -notmatch '^[Yy]') {
            Write-Host "Installation cancelled."
            exit 0
        }
    }
    Write-Host "Removing existing installation..."
    Remove-Item -Path $InstallDir -Recurse -Force
}

# Create directories
Write-Host "Creating directories..."
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null

# Copy files
Write-Host "Installing phonehome..."
$filesToCopy = @(
    "python",
    "app",
    "packages",
    "run.bat",
    "setup.bat",
    "python_version.txt",
    "build_time.txt"
)

foreach ($item in $filesToCopy) {
    $source = Join-Path $ScriptDir $item
    if (Test-Path $source) {
        $dest = Join-Path $InstallDir $item
        if (Test-Path $source -PathType Container) {
            Copy-Item -Path $source -Destination $dest -Recurse -Force
        } else {
            Copy-Item -Path $source -Destination $dest -Force
        }
    }
}

# Copy uninstaller
Copy-Item -Path (Join-Path $ScriptDir "uninstall.ps1") -Destination $InstallDir -Force

# Create phonehome.cmd wrapper for easy execution
$wrapperContent = @"
@echo off
"%~dp0run.bat" %*
"@
$wrapperPath = Join-Path $InstallDir "phonehome.cmd"
Set-Content -Path $wrapperPath -Value $wrapperContent

# Add to user PATH if not already present
Write-Host "Configuring PATH..."
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$InstallDir*") {
    $newPath = "$InstallDir;$userPath"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    Write-Host "  Added $InstallDir to user PATH" -ForegroundColor Green
} else {
    Write-Host "  $InstallDir already in PATH" -ForegroundColor Gray
}

# Run initial setup
Write-Host ""
Write-Host "Running initial setup..."
Push-Location $InstallDir
try {
    & ".\setup.bat"
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "You can now run phonehome from any terminal:"
Write-Host "  phonehome --help"
Write-Host "  phonehome -s your-server.com -p 443"
Write-Host ""
Write-Host "Configuration: $ConfigDir\config.yaml"
Write-Host "Uninstall: Run uninstall.ps1 from $InstallDir"
Write-Host ""
Write-Host "Note: You may need to restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
