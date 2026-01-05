#!/usr/bin/env python3
"""
ET Phone Home - MCP Server

Exposes tools to Claude CLI for interacting with connected remote clients.
"""

import argparse
import asyncio
import json
import logging
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

# Configure logging to stderr (stdout is used for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("etphonehome")

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
                raise RuntimeError("No active client. Use list_clients and select_client first.")
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
                raise RuntimeError(f"Client not found: {client_id}")
            port = stored.last_client_info.get("tunnel_port")
            if not port:
                raise RuntimeError(f"No tunnel port for client: {client_id}")

    if client_id not in _connections:
        _connections[client_id] = ClientConnection("127.0.0.1", port)

    return _connections[client_id]


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("etphonehome")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="list_clients",
                description="List all connected clients with their status and metadata",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="select_client",
                description="Select a client to use for subsequent commands",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string", "description": "The client ID to select"}
                    },
                    "required": ["client_id"],
                },
            ),
            Tool(
                name="run_command",
                description="Execute a shell command on the active client",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "string", "description": "The command to execute"},
                        "cwd": {
                            "type": "string",
                            "description": "Working directory for the command (optional)",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Command timeout in seconds (default: 300)",
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Specific client ID (optional, uses active client if not specified)",
                        },
                    },
                    "required": ["cmd"],
                },
            ),
            Tool(
                name="read_file",
                description="Read a file from the active client",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path to the file"},
                        "client_id": {
                            "type": "string",
                            "description": "Specific client ID (optional)",
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="write_file",
                description="Write content to a file on the active client",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path to the file"},
                        "content": {"type": "string", "description": "Content to write"},
                        "client_id": {
                            "type": "string",
                            "description": "Specific client ID (optional)",
                        },
                    },
                    "required": ["path", "content"],
                },
            ),
            Tool(
                name="list_files",
                description="List files in a directory on the active client",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path to the directory"},
                        "client_id": {
                            "type": "string",
                            "description": "Specific client ID (optional)",
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="upload_file",
                description="Upload a file from the server to the active client",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "local_path": {
                            "type": "string",
                            "description": "Path to the file on the server",
                        },
                        "remote_path": {
                            "type": "string",
                            "description": "Destination path on the client",
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Specific client ID (optional)",
                        },
                    },
                    "required": ["local_path", "remote_path"],
                },
            ),
            Tool(
                name="download_file",
                description="Download a file from the active client to the server",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "remote_path": {
                            "type": "string",
                            "description": "Path to the file on the client",
                        },
                        "local_path": {
                            "type": "string",
                            "description": "Destination path on the server",
                        },
                        "client_id": {
                            "type": "string",
                            "description": "Specific client ID (optional)",
                        },
                    },
                    "required": ["remote_path", "local_path"],
                },
            ),
            Tool(
                name="find_client",
                description="Search for clients by name, purpose, tags, or capabilities",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term (matches display_name, purpose, hostname)",
                        },
                        "purpose": {"type": "string", "description": "Filter by purpose"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by tags (must have all)",
                        },
                        "capabilities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by capabilities (must have all)",
                        },
                        "online_only": {
                            "type": "boolean",
                            "description": "Only show currently connected clients",
                        },
                    },
                },
            ),
            Tool(
                name="describe_client",
                description="Get detailed information about a specific client",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uuid": {"type": "string", "description": "Client UUID"},
                        "client_id": {
                            "type": "string",
                            "description": "Client ID (alternative to UUID)",
                        },
                    },
                },
            ),
            Tool(
                name="update_client",
                description="Update client metadata (display_name, purpose, tags, allowed_paths)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uuid": {"type": "string", "description": "Client UUID"},
                        "display_name": {"type": "string", "description": "New display name"},
                        "purpose": {"type": "string", "description": "New purpose"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "New tags (replaces existing)",
                        },
                        "allowed_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Allowed path prefixes for file operations (replaces existing, null for all paths)",
                        },
                    },
                    "required": ["uuid"],
                },
            ),
            Tool(
                name="accept_key",
                description="Accept a client's new SSH key, clearing the key_mismatch flag. Use after verifying a key change is legitimate.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "uuid": {"type": "string", "description": "Client UUID"},
                    },
                    "required": ["uuid"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls."""
        try:
            result = await _handle_tool(name, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            logger.exception(f"Tool error: {name}")
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

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
            return {"error": f"Client not found: {client_id}"}

    elif name == "run_command":
        conn = await get_connection(args.get("client_id"))
        result = await conn.run_command(
            cmd=args["cmd"], cwd=args.get("cwd"), timeout=args.get("timeout")
        )
        return result

    elif name == "read_file":
        conn = await get_connection(args.get("client_id"))
        result = await conn.read_file(args["path"])
        return result

    elif name == "write_file":
        conn = await get_connection(args.get("client_id"))
        result = await conn.write_file(args["path"], args["content"])
        return result

    elif name == "list_files":
        conn = await get_connection(args.get("client_id"))
        result = await conn.list_files(args["path"])
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
            return {"error": "Must provide either 'uuid' or 'client_id'"}

        result = await registry.describe_client(identifier)
        if not result:
            return {"error": f"Client not found: {identifier}"}
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
            return {"error": f"Client not found: {uuid}"}
        return {"updated": result, "message": f"Updated client: {uuid}"}

    elif name == "accept_key":
        uuid = args["uuid"]
        result = await registry.accept_key(uuid)
        if not result:
            return {"error": f"Client not found: {uuid}"}
        if result.get("no_mismatch"):
            return {"message": f"Client {uuid} had no key mismatch to clear"}
        return {"accepted": result, "message": f"Accepted new key for client: {uuid}"}

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


async def run_http(host: str, port: int, api_key: str = None):
    """Run the MCP server with HTTP/SSE transport."""
    global _health_monitor

    from server.http_server import run_http_server

    # Start health monitor for automatic disconnect detection
    _health_monitor = HealthMonitor(registry, _connections)
    await _health_monitor.start()

    try:
        await run_http_server(host=host, port=port, api_key=api_key)
    finally:
        if _health_monitor:
            await _health_monitor.stop()


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
