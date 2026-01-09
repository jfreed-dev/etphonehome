---
name: etphonehome-remote-access
description: Best practices for safe remote access using ET Phone Home. Use when executing commands, reading/writing files, or managing remote clients through the etphonehome MCP server.
allowed-tools: mcp__etphonehome__*
---

# ET Phone Home - Safe Remote Access

This skill provides guidance for safely interacting with remote machines through ET Phone Home.

## Core Principles

1. **Always verify before acting** - Confirm you're targeting the correct client
2. **Use absolute paths** - Never use relative paths for file operations
3. **Set appropriate timeouts** - Long commands need longer timeouts
4. **Check errors carefully** - Review stderr and exit codes

## Before Any Remote Operation

Follow this workflow before executing commands or file operations:

```
1. List available clients
   → Use: list_clients
   → Note: Shows online/offline status, UUID, display name

2. Identify your target
   → Use: find_client with query, tags, or capabilities
   → Or: describe_client with UUID for full details

3. Select the client
   → Use: select_client with client_id or UUID
   → Note: Auto-selected if only one client is online

4. Verify selection
   → Use: describe_client to confirm correct target
```

## Command Execution Rules

### Always Do
- Specify full absolute paths in commands: `/usr/bin/python3` not `python3`
- Set timeout for long operations: `timeout: 600` for builds, backups
- Check the return code in results: `returncode: 0` means success
- Review stderr even on success - may contain warnings

### Never Do
- Run destructive commands without confirmation
- Assume the working directory
- Ignore non-zero return codes
- Run commands with unbounded output without limits

### Timeout Guidelines

| Operation Type | Recommended Timeout |
|----------------|---------------------|
| Quick queries (ls, cat, pwd) | 30 seconds |
| Normal commands | 300 seconds (default) |
| Package installs | 600 seconds |
| Builds, backups | 900-1800 seconds |
| Long-running scripts | Set explicitly |

### Example: Safe Command Execution

```
# Good - explicit path, reasonable timeout
run_command:
  cmd: "/usr/bin/df -h"
  timeout: 60

# Good - working directory specified
run_command:
  cmd: "ls -la"
  cwd: "/home/user/projects"

# Bad - relative path, no timeout awareness
run_command:
  cmd: "python script.py"
```

## File Operation Rules

### Choosing the Right Tool

| Tool | Use Case | Size Limit | Method |
|------|----------|------------|--------|
| `upload_file` | Server → Client transfers | **No limit** | SFTP (streaming) |
| `download_file` | Client → Server transfers | **No limit** | SFTP (streaming) |
| `read_file` | Quick content inspection | 10MB | JSON-RPC |
| `write_file` | Small file writes | ~10MB | JSON-RPC |

**Prefer `upload_file` and `download_file`** - they use SFTP for streaming transfers with no size limits. Falls back to JSON-RPC automatically if SFTP unavailable.

### Path Requirements
- **ALWAYS** use absolute paths: `/home/user/file.txt`
- **NEVER** use relative paths: `./file.txt`, `../config`
- **NEVER** use home shortcuts without expansion: `~/file.txt`

### Before Reading Files
1. Verify the file exists: `run_command: "test -f /path/to/file && echo exists"`
2. Check file size if potentially large: `run_command: "ls -lh /path/to/file"`
3. For files over 10MB, use `download_file` instead of `read_file`

### Before Writing Files
1. Check available disk space: `run_command: "df -h /path"`
2. Verify parent directory exists
3. Consider if backup is needed first

### Example: Safe File Operations

```
# RECOMMENDED - SFTP-based transfers (no size limits)
upload_file:
  local_path: "/path/on/server/config.yaml"
  remote_path: "/home/user/config/config.yaml"

download_file:
  remote_path: "/var/log/app.log"
  local_path: "/tmp/downloaded_app.log"

# For quick reads of small files (< 10MB)
read_file:
  path: "/etc/hostname"

# Good - verify before write
run_command:
  cmd: "test -d /home/user/config && echo 'directory exists'"

write_file:
  path: "/home/user/config/settings.json"
  content: "{...}"

# Bad - relative path
read_file:
  path: "config/settings.json"
```

## SSH Key Mismatch Handling

When a client reconnects with a different SSH key, the server flags it with `key_mismatch: true`.

### Investigation Steps

1. Check client details:
   ```
   describe_client:
     uuid: "<client-uuid>"
   ```
   Look for: `key_mismatch: true`, `previous_fingerprint`

2. Determine if change is legitimate:
   - Was the client reinstalled?
   - Was the SSH key intentionally rotated?
   - Is this an unexpected change?

3. If legitimate, accept the new key:
   ```
   accept_key:
     uuid: "<client-uuid>"
   ```

4. If unexpected, investigate further before accepting

### Warning Signs
- Key changed without known cause
- Multiple clients showing key mismatches
- Client metadata doesn't match expectations

## Error Recovery

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "No active client" | No client selected | Run `list_clients`, then `select_client` |
| "Client not found" | Client offline or wrong ID | Check `list_clients` for online clients |
| "Path not in allowed list" | Client has path restrictions | Check `allowed_paths` in `describe_client` |
| "Command timed out" | Timeout too short | Retry with longer `timeout` value |
| "File too large" | File exceeds 10MB limit | Use `download_file` (SFTP, no limit) |

### When Commands Fail

1. Check the `returncode` - non-zero indicates failure
2. Read `stderr` for error messages
3. Verify the command works locally on that platform
4. Check if required tools are installed on client

## Multi-Client Operations

When working with multiple clients:

1. **Always re-verify** the selected client before each operation
2. **Use client_id parameter** to explicitly target a specific client
3. **Don't assume** the active client hasn't changed

```
# Explicit targeting - safer for multi-client work
run_command:
  client_id: "laptop-abc123"
  cmd: "/usr/bin/uptime"

run_command:
  client_id: "server-xyz789"
  cmd: "/usr/bin/uptime"
```

## Quick Reference

### Essential Tools
- `list_clients` - See all clients and their status
- `select_client` - Choose active client
- `describe_client` - Get detailed client info
- `run_command` - Execute commands
- `upload_file` / `download_file` - File transfers (SFTP, no size limit)
- `read_file` / `write_file` - Quick file ops (< 10MB only)
- `get_client_metrics` - System health check

### Safety Checklist
- [ ] Correct client selected?
- [ ] Using absolute paths?
- [ ] Appropriate timeout set?
- [ ] Checked for key mismatch warnings?
- [ ] Reviewed error output?

## Windows Client Specifics

Windows clients have different command syntax and path requirements.

### Path Differences

| Linux | Windows |
|-------|---------|
| `/home/user/file.txt` | `C:\Users\user\file.txt` |
| Forward slashes | Backslashes (or forward in some contexts) |
| Case-sensitive | Case-insensitive |

### Important: write_file Path Validation

The `write_file` tool validates paths must start with `/`. This fails for Windows paths like `C:\temp\file.txt`.

**Workaround**: Use `run_command` with PowerShell instead:

```
# Instead of write_file (which fails on Windows paths)
run_command:
  cmd: 'powershell -Command "Set-Content -Path ''C:\temp\file.txt'' -Value ''content here''"'
```

### Windows Command Execution

```
# PowerShell commands
run_command:
  cmd: "powershell -Command \"Get-Process | Select-Object -First 5\""

# CMD commands
run_command:
  cmd: "cmd /c dir C:\\temp"

# Check if file exists (Windows)
run_command:
  cmd: "powershell -Command \"Test-Path 'C:\\temp\\file.txt'\""
```

## Multi-Hop SSH (Windows → Linux)

When using a Windows client to reach a Linux server via SSH:

### Connection Pattern

```
# From Windows client, SSH to Linux server
run_command:
  cmd: "ssh -o StrictHostKeyChecking=no user@linux-server \"command here\""
  timeout: 60
```

### Known Issues and Solutions

#### Issue 1: Heredocs Don't Work Through SSH
**Problem**: `cat << 'EOF'` syntax fails with "unexpected EOF" errors.

**Solution**: Use base64 encoding instead:
```
# Encode script content as base64, decode on remote
run_command:
  cmd: "ssh user@server \"echo 'BASE64_CONTENT' | base64 -d > /tmp/script.py && python /tmp/script.py\""
```

#### Issue 2: Complex Quote Escaping
**Problem**: Multi-layer escaping (Windows → SSH → Shell → Command) breaks.

**Solution**: Use base64 for complex content, or write to temp file first:
```
# Write simple command results to temp file, then read
run_command:
  cmd: "ssh user@server \"mysql -e 'SELECT 1'\" > C:\\temp\\result.txt"

# Then read the file separately
run_command:
  cmd: "type C:\\temp\\result.txt"
```

#### Issue 3: SSH Session Expiration
**Problem**: `ssh_session_open` sessions can expire, returning "Socket is closed".

**Solution**: Use direct SSH commands via `run_command` instead of persistent sessions for reliability:
```
# More reliable than ssh_session_command
run_command:
  cmd: "ssh user@server \"command\""
```

#### Issue 4: Empty stdout from SSH
**Problem**: SSH commands through Windows sometimes return empty stdout.

**Solution**: Redirect output to temp file, then read:
```
# Step 1: Run SSH command, save to file
run_command:
  cmd: "ssh user@server \"mysql -e 'query'\" > C:\\temp\\out.txt 2>&1"

# Step 2: Read the file
run_command:
  cmd: "type C:\\temp\\out.txt"
```

## Base64 Encoding for Code Transfer

For transferring scripts or complex content through multiple SSH hops:

### Pattern: Encode → Transfer → Decode → Execute

```python
# 1. Encode your script content as base64 (do this locally or calculate)
# Example: "print('hello')" → "cHJpbnQoJ2hlbGxvJyk="

# 2. Transfer and execute via SSH
run_command:
  cmd: "ssh user@server \"echo 'cHJpbnQoJ2hlbGxvJyk=' | base64 -d > /tmp/script.py && python /tmp/script.py\""
```

### Large File Chunking

For files larger than ~4KB (command line limits):

```
# Split base64 into chunks and append
run_command:
  cmd: "ssh user@server \"echo 'CHUNK1' | base64 -d > /tmp/file.py\""

run_command:
  cmd: "ssh user@server \"echo 'CHUNK2' | base64 -d >> /tmp/file.py\""

# Continue for each chunk...
```

### Quick Base64 Reference

```bash
# Encode on Linux
cat script.py | base64 -w 0

# Decode on Linux
echo "BASE64" | base64 -d > script.py

# Encode on Windows PowerShell
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("script.py"))

# Decode on Windows PowerShell
[System.IO.File]::WriteAllBytes("script.py", [Convert]::FromBase64String("BASE64"))
```

## Database Operations Through SSH

When running MySQL/MariaDB queries through SSH from Windows:

### Simple Queries Work

```
run_command:
  cmd: "ssh user@server \"mysql -e 'SELECT 1'\""
```

### Complex Queries Need Escaping Care

```
# Use double-escaping for quotes
run_command:
  cmd: "ssh user@server \"mysql -e \\\"SELECT * FROM table WHERE col = 'value';\\\"\""
```

### Reserved Column Names (like `key`)

```
# Use table.column notation instead of backticks
run_command:
  cmd: "ssh user@server \"mysql cache -e \\\"SELECT dynamic_app.key FROM dynamic_app;\\\"\""
```

### Python Script for Complex Queries

For complex database operations, create a Python script via base64:

```python
# Script to run on remote server
#!/usr/bin/env python2.7
import subprocess
result = subprocess.check_output("mysql -e 'complex query'", shell=True)
print result
```

## Troubleshooting Checklist

### Command Returns Empty

1. Check if command works directly on the target system
2. Try redirecting to temp file and reading separately
3. Check stderr for error messages
4. Verify the command path exists on target OS

### SSH Connection Issues

1. Verify client is online: `list_clients`
2. Check SSH key is accepted: `ssh -o StrictHostKeyChecking=no`
3. Test simple command first: `echo test`
4. Increase timeout for slow connections

### File Transfer Failures

1. Use `upload_file` / `download_file` for reliable SFTP transfers
2. Use `run_command` with shell redirection instead of `write_file` for Windows
3. For very large files (> 100MB), consider R2 file exchange (see file-exchange skill)
4. Verify target directory exists before writing
5. Check disk space on target

### Escaping Problems

1. Start with single quotes around entire command
2. Use base64 encoding for complex content
3. Write to temp file and execute, instead of inline
4. Test incrementally - simple command first, then add complexity
