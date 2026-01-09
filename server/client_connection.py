"""Handle communication with connected clients."""

import asyncio
import logging

from shared.protocol import Request, Response, encode_message

# Use the etphonehome logger to ensure logs are captured
logger = logging.getLogger("etphonehome.client_connection")


class ClientConnection:
    """Manages communication with a single client through its tunnel."""

    def __init__(self, host: str, port: int, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._request_id = 0

    async def connect(self) -> None:
        """Establish connection to the client's tunnel."""
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=self.timeout
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
            request = Request(method=method, params=params or {}, id=str(self._request_id))

            try:
                # Send request
                data = encode_message(request.to_json())
                self._writer.write(data)
                await self._writer.drain()

                # Read response
                response_data = await asyncio.wait_for(self._read_response(), timeout=self.timeout)
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
        response = await self.send_request("read_file", {"path": path, "encoding": encoding})
        if response.error:
            raise RuntimeError(f"Read failed: {response.error['message']}")
        return response.result

    async def write_file(self, path: str, content: str, binary: bool = False) -> dict:
        """Write a file to the client."""
        response = await self.send_request(
            "write_file", {"path": path, "content": content, "binary": binary}
        )
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
        """Check if the client is responsive.

        Raises:
            ConnectionRefusedError: If the tunnel port is not listening
            OSError: If there's a network error
            asyncio.TimeoutError: If the request times out
        """
        # Let connection errors propagate for proper handling by health monitor
        response = await self.send_request("heartbeat")
        return response.result.get("status") == "alive"

    async def get_metrics(self, summary: bool = False) -> dict:
        """Get system health metrics from the client."""
        response = await self.send_request("get_metrics", {"summary": summary})
        if response.error:
            raise RuntimeError(f"Metrics failed: {response.error['message']}")
        return response.result

    # SSH Session Management
    async def ssh_session_open(
        self,
        host: str,
        username: str,
        password: str = None,
        key_file: str = None,
        port: int = 22,
        jump_hosts: list[dict] = None,
    ) -> dict:
        """Open a persistent SSH session on the client."""
        params = {
            "host": host,
            "username": username,
            "port": port,
        }
        if password:
            params["password"] = password
        if key_file:
            params["key_file"] = key_file
        if jump_hosts:
            params["jump_hosts"] = jump_hosts

        response = await self.send_request("ssh_session_open", params)
        if response.error:
            raise RuntimeError(f"SSH session open failed: {response.error['message']}")
        return response.result

    async def ssh_session_command(self, session_id: str, command: str, timeout: int = 300) -> dict:
        """Send a command to an existing SSH session."""
        params = {
            "session_id": session_id,
            "command": command,
            "timeout": timeout,
        }
        response = await self.send_request("ssh_session_command", params)
        if response.error:
            raise RuntimeError(f"SSH session command failed: {response.error['message']}")
        return response.result

    async def ssh_session_close(self, session_id: str) -> dict:
        """Close an SSH session."""
        response = await self.send_request("ssh_session_close", {"session_id": session_id})
        if response.error:
            raise RuntimeError(f"SSH session close failed: {response.error['message']}")
        return response.result

    async def ssh_session_list(self) -> dict:
        """List all active SSH sessions."""
        response = await self.send_request("ssh_session_list", {})
        if response.error:
            raise RuntimeError(f"SSH session list failed: {response.error['message']}")
        return response.result

    async def ssh_session_send(
        self,
        session_id: str,
        text: str,
        send_newline: bool = True,
    ) -> dict:
        """Send raw input to an SSH session for interactive prompts."""
        params = {
            "session_id": session_id,
            "text": text,
            "send_newline": send_newline,
        }
        response = await self.send_request("ssh_session_send", params)
        if response.error:
            raise RuntimeError(f"SSH session send failed: {response.error['message']}")
        return response.result

    async def ssh_session_read(
        self,
        session_id: str,
        timeout: float = 0.5,
    ) -> dict:
        """Read pending output from an SSH session."""
        params = {
            "session_id": session_id,
            "timeout": timeout,
        }
        response = await self.send_request("ssh_session_read", params)
        if response.error:
            raise RuntimeError(f"SSH session read failed: {response.error['message']}")
        return response.result

    async def ssh_session_restore(self) -> dict:
        """Attempt to restore SSH sessions after client reconnect."""
        response = await self.send_request("ssh_session_restore", {})
        if response.error:
            raise RuntimeError(f"SSH session restore failed: {response.error['message']}")
        return response.result

    # SFTP Support
    async def has_sftp_support(self) -> bool:
        """
        Check if client supports SFTP subsystem.

        Returns:
            True if client supports SFTP, False otherwise
        """
        if hasattr(self, "_sftp_support_cached"):
            return self._sftp_support_cached

        try:
            # Try to connect to SFTP subsystem
            from server.sftp_connection import SFTPConnection

            async with SFTPConnection(self.host, self.port, timeout=5):
                # If connection succeeds, client supports SFTP
                self._sftp_support_cached = True
                logger.debug(f"Client at {self.host}:{self.port} supports SFTP")
                return True

        except Exception as e:
            logger.debug(f"Client at {self.host}:{self.port} does not support SFTP: {e}")
            self._sftp_support_cached = False
            return False

    async def get_sftp_connection(self):
        """
        Get or create SFTP connection through tunnel.

        Returns:
            SFTPConnection instance

        Raises:
            RuntimeError: If SFTP not supported or connection fails
        """
        from server.sftp_connection import SFTPConnection

        # Check if we already have a connection
        if hasattr(self, "_sftp_conn") and self._sftp_conn and self._sftp_conn.is_connected:
            return self._sftp_conn

        # Check if client supports SFTP
        if not await self.has_sftp_support():
            raise RuntimeError("Client does not support SFTP subsystem")

        # Create new connection
        self._sftp_conn = SFTPConnection(self.host, self.port)
        await self._sftp_conn.connect()

        return self._sftp_conn

    async def close_sftp_connection(self) -> None:
        """Close SFTP connection if open."""
        if hasattr(self, "_sftp_conn") and self._sftp_conn:
            try:
                await self._sftp_conn.close()
            except Exception as e:
                logger.warning(f"Error closing SFTP connection: {e}")
            finally:
                self._sftp_conn = None
