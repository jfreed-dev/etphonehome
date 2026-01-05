# Webhooks and Rate Limiting Guide

This guide covers the webhook notification system and per-client rate limiting features in ET Phone Home.

## Overview

ET Phone Home can send HTTP webhooks when events occur, allowing you to:
- Monitor client connections in real-time
- Track command execution and file access
- Alert on security-related events (key mismatches)
- Integrate with external monitoring systems (Slack, Discord, PagerDuty, etc.)

Rate limiting tracks request frequency per client and logs warnings when limits are exceeded.

## Webhook Events

| Event | Description | Trigger |
|-------|-------------|---------|
| `client.connected` | Client connected to server | Client registration |
| `client.disconnected` | Client disconnected | Unregistration or disconnect |
| `client.key_mismatch` | SSH key changed | Registration with different key |
| `client.unhealthy` | Health check failed | Multiple heartbeat failures |
| `command_executed` | Shell command run | `run_command` tool |
| `file_accessed` | File operation | `read_file`, `write_file`, `list_files` |

## Webhook Payload Format

All webhooks use this JSON structure:

```json
{
  "event": "client.connected",
  "timestamp": "2026-01-05T10:30:00Z",
  "client_uuid": "abc-123-def-456",
  "client_display_name": "Production Server",
  "data": {
    "hostname": "prod.example.com",
    "platform": "Linux 6.8"
  }
}
```

### Event-Specific Data

**client.connected**
```json
{
  "data": {
    "hostname": "server.example.com",
    "platform": "Linux 6.8",
    "username": "deploy"
  }
}
```

**client.disconnected**
```json
{
  "data": {}
}
```

**client.key_mismatch**
```json
{
  "data": {
    "previous_fingerprint": "SHA256:oldkey...",
    "new_fingerprint": "SHA256:newkey..."
  }
}
```

**client.unhealthy**
```json
{
  "data": {
    "reason": "timeout",
    "consecutive_failures": 3
  }
}
```

**command_executed**
```json
{
  "data": {
    "cmd": "ls -la /var/log",
    "cwd": "/home/user",
    "returncode": 0
  }
}
```

**file_accessed**
```json
{
  "data": {
    "operation": "read",  // or "write", "list"
    "path": "/etc/hosts",
    "size": 1024
  }
}
```

## Configuration

### Environment Variables

Set in `/etc/etphonehome/server.env`:

```bash
# Global webhook URL (all events)
ETPHONEHOME_WEBHOOK_URL=https://your-server.com/webhook

# HTTP timeout for webhook requests (seconds)
ETPHONEHOME_WEBHOOK_TIMEOUT=10.0

# Maximum retry attempts for failed webhooks
ETPHONEHOME_WEBHOOK_MAX_RETRIES=3

# Rate limiting (warn-only mode)
ETPHONEHOME_RATE_LIMIT_RPM=60        # Requests per minute
ETPHONEHOME_RATE_LIMIT_CONCURRENT=10  # Max concurrent requests
```

### Per-Client Configuration

Use the `configure_client` MCP tool to set per-client webhook URLs and rate limits:

```python
# Via MCP tool
configure_client(
    uuid="client-uuid-here",
    webhook_url="https://custom-endpoint.com/hook",
    rate_limit_rpm=30,
    rate_limit_concurrent=5
)
```

Per-client webhook URLs override the global URL. Per-client rate limits override the defaults.

## Integration Examples

### Slack Integration

Create a Slack webhook URL at https://api.slack.com/messaging/webhooks, then use a simple proxy server:

```python
#!/usr/bin/env python3
"""Simple webhook proxy for Slack."""
from flask import Flask, request
import requests

app = Flask(__name__)

SLACK_WEBHOOK = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

EMOJI_MAP = {
    "client.connected": ":white_check_mark:",
    "client.disconnected": ":x:",
    "client.key_mismatch": ":warning:",
    "client.unhealthy": ":skull:",
    "command_executed": ":computer:",
    "file_accessed": ":file_folder:",
}

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    event = data.get("event", "unknown")
    emoji = EMOJI_MAP.get(event, ":question:")

    text = (
        f"{emoji} *{event}*\n"
        f"Client: {data.get('client_display_name', 'Unknown')}\n"
        f"Time: {data.get('timestamp', 'N/A')}"
    )

    if event == "command_executed":
        cmd = data.get("data", {}).get("cmd", "")
        text += f"\nCommand: `{cmd}`"
    elif event == "file_accessed":
        op = data.get("data", {}).get("operation", "")
        path = data.get("data", {}).get("path", "")
        text += f"\nOperation: {op} `{path}`"

    requests.post(SLACK_WEBHOOK, json={"text": text})
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

### Discord Integration

```python
#!/usr/bin/env python3
"""Webhook proxy for Discord."""
from flask import Flask, request
import requests

app = Flask(__name__)

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/YOUR/WEBHOOK"

COLOR_MAP = {
    "client.connected": 0x00FF00,      # Green
    "client.disconnected": 0xFF0000,   # Red
    "client.key_mismatch": 0xFFFF00,   # Yellow
    "client.unhealthy": 0xFF8C00,      # Orange
    "command_executed": 0x0000FF,      # Blue
    "file_accessed": 0x808080,         # Gray
}

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    event = data.get("event", "unknown")

    embed = {
        "title": event,
        "color": COLOR_MAP.get(event, 0x000000),
        "fields": [
            {"name": "Client", "value": data.get("client_display_name", "Unknown"), "inline": True},
            {"name": "UUID", "value": data.get("client_uuid", "N/A")[:8] + "...", "inline": True},
        ],
        "timestamp": data.get("timestamp"),
    }

    # Add event-specific fields
    if event == "command_executed":
        embed["fields"].append({
            "name": "Command",
            "value": f"```{data.get('data', {}).get('cmd', '')}```",
            "inline": False
        })

    requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]})
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

### PagerDuty Integration

For critical alerts (key_mismatch, unhealthy):

```python
#!/usr/bin/env python3
"""PagerDuty integration for critical events."""
from flask import Flask, request
import requests

app = Flask(__name__)

PAGERDUTY_KEY = "your-pagerduty-integration-key"
CRITICAL_EVENTS = {"client.key_mismatch", "client.unhealthy"}

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    event = data.get("event", "unknown")

    if event not in CRITICAL_EVENTS:
        return "OK"  # Ignore non-critical events

    payload = {
        "routing_key": PAGERDUTY_KEY,
        "event_action": "trigger",
        "payload": {
            "summary": f"ET Phone Home: {event}",
            "source": data.get("client_display_name", "Unknown"),
            "severity": "critical" if event == "client.key_mismatch" else "warning",
            "custom_details": {
                "client_uuid": data.get("client_uuid"),
                "timestamp": data.get("timestamp"),
                **data.get("data", {})
            }
        }
    }

    requests.post(
        "https://events.pagerduty.com/v2/enqueue",
        json=payload
    )
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

### Simple Logging Server

For development and debugging:

```python
#!/usr/bin/env python3
"""Simple webhook logging server."""
from flask import Flask, request
from datetime import datetime
import json

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    timestamp = datetime.now().isoformat()

    print(f"\n{'='*60}")
    print(f"Received at: {timestamp}")
    print(f"Event: {data.get('event')}")
    print(f"Client: {data.get('client_display_name')} ({data.get('client_uuid', '')[:8]}...)")
    print(f"Data: {json.dumps(data.get('data', {}), indent=2)}")
    print(f"{'='*60}\n")

    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

### Webhook Receiver with Verification

For production, verify webhook authenticity:

```python
#!/usr/bin/env python3
"""Webhook receiver with IP verification."""
from flask import Flask, request, abort

app = Flask(__name__)

# Only accept webhooks from trusted IPs
ALLOWED_IPS = {"192.168.1.100", "10.0.0.50"}

@app.route("/webhook", methods=["POST"])
def webhook():
    # Verify source IP
    client_ip = request.remote_addr
    if client_ip not in ALLOWED_IPS:
        abort(403)

    data = request.json
    # Process webhook...
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

## Rate Limiting

### How It Works

Rate limiting operates in **warn-only mode**:
- Tracks requests per minute (RPM) and concurrent requests per client
- Logs warnings when limits are exceeded
- **Does NOT block requests** - all requests still execute

### Monitoring Rate Limits

Use the `get_rate_limit_stats` MCP tool:

```python
get_rate_limit_stats(uuid="client-uuid-here")
```

Returns:
```json
{
  "uuid": "client-uuid-here",
  "stats": {
    "current_rpm": 45,
    "rpm_limit": 60,
    "current_concurrent": 3,
    "concurrent_limit": 10,
    "rpm_warnings_total": 2,
    "concurrent_warnings_total": 0
  }
}
```

### Per-Client Rate Limits

Set custom limits for specific clients:

```python
configure_client(
    uuid="high-volume-client",
    rate_limit_rpm=120,        # Double the default
    rate_limit_concurrent=20   # Double the default
)
```

Or for restricted clients:

```python
configure_client(
    uuid="restricted-client",
    rate_limit_rpm=10,
    rate_limit_concurrent=2
)
```

## Troubleshooting

### Webhooks Not Firing

1. Check the global webhook URL is set:
   ```bash
   grep WEBHOOK /etc/etphonehome/server.env
   ```

2. Verify the URL is reachable from the server:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"test": true}' \
     https://your-webhook-url.com/hook
   ```

3. Check server logs for errors:
   ```bash
   journalctl -u etphonehome-mcp -f
   ```

### Rate Limit Warnings

If you see rate limit warnings in logs:

1. Check current stats: `get_rate_limit_stats(uuid="...")`
2. Consider increasing limits if legitimate:
   ```python
   configure_client(uuid="...", rate_limit_rpm=120)
   ```
3. Or investigate why requests are so frequent

### Webhook Timeouts

If webhooks are timing out:

1. Increase the timeout:
   ```bash
   ETPHONEHOME_WEBHOOK_TIMEOUT=30.0
   ```

2. Ensure your webhook endpoint responds quickly
3. Consider async processing in your webhook handler

## Security Considerations

1. **Use HTTPS** for all webhook URLs
2. **Verify source IPs** when possible
3. **Keep webhook URLs secret** - treat them like API keys
4. **Rate limit your webhook endpoint** to prevent abuse
5. **Log webhook events** for audit trails
6. **Monitor for key_mismatch events** - may indicate security issues
