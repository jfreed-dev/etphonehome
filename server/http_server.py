#!/usr/bin/env python3
"""
ET Phone Home - HTTP/SSE Transport for MCP Server

Provides HTTP/SSE transport so the MCP server can run as a persistent daemon.
"""

import logging
import os
from typing import Optional

from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

logger = logging.getLogger("etphonehome.http")

# Default configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class AuthMiddleware:
    """Simple bearer token authentication middleware."""

    def __init__(self, app, api_key: Optional[str] = None):
        self.app = app
        self.api_key = api_key or os.environ.get("ETPHONEHOME_API_KEY")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.api_key:
            # Skip auth for health, clients list, and internal endpoints (localhost only)
            path = scope.get("path", "")
            if path not in ("/health", "/clients", "/internal/register"):
                headers = dict(scope.get("headers", []))
                auth = headers.get(b"authorization", b"").decode()
                if not auth.startswith("Bearer ") or auth[7:] != self.api_key:
                    response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


def create_http_app(api_key: Optional[str] = None) -> Starlette:
    """Create the Starlette ASGI application with MCP SSE transport."""
    # Import here to avoid circular imports and ensure globals are initialized
    from server.mcp_server import create_server, registry

    # Create MCP server instance
    mcp_server = create_server()

    # Create SSE transport
    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> Response:
        """Handle SSE connection requests."""
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
        return Response()

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

    async def list_clients(request: Request) -> JSONResponse:
        """List all registered clients."""
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
        try:
            registration = await request.json()
            await registry.register(registration)
            uuid = registration.get("identity", {}).get("uuid", "unknown")
            display_name = registration.get("identity", {}).get("display_name", "unknown")
            logger.info(f"Registered client via internal API: {display_name} ({uuid[:8]}...)")
            return JSONResponse({"registered": uuid, "display_name": display_name})
        except Exception as e:
            logger.error(f"Internal registration error: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    # Define routes
    routes = [
        Route("/health", endpoint=health_check, methods=["GET"]),
        Route("/clients", endpoint=list_clients, methods=["GET"]),
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Mount("/messages/", app=sse_transport.handle_post_message),
        Route("/internal/register", endpoint=internal_register, methods=["POST"]),
    ]

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
    api_key: Optional[str] = None,
):
    """Run the HTTP/SSE server."""
    import uvicorn

    app = create_http_app(api_key)

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
