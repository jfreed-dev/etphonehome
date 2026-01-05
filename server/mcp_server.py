#!/usr/bin/env python3
"""
ET Phone Home - MCP Server

Exposes tools to Claude CLI for interacting with connected remote clients.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from server.client_connection import ClientConnection
from server.client_registry import ClientRegistry
from server.client_store import ClientStore
from server.health_monitor import HealthMonitor
from server.rate_limiter import (
    RateLimitConfig,
    RateLimitContext,
    RateLimiter,
    get_rate_limiter,
    set_rate_limiter,
)
from server.webhooks import (
    EventType,
    WebhookDispatcher,
    get_dispatcher,
    set_dispatcher,
)
from shared.logging_config import get_default_log_file, setup_logging
from shared.protocol import (
    ClientNotFoundError,
    InvalidArgumentError,
    NoActiveClientError,
    ToolError,
)

# Get logging configuration from environment
_log_level = os.environ.get("ETPHONEHOME_LOG_LEVEL", "INFO")
_log_file = os.environ.get("ETPHONEHOME_LOG_FILE", str(get_default_log_file("server")))
_log_max_bytes = int(os.environ.get("ETPHONEHOME_LOG_MAX_BYTES", 10 * 1024 * 1024))
_log_backup_count = int(os.environ.get("ETPHONEHOME_LOG_BACKUP_COUNT", 5))

# Configure logging to stderr (stdout is used for MCP protocol) and file with rotation
logger = setup_logging(
    name="etphonehome",
    level=_log_level,
    log_file=_log_file,
    max_bytes=_log_max_bytes,
    backup_count=_log_backup_count,
    stream=sys.stderr,
)

# Global store and registry
store = ClientStore()
registry = ClientRegistry(store)

# Cache of client connections
_connections: dict[str, ClientConnection] = {}

# Health monitor for automatic disconnect detection
_health_monitor: HealthMonitor | None = None


async def get_connection(client_id: str = None) -> ClientConnection:
    """Get a connection to a client."""
    if client_id is None:
        # Try active registry first
        client = await registry.get_active_client()
        if client:
            client_id = client.info.client_id
            port = client.info.tunnel_port
        else:
            # Fall back to stored clients - find one with a valid tunnel
            stored_clients = store.list_all()
            for sc in stored_clients:
                if sc.last_client_info and sc.last_client_info.get("tunnel_port"):
                    port = sc.last_client_info["tunnel_port"]
                    client_id = sc.last_client_info.get("client_id", sc.identity.uuid)
                    break
            else:
                # Get online client names for helpful error
                online_clients = [
                    sc.identity.display_name
                    for sc in stored_clients
                    if sc.last_client_info and sc.last_client_info.get("tunnel_port")
                ]
                raise NoActiveClientError(
                    online_count=len(online_clients),
                    client_names=online_clients,
                )
    else:
        # Try active registry first
        client = await registry.get_client(client_id)
        if client:
            port = client.info.tunnel_port
        else:
            # Look up in store by client_id or UUID
            stored = store.get_by_uuid(client_id)
            if not stored:
                # Try to find by client_id in last_client_info
                for sc in store.list_all():
                    if sc.last_client_info and sc.last_client_info.get("client_id") == client_id:
                        stored = sc
                        break
            if not stored or not stored.last_client_info:
                # Get available client IDs for helpful error
                available = [sc.identity.display_name for sc in store.list_all()]
                raise ClientNotFoundError(client_id, available_clients=available)
            port = stored.last_client_info.get("tunnel_port")
            if not port:
                raise ClientNotFoundError(client_id)

    if client_id not in _connections:
        _connections[client_id] = ClientConnection("127.0.0.1", port)

    return _connections[client_id]


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("etphonehome")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools organized by category."""
        return [
            # ===== CLIENT MANAGEMENT =====
            Tool(
                name="list_clients",
                description="List all clients registered with the server, showing UUID, display name, purpose, online/offline status, and metadata. Use this first to discover available clients.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="select_client",
                description="Select a client as the active target for subsequent operations. The selected client becomes the default for commands and file operations until changed.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "client_id": {
                            "type": "string",
                            "description": "Client ID or UUID to select as active",
                            "minLength": 1,
                        }
                    },
                    "required": ["client_id"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="find_client",
                description="Search for clients matching specific criteria. Returns clients filtered by search query, purpose, tags, or capabilities. Use online_only to filter to connected clients.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term matching display_name, purpose, or hostname",
                            "minLength": 1,
                        },
                        "purpose": {
                            "type": "string",
                            "description": "Filter by purpose (e.g., 'Production', 'Development')",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by tags - client must have ALL specified tags",
                        },
                        "capabilities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by capabilities (e.g., 'docker', 'python3.12')",
                        },
                        "online_only": {
                            "type": "boolean",
                            "description": "Only return currently connected clients (default: false)",
                            "default": False,
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="describe_client",
                description="Get detailed information about a specific client including full metadata, connection history, SSH key fingerprint, allowed paths, and current status.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uuid": {
                            "type": "string",
                            "description": "Client UUID (36 character identifier)",
                            "minLength": 1,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Client ID (alternative to UUID)",
                            "minLength": 1,
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="update_client",
                description="Update client metadata including display name, purpose, tags, and allowed paths. Changes are persisted and survive reconnections.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uuid": {
                            "type": "string",
                            "description": "Client UUID to update",
                            "minLength": 1,
                        },
                        "display_name": {
                            "type": "string",
                            "description": "Human-readable name (e.g., 'Production API Server')",
                            "minLength": 1,
                            "maxLength": 100,
                        },
                        "purpose": {
                            "type": "string",
                            "description": "Role or function (e.g., 'CI Runner', 'Database')",
                            "maxLength": 200,
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Categorization tags (replaces existing tags)",
                        },
                        "allowed_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Allowed path prefixes for file operations (null for unrestricted)",
                        },
                    },
                    "required": ["uuid"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="accept_key",
                description="Accept a client's new SSH key after verifying the change is legitimate (reinstall, key rotation). Clears the key_mismatch flag allowing normal operations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uuid": {
                            "type": "string",
                            "description": "Client UUID with key mismatch to accept",
                            "minLength": 1,
                        },
                    },
                    "required": ["uuid"],
                    "additionalProperties": False,
                },
            ),
            # ===== COMMAND EXECUTION =====
            Tool(
                name="run_command",
                description="Execute a shell command on a remote client. Returns stdout, stderr, and exit code. Use absolute paths for cwd. Commands run with the client user's permissions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cmd": {
                            "type": "string",
                            "description": "Shell command to execute",
                            "minLength": 1,
                            "maxLength": 10000,
                        },
                        "cwd": {
                            "type": "string",
                            "description": "Working directory (must be absolute path starting with /)",
                            "pattern": "^/.*",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Command timeout in seconds (default: 300, max: 3600)",
                            "minimum": 1,
                            "maximum": 3600,
                            "default": 300,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Target client ID/UUID (uses active client if not specified)",
                        },
                    },
                    "required": ["cmd"],
                    "additionalProperties": False,
                },
            ),
            # ===== FILE OPERATIONS =====
            Tool(
                name="read_file",
                description="Read the contents of a file from a remote client. Returns content as text (or base64 for binary). Files over 10MB are rejected - use download_file for large files.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file (must start with /)",
                            "pattern": "^/.*",
                            "minLength": 1,
                            "maxLength": 4096,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Target client ID/UUID (uses active client if not specified)",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="write_file",
                description="Write content to a file on a remote client. Creates parent directories if needed. Use absolute paths only.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute destination path (must start with /)",
                            "pattern": "^/.*",
                            "minLength": 1,
                            "maxLength": 4096,
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file",
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Target client ID/UUID (uses active client if not specified)",
                        },
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="list_files",
                description="List files and directories at a path on a remote client. Returns name, type (file/dir), size, permissions, and modification time for each entry.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to directory (must start with /)",
                            "pattern": "^/.*",
                            "minLength": 1,
                            "maxLength": 4096,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Target client ID/UUID (uses active client if not specified)",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="upload_file",
                description="Upload a file from the MCP server to a remote client. Use for transferring files that exist on the server to client machines.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "local_path": {
                            "type": "string",
                            "description": "Source path on the MCP server",
                            "minLength": 1,
                            "maxLength": 4096,
                        },
                        "remote_path": {
                            "type": "string",
                            "description": "Destination path on the client (absolute, must start with /)",
                            "pattern": "^/.*",
                            "minLength": 1,
                            "maxLength": 4096,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Target client ID/UUID (uses active client if not specified)",
                        },
                    },
                    "required": ["local_path", "remote_path"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="download_file",
                description="Download a file from a remote client to the MCP server. Use for large files or when you need the file on the server filesystem.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "remote_path": {
                            "type": "string",
                            "description": "Source path on the client (absolute, must start with /)",
                            "pattern": "^/.*",
                            "minLength": 1,
                            "maxLength": 4096,
                        },
                        "local_path": {
                            "type": "string",
                            "description": "Destination path on the MCP server",
                            "minLength": 1,
                            "maxLength": 4096,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Target client ID/UUID (uses active client if not specified)",
                        },
                    },
                    "required": ["remote_path", "local_path"],
                    "additionalProperties": False,
                },
            ),
            # ===== MONITORING & DIAGNOSTICS =====
            Tool(
                name="get_client_metrics",
                description="Get real-time system health metrics from a client including CPU load, memory usage, disk space, network stats, and uptime. Use summary=true for condensed output.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "client_id": {
                            "type": "string",
                            "description": "Target client ID/UUID (uses active client if not specified)",
                        },
                        "summary": {
                            "type": "boolean",
                            "description": "Return condensed summary instead of full metrics (default: false)",
                            "default": False,
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="get_rate_limit_stats",
                description="Get rate limiting statistics for a client including current request rate, concurrent requests, and limit thresholds.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uuid": {
                            "type": "string",
                            "description": "Client UUID to get stats for",
                            "minLength": 1,
                        },
                    },
                    "required": ["uuid"],
                    "additionalProperties": False,
                },
            ),
            # ===== CONFIGURATION & ADMINISTRATION =====
            Tool(
                name="configure_client",
                description="Configure per-client operational settings including webhook URL for event notifications and rate limits (requests per minute, max concurrent).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uuid": {
                            "type": "string",
                            "description": "Client UUID to configure",
                            "minLength": 1,
                        },
                        "webhook_url": {
                            "type": "string",
                            "description": "Webhook URL for client events (empty string to clear)",
                            "maxLength": 2000,
                        },
                        "rate_limit_rpm": {
                            "type": "integer",
                            "description": "Max requests per minute (null for server default)",
                            "minimum": 1,
                            "maximum": 1000,
                        },
                        "rate_limit_concurrent": {
                            "type": "integer",
                            "description": "Max concurrent requests (null for server default)",
                            "minimum": 1,
                            "maximum": 100,
                        },
                    },
                    "required": ["uuid"],
                    "additionalProperties": False,
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls with structured error responses."""
        try:
            result = await _handle_tool(name, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except ToolError as e:
            # Structured error with recovery hints
            logger.warning(f"Tool error in {name}: {e.code} - {e.message}")
            return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]
        except asyncio.TimeoutError:
            logger.warning(f"Tool timeout in {name}")
            error_response = {
                "error": "TIMEOUT",
                "message": "Operation timed out",
                "recovery_hint": "Try with a longer timeout or break into smaller operations.",
            }
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
        except FileNotFoundError as e:
            logger.warning(f"File not found in {name}: {e}")
            error_response = {
                "error": "FILE_NOT_FOUND",
                "message": str(e),
                "recovery_hint": "Verify the path exists using 'list_files' or 'run_command' with 'ls'.",
            }
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
        except PermissionError as e:
            logger.warning(f"Permission denied in {name}: {e}")
            error_response = {
                "error": "PERMISSION_DENIED",
                "message": str(e),
                "recovery_hint": "Check client's allowed_paths with 'describe_client', or verify file permissions.",
            }
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
        except ConnectionError as e:
            logger.warning(f"Connection error in {name}: {e}")
            error_response = {
                "error": "CONNECTION_ERROR",
                "message": f"Failed to connect to client: {e}",
                "recovery_hint": "Check if the client is online with 'list_clients'. The client may have disconnected.",
            }
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
        except Exception as e:
            logger.exception(f"Unexpected tool error in {name}")
            error_response = {
                "error": "INTERNAL_ERROR",
                "message": str(e),
                "recovery_hint": "An unexpected error occurred. Check server logs for details.",
            }
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

    return server


async def _handle_tool(name: str, args: dict) -> Any:
    """Route tool calls to their implementations."""

    if name == "list_clients":
        clients = await registry.list_clients()
        return {
            "clients": clients,
            "active_client": registry.active_client_uuid,
            "online_count": registry.online_count,
            "total_count": registry.total_count,
            "message": "No clients connected" if not clients else None,
        }

    elif name == "select_client":
        client_id = args["client_id"]
        success = await registry.select_client(client_id)
        if success:
            return {"selected": client_id, "message": f"Selected client: {client_id}"}
        else:
            # Get available clients for helpful error
            clients = await registry.list_clients()
            available = [c["display_name"] for c in clients if c.get("online")]
            raise ClientNotFoundError(client_id, available_clients=available)

    elif name == "run_command":
        client_id = args.get("client_id")
        conn = await get_connection(client_id)

        # Get client UUID for rate limiting and webhooks
        client = (
            await registry.get_client(client_id)
            if client_id
            else await registry.get_active_client()
        )
        client_uuid = client.identity.uuid if client else None
        client_display_name = client.identity.display_name if client else "Unknown"
        client_webhook_url = client.identity.webhook_url if client else None

        limiter = get_rate_limiter()
        if limiter and client_uuid:
            async with RateLimitContext(limiter, client_uuid, "run_command"):
                result = await conn.run_command(
                    cmd=args["cmd"], cwd=args.get("cwd"), timeout=args.get("timeout")
                )
        else:
            result = await conn.run_command(
                cmd=args["cmd"], cwd=args.get("cwd"), timeout=args.get("timeout")
            )

        # Dispatch command executed webhook
        dispatcher = get_dispatcher()
        if dispatcher and client_uuid:
            dispatcher.dispatch(
                event=EventType.COMMAND_EXECUTED,
                client_uuid=client_uuid,
                client_display_name=client_display_name,
                data={
                    "cmd": args["cmd"],
                    "cwd": args.get("cwd"),
                    "returncode": result.get("returncode"),
                },
                client_webhook_url=client_webhook_url,
            )

        return result

    elif name == "read_file":
        client_id = args.get("client_id")
        conn = await get_connection(client_id)

        # Get client UUID for rate limiting and webhooks
        client = (
            await registry.get_client(client_id)
            if client_id
            else await registry.get_active_client()
        )
        client_uuid = client.identity.uuid if client else None
        client_display_name = client.identity.display_name if client else "Unknown"
        client_webhook_url = client.identity.webhook_url if client else None

        limiter = get_rate_limiter()
        if limiter and client_uuid:
            async with RateLimitContext(limiter, client_uuid, "read_file"):
                result = await conn.read_file(args["path"])
        else:
            result = await conn.read_file(args["path"])

        # Dispatch file accessed webhook
        dispatcher = get_dispatcher()
        if dispatcher and client_uuid:
            dispatcher.dispatch(
                event=EventType.FILE_ACCESSED,
                client_uuid=client_uuid,
                client_display_name=client_display_name,
                data={
                    "operation": "read",
                    "path": args["path"],
                    "size": result.get("size"),
                },
                client_webhook_url=client_webhook_url,
            )

        return result

    elif name == "write_file":
        client_id = args.get("client_id")
        conn = await get_connection(client_id)

        # Get client UUID for rate limiting and webhooks
        client = (
            await registry.get_client(client_id)
            if client_id
            else await registry.get_active_client()
        )
        client_uuid = client.identity.uuid if client else None
        client_display_name = client.identity.display_name if client else "Unknown"
        client_webhook_url = client.identity.webhook_url if client else None

        limiter = get_rate_limiter()
        if limiter and client_uuid:
            async with RateLimitContext(limiter, client_uuid, "write_file"):
                result = await conn.write_file(args["path"], args["content"])
        else:
            result = await conn.write_file(args["path"], args["content"])

        # Dispatch file accessed webhook
        dispatcher = get_dispatcher()
        if dispatcher and client_uuid:
            dispatcher.dispatch(
                event=EventType.FILE_ACCESSED,
                client_uuid=client_uuid,
                client_display_name=client_display_name,
                data={
                    "operation": "write",
                    "path": args["path"],
                    "size": result.get("size"),
                },
                client_webhook_url=client_webhook_url,
            )

        return result

    elif name == "list_files":
        client_id = args.get("client_id")
        conn = await get_connection(client_id)

        # Get client UUID for rate limiting and webhooks
        client = (
            await registry.get_client(client_id)
            if client_id
            else await registry.get_active_client()
        )
        client_uuid = client.identity.uuid if client else None
        client_display_name = client.identity.display_name if client else "Unknown"
        client_webhook_url = client.identity.webhook_url if client else None

        limiter = get_rate_limiter()
        if limiter and client_uuid:
            async with RateLimitContext(limiter, client_uuid, "list_files"):
                result = await conn.list_files(args["path"])
        else:
            result = await conn.list_files(args["path"])

        # Dispatch file accessed webhook
        dispatcher = get_dispatcher()
        if dispatcher and client_uuid:
            dispatcher.dispatch(
                event=EventType.FILE_ACCESSED,
                client_uuid=client_uuid,
                client_display_name=client_display_name,
                data={
                    "operation": "list",
                    "path": args["path"],
                    "count": len(result.get("files", [])),
                },
                client_webhook_url=client_webhook_url,
            )

        return result

    elif name == "upload_file":
        local_path = Path(args["local_path"])
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        # Read local file
        content = local_path.read_bytes()
        import base64

        encoded = base64.b64encode(content).decode("ascii")

        # Write to remote
        conn = await get_connection(args.get("client_id"))
        result = await conn.write_file(args["remote_path"], encoded, binary=True)
        return {"uploaded": args["remote_path"], "size": result["size"]}

    elif name == "download_file":
        conn = await get_connection(args.get("client_id"))
        result = await conn.read_file(args["remote_path"])

        local_path = Path(args["local_path"])
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if result.get("binary"):
            import base64

            content = base64.b64decode(result["content"])
            local_path.write_bytes(content)
        else:
            local_path.write_text(result["content"])

        return {"downloaded": str(local_path), "size": result["size"]}

    elif name == "find_client":
        results = await registry.find_clients(
            query=args.get("query"),
            purpose=args.get("purpose"),
            tags=args.get("tags"),
            capabilities=args.get("capabilities"),
            online_only=args.get("online_only", False),
        )
        return {
            "clients": results,
            "count": len(results),
            "message": "No matching clients found" if not results else None,
        }

    elif name == "describe_client":
        identifier = args.get("uuid") or args.get("client_id")
        if not identifier:
            raise InvalidArgumentError(
                "uuid/client_id",
                "Must provide either 'uuid' or 'client_id' parameter",
            )

        result = await registry.describe_client(identifier)
        if not result:
            raise ClientNotFoundError(identifier)
        return result

    elif name == "update_client":
        uuid = args["uuid"]
        result = await registry.update_client(
            uuid=uuid,
            display_name=args.get("display_name"),
            purpose=args.get("purpose"),
            tags=args.get("tags"),
            allowed_paths=args.get("allowed_paths"),
        )
        if not result:
            raise ClientNotFoundError(uuid)
        return {"updated": result, "message": f"Updated client: {uuid}"}

    elif name == "accept_key":
        uuid = args["uuid"]
        result = await registry.accept_key(uuid)
        if not result:
            raise ClientNotFoundError(uuid)
        if result.get("no_mismatch"):
            return {"message": f"Client {uuid} had no key mismatch to clear"}
        return {"accepted": result, "message": f"Accepted new key for client: {uuid}"}

    elif name == "get_client_metrics":
        conn = await get_connection(args.get("client_id"))
        summary = args.get("summary", False)
        result = await conn.get_metrics(summary=summary)
        return result

    elif name == "configure_client":
        uuid = args["uuid"]
        webhook_url = args.get("webhook_url")
        rate_limit_rpm = args.get("rate_limit_rpm")
        rate_limit_concurrent = args.get("rate_limit_concurrent")

        # Update client store
        result = await registry.update_client(
            uuid=uuid,
            webhook_url=webhook_url,
            rate_limit_rpm=rate_limit_rpm,
            rate_limit_concurrent=rate_limit_concurrent,
        )

        if not result:
            raise ClientNotFoundError(uuid)

        # Update rate limiter config if provided
        limiter = get_rate_limiter()
        if limiter and (rate_limit_rpm is not None or rate_limit_concurrent is not None):
            config = limiter.get_client_config(uuid)
            new_config = RateLimitConfig(
                requests_per_minute=(
                    rate_limit_rpm if rate_limit_rpm is not None else config.requests_per_minute
                ),
                max_concurrent=(
                    rate_limit_concurrent
                    if rate_limit_concurrent is not None
                    else config.max_concurrent
                ),
            )
            limiter.set_client_config(uuid, new_config)

        return {
            "configured": uuid,
            "webhook_url": webhook_url,
            "rate_limit_rpm": rate_limit_rpm,
            "rate_limit_concurrent": rate_limit_concurrent,
            "message": f"Configured client: {uuid}",
        }

    elif name == "get_rate_limit_stats":
        uuid = args["uuid"]
        limiter = get_rate_limiter()
        if not limiter:
            raise ToolError(
                code="RATE_LIMITER_NOT_INITIALIZED",
                message="Rate limiter is not initialized",
                recovery_hint="Rate limiting may be disabled. Check server configuration.",
            )
        stats = limiter.get_stats(uuid)
        return {"uuid": uuid, "stats": stats}

    else:
        raise ValueError(f"Unknown tool: {name}")


async def register_client_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle client registration connections."""
    try:
        data = await reader.read(4096)
        if data:
            # Parse registration data
            text = data.decode("utf-8").strip()
            if text.startswith("register "):
                info_str = text[9:]
                info_dict = json.loads(info_str.replace("'", '"'))
                from shared.protocol import ClientInfo

                info = ClientInfo.from_dict(info_dict)
                await registry.register(info)
                writer.write(b"OK\n")
            else:
                writer.write(b"ERROR: Unknown command\n")
    except Exception as e:
        logger.error(f"Registration error: {e}")
        writer.write(f"ERROR: {e}\n".encode())
    finally:
        await writer.drain()
        writer.close()


async def run_stdio():
    """Run the MCP server with stdio transport."""
    global _health_monitor

    logger.info("Starting ET Phone Home MCP server (stdio)")

    server = create_server()

    # Initialize and start webhook dispatcher
    dispatcher = WebhookDispatcher()
    set_dispatcher(dispatcher)
    await dispatcher.start()
    logger.info("Webhook dispatcher started")

    # Initialize rate limiter
    limiter = RateLimiter()
    set_rate_limiter(limiter)
    logger.info(
        f"Rate limiter initialized (rpm={limiter.default_rpm}, concurrent={limiter.default_concurrent})"
    )

    # Start health monitor for automatic disconnect detection
    _health_monitor = HealthMonitor(registry, _connections)
    await _health_monitor.start()

    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP server ready")
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        if _health_monitor:
            await _health_monitor.stop()
        if dispatcher:
            await dispatcher.stop()
            logger.info("Webhook dispatcher stopped")


async def run_http(host: str, port: int, api_key: str = None):
    """Run the MCP server with HTTP/SSE transport."""
    global _health_monitor

    from server.http_server import run_http_server

    # Initialize and start webhook dispatcher
    dispatcher = WebhookDispatcher()
    set_dispatcher(dispatcher)
    await dispatcher.start()
    logger.info("Webhook dispatcher started")

    # Initialize rate limiter
    limiter = RateLimiter()
    set_rate_limiter(limiter)
    logger.info(
        f"Rate limiter initialized (rpm={limiter.default_rpm}, concurrent={limiter.default_concurrent})"
    )

    # Start health monitor for automatic disconnect detection
    _health_monitor = HealthMonitor(registry, _connections)
    await _health_monitor.start()

    try:
        await run_http_server(host=host, port=port, api_key=api_key)
    finally:
        if _health_monitor:
            await _health_monitor.stop()
        if dispatcher:
            await dispatcher.stop()
            logger.info("Webhook dispatcher stopped")


def main():
    """Entry point with transport selection."""
    parser = argparse.ArgumentParser(description="ET Phone Home MCP Server")
    parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8765,
        help="HTTP server port (default: 8765)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for authentication (or set ETPHONEHOME_API_KEY env var)",
    )

    args = parser.parse_args()

    if args.transport == "http":
        asyncio.run(run_http(args.host, args.port, args.api_key))
    else:
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
