"""Handle communication with connected clients."""

import asyncio
import logging
import socket
from typing import Any, Optional

from shared.protocol import Request, Response, encode_message, decode_message

logger = logging.getLogger(__name__)


class ClientConnection:
    """Manages communication with a single client through its tunnel."""

    def __init__(self, host: str, port: int, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._lock = asyncio.Lock()
        self._request_id = 0

    async def connect(self) -> None:
        """Establish connection to the client's tunnel."""
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self.timeout
        )
        logger.debug(f"Connected to client tunnel at {self.host}:{self.port}")

    async def disconnect(self) -> None:
        """Close the connection."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

    async def send_request(self, method: str, params: dict = None) -> Response:
        """Send a request to the client and wait for response."""
        async with self._lock:
            if not self._writer or not self._reader:
                await self.connect()

            self._request_id += 1
            request = Request(
                method=method,
                params=params or {},
                id=str(self._request_id)
            )

            try:
                # Send request
                data = encode_message(request.to_json())
                self._writer.write(data)
                await self._writer.drain()

                # Read response
                response_data = await asyncio.wait_for(
                    self._read_response(),
                    timeout=self.timeout
                )
                return Response.from_json(response_data)

            except Exception as e:
                logger.error(f"Error communicating with client: {e}")
                await self.disconnect()
                raise

    async def _read_response(self) -> str:
        """Read a length-prefixed response from the client."""
        # Read length header
        header = await self._reader.readexactly(4)
        length = int.from_bytes(header, "big")

        # Read message body
        body = await self._reader.readexactly(length)
        return body.decode("utf-8")

    async def run_command(self, cmd: str, cwd: str = None, timeout: int = None) -> dict:
        """Execute a command on the client."""
        params = {"cmd": cmd}
        if cwd:
            params["cwd"] = cwd
        if timeout:
            params["timeout"] = timeout

        response = await self.send_request("run_command", params)
        if response.error:
            raise RuntimeError(f"Command failed: {response.error['message']}")
        return response.result

    async def read_file(self, path: str, encoding: str = "utf-8") -> dict:
        """Read a file from the client."""
        response = await self.send_request("read_file", {
            "path": path,
            "encoding": encoding
        })
        if response.error:
            raise RuntimeError(f"Read failed: {response.error['message']}")
        return response.result

    async def write_file(self, path: str, content: str, binary: bool = False) -> dict:
        """Write a file to the client."""
        response = await self.send_request("write_file", {
            "path": path,
            "content": content,
            "binary": binary
        })
        if response.error:
            raise RuntimeError(f"Write failed: {response.error['message']}")
        return response.result

    async def list_files(self, path: str) -> dict:
        """List files in a directory on the client."""
        response = await self.send_request("list_files", {"path": path})
        if response.error:
            raise RuntimeError(f"List failed: {response.error['message']}")
        return response.result

    async def heartbeat(self) -> bool:
        """Check if the client is responsive."""
        try:
            response = await self.send_request("heartbeat")
            return response.result.get("status") == "alive"
        except Exception:
            return False
