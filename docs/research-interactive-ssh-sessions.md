# Research: Interactive SSH Session Management for MCP

## Overview

This document explores adding persistent, interactive SSH session management to the ET Phone Home MCP server. This would enable Claude to maintain stateful SSH connections to remote systems through connected clients.

## Current Architecture

ET Phone Home currently:
- Uses **paramiko** for SSH connections (client → server)
- Creates **reverse tunnels** for server → client communication
- Executes commands via **JSON-RPC** over the tunnel
- Each `run_command` is **stateless** (no session persistence)

## The Problem

When accessing remote systems (like SL1) through an ET Phone Home client:
1. Each SSH command runs in a **new session**
2. State is lost between commands (environment variables, working directory)
3. Commands requiring **interactive prompts** (sudo, confirmations) fail
4. **Overhead** from reconnecting for each command
5. No way to run **multi-step workflows** that depend on session state

## Research Findings

### Paramiko: exec_command() vs invoke_shell()

| Method | Behavior | Use Case |
|--------|----------|----------|
| `exec_command()` | Single command, new session each time | Simple automation |
| `invoke_shell()` | Persistent interactive session | Stateful workflows |

**Key insight**: `exec_command('cd /tmp')` followed by `exec_command('pwd')` returns home directory, not `/tmp`, because each command runs in isolation.

**Sources**:
- [Paramiko Interactive Shell Guide](https://www.pythontutorials.net/blog/implement-an-interactive-shell-over-ssh-in-python-using-paramiko/)
- [Paramiko Official Docs](https://docs.paramiko.org/en/stable/api/client.html)

### invoke_shell() Pattern

```python
import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('host', username='user', password='pass')  # pragma: allowlist secret

# Create persistent shell
shell = client.invoke_shell()

def send_command(shell, cmd, timeout=2):
    shell.send(cmd + '\n')
    time.sleep(timeout)  # Wait for output
    output = ''
    while shell.recv_ready():
        output += shell.recv(4096).decode()
    return output

# Commands share state
send_command(shell, 'cd /tmp')
result = send_command(shell, 'pwd')  # Returns /tmp!
```

### Keeping Sessions Alive

```python
# SSH keepalive to prevent timeout
transport = client.get_transport()
transport.set_keepalive(30)  # Send keepalive every 30 seconds
```

**Source**: [Keep SSH Session Alive with Paramiko](https://www.pythontutorials.net/blog/how-to-keep-ssh-session-not-expired-using-paramiko/)

### AsyncSSH - Better Performance

AsyncSSH provides native async support with better performance:

| Library | Benchmark (10 runs) |
|---------|---------------------|
| asyncssh | 5.31 seconds |
| paramiko | 11.58 seconds |
| netmiko | 27.11 seconds |

```python
import asyncssh

async def run_client():
    async with asyncssh.connect('host', username='user') as conn:
        # Multiple commands share connection
        result1 = await conn.run('cd /tmp && pwd')
        result2 = await conn.run('ls -la')
```

**Sources**:
- [AsyncSSH Documentation](https://asyncssh.readthedocs.io/)
- [SSH Libraries Comparison](https://elegantnetwork.github.io/posts/comparing-ssh/)

### Jump Host / Proxy Support

For scenarios where the ET Phone Home client needs to SSH to another system:

**paramiko-jump** - Easy chaining of SSH connections:
```python
from paramiko_jump import SSHJumpClient

# Connect through jump host
with SSHJumpClient() as jumper:
    jumper.connect(hostname='jump-host', username='user')

    with SSHJumpClient(jump_session=jumper) as target:
        target.connect(hostname='target-host', username='user')
        stdin, stdout, stderr = target.exec_command('command')
```

**jumpssh** - Session management with multiple jumps:
```python
from jumpssh import SSHSession

gateway = SSHSession('gateway', 'user', password='pass').open()  # pragma: allowlist secret
target = gateway.get_remote_session('target', 'user', password='pass')  # pragma: allowlist secret
target.run_cmd('command')
```

**Sources**:
- [paramiko-jump on PyPI](https://pypi.org/project/paramiko-jump/)
- [jumpssh Documentation](https://jumpssh.readthedocs.io/en/latest/introduction.html)

### MCP Stateful Sessions

MCP already supports stateful connections:

> "MCP establishes stateful, persistent connections between a client and server instance. All communication happens over WebSocket + JSON-RPC 2.0. That gives us a stateful, low-latency, two-way connection—perfect for interactive sessions."

**Key MCP features**:
- Persistent connections with session context
- Bidirectional communication
- Context objects for tool state management

**Sources**:
- [MCP Comprehensive Guide](https://dysnix.com/blog/model-context-protocol)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## Proposed Implementation

### Architecture Options

#### Option A: Client-Side SSH Sessions

Add SSH session management to the **ET Phone Home client agent**:

```
Claude CLI → MCP Server → ET Phone Home Client → SSH Session → Target Host
```

**Pros**:
- Client already has network access to targets
- Sessions managed close to the target
- Minimal changes to MCP server

**Cons**:
- Adds complexity to client agent
- State stored on potentially unreliable client

#### Option B: MCP Server-Side Sessions

Add SSH session management to the **MCP server** (using client as jump host):

```
Claude CLI → MCP Server → SSH Session (via client tunnel) → Target Host
```

**Pros**:
- Centralized session management
- Better visibility and control
- Sessions survive client reconnects (if using jump host pattern)

**Cons**:
- More complex routing
- Additional latency

### Recommended: Client-Side Implementation

#### New MCP Tools

```python
# Session lifecycle
ssh_session_open(host, username, [password], [key_file]) -> session_id
ssh_session_close(session_id)
ssh_session_list() -> [sessions]

# Session operations
ssh_session_command(session_id, command) -> output
ssh_session_send(session_id, input) -> output  # For interactive prompts
ssh_session_read(session_id) -> output  # Read pending output
```

#### Client Agent Changes

Add to `client/agent.py`:

```python
class SSHSessionManager:
    """Manage persistent SSH sessions."""

    def __init__(self):
        self.sessions: dict[str, paramiko.Channel] = {}
        self.clients: dict[str, paramiko.SSHClient] = {}

    def open_session(self, session_id: str, host: str,
                     username: str, password: str = None) -> str:
        """Open a new interactive SSH session."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=username, password=password)

        # Enable keepalive
        transport = client.get_transport()
        transport.set_keepalive(30)

        # Create interactive shell
        shell = client.invoke_shell()

        self.clients[session_id] = client
        self.sessions[session_id] = shell
        return session_id

    def send_command(self, session_id: str, cmd: str,
                     timeout: float = 5.0) -> str:
        """Send command and return output."""
        shell = self.sessions[session_id]
        shell.send(cmd + '\n')

        # Wait for output
        output = ''
        deadline = time.time() + timeout
        while time.time() < deadline:
            if shell.recv_ready():
                output += shell.recv(4096).decode()
            else:
                time.sleep(0.1)
        return output

    def close_session(self, session_id: str):
        """Close SSH session."""
        if session_id in self.sessions:
            self.sessions[session_id].close()
            del self.sessions[session_id]
        if session_id in self.clients:
            self.clients[session_id].close()
            del self.clients[session_id]
```

### Session Lifecycle

```
1. ssh_session_open()
   - Claude requests new session
   - Client creates paramiko SSHClient
   - Client invokes interactive shell
   - Returns session_id to Claude

2. ssh_session_command() [repeatable]
   - Claude sends command with session_id
   - Client sends to shell, reads output
   - Returns output to Claude
   - State preserved between calls

3. ssh_session_close()
   - Claude closes session
   - Client closes shell and connection
   - Session resources freed
```

### Considerations

#### Session Timeout
- Implement idle timeout (e.g., 30 minutes)
- Background cleanup of stale sessions
- Keepalive to prevent SSH timeout

#### Output Handling
- Detect command completion (prompt detection)
- Handle long-running commands
- Stream output for commands with continuous output

#### Security
- Credential handling (password vs key-based)
- Session isolation between Claude conversations
- Audit logging of session activity

#### Error Handling
- Connection failures
- Session expiration
- Network interruptions

## Alternative: SSH Config Proxy

For simpler use cases, use SSH config with ProxyJump:

```
# ~/.ssh/config on ET Phone Home client
Host sl1
    HostName 108.174.225.156
    User em7admin
    ProxyJump etphonehome-server

Host target-*
    ProxyJump sl1
```

Then `run_command` can use: `ssh sl1 "command"`

## Implementation Priority

### Phase 1: Basic Sessions
- [ ] `ssh_session_open` / `ssh_session_close`
- [ ] `ssh_session_command`
- [ ] Session timeout/cleanup

### Phase 2: Enhanced Features
- [ ] `ssh_session_send` for interactive prompts
- [ ] Prompt detection for better output handling
- [ ] Session listing and management

### Phase 3: Advanced
- [ ] Jump host support
- [ ] Key-based authentication
- [ ] Session persistence across client reconnects

## References

- [Paramiko Interactive Shell](https://www.pythontutorials.net/blog/implement-an-interactive-shell-over-ssh-in-python-using-paramiko/)
- [AsyncSSH Documentation](https://asyncssh.readthedocs.io/)
- [paramiko-jump](https://github.com/andrewschenck/paramiko-jump)
- [jumpssh](https://jumpssh.readthedocs.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Keeping SSH Alive](https://www.pythontutorials.net/blog/how-to-keep-ssh-session-not-expired-using-paramiko/)
