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
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

# CRITICAL: Prevent module duplication when running as `python -m server.mcp_server`
# Without this, __main__ and server.mcp_server are separate modules with separate globals,
# causing registry updates in __main__ to be invisible to code imported from server.mcp_server
if __name__ == "__main__":
    sys.modules["server.mcp_server"] = sys.modules[__name__]

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


async def recover_active_clients():
    """
    Recover clients that have active tunnels after server restart.

    On server restart, SSH tunnels may still be active but the in-memory
    registry is empty. This function checks stored clients and re-registers
    those with working tunnel connections.
    """
    from shared.protocol import METHOD_HEARTBEAT

    stored_clients = store.list_all()
    recovered = 0

    for sc in stored_clients:
        if not sc.last_client_info:
            continue

        port = sc.last_client_info.get("tunnel_port")
        if not port:
            continue

        # Try to connect and send heartbeat
        try:
            conn = ClientConnection("127.0.0.1", port, timeout=3.0)
            response = await conn.send_request(METHOD_HEARTBEAT)
            await conn.disconnect()

            if response.result and response.result.get("status") == "alive":
                # Client is alive - re-register it
                registration = {
                    "identity": sc.identity.to_dict(),
                    "client_info": sc.last_client_info,
                }
                await registry.register(registration)
                logger.info(f"Recovered client: {sc.identity.display_name} " f"(port {port})")
                recovered += 1
        except Exception as e:
            # Tunnel not responding - client likely disconnected
            logger.debug(f"Client {sc.identity.display_name} tunnel not responding: {e}")

    if recovered > 0:
        logger.info(f"Startup recovery: {recovered} client(s) reconnected")
    else:
        logger.debug("Startup recovery: no active tunnels found")


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


async def _execute_with_tracking(
    client_id: str | None,
    method_name: str,
    operation: Callable[[ClientConnection], Awaitable[Any]],
    webhook_event: EventType | None = None,
    webhook_data_fn: Callable[[dict, Any], dict] | None = None,
    operation_args: dict | None = None,
) -> Any:
    """
    Execute an operation with rate limiting and webhook dispatch.

    This helper consolidates the common pattern used by run_command, read_file,
    write_file, and list_files to reduce code duplication.

    Args:
        client_id: Target client ID/UUID (uses active client if not specified)
        method_name: Name of the method for rate limiting tracking
        operation: Async callable that takes a ClientConnection and returns a result
        webhook_event: Event type to dispatch (None to skip webhook)
        webhook_data_fn: Function(args, result) to generate webhook data
        operation_args: Original operation arguments (passed to webhook_data_fn)

    Returns:
        Result from the operation
    """
    conn = await get_connection(client_id)

    # Get client for rate limiting and webhooks
    client = (
        await registry.get_client(client_id) if client_id else await registry.get_active_client()
    )
    client_uuid = client.identity.uuid if client else None
    client_display_name = client.identity.display_name if client else "Unknown"
    client_webhook_url = client.identity.webhook_url if client else None

    # Execute with rate limiting
    limiter = get_rate_limiter()
    if limiter and client_uuid:
        async with RateLimitContext(limiter, client_uuid, method_name):
            result = await operation(conn)
    else:
        result = await operation(conn)

    # Dispatch webhook
    dispatcher = get_dispatcher()
    if dispatcher and client_uuid and webhook_event and webhook_data_fn:
        webhook_data = webhook_data_fn(operation_args or {}, result)
        dispatcher.dispatch(
            event=webhook_event,
            client_uuid=client_uuid,
            client_display_name=client_display_name,
            data=webhook_data,
            client_webhook_url=client_webhook_url,
        )

    return result


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
            # ===== SSH SESSION MANAGEMENT =====
            Tool(
                name="ssh_session_open",
                description="Open a persistent SSH session to a remote host through the ET Phone Home client. The session maintains state (working directory, environment) across commands. Use password OR key_file for authentication.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Target hostname or IP address",
                            "minLength": 1,
                            "maxLength": 255,
                        },
                        "username": {
                            "type": "string",
                            "description": "SSH username",
                            "minLength": 1,
                            "maxLength": 64,
                        },
                        "password": {
                            "type": "string",
                            "description": "SSH password (optional if using key_file)",
                        },
                        "key_file": {
                            "type": "string",
                            "description": "Path to SSH private key file on the client (optional if using password)",
                        },
                        "port": {
                            "type": "integer",
                            "description": "SSH port (default: 22)",
                            "default": 22,
                            "minimum": 1,
                            "maximum": 65535,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "ET Phone Home client to use (uses active client if not specified)",
                        },
                    },
                    "required": ["host", "username"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="ssh_session_command",
                description="Execute a command in an existing SSH session. State is preserved between commands (cd, export, etc. persist). Returns stdout output.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID from ssh_session_open",
                            "minLength": 1,
                        },
                        "command": {
                            "type": "string",
                            "description": "Command to execute in the SSH session",
                            "minLength": 1,
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Command timeout in seconds (default: 300)",
                            "default": 300,
                            "minimum": 1,
                            "maximum": 3600,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "ET Phone Home client (uses active client if not specified)",
                        },
                    },
                    "required": ["session_id", "command"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="ssh_session_close",
                description="Close an SSH session and free resources. Always close sessions when done to release connections.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to close",
                            "minLength": 1,
                        },
                        "client_id": {
                            "type": "string",
                            "description": "ET Phone Home client (uses active client if not specified)",
                        },
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="ssh_session_list",
                description="List all active SSH sessions on the client. Shows session IDs, target hosts, and creation times.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "client_id": {
                            "type": "string",
                            "description": "ET Phone Home client (uses active client if not specified)",
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            # ===== FILE EXCHANGE (R2 STORAGE) =====
            Tool(
                name="exchange_upload",
                description="Upload a file to Cloudflare R2 for transfer to a client. Generates a presigned download URL valid for specified hours. Use for server→client transfers, large files, or async transfers.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "local_path": {
                            "type": "string",
                            "description": "Path to file on the MCP server",
                            "minLength": 1,
                        },
                        "dest_client": {
                            "type": "string",
                            "description": "Destination client UUID (optional, for tracking)",
                        },
                        "expires_hours": {
                            "type": "integer",
                            "description": "URL expiration time in hours (default: 12, max: 12)",
                            "minimum": 1,
                            "maximum": 12,
                            "default": 12,
                        },
                    },
                    "required": ["local_path"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="exchange_download",
                description="Download a file from a presigned URL to the MCP server. Use to receive files uploaded by clients or from exchange_upload.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "download_url": {
                            "type": "string",
                            "description": "Presigned URL from exchange_upload or R2",
                            "minLength": 1,
                        },
                        "local_path": {
                            "type": "string",
                            "description": "Destination path on MCP server",
                            "minLength": 1,
                        },
                    },
                    "required": ["download_url", "local_path"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="exchange_list",
                description="List pending file transfers in R2 storage. Returns transfer metadata including source/dest clients, file sizes, and upload timestamps.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "client_id": {
                            "type": "string",
                            "description": "Filter by source client UUID (optional)",
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="exchange_delete",
                description="Manually delete a transfer from R2 before automatic expiration (48 hours). Use after successful download to clean up.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "transfer_id": {
                            "type": "string",
                            "description": "Transfer ID from exchange_upload",
                            "minLength": 1,
                        },
                        "source_client": {
                            "type": "string",
                            "description": "Source client UUID",
                            "minLength": 1,
                        },
                    },
                    "required": ["transfer_id", "source_client"],
                    "additionalProperties": False,
                },
            ),
            # ===== R2 KEY ROTATION & SECRETS MANAGEMENT =====
            Tool(
                name="r2_rotate_keys",
                description="Rotate Cloudflare R2 API keys. Creates new token, updates GitHub Secrets, and optionally deletes old token. Use for manual rotation or when keys are compromised.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "old_access_key_id": {
                            "type": "string",
                            "description": "Old R2 access key ID to delete (optional)",
                        },
                        "keep_old": {
                            "type": "boolean",
                            "description": "Keep old token instead of deleting (default: false)",
                            "default": False,
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="r2_list_tokens",
                description="List all active R2 API tokens for the Cloudflare account. Shows token IDs, creation dates, and names.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="r2_check_rotation_status",
                description="Check if R2 key rotation is due based on configured schedule. Returns last rotation date and days until next rotation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "rotation_days": {
                            "type": "integer",
                            "description": "Days between rotations (default: 90)",
                            "minimum": 1,
                            "maximum": 365,
                            "default": 90,
                        },
                    },
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
        return await _execute_with_tracking(
            client_id=args.get("client_id"),
            method_name="run_command",
            operation=lambda conn: conn.run_command(
                cmd=args["cmd"], cwd=args.get("cwd"), timeout=args.get("timeout")
            ),
            webhook_event=EventType.COMMAND_EXECUTED,
            webhook_data_fn=lambda a, r: {
                "cmd": a["cmd"],
                "cwd": a.get("cwd"),
                "returncode": r.get("returncode"),
            },
            operation_args=args,
        )

    elif name == "read_file":
        return await _execute_with_tracking(
            client_id=args.get("client_id"),
            method_name="read_file",
            operation=lambda conn: conn.read_file(args["path"]),
            webhook_event=EventType.FILE_ACCESSED,
            webhook_data_fn=lambda a, r: {
                "operation": "read",
                "path": a["path"],
                "size": r.get("size"),
            },
            operation_args=args,
        )

    elif name == "write_file":
        return await _execute_with_tracking(
            client_id=args.get("client_id"),
            method_name="write_file",
            operation=lambda conn: conn.write_file(args["path"], args["content"]),
            webhook_event=EventType.FILE_ACCESSED,
            webhook_data_fn=lambda a, r: {
                "operation": "write",
                "path": a["path"],
                "size": r.get("size"),
            },
            operation_args=args,
        )

    elif name == "list_files":
        return await _execute_with_tracking(
            client_id=args.get("client_id"),
            method_name="list_files",
            operation=lambda conn: conn.list_files(args["path"]),
            webhook_event=EventType.FILE_ACCESSED,
            webhook_data_fn=lambda a, r: {
                "operation": "list",
                "path": a["path"],
                "count": len(r.get("files", [])),
            },
            operation_args=args,
        )

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

    # ===== SSH SESSION MANAGEMENT =====
    elif name == "ssh_session_open":
        client_id = args.get("client_id")
        conn = await get_connection(client_id)
        result = await conn.ssh_session_open(
            host=args["host"],
            username=args["username"],
            password=args.get("password"),
            key_file=args.get("key_file"),
            port=args.get("port", 22),
        )
        return result

    elif name == "ssh_session_command":
        client_id = args.get("client_id")
        conn = await get_connection(client_id)
        result = await conn.ssh_session_command(
            session_id=args["session_id"],
            command=args["command"],
            timeout=args.get("timeout", 300),
        )
        return result

    elif name == "ssh_session_close":
        client_id = args.get("client_id")
        conn = await get_connection(client_id)
        result = await conn.ssh_session_close(session_id=args["session_id"])
        return result

    elif name == "ssh_session_list":
        client_id = args.get("client_id")
        conn = await get_connection(client_id)
        result = await conn.ssh_session_list()
        return result

    # ===== FILE EXCHANGE (R2 STORAGE) =====
    elif name == "exchange_upload":
        from shared.r2_client import TransferManager, create_r2_client

        # Check if R2 is configured
        r2_client = create_r2_client()
        if r2_client is None:
            raise ToolError(
                code="R2_NOT_CONFIGURED",
                message="Cloudflare R2 storage is not configured. Set environment variables: ETPHONEHOME_R2_ACCOUNT_ID, ETPHONEHOME_R2_ACCESS_KEY, ETPHONEHOME_R2_SECRET_KEY, ETPHONEHOME_R2_BUCKET",
                recovery_hint="Configure R2 credentials in your server.env file or environment variables. See FILE_TRANSFER_IMPROVEMENT_RESEARCH.md for setup instructions.",
            )

        # Get source client info (for metadata)
        try:
            client = await registry.get_active_client()
            source_client = client.identity.uuid if client else "server"
        except NoActiveClientError:
            source_client = "server"

        # Upload file
        local_path = Path(args["local_path"])
        dest_client = args.get("dest_client")
        expires_hours = args.get("expires_hours", 12)

        manager = TransferManager(r2_client)
        result = manager.upload_for_transfer(
            local_path=local_path,
            source_client=source_client,
            dest_client=dest_client,
            expires_hours=expires_hours,
        )

        logger.info(
            f"File exchange upload: {local_path} -> {result['transfer_id']} (expires: {result['expires_at']})"
        )
        return result

    elif name == "exchange_download":
        from shared.r2_client import TransferManager, create_r2_client

        r2_client = create_r2_client()
        if r2_client is None:
            raise ToolError(
                code="R2_NOT_CONFIGURED",
                message="Cloudflare R2 storage is not configured",
                recovery_hint="Configure R2 credentials in your server.env file",
            )

        download_url = args["download_url"]
        local_path = Path(args["local_path"])

        manager = TransferManager(r2_client)
        result = manager.download_from_url(
            download_url=download_url,
            local_path=local_path,
        )

        logger.info(f"File exchange download: {download_url} -> {local_path}")
        return result

    elif name == "exchange_list":
        from shared.r2_client import TransferManager, create_r2_client

        r2_client = create_r2_client()
        if r2_client is None:
            raise ToolError(
                code="R2_NOT_CONFIGURED",
                message="Cloudflare R2 storage is not configured",
                recovery_hint="Configure R2 credentials in your server.env file",
            )

        client_id = args.get("client_id")

        manager = TransferManager(r2_client)
        transfers = manager.list_pending_transfers(client_id=client_id)

        return {
            "transfers": transfers,
            "count": len(transfers),
            "message": (
                f"Found {len(transfers)} pending transfer(s)"
                if client_id
                else f"Found {len(transfers)} total pending transfer(s)"
            ),
        }

    elif name == "exchange_delete":
        from shared.r2_client import TransferManager, create_r2_client

        r2_client = create_r2_client()
        if r2_client is None:
            raise ToolError(
                code="R2_NOT_CONFIGURED",
                message="Cloudflare R2 storage is not configured",
                recovery_hint="Configure R2 credentials in your server.env file",
            )

        transfer_id = args["transfer_id"]
        source_client = args["source_client"]

        manager = TransferManager(r2_client)
        result = manager.delete_transfer(
            transfer_id=transfer_id,
            source_client=source_client,
        )

        logger.info(f"File exchange delete: {transfer_id}")
        return result

    # ===== R2 KEY ROTATION & SECRETS MANAGEMENT =====
    elif name == "r2_rotate_keys":
        from shared.r2_rotation import R2KeyRotationManager

        rotation_manager = R2KeyRotationManager.from_env()
        if rotation_manager is None:
            raise ToolError(
                code="ROTATION_NOT_CONFIGURED",
                message="R2 rotation is not configured. Required environment variables: ETPHONEHOME_CLOUDFLARE_API_TOKEN, ETPHONEHOME_R2_ACCOUNT_ID, ETPHONEHOME_GITHUB_REPO",
                recovery_hint="Set up Cloudflare API token and GitHub repository configuration. See docs/SECRETS_MANAGEMENT.md for setup instructions.",
            )

        old_access_key_id = args.get("old_access_key_id")
        keep_old = args.get("keep_old", False)

        result = rotation_manager.rotate_r2_keys(
            old_access_key_id=old_access_key_id,
            delete_old=not keep_old,
        )

        logger.info(f"R2 keys rotated: new key {result['new_access_key_id']}")
        return result

    elif name == "r2_list_tokens":
        from shared.r2_rotation import R2KeyRotationManager

        rotation_manager = R2KeyRotationManager.from_env()
        if rotation_manager is None:
            raise ToolError(
                code="ROTATION_NOT_CONFIGURED",
                message="R2 rotation is not configured",
                recovery_hint="Set required environment variables for rotation manager",
            )

        tokens = rotation_manager.list_active_tokens()
        return {
            "tokens": tokens,
            "count": len(tokens),
        }

    elif name == "r2_check_rotation_status":
        from shared.r2_rotation import R2KeyRotationManager, RotationScheduler

        rotation_manager = R2KeyRotationManager.from_env()
        if rotation_manager is None:
            raise ToolError(
                code="ROTATION_NOT_CONFIGURED",
                message="R2 rotation is not configured",
                recovery_hint="Set required environment variables for rotation manager",
            )

        rotation_days = args.get("rotation_days", 90)
        scheduler = RotationScheduler(rotation_manager, rotation_days=rotation_days)

        last_rotation = scheduler.get_last_rotation_date()
        should_rotate = scheduler.should_rotate()

        result = {
            "rotation_due": should_rotate,
            "rotation_interval_days": rotation_days,
        }

        if last_rotation:
            from datetime import datetime, timezone

            days_since = (datetime.now(timezone.utc) - last_rotation).days
            result["last_rotation"] = last_rotation.isoformat()
            result["days_since_rotation"] = days_since
            result["days_until_next"] = max(0, rotation_days - days_since)
        else:
            result["last_rotation"] = None
            result["days_since_rotation"] = None
            result["days_until_next"] = 0
            result["message"] = "No previous rotation found - rotation recommended"

        return result

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

    # Initialize secret sync (if enabled)
    from shared.secret_sync import initialize_secret_sync

    secret_sync_enabled = os.getenv("ETPHONEHOME_SECRET_SYNC_ENABLED", "false").lower() == "true"
    secret_sync_interval = int(os.getenv("ETPHONEHOME_SECRET_SYNC_INTERVAL", "3600"))

    secret_sync = await initialize_secret_sync(
        enabled=secret_sync_enabled,
        sync_interval=secret_sync_interval,
    )
    if secret_sync:
        logger.info(f"Secret sync enabled (interval: {secret_sync_interval}s)")

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
        if secret_sync:
            await secret_sync.stop()
            logger.info("Secret sync stopped")
        if dispatcher:
            await dispatcher.stop()
            logger.info("Webhook dispatcher stopped")


async def run_http(host: str, port: int, api_key: str = None):
    """Run the MCP server with HTTP/SSE transport."""
    global _health_monitor

    from server.http_server import run_http_server

    # Initialize secret sync (if enabled)
    from shared.secret_sync import initialize_secret_sync

    secret_sync_enabled = os.getenv("ETPHONEHOME_SECRET_SYNC_ENABLED", "false").lower() == "true"
    secret_sync_interval = int(os.getenv("ETPHONEHOME_SECRET_SYNC_INTERVAL", "3600"))

    secret_sync = await initialize_secret_sync(
        enabled=secret_sync_enabled,
        sync_interval=secret_sync_interval,
    )
    if secret_sync:
        logger.info(f"Secret sync enabled (interval: {secret_sync_interval}s)")

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

    # Recover any clients with active tunnels from before restart
    await recover_active_clients()

    try:
        await run_http_server(host=host, port=port, api_key=api_key, registry=registry)
    finally:
        if _health_monitor:
            await _health_monitor.stop()
        if secret_sync:
            await secret_sync.stop()
            logger.info("Secret sync stopped")
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
