#!/usr/bin/env python3
"""Handle SSH exec commands for client registration."""
import json
import sys
import os
import urllib.request
import urllib.error

# Add the etphonehome directory to path
sys.path.insert(0, "/opt/etphonehome")
os.chdir("/opt/etphonehome")

from pathlib import Path
from datetime import datetime

MCP_SERVER_URL = "http://127.0.0.1:8765/internal/register"

STORE_PATH = Path("/home/etphonehome/.etphonehome-server/clients.json")

def load_store():
    if STORE_PATH.exists():
        with open(STORE_PATH) as f:
            return json.load(f)
    return {"version": 1, "clients": {}}

def save_store(data):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STORE_PATH.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    tmp_path.rename(STORE_PATH)

def notify_mcp_server(registration):
    """Notify the MCP HTTP server about the new registration."""
    try:
        data = json.dumps(registration).encode("utf-8")
        req = urllib.request.Request(
            MCP_SERVER_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        # MCP server might not be running, log but don't fail
        print(f"Warning: Could not notify MCP server: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: MCP notification error: {e}", file=sys.stderr)
        return None

def handle_register(registration):
    identity = registration.get("identity", {})
    client_info = registration.get("client_info", {})

    uuid = identity.get("uuid", "")
    if not uuid:
        return {"error": "No UUID in registration"}

    store = load_store()
    now = datetime.utcnow().isoformat() + "Z"

    existing = store["clients"].get(uuid)
    if existing:
        conn_count = existing.get("connection_count", 0) + 1
    else:
        conn_count = 1

    store["clients"][uuid] = {
        "identity": identity,
        "last_seen": now,
        "connection_count": conn_count,
        "last_client_info": client_info
    }

    save_store(store)

    # Notify MCP HTTP server to update in-memory registry
    notify_mcp_server(registration)

    return {"registered": uuid, "display_name": identity.get("display_name", "")}

def main():
    # Read the command from SSH_ORIGINAL_COMMAND
    cmd = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    
    if not cmd:
        print("No command provided", file=sys.stderr)
        sys.exit(1)
    
    if cmd.startswith("register "):
        try:
            payload = cmd[9:]  # Remove "register "
            registration = json.loads(payload)
            result = handle_register(registration)
            print(json.dumps(result))
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON: {e}"}))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
