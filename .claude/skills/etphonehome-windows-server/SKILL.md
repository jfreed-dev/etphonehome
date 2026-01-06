---
name: etphonehome-windows-server
description: Windows Server 2019 and PowerShell expert for remote administration. Use when managing Windows clients, running PowerShell commands, checking server health, or troubleshooting Windows-specific issues.
allowed-tools: mcp__etphonehome__*
---

# ET Phone Home - Windows Server & PowerShell Expert

This skill provides comprehensive guidance for managing Windows Server 2019 clients via ET Phone Home using PowerShell.

## PowerShell Execution Guidelines

### Command Format

Always use PowerShell cmdlets. Commands are executed via the phonehome agent which wraps them appropriately.

```
run_command:
  cmd: "powershell -Command \"Get-Service | Where-Object {$_.Status -eq 'Running'}\""
  timeout: 60
```

### Output Formatting

For clean, parseable output:

```powershell
# Use Format-List for detailed single objects
Get-ComputerInfo | Format-List OsName, OsVersion, CsName

# Use Format-Table for lists
Get-Service | Format-Table -AutoSize

# Use Select-Object to limit properties
Get-Process | Select-Object -First 10 Name, CPU, WorkingSet

# ConvertTo-Json for structured data
Get-Service | Select-Object Name, Status | ConvertTo-Json
```

### Error Handling

```powershell
# Suppress errors for commands that may fail
Get-Service "NonExistent" -ErrorAction SilentlyContinue

# Show all errors
$ErrorActionPreference = "Continue"

# Stop on first error
$ErrorActionPreference = "Stop"
```

### Timeout Considerations

| Operation | Recommended Timeout |
|-----------|---------------------|
| Quick queries (Get-Service, Get-Process) | 30-60 seconds |
| System info (Get-ComputerInfo) | 120 seconds |
| Windows Update checks | 300 seconds |
| Large file operations | 600+ seconds |

---

## System Administration

### System Information

```powershell
# Quick system overview
systeminfo | Select-String "OS Name|OS Version|System Type|Total Physical Memory"

# Detailed computer info
Get-ComputerInfo | Select-Object OsName, OsVersion, OsArchitecture, CsName, CsDomain, WindowsVersion

# Hostname
$env:COMPUTERNAME

# OS version
[System.Environment]::OSVersion
```

### Service Management

```powershell
# List all services
Get-Service | Format-Table -AutoSize

# List running services
Get-Service | Where-Object {$_.Status -eq 'Running'}

# Check specific service
Get-Service -Name "wuauserv" | Format-List *

# Start/Stop/Restart service
Start-Service -Name "ServiceName"
Stop-Service -Name "ServiceName" -Force
Restart-Service -Name "ServiceName"

# Set service startup type
Set-Service -Name "ServiceName" -StartupType Automatic
```

### Process Management

```powershell
# List all processes
Get-Process | Sort-Object CPU -Descending | Select-Object -First 20

# Find process by name
Get-Process -Name "python*"

# Kill process
Stop-Process -Name "ProcessName" -Force
Stop-Process -Id 1234 -Force

# Process details
Get-Process | Where-Object {$_.CPU -gt 100} | Format-List *
```

### Scheduled Tasks

```powershell
# List all scheduled tasks
Get-ScheduledTask | Format-Table TaskName, State, TaskPath

# Get task details
Get-ScheduledTask -TaskName "TaskName" | Get-ScheduledTaskInfo

# Run task immediately
Start-ScheduledTask -TaskName "TaskName"

# Disable/Enable task
Disable-ScheduledTask -TaskName "TaskName"
Enable-ScheduledTask -TaskName "TaskName"
```

### Windows Updates

```powershell
# Check for updates (requires PSWindowsUpdate module)
Get-WindowsUpdate

# List installed updates
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10

# Check last update time
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1
```

---

## Development Environment

### Git Operations

```powershell
# Check git version
git --version

# Git status
git status

# Git config
git config --global --list

# Clone repository
git clone https://github.com/user/repo.git C:\Projects\repo
```

### Python Management

```powershell
# Python version
python --version
python3 --version

# Pip packages
pip list
pip show package-name

# Install package
pip install package-name

# Virtual environment
python -m venv C:\Projects\myenv
C:\Projects\myenv\Scripts\Activate.ps1
```

### Compiler Toolchain

```powershell
# Check CMake
cmake --version

# Check MSVC (if installed)
cl.exe 2>&1 | Select-String "Version"

# Check build tools
where.exe cl
where.exe cmake
where.exe nmake

# Run CMake build
cmake -B build -S .
cmake --build build --config Release
```

### Environment Variables

```powershell
# List all environment variables
Get-ChildItem Env: | Format-Table -AutoSize

# Get specific variable
$env:PATH
$env:USERPROFILE
$env:TEMP

# Set environment variable (session)
$env:MY_VAR = "value"

# Set environment variable (permanent - user)
[Environment]::SetEnvironmentVariable("MY_VAR", "value", "User")

# Set environment variable (permanent - machine, requires admin)
[Environment]::SetEnvironmentVariable("MY_VAR", "value", "Machine")

# Update PATH
$env:PATH += ";C:\NewPath"
```

---

## Server Monitoring

### CPU & Memory

```powershell
# Quick CPU/Memory snapshot
Get-Counter '\Processor(_Total)\% Processor Time', '\Memory\Available MBytes' -SampleInterval 1 -MaxSamples 1

# CPU usage by process
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, @{N='Memory(MB)';E={[math]::Round($_.WorkingSet/1MB,2)}}

# Memory usage
Get-CimInstance Win32_OperatingSystem | Select-Object @{N='TotalGB';E={[math]::Round($_.TotalVisibleMemorySize/1MB,2)}}, @{N='FreeGB';E={[math]::Round($_.FreePhysicalMemory/1MB,2)}}, @{N='UsedPercent';E={[math]::Round((($_.TotalVisibleMemorySize-$_.FreePhysicalMemory)/$_.TotalVisibleMemorySize)*100,1)}}

# Detailed memory
systeminfo | Select-String "Memory"
```

### Disk Space

```powershell
# All volumes
Get-Volume | Format-Table -AutoSize

# Disk usage with percentages
Get-Volume | Where-Object {$_.DriveLetter} | Select-Object DriveLetter, FileSystemLabel, @{N='SizeGB';E={[math]::Round($_.Size/1GB,2)}}, @{N='FreeGB';E={[math]::Round($_.SizeRemaining/1GB,2)}}, @{N='UsedPercent';E={[math]::Round((($_.Size-$_.SizeRemaining)/$_.Size)*100,1)}}

# PSDrive alternative
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='UsedGB';E={[math]::Round($_.Used/1GB,2)}}, @{N='FreeGB';E={[math]::Round($_.Free/1GB,2)}}

# Large files
Get-ChildItem C:\ -Recurse -ErrorAction SilentlyContinue | Where-Object {$_.Length -gt 100MB} | Sort-Object Length -Descending | Select-Object -First 20 FullName, @{N='SizeMB';E={[math]::Round($_.Length/1MB,2)}}
```

### Network

```powershell
# Network adapters
Get-NetAdapter | Format-Table -AutoSize

# IP configuration
Get-NetIPAddress | Where-Object {$_.AddressFamily -eq 'IPv4'} | Format-Table InterfaceAlias, IPAddress, PrefixLength

# Test connectivity
Test-NetConnection -ComputerName google.com
Test-NetConnection -ComputerName 8.8.8.8 -Port 443

# Active connections
Get-NetTCPConnection | Where-Object {$_.State -eq 'Established'} | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, OwningProcess

# Listening ports
Get-NetTCPConnection -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess

# DNS
Resolve-DnsName google.com
Get-DnsClientServerAddress
```

### Uptime & Boot Time

```powershell
# System uptime
(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime

# Last boot time
(Get-CimInstance Win32_OperatingSystem).LastBootUpTime

# Uptime in days
$uptime = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
"Uptime: $($uptime.Days) days, $($uptime.Hours) hours, $($uptime.Minutes) minutes"
```

### Performance Counters

```powershell
# Common counters
Get-Counter -Counter "\Processor(_Total)\% Processor Time", "\Memory\% Committed Bytes In Use", "\LogicalDisk(C:)\% Free Space"

# Continuous monitoring (5 samples, 2 second interval)
Get-Counter -Counter "\Processor(_Total)\% Processor Time" -SampleInterval 2 -MaxSamples 5

# All available counters (for reference)
Get-Counter -ListSet * | Select-Object CounterSetName
```

---

## Security & Hardening

### Event Logs

```powershell
# List available logs
Get-EventLog -List

# Recent system errors
Get-EventLog -LogName System -EntryType Error -Newest 20 | Format-Table TimeGenerated, Source, Message -Wrap

# Security events (login failures)
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4625} -MaxEvents 20 | Format-Table TimeCreated, Message -Wrap

# Application errors
Get-EventLog -LogName Application -EntryType Error -Newest 20

# Search for specific text
Get-EventLog -LogName System -Newest 100 | Where-Object {$_.Message -like "*error*"}
```

### Important Security Event IDs

| Event ID | Description |
|----------|-------------|
| 4624 | Successful login |
| 4625 | Failed login |
| 4634 | Logoff |
| 4648 | Explicit credential logon |
| 4672 | Admin login |
| 4720 | User account created |
| 4722 | User account enabled |
| 4725 | User account disabled |
| 4726 | User account deleted |
| 4732 | Member added to local group |
| 4756 | Member added to security group |

### Firewall

```powershell
# Firewall status
Get-NetFirewallProfile | Select-Object Name, Enabled

# List firewall rules
Get-NetFirewallRule | Where-Object {$_.Enabled -eq 'True'} | Select-Object DisplayName, Direction, Action | Format-Table

# Inbound rules
Get-NetFirewallRule -Direction Inbound -Enabled True | Select-Object DisplayName, Action

# Check specific port
Get-NetFirewallRule | Where-Object {$_.LocalPort -eq 443}

# Allow inbound port (requires admin)
New-NetFirewallRule -DisplayName "Allow Port 8080" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
```

### Local Users & Groups

```powershell
# List local users
Get-LocalUser | Format-Table Name, Enabled, LastLogon

# User details
Get-LocalUser -Name "Administrator" | Format-List *

# List local groups
Get-LocalGroup | Format-Table Name, Description

# Group members
Get-LocalGroupMember -Group "Administrators"

# Check user's groups
Get-LocalGroup | ForEach-Object { $group = $_; Get-LocalGroupMember -Group $_.Name -ErrorAction SilentlyContinue | Where-Object {$_.Name -like "*username*"} | ForEach-Object { [PSCustomObject]@{Group=$group.Name; Member=$_.Name} } }
```

### Audit Policies

```powershell
# View audit policies
auditpol /get /category:*

# Check specific category
auditpol /get /category:"Account Logon"

# Check login auditing
auditpol /get /subcategory:"Logon"
```

---

## Common Paths & Locations

### System Directories

| Path | Description |
|------|-------------|
| `C:\Windows` | Windows installation |
| `C:\Windows\System32` | System binaries |
| `C:\Windows\Temp` | System temp files |
| `C:\Program Files` | 64-bit applications |
| `C:\Program Files (x86)` | 32-bit applications |
| `C:\ProgramData` | Application data (all users) |

### User Profile Paths

| Variable | Typical Path |
|----------|--------------|
| `$env:USERPROFILE` | `C:\Users\username` |
| `$env:APPDATA` | `C:\Users\username\AppData\Roaming` |
| `$env:LOCALAPPDATA` | `C:\Users\username\AppData\Local` |
| `$env:TEMP` | `C:\Users\username\AppData\Local\Temp` |

### Log File Locations

| Log | Location |
|-----|----------|
| Windows Event Logs | `C:\Windows\System32\winevt\Logs\` |
| IIS Logs | `C:\inetpub\logs\LogFiles\` |
| Windows Update | `C:\Windows\SoftwareDistribution\` |
| CBS/DISM | `C:\Windows\Logs\CBS\` |

### Registry Key Paths

```powershell
# Common registry locations
Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\*"
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
```

---

## Troubleshooting Workflows

### Service Failures

```
1. Check service status
   Get-Service -Name "ServiceName" | Format-List *

2. Check service dependencies
   Get-Service -Name "ServiceName" -DependentServices
   Get-Service -Name "ServiceName" -RequiredServices

3. View service events
   Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Service Control Manager'} -MaxEvents 20

4. Check service account
   Get-WmiObject Win32_Service | Where-Object {$_.Name -eq "ServiceName"} | Select-Object Name, StartName

5. Attempt restart
   Restart-Service -Name "ServiceName" -Force
```

### High Resource Usage

```
1. Identify top CPU consumers
   Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, Id

2. Identify top memory consumers
   Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10 Name, @{N='MemMB';E={[math]::Round($_.WorkingSet/1MB)}}, Id

3. Check for runaway processes
   Get-Process | Where-Object {$_.CPU -gt 100}

4. Monitor real-time
   Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 2 -MaxSamples 5

5. Check for memory leaks (growing processes)
   Get-Process | Where-Object {$_.WorkingSet -gt 1GB}
```

### Network Connectivity

```
1. Check adapter status
   Get-NetAdapter | Format-Table Name, Status, LinkSpeed

2. Verify IP configuration
   Get-NetIPConfiguration

3. Test external connectivity
   Test-NetConnection -ComputerName 8.8.8.8
   Test-NetConnection -ComputerName google.com -Port 443

4. Check DNS resolution
   Resolve-DnsName google.com
   nslookup google.com

5. Check routing
   Get-NetRoute | Where-Object {$_.DestinationPrefix -eq '0.0.0.0/0'}

6. Trace route
   Test-NetConnection -ComputerName google.com -TraceRoute
```

### Application Crashes

```
1. Check Application event log
   Get-EventLog -LogName Application -EntryType Error -Newest 20

2. Look for crash dumps
   Get-ChildItem C:\Windows\Minidump -ErrorAction SilentlyContinue
   Get-ChildItem "$env:LOCALAPPDATA\CrashDumps" -ErrorAction SilentlyContinue

3. Check Windows Error Reporting
   Get-WinEvent -LogName "Application" | Where-Object {$_.ProviderName -eq "Windows Error Reporting"} | Select-Object -First 10

4. Verify application files
   Get-FileHash "C:\Path\To\Application.exe"
```

### Login Failures

```
1. Check failed logins
   Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4625} -MaxEvents 20 | Format-Table TimeCreated, Message -Wrap

2. Check account lockouts
   Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4740} -MaxEvents 10

3. Verify user status
   Get-LocalUser -Name "username" | Select-Object Name, Enabled, LastLogon, PasswordExpires

4. Check group membership
   Get-LocalGroupMember -Group "Administrators"
   Get-LocalGroupMember -Group "Remote Desktop Users"

5. Check account policies
   net accounts
```

---

## Quick Reference

### Essential Cmdlets

| Task | Command |
|------|---------|
| System info | `Get-ComputerInfo \| Select-Object OsName, OsVersion` |
| Hostname | `$env:COMPUTERNAME` |
| Uptime | `(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime` |
| Services | `Get-Service \| Where-Object {$_.Status -eq 'Running'}` |
| Processes | `Get-Process \| Sort-Object CPU -Descending \| Select-Object -First 10` |
| Disk space | `Get-Volume \| Format-Table -AutoSize` |
| Memory | `gcim Win32_OperatingSystem \| Select-Object FreePhysicalMemory, TotalVisibleMemorySize` |
| Network | `Get-NetIPAddress -AddressFamily IPv4` |
| Firewall | `Get-NetFirewallProfile` |
| Event log | `Get-EventLog -LogName System -EntryType Error -Newest 10` |
| Users | `Get-LocalUser` |
| Env vars | `Get-ChildItem Env:` |
| Installed apps | `Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` |

### Common Aliases

| Alias | Full Command |
|-------|--------------|
| `gcim` | `Get-CimInstance` |
| `gps` | `Get-Process` |
| `gsv` | `Get-Service` |
| `gci` | `Get-ChildItem` |
| `gc` | `Get-Content` |
| `sc` | `Set-Content` |
| `sls` | `Select-String` |
| `ft` | `Format-Table` |
| `fl` | `Format-List` |
