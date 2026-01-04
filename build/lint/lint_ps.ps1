# ET Phone Home - PowerShell Lint Script
# Runs PSScriptAnalyzer on all PowerShell scripts

param(
    [switch]$Fix  # Auto-fix issues where possible
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)

Set-Location $ProjectDir

Write-Host "=== ET Phone Home PowerShell Linting ===" -ForegroundColor Cyan
Write-Host ""

# Check if PSScriptAnalyzer is installed
if (-not (Get-Module -ListAvailable -Name PSScriptAnalyzer)) {
    Write-Host "Installing PSScriptAnalyzer..." -ForegroundColor Yellow
    Install-Module -Name PSScriptAnalyzer -Force -Scope CurrentUser
}

Import-Module PSScriptAnalyzer

# Find all PowerShell scripts
$Scripts = Get-ChildItem -Path $ProjectDir -Include "*.ps1" -Recurse

if ($Scripts.Count -eq 0) {
    Write-Host "No PowerShell scripts found" -ForegroundColor Yellow
    exit 0
}

Write-Host "Analyzing $($Scripts.Count) PowerShell script(s)..." -ForegroundColor Yellow
Write-Host ""

$AllIssues = @()

foreach ($Script in $Scripts) {
    $RelPath = $Script.FullName.Replace($ProjectDir, "").TrimStart("\", "/")
    Write-Host "  Checking: $RelPath" -ForegroundColor Gray

    $Issues = Invoke-ScriptAnalyzer -Path $Script.FullName -Severity @("Error", "Warning")

    if ($Issues) {
        $AllIssues += $Issues
        foreach ($Issue in $Issues) {
            $Color = if ($Issue.Severity -eq "Error") { "Red" } else { "Yellow" }
            Write-Host "    [$($Issue.Severity)] Line $($Issue.Line): $($Issue.Message)" -ForegroundColor $Color
        }
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan

$Errors = ($AllIssues | Where-Object { $_.Severity -eq "Error" }).Count
$Warnings = ($AllIssues | Where-Object { $_.Severity -eq "Warning" }).Count

if ($AllIssues.Count -eq 0) {
    Write-Host "All checks passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "$Errors error(s), $Warnings warning(s)" -ForegroundColor $(if ($Errors -gt 0) { "Red" } else { "Yellow" })

    if ($Errors -gt 0) {
        exit 1
    } else {
        # Warnings only - don't fail the build
        exit 0
    }
}
