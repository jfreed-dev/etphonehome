# Package ET Phone Home for Windows with embedded Python
# Creates a self-contained archive that runs from any directory

param(
    [string]$PythonVersion = "3.12.8",
    [string]$Arch = "amd64"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$BuildDir = Join-Path $ScriptDir "work"
$OutputDir = Join-Path $ProjectDir "dist"

# Python embeddable URL
$PythonShort = $PythonVersion -replace '\.', ''
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-$Arch.zip"

Write-Host "=== Packaging ET Phone Home for Windows ===" -ForegroundColor Cyan
Write-Host "Python: $PythonVersion"
Write-Host "Architecture: $Arch"
Write-Host ""

# Clean and create build directory
if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force $BuildDir
}
New-Item -ItemType Directory -Path "$BuildDir\phonehome" -Force | Out-Null
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

Set-Location "$BuildDir\phonehome"

# Download embedded Python
Write-Host "Downloading embedded Python..."
$PythonZip = "python.zip"
Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZip

Write-Host "Extracting Python..."
New-Item -ItemType Directory -Path "python" -Force | Out-Null
Expand-Archive -Path $PythonZip -DestinationPath "python" -Force
Remove-Item $PythonZip

# Enable pip in embedded Python
# The ._pth file restricts imports; we need to modify it
$PthFile = Get-ChildItem -Path "python" -Filter "python*._pth" | Select-Object -First 1
if ($PthFile) {
    $PthContent = Get-Content $PthFile.FullName
    $PthContent = $PthContent -replace '#import site', 'import site'
    $PthContent += "`n..\packages"
    $PthContent += "`n..\app"
    Set-Content -Path $PthFile.FullName -Value $PthContent
}

# Download and install pip
Write-Host "Installing pip..."
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPipPath = "get-pip.py"
Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipPath
& "python\python.exe" $GetPipPath --no-warn-script-location
Remove-Item $GetPipPath

# Install dependencies to packages folder
Write-Host "Installing dependencies..."
New-Item -ItemType Directory -Path "packages" -Force | Out-Null
& "python\python.exe" -m pip install --target=packages --no-cache-dir `
    "paramiko>=3.0.0" `
    "pyyaml>=6.0" `
    "cryptography>=41.0.0"

# Copy application code
Write-Host "Copying application code..."
New-Item -ItemType Directory -Path "app\client" -Force | Out-Null
New-Item -ItemType Directory -Path "app\shared" -Force | Out-Null

Copy-Item "$ProjectDir\client\*.py" "app\client\" -Force
Copy-Item "$ProjectDir\shared\*.py" "app\shared\" -Force

# Create __init__.py files
"" | Out-File -FilePath "app\__init__.py" -Encoding utf8
"" | Out-File -FilePath "app\client\__init__.py" -Encoding utf8
"" | Out-File -FilePath "app\shared\__init__.py" -Encoding utf8

# Copy runner scripts
Write-Host "Copying scripts..."
Copy-Item "$ScriptDir\run.bat" ".\" -Force
Copy-Item "$ScriptDir\setup.bat" ".\" -Force

# Create version files
$PythonVersion | Out-File -FilePath "python_version.txt" -Encoding utf8
(Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ") | Out-File -FilePath "build_time.txt" -Encoding utf8

# Create SECURITY.txt with Windows-specific notes
@"
WINDOWS SECURITY NOTES
======================

1. Windows Defender / Antivirus
   This package contains Python and cryptography libraries which may trigger
   false positive detections. If blocked:
   - Add the phonehome folder to your AV exclusions
   - Or use the portable archive instead of the single executable

2. SmartScreen Warning
   Windows may show "Windows protected your PC" when running scripts.
   Click "More info" then "Run anyway" to proceed.

3. Firewall
   The client needs outbound access on the configured SSH port (default: 2222).
   If this port is blocked, ask your server admin to use port 443 instead.

4. Execution Policy
   If PowerShell blocks scripts, run:
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

"@ | Out-File -FilePath "SECURITY.txt" -Encoding utf8

# Create the archive
Write-Host "Creating archive..."
Set-Location $BuildDir
$ArchiveName = "phonehome-windows-$Arch.zip"
Compress-Archive -Path "phonehome" -DestinationPath "$OutputDir\$ArchiveName" -Force

# Cleanup
Set-Location $ProjectDir
Remove-Item -Recurse -Force $BuildDir

Write-Host ""
Write-Host "=== Package Complete ===" -ForegroundColor Green
Get-Item "$OutputDir\$ArchiveName" | Format-Table Name, Length -AutoSize
Write-Host ""
Write-Host "To deploy:"
Write-Host "  Expand-Archive $ArchiveName -DestinationPath ."
Write-Host "  cd phonehome"
Write-Host "  .\setup.bat"
Write-Host "  .\run.bat -s your-server.com"
