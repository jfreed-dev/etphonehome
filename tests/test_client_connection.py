"""Tests for client connection handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.client_connection import ClientConnection
from shared.protocol import Response


class TestClientConnectionInit:
    """Tests for ClientConnection initialization."""

    def test_stores_connection_params(self):
        """Should store host, port, and timeout."""
        conn = ClientConnection("127.0.0.1", 12345, timeout=60.0)

        assert conn.host == "127.0.0.1"
        assert conn.port == 12345
        assert conn.timeout == 60.0

    def test_default_timeout(self):
        """Should use default timeout."""
        conn = ClientConnection("localhost", 8080)

        assert conn.timeout == 30.0

    def test_initial_state(self):
        """Should initialize with no connection."""
        conn = ClientConnection("localhost", 8080)

        assert conn._reader is None
        assert conn._writer is None
        assert conn._request_id == 0


class TestClientConnectionConnect:
    """Tests for ClientConnection.connect method."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Should establish connection."""
        conn = ClientConnection("127.0.0.1", 12345)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()

        with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            await conn.connect()

            mock_open.assert_called_once()
            assert conn._reader is mock_reader
            assert conn._writer is mock_writer

    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        """Should respect timeout on connection."""
        conn = ClientConnection("127.0.0.1", 12345, timeout=1.0)

        with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_open:
            mock_open.side_effect = asyncio.TimeoutError()

            with pytest.raises(asyncio.TimeoutError):
                await conn.connect()


class TestClientConnectionDisconnect:
    """Tests for ClientConnection.disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_writer(self):
        """Should close writer on disconnect."""
        conn = ClientConnection("127.0.0.1", 12345)
        mock_writer = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        conn._writer = mock_writer
        conn._reader = MagicMock()

        await conn.disconnect()

        mock_writer.close.assert_called_once()
        assert conn._writer is None
        assert conn._reader is None

    @pytest.mark.asyncio
    async def test_disconnect_no_connection(self):
        """Should handle disconnect with no connection."""
        conn = ClientConnection("127.0.0.1", 12345)

        # Should not raise
        await conn.disconnect()


class TestClientConnectionSendRequest:
    """Tests for ClientConnection.send_request method."""

    @pytest.mark.asyncio
    async def test_auto_connects(self):
        """Should auto-connect if not connected."""
        conn = ClientConnection("127.0.0.1", 12345)

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock()
        # Return length header (4 bytes) then message
        response = Response.success({"status": "ok"}, "1")
        response_json = response.to_json().encode()
        mock_reader.readexactly.side_effect = [
            len(response_json).to_bytes(4, "big"),
            response_json,
        ]

        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()

        with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            result = await conn.send_request("heartbeat")

            mock_open.assert_called_once()
            assert result.result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_increments_request_id(self):
        """Should increment request ID for each request."""
        conn = ClientConnection("127.0.0.1", 12345)

        mock_reader = AsyncMock()
        response = Response.success({}, "1")
        response_json = response.to_json().encode()
        mock_reader.readexactly = AsyncMock(
            side_effect=[
                len(response_json).to_bytes(4, "big"),
                response_json,
                len(response_json).to_bytes(4, "big"),
                response_json,
            ]
        )

        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        await conn.send_request("method1")
        assert conn._request_id == 1

        await conn.send_request("method2")
        assert conn._request_id == 2


class TestClientConnectionRunCommand:
    """Tests for ClientConnection.run_command method."""

    @pytest.mark.asyncio
    async def test_run_command_success(self):
        """Should execute command and return result."""
        conn = ClientConnection("127.0.0.1", 12345)

        result = {"stdout": "hello\n", "stderr": "", "returncode": 0}
        response = Response.success(result, "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        cmd_result = await conn.run_command("echo hello")

        assert cmd_result["stdout"] == "hello\n"
        assert cmd_result["returncode"] == 0

    @pytest.mark.asyncio
    async def test_run_command_with_cwd(self):
        """Should pass cwd parameter."""
        conn = ClientConnection("127.0.0.1", 12345)

        response = Response.success({"stdout": "", "returncode": 0}, "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        await conn.run_command("ls", cwd="/tmp")

        # Verify the request was sent with cwd
        call_args = mock_writer.write.call_args[0][0]
        assert b"cwd" in call_args

    @pytest.mark.asyncio
    async def test_run_command_error(self):
        """Should raise RuntimeError on command failure."""
        conn = ClientConnection("127.0.0.1", 12345)

        response = Response.error_response(-32002, "Command failed", "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        with pytest.raises(RuntimeError, match="Command failed"):
            await conn.run_command("invalid_command")


class TestClientConnectionFileOps:
    """Tests for ClientConnection file operations."""

    @pytest.mark.asyncio
    async def test_read_file(self):
        """Should read file content."""
        conn = ClientConnection("127.0.0.1", 12345)

        result = {"content": "file content", "size": 12, "path": "/tmp/test.txt"}
        response = Response.success(result, "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        file_result = await conn.read_file("/tmp/test.txt")

        assert file_result["content"] == "file content"

    @pytest.mark.asyncio
    async def test_write_file(self):
        """Should write file content."""
        conn = ClientConnection("127.0.0.1", 12345)

        result = {"path": "/tmp/test.txt", "size": 12}
        response = Response.success(result, "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        write_result = await conn.write_file("/tmp/test.txt", "file content")

        assert write_result["size"] == 12

    @pytest.mark.asyncio
    async def test_list_files(self):
        """Should list directory contents."""
        conn = ClientConnection("127.0.0.1", 12345)

        result = {
            "path": "/tmp",
            "entries": [
                {"name": "file1.txt", "type": "file", "size": 100},
                {"name": "subdir", "type": "dir", "size": 0},
            ],
        }
        response = Response.success(result, "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        list_result = await conn.list_files("/tmp")

        assert len(list_result["entries"]) == 2


class TestClientConnectionHeartbeat:
    """Tests for ClientConnection.heartbeat method."""

    @pytest.mark.asyncio
    async def test_heartbeat_success(self):
        """Should return True for alive response."""
        conn = ClientConnection("127.0.0.1", 12345)

        response = Response.success({"status": "alive"}, "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        result = await conn.heartbeat()

        assert result is True

    @pytest.mark.asyncio
    async def test_heartbeat_failure(self):
        """Should return False on error."""
        conn = ClientConnection("127.0.0.1", 12345)

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(side_effect=Exception("Connection lost"))
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        result = await conn.heartbeat()

        assert result is False


class TestClientConnectionGetMetrics:
    """Tests for ClientConnection.get_metrics method."""

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """Should return metrics from client."""
        conn = ClientConnection("127.0.0.1", 12345)

        result = {
            "timestamp": "2024-01-01T00:00:00Z",
            "cpu": {"usage_percent": 25.0},
            "memory": {"usage_percent": 50.0},
        }
        response = Response.success(result, "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        metrics = await conn.get_metrics()

        assert metrics["cpu"]["usage_percent"] == 25.0

    @pytest.mark.asyncio
    async def test_get_metrics_summary(self):
        """Should request summary when specified."""
        conn = ClientConnection("127.0.0.1", 12345)

        result = {"cpu_percent": 25.0, "memory_percent": 50.0}
        response = Response.success(result, "1")
        response_json = response.to_json().encode()

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=[len(response_json).to_bytes(4, "big"), response_json]
        )
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        conn._reader = mock_reader
        conn._writer = mock_writer

        _metrics = await conn.get_metrics(summary=True)

        # Verify summary parameter was passed
        call_args = mock_writer.write.call_args[0][0]
        assert b"summary" in call_args
