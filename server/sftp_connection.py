"""SFTP connection manager for server-side file transfers through reverse tunnels.

This module provides an async wrapper around paramiko's SFTP client, enabling
the MCP server to perform streaming file transfers with clients.
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

import paramiko

logger = logging.getLogger(__name__)


class SFTPConnection:
    """SFTP client connection through reverse tunnel.

    This class wraps paramiko's SFTP client to provide async file transfer
    operations through the existing reverse SSH tunnel.
    """

    def __init__(self, host: str, port: int, timeout: int = 30):
        """
        Initialize SFTP connection.

        Args:
            host: Tunnel host (typically 127.0.0.1)
            port: Tunnel port on server
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout

        self.ssh_client: paramiko.SSHClient | None = None
        self.sftp: paramiko.SFTPClient | None = None
        self._connected = False

    async def connect(self) -> None:
        """
        Connect to SFTP subsystem through tunnel.

        Raises:
            Exception: If connection fails
        """
        if self._connected:
            return

        logger.info(f"Connecting to SFTP subsystem at {self.host}:{self.port}")

        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507

        try:
            # Connect via SSH to tunnel port
            await asyncio.to_thread(
                self.ssh_client.connect,
                hostname=self.host,
                port=self.port,
                username="reach",  # Fixed username for tunnel connections
                look_for_keys=False,
                allow_agent=False,
                timeout=self.timeout,
                auth_timeout=self.timeout,
            )

            # Open SFTP session
            self.sftp = await asyncio.to_thread(self.ssh_client.open_sftp)
            self._connected = True

            logger.info("SFTP connection established")

        except Exception as e:
            logger.error(f"Failed to connect to SFTP: {e}")
            await self.close()
            raise

    async def upload(
        self, local_path: str | Path, remote_path: str, callback: Callable | None = None
    ) -> dict:
        """
        Upload file via SFTP.

        Args:
            local_path: Path to local file
            remote_path: Destination path on remote
            callback: Optional progress callback (bytes_transferred, total_bytes)

        Returns:
            Dict with upload result (size, remote_path)

        Raises:
            Exception: If upload fails
        """
        if not self._connected or not self.sftp:
            raise RuntimeError("SFTP not connected")

        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        logger.info(f"Uploading {local_path} to {remote_path}")

        try:
            # Perform upload in thread pool
            await asyncio.to_thread(self.sftp.put, str(local_path), remote_path, callback=callback)

            # Get file size
            size = local_path.stat().st_size

            logger.info(f"Upload complete: {size} bytes")

            return {"remote_path": remote_path, "size": size, "method": "sftp"}

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise

    async def download(
        self, remote_path: str, local_path: str | Path, callback: Callable | None = None
    ) -> dict:
        """
        Download file via SFTP.

        Args:
            remote_path: Path to remote file
            local_path: Destination path on local system
            callback: Optional progress callback (bytes_transferred, total_bytes)

        Returns:
            Dict with download result (size, local_path)

        Raises:
            Exception: If download fails
        """
        if not self._connected or not self.sftp:
            raise RuntimeError("SFTP not connected")

        local_path = Path(local_path)

        # Create parent directory if needed
        local_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading {remote_path} to {local_path}")

        try:
            # Perform download in thread pool
            await asyncio.to_thread(self.sftp.get, remote_path, str(local_path), callback=callback)

            # Get file size
            size = local_path.stat().st_size

            logger.info(f"Download complete: {size} bytes")

            return {"local_path": str(local_path), "size": size, "method": "sftp"}

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise

    async def listdir(self, path: str) -> list[dict]:
        """
        List directory contents via SFTP.

        Args:
            path: Remote directory path

        Returns:
            List of dicts with file info (filename, size, mode, mtime)

        Raises:
            Exception: If listing fails
        """
        if not self._connected or not self.sftp:
            raise RuntimeError("SFTP not connected")

        logger.debug(f"Listing directory: {path}")

        try:
            attrs = await asyncio.to_thread(self.sftp.listdir_attr, path)

            result = []
            for attr in attrs:
                result.append(
                    {
                        "filename": attr.filename,
                        "size": attr.st_size if attr.st_size else 0,
                        "mode": attr.st_mode if attr.st_mode else 0,
                        "mtime": attr.st_mtime if attr.st_mtime else 0,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"listdir failed: {e}")
            raise

    async def stat(self, path: str) -> dict:
        """
        Get file/directory attributes via SFTP.

        Args:
            path: Remote path

        Returns:
            Dict with file attributes (size, mode, mtime)

        Raises:
            Exception: If stat fails
        """
        if not self._connected or not self.sftp:
            raise RuntimeError("SFTP not connected")

        logger.debug(f"Getting attributes: {path}")

        try:
            attr = await asyncio.to_thread(self.sftp.stat, path)

            return {
                "size": attr.st_size if attr.st_size else 0,
                "mode": attr.st_mode if attr.st_mode else 0,
                "mtime": attr.st_mtime if attr.st_mtime else 0,
                "atime": attr.st_atime if attr.st_atime else 0,
            }

        except Exception as e:
            logger.error(f"stat failed: {e}")
            raise

    async def remove(self, path: str) -> None:
        """
        Remove a file via SFTP.

        Args:
            path: Remote file path

        Raises:
            Exception: If removal fails
        """
        if not self._connected or not self.sftp:
            raise RuntimeError("SFTP not connected")

        logger.info(f"Removing file: {path}")

        try:
            await asyncio.to_thread(self.sftp.remove, path)
            logger.info(f"File removed: {path}")

        except Exception as e:
            logger.error(f"remove failed: {e}")
            raise

    async def mkdir(self, path: str, mode: int = 0o755) -> None:
        """
        Create a directory via SFTP.

        Args:
            path: Remote directory path
            mode: Directory permissions (default: 0o755)

        Raises:
            Exception: If mkdir fails
        """
        if not self._connected or not self.sftp:
            raise RuntimeError("SFTP not connected")

        logger.info(f"Creating directory: {path}")

        try:
            await asyncio.to_thread(self.sftp.mkdir, path, mode)
            logger.info(f"Directory created: {path}")

        except Exception as e:
            logger.error(f"mkdir failed: {e}")
            raise

    async def rmdir(self, path: str) -> None:
        """
        Remove a directory via SFTP.

        Args:
            path: Remote directory path

        Raises:
            Exception: If rmdir fails
        """
        if not self._connected or not self.sftp:
            raise RuntimeError("SFTP not connected")

        logger.info(f"Removing directory: {path}")

        try:
            await asyncio.to_thread(self.sftp.rmdir, path)
            logger.info(f"Directory removed: {path}")

        except Exception as e:
            logger.error(f"rmdir failed: {e}")
            raise

    async def rename(self, oldpath: str, newpath: str) -> None:
        """
        Rename/move a file or directory via SFTP.

        Args:
            oldpath: Current path
            newpath: New path

        Raises:
            Exception: If rename fails
        """
        if not self._connected or not self.sftp:
            raise RuntimeError("SFTP not connected")

        logger.info(f"Renaming: {oldpath} -> {newpath}")

        try:
            await asyncio.to_thread(self.sftp.rename, oldpath, newpath)
            logger.info(f"Rename complete: {oldpath} -> {newpath}")

        except Exception as e:
            logger.error(f"rename failed: {e}")
            raise

    async def close(self) -> None:
        """Close SFTP connection and cleanup resources."""
        if self.sftp:
            try:
                await asyncio.to_thread(self.sftp.close)
            except Exception as e:
                logger.warning(f"Error closing SFTP: {e}")
            self.sftp = None

        if self.ssh_client:
            try:
                await asyncio.to_thread(self.ssh_client.close)
            except Exception as e:
                logger.warning(f"Error closing SSH client: {e}")
            self.ssh_client = None

        self._connected = False
        logger.info("SFTP connection closed")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    @property
    def is_connected(self) -> bool:
        """Check if SFTP connection is active."""
        return self._connected and self.sftp is not None
