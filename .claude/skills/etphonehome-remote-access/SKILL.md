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

### Path Requirements
- **ALWAYS** use absolute paths: `/home/user/file.txt`
- **NEVER** use relative paths: `./file.txt`, `../config`
- **NEVER** use home shortcuts without expansion: `~/file.txt`

### Before Reading Files
1. Verify the file exists: `run_command: "test -f /path/to/file && echo exists"`
2. Check file size if potentially large: `run_command: "ls -lh /path/to/file"`
3. Files over 10MB will be rejected

### Before Writing Files
1. Check available disk space: `run_command: "df -h /path"`
2. Verify parent directory exists
3. Consider if backup is needed first

### Example: Safe File Operations

```
# Good - absolute path
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
| "File too large" | File exceeds 10MB limit | Use `download_file` for large files |

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
- `read_file` / `write_file` - File operations
- `get_client_metrics` - System health check

### Safety Checklist
- [ ] Correct client selected?
- [ ] Using absolute paths?
- [ ] Appropriate timeout set?
- [ ] Checked for key mismatch warnings?
- [ ] Reviewed error output?
