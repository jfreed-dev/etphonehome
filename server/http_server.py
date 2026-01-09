#!/usr/bin/env python3
"""
ET Phone Home - HTTP/SSE Transport for MCP Server

Provides HTTP/SSE transport so the MCP server can run as a persistent daemon.
Includes web management interface with real-time updates.
"""

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from shared.version import __version__

logger = logging.getLogger("etphonehome.http")

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
    PUBLIC_PATHS = {"/health", "/clients", "/internal/register", "/", "/client.html"}

    def __init__(self, app, api_key: str | None = None):
        self.app = app
        self.api_key = api_key or os.environ.get("ETPHONEHOME_API_KEY")

    def _is_public_path(self, path: str) -> bool:
        """Check if a path is publicly accessible."""
        if path in self.PUBLIC_PATHS:
            return True
        # Static files are public
        if path.startswith("/static/"):
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

    # Create SSE transport
    sse_transport = SseServerTransport("/messages/")

    # =========================================================================
    # MCP SSE Endpoints
    # =========================================================================

    async def handle_sse(request: Request) -> Response:
        """Handle SSE connection requests."""
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

    # =========================================================================
    # Health & Legacy Endpoints
    # =========================================================================

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint for monitoring."""
        return JSONResponse(
            {
                "status": "healthy",
                "service": "etphonehome-mcp",
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
    # Web UI - Dashboard & Static Pages
    # =========================================================================

    async def dashboard_page(request: Request) -> Response:
        """Serve the dashboard HTML page."""
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        # Fallback if static files not found
        return HTMLResponse(
            "<html><body><h1>ET Phone Home</h1>"
            "<p>Static files not found. Run from project root.</p></body></html>",
            status_code=500,
        )

    async def client_page(request: Request) -> Response:
        """Serve the client detail HTML page."""
        client_path = STATIC_DIR / "client.html"
        if client_path.exists():
            return FileResponse(client_path, media_type="text/html")
        return HTMLResponse(
            "<html><body><h1>Client page not found</h1></body></html>", status_code=404
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
        # MCP SSE endpoints
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Mount("/messages/", app=sse_transport.handle_post_message),
        # Health & legacy
        Route("/health", endpoint=health_check, methods=["GET"]),
        Route("/clients", endpoint=list_clients_legacy, methods=["GET"]),
        Route("/internal/register", endpoint=internal_register, methods=["POST"]),
        # Web UI pages
        Route("/", endpoint=dashboard_page, methods=["GET"]),
        Route("/client.html", endpoint=client_page, methods=["GET"]),
        # REST API v1
        Route("/api/v1/dashboard", endpoint=api_dashboard, methods=["GET"]),
        Route("/api/v1/clients", endpoint=api_clients, methods=["GET"]),
        Route("/api/v1/clients/{uuid}", endpoint=api_client_detail, methods=["GET"]),
        Route("/api/v1/events", endpoint=api_events, methods=["GET"]),
        # WebSocket
        WebSocketRoute("/api/v1/ws", endpoint=websocket_handler),
    ]

    # Add static files mount if directory exists
    if STATIC_DIR.exists():
        routes.append(Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"))
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
    effective_api_key = api_key or os.environ.get("ETPHONEHOME_API_KEY")
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
