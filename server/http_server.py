#!/usr/bin/env python3
"""
Reach - HTTP/SSE Transport for MCP Server

Provides HTTP/SSE transport so the MCP server can run as a persistent daemon.
Includes web management interface with real-time updates.
"""

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from server.command_history import get_history_store, record_command
from shared.version import __version__

logger = logging.getLogger("reach.http")

# Default configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# Server start time for uptime calculation
_server_start_time: float = time.time()

# Static files directory (relative to server module)
STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class Event:
    """Represents a system event for the activity stream."""

    timestamp: str
    type: str
    client_uuid: str
    client_name: str
    summary: str
    data: dict = field(default_factory=dict)


class EventStore:
    """Stores recent events for the dashboard activity stream."""

    def __init__(self, max_events: int = 100):
        self._events: deque[Event] = deque(maxlen=max_events)

    def add(
        self,
        event_type: str,
        client_uuid: str,
        client_name: str,
        summary: str,
        data: dict | None = None,
    ):
        """Add a new event."""
        event = Event(
            timestamp=datetime.now(timezone.utc).isoformat(),
            type=event_type,
            client_uuid=client_uuid,
            client_name=client_name,
            summary=summary,
            data=data or {},
        )
        self._events.appendleft(event)
        return event

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Get the most recent events."""
        return [
            {
                "timestamp": e.timestamp,
                "type": e.type,
                "client_uuid": e.client_uuid,
                "client_name": e.client_name,
                "summary": e.summary,
            }
            for e in list(self._events)[:limit]
        ]


# Global event store
_event_store = EventStore()


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Register a new WebSocket connection."""
        async with self._lock:
            self._connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected WebSocket clients."""
        if not self._connections:
            return

        message_text = json.dumps(message)
        disconnected = []

        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(message_text)
                except Exception:
                    disconnected.append(ws)

            # Clean up disconnected sockets
            for ws in disconnected:
                self._connections.discard(ws)


# Global WebSocket manager
_ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """Get the global WebSocket manager for broadcasting events."""
    return _ws_manager


def get_event_store() -> EventStore:
    """Get the global event store."""
    return _event_store


class AuthMiddleware:
    """Simple bearer token authentication middleware."""

    # Paths that don't require authentication
    PUBLIC_PATHS = {"/health", "/clients", "/internal/register", "/", "/client"}

    def __init__(self, app, api_key: str | None = None):
        self.app = app
        from shared.compat import env as _env

        self.api_key = api_key or _env("REACH_API_KEY", "ETPHONEHOME_API_KEY")

    def _is_public_path(self, path: str) -> bool:
        """Check if a path is publicly accessible."""
        if path in self.PUBLIC_PATHS:
            return True
        # Static files are public (SvelteKit assets, icons, logos)
        if path.startswith(("/static/", "/_app/", "/icons/", "/logos/")):
            return True
        return False

    def _check_auth(self, scope) -> bool:
        """Check authorization header or query param for valid API key."""
        # Check Authorization header
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        if auth.startswith("Bearer ") and auth[7:] == self.api_key:
            return True

        # Check query param (for WebSocket and initial page load)
        query_string = scope.get("query_string", b"").decode()
        if query_string:
            from urllib.parse import parse_qs

            params = parse_qs(query_string)
            token = params.get("token", [None])[0]
            if token == self.api_key:
                return True

        return False

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")

        # HTTP requests
        if scope["type"] == "http" and self.api_key:
            if not self._is_public_path(path):
                if not self._check_auth(scope):
                    response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                    await response(scope, receive, send)
                    return

        # WebSocket requests
        elif scope["type"] == "websocket" and self.api_key:
            if not self._check_auth(scope):
                # For WebSocket, we need to accept then close with error
                await send({"type": "websocket.close", "code": 4001})
                return

        await self.app(scope, receive, send)


def create_http_app(api_key: str | None = None, registry=None) -> Starlette:
    """Create the Starlette ASGI application with MCP SSE transport and web UI."""
    global _server_start_time
    _server_start_time = time.time()

    # Import create_server - registry is now passed as parameter to avoid __main__ issue
    from server.mcp_server import create_server

    if registry is None:
        # Fallback for backwards compatibility
        from server.mcp_server import registry as imported_registry

        registry = imported_registry

    # Create MCP server instance, passing registry explicitly to avoid __main__ import issues
    mcp_server = create_server(registry_override=registry)

    # Create SSE transport (legacy, for GET /sse)
    sse_transport = SseServerTransport("/messages/")

    # Track Streamable HTTP sessions: session_id -> transport
    _streamable_sessions: dict[str, StreamableHTTPServerTransport] = {}

    # =========================================================================
    # MCP Endpoints (SSE legacy + Streamable HTTP)
    # =========================================================================

    async def handle_sse_get(request: Request) -> Response:
        """Handle legacy SSE connection requests (GET /sse)."""
        async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (
            read_stream,
            write_stream,
        ):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
        return Response()

    class _AsgiResponseSent(Response):
        """No-op Response: the real response was already sent via ASGI by handle_request()."""

        async def __call__(self, scope, receive, send):
            pass

    async def handle_streamable_http(request: Request) -> Response:
        """Handle Streamable HTTP MCP requests (POST/GET/DELETE /sse)."""
        session_id = request.headers.get("mcp-session-id")

        if request.method == "GET":
            # GET without session = legacy SSE, delegate
            if not session_id or session_id not in _streamable_sessions:
                return await handle_sse_get(request)
            # GET with valid session = SSE stream for that session
            transport = _streamable_sessions[session_id]
            await transport.handle_request(request.scope, request.receive, request._send)
            return _AsgiResponseSent()

        if request.method == "POST":
            if session_id and session_id in _streamable_sessions:
                transport = _streamable_sessions[session_id]
            else:
                # New session — create transport with a unique session ID
                new_session_id = uuid.uuid4().hex
                transport = StreamableHTTPServerTransport(
                    mcp_session_id=new_session_id,
                    is_json_response_enabled=True,
                )
                ready_event = asyncio.Event()

                async def _run_mcp(t: StreamableHTTPServerTransport, evt: asyncio.Event):
                    try:
                        async with t.connect() as (read_stream, write_stream):
                            evt.set()
                            await mcp_server.run(
                                read_stream,
                                write_stream,
                                mcp_server.create_initialization_options(),
                            )
                    finally:
                        sid = t.mcp_session_id
                        if sid and sid in _streamable_sessions:
                            del _streamable_sessions[sid]

                asyncio.create_task(_run_mcp(transport, ready_event))
                await ready_event.wait()

            await transport.handle_request(request.scope, request.receive, request._send)

            # Store transport by its session ID
            sid = transport.mcp_session_id
            if sid and sid not in _streamable_sessions:
                _streamable_sessions[sid] = transport

            return _AsgiResponseSent()

        if request.method == "DELETE":
            if session_id and session_id in _streamable_sessions:
                transport = _streamable_sessions.pop(session_id)
                transport.terminate()
            return Response(status_code=200)

        return Response(status_code=405)

    # =========================================================================
    # Health & Legacy Endpoints
    # =========================================================================

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint for monitoring."""
        return JSONResponse(
            {
                "status": "healthy",
                "service": "reach-mcp",
                "online_clients": registry.online_count,
                "total_clients": registry.total_count,
            }
        )

    async def list_clients_legacy(request: Request) -> JSONResponse:
        """List all registered clients (legacy endpoint)."""
        logger.info(
            f"HTTP list_clients: registry id={id(registry)}, online_count={registry.online_count}"
        )
        clients = await registry.list_clients()
        return JSONResponse(
            {
                "clients": clients,
                "online_count": registry.online_count,
                "total_count": registry.total_count,
            }
        )

    async def internal_register(request: Request) -> JSONResponse:
        """Internal endpoint for registering clients from SSH handler."""
        # Import health monitor to reset health tracking on registration
        from server.mcp_server import _health_monitor

        try:
            registration = await request.json()
            uuid = registration.get("identity", {}).get("uuid", "unknown")
            client_id = registration.get("client_info", {}).get("client_id")
            display_name = registration.get("identity", {}).get("display_name", "unknown")

            # Clear stale connections BEFORE registration
            # Tunnel port may have changed on reconnect, so we must not reuse old connections
            if client_id:
                from server.mcp_server import clear_stale_connection

                clear_stale_connection(client_id)

            # Reset health tracking BEFORE registration to ensure fresh grace period
            # Pass client_id to clear health monitor's cached connection too
            if _health_monitor and uuid != "unknown":
                _health_monitor.reset_health(uuid, client_id=client_id)

            await registry.register(registration)
            logger.info(f"Registered client via internal API: {display_name} ({uuid[:8]}...)")

            # Add event and broadcast to WebSocket clients
            event = _event_store.add(
                event_type="client.connected",
                client_uuid=uuid,
                client_name=display_name,
                summary="Connected",
            )
            await _ws_manager.broadcast(
                {
                    "type": "client.connected",
                    "timestamp": event.timestamp,
                    "data": {"uuid": uuid, "display_name": display_name},
                }
            )

            return JSONResponse({"registered": uuid, "display_name": display_name})
        except Exception as e:
            logger.error(f"Internal registration error: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    # =========================================================================
    # Web UI - SPA Fallback
    # =========================================================================

    async def spa_fallback(request: Request) -> Response:
        """Serve SPA index.html for all UI routes (client-side routing)."""
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        # Fallback if static files not found
        return HTMLResponse(
            "<html><body><h1>Reach</h1>"
            "<p>Static files not found. Build the web UI first.</p></body></html>",
            status_code=500,
        )

    # =========================================================================
    # REST API v1 Endpoints
    # =========================================================================

    async def api_dashboard(request: Request) -> JSONResponse:
        """Dashboard summary data."""
        uptime_seconds = int(time.time() - _server_start_time)
        return JSONResponse(
            {
                "server": {
                    "uptime_seconds": uptime_seconds,
                    "version": __version__,
                },
                "clients": {
                    "online": registry.online_count,
                    "total": registry.total_count,
                },
                "tunnels": {
                    "active": registry.online_count,
                },
            }
        )

    async def api_clients(request: Request) -> JSONResponse:
        """List all clients with status."""
        clients = await registry.list_clients()
        return JSONResponse({"clients": clients})

    async def api_client_detail(request: Request) -> JSONResponse:
        """Get detailed info about a specific client."""
        uuid = request.path_params["uuid"]
        try:
            client_info = await registry.describe_client(uuid)
            if client_info is None:
                return JSONResponse({"error": "Client not found"}, status_code=404)
            return JSONResponse(client_info)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=404)

    async def api_events(request: Request) -> JSONResponse:
        """Get recent events for activity stream."""
        limit = int(request.query_params.get("limit", 20))
        events = _event_store.get_recent(limit)
        return JSONResponse({"events": events})

    # =========================================================================
    # Command History Endpoints
    # =========================================================================

    async def api_command_history(request: Request) -> JSONResponse:
        """Get command history for a client."""
        uuid = request.path_params["uuid"]
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        search = request.query_params.get("search")
        status = request.query_params.get("status")  # 'success', 'failed', or None

        # Convert status to returncode filter
        returncode_filter = None
        if status == "success":
            returncode_filter = 0
        elif status == "failed":
            returncode_filter = -1  # Non-zero

        store = get_history_store()
        records, total = await store.list_for_client(
            client_uuid=uuid,
            limit=limit,
            offset=offset,
            search=search,
            returncode_filter=returncode_filter,
        )

        return JSONResponse(
            {
                "commands": [r.to_dict() for r in records],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    async def api_command_detail(request: Request) -> JSONResponse:
        """Get a single command record."""
        command_id = request.path_params["command_id"]
        store = get_history_store()
        record = await store.get(command_id)

        if record is None:
            return JSONResponse({"error": "Command not found"}, status_code=404)

        return JSONResponse(record.to_dict())

    async def api_run_command(request: Request) -> JSONResponse:
        """Run a command on a client and save to history."""
        from datetime import datetime, timezone

        from server.mcp_server import get_connection

        uuid = request.path_params["uuid"]

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        command = body.get("command")
        if not command:
            return JSONResponse({"error": "Missing 'command' field"}, status_code=400)

        cwd = body.get("cwd")
        timeout = body.get("timeout", 300)

        # Verify client exists
        client_info = await registry.describe_client(uuid)
        if client_info is None:
            return JSONResponse({"error": "Client not found"}, status_code=404)

        # Check if client is online
        if not client_info.get("online", False):
            return JSONResponse({"error": "Client is offline"}, status_code=503)

        started_at = datetime.now(timezone.utc)

        try:
            # Get connection and execute command
            conn = await get_connection(uuid)
            result = await conn.run_command(command, cwd=cwd, timeout=timeout)
            completed_at = datetime.now(timezone.utc)

            # Record to history
            record = await record_command(
                client_uuid=uuid,
                command=command,
                cwd=cwd,
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                returncode=result.get("returncode", -1),
                started_at=started_at,
                completed_at=completed_at,
                user="web",
            )

            # Add event
            _event_store.add(
                event_type="command_executed",
                client_uuid=uuid,
                client_name=client_info.get("display_name", "Unknown"),
                summary=f"Ran: {command[:50]}{'...' if len(command) > 50 else ''}",
                data={"command": command, "returncode": result.get("returncode", -1)},
            )

            return JSONResponse(record.to_dict())

        except Exception as e:
            completed_at = datetime.now(timezone.utc)

            # Record failed command to history
            record = await record_command(
                client_uuid=uuid,
                command=command,
                cwd=cwd,
                stdout="",
                stderr=str(e),
                returncode=-1,
                started_at=started_at,
                completed_at=completed_at,
                user="web",
            )

            return JSONResponse({"error": str(e), "record": record.to_dict()}, status_code=500)

    # =========================================================================
    # File Browser Endpoints
    # =========================================================================

    async def api_list_files(request: Request) -> JSONResponse:
        """List files in a directory on a client."""
        from server.mcp_server import get_connection

        uuid = request.path_params["uuid"]
        path = request.query_params.get("path", "/")

        # Verify client exists and is online
        client_info = await registry.describe_client(uuid)
        if client_info is None:
            return JSONResponse({"error": "Client not found"}, status_code=404)
        if not client_info.get("online", False):
            return JSONResponse({"error": "Client is offline"}, status_code=503)

        try:
            conn = await get_connection(uuid)
            result = await conn.list_files(path)

            # Add event
            _event_store.add(
                event_type="file_accessed",
                client_uuid=uuid,
                client_name=client_info.get("display_name", "Unknown"),
                summary=f"Listed: {path}",
                data={"path": path, "operation": "list"},
            )

            return JSONResponse(
                {
                    "path": path,
                    "entries": result.get("entries", []),
                }
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def api_file_preview(request: Request) -> JSONResponse:
        """Preview file content (text files only, limited size)."""
        from server.mcp_server import get_connection

        uuid = request.path_params["uuid"]
        path = request.query_params.get("path")

        if not path:
            return JSONResponse({"error": "Missing 'path' parameter"}, status_code=400)

        # Verify client exists and is online
        client_info = await registry.describe_client(uuid)
        if client_info is None:
            return JSONResponse({"error": "Client not found"}, status_code=404)
        if not client_info.get("online", False):
            return JSONResponse({"error": "Client is offline"}, status_code=503)

        try:
            conn = await get_connection(uuid)
            result = await conn.read_file(path)

            content = result.get("content", "")
            binary = result.get("binary", False)
            size = result.get("size", len(content))

            # Determine MIME type from extension
            ext = Path(path).suffix.lower()
            mime_types = {
                ".txt": "text/plain",
                ".md": "text/markdown",
                ".py": "text/x-python",
                ".js": "text/javascript",
                ".ts": "text/typescript",
                ".json": "application/json",
                ".yaml": "text/yaml",
                ".yml": "text/yaml",
                ".xml": "text/xml",
                ".html": "text/html",
                ".css": "text/css",
                ".sh": "text/x-shellscript",
                ".log": "text/plain",
                ".csv": "text/csv",
            }
            mime_type = mime_types.get(ext, "application/octet-stream")

            return JSONResponse(
                {
                    "path": path,
                    "content": content if not binary else None,
                    "binary": binary,
                    "size": size,
                    "mimeType": mime_type,
                }
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def api_file_download(request: Request) -> Response:
        """Download a file from a client."""

        from server.mcp_server import get_connection

        uuid = request.path_params["uuid"]
        path = request.query_params.get("path")

        if not path:
            return JSONResponse({"error": "Missing 'path' parameter"}, status_code=400)

        # Verify client exists and is online
        client_info = await registry.describe_client(uuid)
        if client_info is None:
            return JSONResponse({"error": "Client not found"}, status_code=404)
        if not client_info.get("online", False):
            return JSONResponse({"error": "Client is offline"}, status_code=503)

        try:
            conn = await get_connection(uuid)
            result = await conn.read_file(path)

            content = result.get("content", "")
            binary = result.get("binary", False)

            # Convert content to bytes
            if binary:
                import base64

                data = base64.b64decode(content)
            else:
                data = content.encode("utf-8")

            filename = Path(path).name

            # Add event
            _event_store.add(
                event_type="file_accessed",
                client_uuid=uuid,
                client_name=client_info.get("display_name", "Unknown"),
                summary=f"Downloaded: {filename}",
                data={"path": path, "operation": "download"},
            )

            return Response(
                content=data,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def api_file_upload(request: Request) -> JSONResponse:
        """Upload a file to a client."""
        from server.mcp_server import get_connection

        uuid = request.path_params["uuid"]

        # Verify client exists and is online
        client_info = await registry.describe_client(uuid)
        if client_info is None:
            return JSONResponse({"error": "Client not found"}, status_code=404)
        if not client_info.get("online", False):
            return JSONResponse({"error": "Client is offline"}, status_code=503)

        try:
            # Parse multipart form data
            form = await request.form()
            file = form.get("file")
            dest_path = form.get("path")

            if not file:
                return JSONResponse({"error": "No file provided"}, status_code=400)
            if not dest_path:
                return JSONResponse({"error": "Missing 'path' field"}, status_code=400)

            # Read file content
            content = await file.read()

            # Check if binary (try to decode as UTF-8)
            try:
                text_content = content.decode("utf-8")
                binary = False
            except UnicodeDecodeError:
                import base64

                text_content = base64.b64encode(content).decode("ascii")
                binary = True

            conn = await get_connection(uuid)
            await conn.write_file(dest_path, text_content)

            # Add event
            _event_store.add(
                event_type="file_accessed",
                client_uuid=uuid,
                client_name=client_info.get("display_name", "Unknown"),
                summary=f"Uploaded: {Path(dest_path).name}",
                data={"path": dest_path, "operation": "upload", "size": len(content)},
            )

            return JSONResponse(
                {
                    "path": dest_path,
                    "size": len(content),
                    "binary": binary,
                }
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    # =========================================================================
    # WebSocket Endpoint
    # =========================================================================

    async def websocket_handler(websocket: WebSocket):
        """Handle WebSocket connections for real-time updates."""
        await websocket.accept()
        await _ws_manager.connect(websocket)

        try:
            # Send initial state
            clients = await registry.list_clients()
            await websocket.send_json(
                {
                    "type": "initial_state",
                    "data": {
                        "clients": clients,
                        "online_count": registry.online_count,
                        "total_count": registry.total_count,
                    },
                }
            )

            # Keep connection alive and listen for messages
            while True:
                try:
                    # Wait for any message (ping/pong handled by Starlette)
                    data = await websocket.receive_text()
                    # Handle ping
                    if data == "ping":
                        await websocket.send_text("pong")
                except WebSocketDisconnect:
                    break
        finally:
            await _ws_manager.disconnect(websocket)

    # =========================================================================
    # Define Routes
    # =========================================================================

    routes = [
        # MCP endpoints: Streamable HTTP (POST/GET/DELETE) + legacy SSE (GET)
        Route("/sse", endpoint=handle_streamable_http, methods=["GET", "POST", "DELETE"]),
        Mount("/messages/", app=sse_transport.handle_post_message),
        # Health & legacy
        Route("/health", endpoint=health_check, methods=["GET"]),
        Route("/clients", endpoint=list_clients_legacy, methods=["GET"]),
        Route("/internal/register", endpoint=internal_register, methods=["POST"]),
        # Web UI - SPA routes (Svelte handles client-side routing)
        Route("/", endpoint=spa_fallback, methods=["GET"]),
        Route("/client", endpoint=spa_fallback, methods=["GET"]),
        # REST API v1
        Route("/api/v1/dashboard", endpoint=api_dashboard, methods=["GET"]),
        Route("/api/v1/clients", endpoint=api_clients, methods=["GET"]),
        Route("/api/v1/clients/{uuid}", endpoint=api_client_detail, methods=["GET"]),
        Route("/api/v1/events", endpoint=api_events, methods=["GET"]),
        # Command History API
        Route(
            "/api/v1/clients/{uuid}/history",
            endpoint=api_command_history,
            methods=["GET"],
        ),
        Route(
            "/api/v1/clients/{uuid}/history",
            endpoint=api_run_command,
            methods=["POST"],
        ),
        Route(
            "/api/v1/clients/{uuid}/history/{command_id}",
            endpoint=api_command_detail,
            methods=["GET"],
        ),
        # File Browser API
        Route(
            "/api/v1/clients/{uuid}/files",
            endpoint=api_list_files,
            methods=["GET"],
        ),
        Route(
            "/api/v1/clients/{uuid}/files/preview",
            endpoint=api_file_preview,
            methods=["GET"],
        ),
        Route(
            "/api/v1/clients/{uuid}/files/download",
            endpoint=api_file_download,
            methods=["GET"],
        ),
        Route(
            "/api/v1/clients/{uuid}/files/upload",
            endpoint=api_file_upload,
            methods=["POST"],
        ),
        # WebSocket
        WebSocketRoute("/api/v1/ws", endpoint=websocket_handler),
    ]

    # Add static files mounts if directory exists
    if STATIC_DIR.exists():
        # SvelteKit puts compiled assets in _app directory
        app_dir = STATIC_DIR / "_app"
        if app_dir.exists():
            routes.append(Mount("/_app", app=StaticFiles(directory=str(app_dir)), name="_app"))
        # Serve icons, logos, and other static assets from root
        routes.append(Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"))
        # Also mount icons/logos at root level for backward compatibility
        icons_dir = STATIC_DIR / "icons"
        logos_dir = STATIC_DIR / "logos"
        if icons_dir.exists():
            routes.append(Mount("/icons", app=StaticFiles(directory=str(icons_dir)), name="icons"))
        if logos_dir.exists():
            routes.append(Mount("/logos", app=StaticFiles(directory=str(logos_dir)), name="logos"))
    else:
        logger.warning(f"Static files directory not found: {STATIC_DIR}")

    # Create middleware stack
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]

    app = Starlette(routes=routes, middleware=middleware)

    # Wrap with auth if API key is configured
    from shared.compat import env as _env

    effective_api_key = api_key or _env("REACH_API_KEY", "ETPHONEHOME_API_KEY")
    if effective_api_key:
        logger.info("API key authentication enabled")
        return AuthMiddleware(app, effective_api_key)

    logger.warning("No API key configured - server is unauthenticated")
    return app


async def run_http_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    api_key: str | None = None,
    registry=None,
):
    """Run the HTTP/SSE server."""
    import uvicorn

    app = create_http_app(api_key, registry=registry)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)

    logger.info(f"Starting HTTP/SSE server on {host}:{port}")
    await server.serve()
