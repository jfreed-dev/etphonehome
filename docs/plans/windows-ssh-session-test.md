# Windows SSH Session Testing Plan

**Date**: 2026-01-07
**Target Client**: ep-dev-ts (Windows Server 2019)
**Tunnel Port**: 34179

## Prerequisites Check

### 1. Verify OpenSSH on Windows Client
```powershell
# Check if OpenSSH client is installed
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH*'

# Check SSH command availability
ssh -V
```

### 2. Verify SSH Keys Exist
```powershell
# Check for existing keys
Get-ChildItem $env:USERPROFILE\.ssh\

# If no keys, generate:
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519
```

### 3. Test Target Host Connectivity
Options for SSH target:
- **localhost** (if OpenSSH Server enabled on Windows)
- **Linux host** (spark-2f34 or update server)
- **Other Windows host**

```powershell
# Check if OpenSSH Server is running locally
Get-Service sshd

# Or test connection to Linux host
ssh -o BatchMode=yes -o ConnectTimeout=5 jon@10.10.88.120 "echo OK"
```

## Test Cases

### Test 1: Open SSH Session
```python
# Via MCP or direct tunnel
ssh_session_open:
  host: "10.10.88.120"  # or localhost
  username: "jon"
  key_file: "C:\\Users\\jfreed\\.ssh\\id_ed25519"
  port: 22
```

Expected: Session ID returned, initial output captured

### Test 2: Basic Command Execution
```python
ssh_session_command:
  session_id: "<from test 1>"
  command: "pwd"  # or "cd" on Windows SSH server
  timeout: 10
```

Expected: Current directory returned

### Test 3: State Preservation - Directory
```python
# Change directory
ssh_session_command:
  command: "cd /tmp"  # Linux target
  # or "cd C:\\Temp"  # Windows target

# Verify preserved
ssh_session_command:
  command: "pwd"
```

Expected: Directory change persists

### Test 4: State Preservation - Environment
```python
# Set variable
ssh_session_command:
  command: "export TESTVAR=windows_test"  # Linux
  # or "$env:TESTVAR = 'windows_test'"  # PowerShell on Windows

# Verify preserved
ssh_session_command:
  command: "echo $TESTVAR"  # Linux
  # or "echo $env:TESTVAR"  # PowerShell
```

Expected: Variable persists

### Test 5: List Sessions
```python
ssh_session_list: {}
```

Expected: Shows session from Test 1

### Test 6: Close Session
```python
ssh_session_close:
  session_id: "<from test 1>"
```

Expected: Session closed, resources freed

### Test 7: Error Handling
```python
# Invalid session
ssh_session_command:
  session_id: "invalid"
  command: "pwd"
```

Expected: Proper error returned

## Windows-Specific Considerations

### Path Formats
- Windows paths use backslashes: `C:\Users\jfreed`
- In SSH commands to Linux: forward slashes `/home/jon`
- Key files may need escaped paths: `C:\\Users\\jfreed\\.ssh\\id_ed25519`

### Shell Differences
If SSH target is Windows:
- Default shell may be cmd.exe or PowerShell
- Environment variables: `%VAR%` (cmd) or `$env:VAR` (PowerShell)
- Path separator: semicolon `;` not colon `:`

### Known Limitations
- Paramiko on Windows may have different behavior
- PTY allocation may differ
- Line endings: CRLF vs LF

## Execution Commands

### Quick Test Script (run from server)
```bash
ssh etphonehome@72.60.125.7 "python3 << 'EOF'
import asyncio
import json

async def send_request(port, method, params=None):
    request = {'method': method, 'params': params or {}, 'id': '1'}
    msg = json.dumps(request).encode('utf-8')
    data = len(msg).to_bytes(4, 'big') + msg

    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    writer.write(data)
    await writer.drain()

    header = await reader.readexactly(4)
    length = int.from_bytes(header, 'big')
    body = await reader.readexactly(length)

    writer.close()
    await writer.wait_closed()
    return json.loads(body.decode('utf-8'))

async def main():
    WINDOWS_PORT = 34179

    # Test SSH session on Windows client
    print('Opening session...')
    result = await send_request(WINDOWS_PORT, 'ssh_session_open', {
        'host': '10.10.88.120',  # SSH to Spark from Windows
        'username': 'jon',
        'key_file': 'C:\\\\Users\\\\jfreed\\\\.ssh\\\\id_ed25519',
        'port': 22
    })
    print(json.dumps(result, indent=2))

asyncio.run(main())
EOF"
```

## Success Criteria

- [ ] SSH session opens from Windows client
- [ ] Commands execute and return output
- [ ] Working directory persists between commands
- [ ] Environment variables persist between commands
- [ ] Session listing works
- [ ] Session closing works
- [ ] Errors handled gracefully

## Fallback Options

If Windows SSH sessions fail:
1. Check if paramiko is installed on Windows client
2. Verify SSH key permissions (Windows ACLs can be tricky)
3. Test with password auth instead of key
4. Check Windows firewall for outbound SSH

## Notes

- Windows client tunnel port: 34179
- Client username: jfreed
- Platform: Windows Server 2019
