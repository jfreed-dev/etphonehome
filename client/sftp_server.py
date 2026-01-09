"""SFTP server interface for ET Phone Home clients.

This module implements an SFTP subsystem that enforces allowed_paths restrictions
and provides streaming file transfers through the existing reverse SSH tunnel.
"""

import logging
import os
import stat as stat_module
from pathlib import Path

from paramiko import SFTPAttributes, SFTPHandle, SFTPServer, SFTPServerInterface
from paramiko.sftp import SFTP_NO_SUCH_FILE, SFTP_OK, SFTP_PERMISSION_DENIED

logger = logging.getLogger(__name__)


class ClientSFTPHandle(SFTPHandle):
    """File handle for SFTP operations supporting streaming read/write."""

    def __init__(self, flags: int = 0):
        """
        Initialize file handle.

        Args:
            flags: File open flags (os.O_RDONLY, os.O_WRONLY, os.O_RDWR, etc.)
        """
        super().__init__(flags)
        self.file_obj: object | None = None
        self._path: Path | None = None

    def open(self, path: Path, flags: int):
        """
        Open file at path with specified flags.

        Args:
            path: Resolved file path
            flags: File open flags

        Raises:
            OSError: If file cannot be opened
        """
        self._path = path

        # Convert paramiko flags to Python file mode
        if flags & os.O_WRONLY:
            if flags & os.O_APPEND:
                mode = "ab"
            else:
                mode = "wb"
        elif flags & os.O_RDWR:
            if flags & os.O_APPEND:
                mode = "ab+"
            else:
                mode = "rb+"
        else:
            mode = "rb"

        # Create parent directory if needed for write operations
        if "w" in mode or "a" in mode:
            path.parent.mkdir(parents=True, exist_ok=True)

        self.file_obj = open(path, mode)
        logger.debug(f"Opened file: {path} (mode: {mode})")

    def read(self, offset: int, length: int) -> bytes:
        """
        Read data from file at offset.

        Args:
            offset: Byte offset to read from
            length: Number of bytes to read

        Returns:
            Data read from file
        """
        if self.file_obj is None:
            return b""

        self.file_obj.seek(offset)
        data = self.file_obj.read(length)
        logger.debug(f"Read {len(data)} bytes from offset {offset}")
        return data

    def write(self, offset: int, data: bytes) -> int:
        """
        Write data to file at offset.

        Args:
            offset: Byte offset to write to
            data: Data to write

        Returns:
            SFTP_OK on success
        """
        if self.file_obj is None:
            return SFTP_PERMISSION_DENIED

        self.file_obj.seek(offset)
        self.file_obj.write(data)
        logger.debug(f"Wrote {len(data)} bytes at offset {offset}")
        return SFTP_OK

    def stat(self) -> SFTPAttributes:
        """
        Get file attributes.

        Returns:
            SFTPAttributes for the open file
        """
        if self._path is None:
            return SFTPAttributes()

        return SFTPAttributes.from_stat(self._path.stat())

    def close(self) -> int:
        """
        Close file handle.

        Returns:
            SFTP_OK on success
        """
        if self.file_obj is not None:
            self.file_obj.close()
            logger.debug(f"Closed file: {self._path}")
            self.file_obj = None
        return SFTP_OK


class ClientSFTPInterface(SFTPServerInterface):
    """SFTP server interface with allowed_paths enforcement.

    This interface implements paramiko's SFTP server protocol while enforcing
    the same security restrictions as the JSON-RPC agent (allowed_paths validation).
    """

    def __init__(self, server: SFTPServer, allowed_paths: list[str] | None = None):
        """
        Initialize SFTP interface.

        Args:
            server: Paramiko SFTP server instance
            allowed_paths: List of allowed path prefixes (None = unrestricted)
        """
        super().__init__(server)
        self.allowed_paths = allowed_paths
        logger.info(
            f"SFTP interface initialized (allowed_paths: "
            f"{allowed_paths if allowed_paths else 'unrestricted'})"
        )

    def _validate_path(self, path: str) -> Path:
        """
        Validate and resolve a path, checking against allowed paths.

        This reuses the same logic as Agent._validate_path() to ensure
        consistent security enforcement.

        Args:
            path: Path to validate

        Returns:
            Resolved Path object

        Raises:
            PermissionError: If path is not in allowed list
        """
        resolved = Path(path).resolve()

        if self.allowed_paths is not None:
            allowed = False
            for allowed_path in self.allowed_paths:
                try:
                    resolved.relative_to(Path(allowed_path).resolve())
                    allowed = True
                    break
                except ValueError:
                    continue
            if not allowed:
                logger.warning(f"Path access denied (not in allowed list): {path}")
                raise PermissionError(f"Path not in allowed list: {path}")

        return resolved

    def canonicalize(self, path: str) -> str:
        """
        Return canonical version of path.

        Args:
            path: Path to canonicalize

        Returns:
            Canonical absolute path as string
        """
        try:
            resolved = self._validate_path(path)
            return str(resolved)
        except PermissionError:
            # Return the path as-is if validation fails
            # This allows SFTP clients to navigate and get proper errors later
            return str(Path(path).resolve())

    def stat(self, path: str) -> SFTPAttributes | int:
        """
        Get file/directory attributes.

        Args:
            path: Path to stat

        Returns:
            SFTPAttributes on success, error code on failure
        """
        try:
            resolved = self._validate_path(path)
            if not resolved.exists():
                return SFTP_NO_SUCH_FILE
            return SFTPAttributes.from_stat(resolved.stat())
        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except OSError as e:
            logger.error(f"stat error: {e}")
            return SFTP_NO_SUCH_FILE

    def lstat(self, path: str) -> SFTPAttributes | int:
        """
        Get file/directory attributes (don't follow symlinks).

        Args:
            path: Path to lstat

        Returns:
            SFTPAttributes on success, error code on failure
        """
        try:
            resolved = self._validate_path(path)
            if not resolved.exists():
                return SFTP_NO_SUCH_FILE
            return SFTPAttributes.from_stat(resolved.lstat())
        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except OSError as e:
            logger.error(f"lstat error: {e}")
            return SFTP_NO_SUCH_FILE

    def list_folder(self, path: str) -> list[SFTPAttributes] | int:
        """
        List directory contents.

        Args:
            path: Directory path to list

        Returns:
            List of SFTPAttributes on success, error code on failure
        """
        try:
            resolved = self._validate_path(path)
            if not resolved.exists():
                return SFTP_NO_SUCH_FILE
            if not resolved.is_dir():
                return SFTP_PERMISSION_DENIED

            result = []
            for item in resolved.iterdir():
                attr = SFTPAttributes.from_stat(item.lstat())
                attr.filename = item.name
                result.append(attr)

            logger.debug(f"Listed directory: {path} ({len(result)} items)")
            return result

        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except OSError as e:
            logger.error(f"list_folder error: {e}")
            return SFTP_NO_SUCH_FILE

    def open(self, path: str, flags: int, attr: SFTPAttributes) -> ClientSFTPHandle | int:
        """
        Open a file for reading or writing.

        Args:
            path: File path to open
            flags: File open flags (os.O_RDONLY, os.O_WRONLY, etc.)
            attr: File attributes (used for creation)

        Returns:
            ClientSFTPHandle on success, error code on failure
        """
        try:
            resolved = self._validate_path(path)

            handle = ClientSFTPHandle(flags)
            handle.open(resolved, flags)

            logger.info(f"Opened file via SFTP: {path}")
            return handle

        except PermissionError:
            logger.warning(f"Permission denied opening file: {path}")
            return SFTP_PERMISSION_DENIED
        except OSError as e:
            logger.error(f"open error: {e}")
            return SFTP_NO_SUCH_FILE

    def remove(self, path: str) -> int:
        """
        Remove a file.

        Args:
            path: File path to remove

        Returns:
            SFTP_OK on success, error code on failure
        """
        try:
            resolved = self._validate_path(path)
            if not resolved.exists():
                return SFTP_NO_SUCH_FILE
            if not resolved.is_file():
                return SFTP_PERMISSION_DENIED

            resolved.unlink()
            logger.info(f"Removed file via SFTP: {path}")
            return SFTP_OK

        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except OSError as e:
            logger.error(f"remove error: {e}")
            return SFTP_NO_SUCH_FILE

    def rename(self, oldpath: str, newpath: str) -> int:
        """
        Rename/move a file or directory.

        Args:
            oldpath: Current path
            newpath: New path

        Returns:
            SFTP_OK on success, error code on failure
        """
        try:
            old_resolved = self._validate_path(oldpath)
            new_resolved = self._validate_path(newpath)

            if not old_resolved.exists():
                return SFTP_NO_SUCH_FILE

            # Create parent directory if needed
            new_resolved.parent.mkdir(parents=True, exist_ok=True)

            old_resolved.rename(new_resolved)
            logger.info(f"Renamed via SFTP: {oldpath} -> {newpath}")
            return SFTP_OK

        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except OSError as e:
            logger.error(f"rename error: {e}")
            return SFTP_NO_SUCH_FILE

    def mkdir(self, path: str, attr: SFTPAttributes) -> int:
        """
        Create a directory.

        Args:
            path: Directory path to create
            attr: Directory attributes (mode, etc.)

        Returns:
            SFTP_OK on success, error code on failure
        """
        try:
            resolved = self._validate_path(path)

            # Use mode from attr if provided, otherwise default to 0o755
            mode = attr.st_mode if attr and attr.st_mode else 0o755
            # Extract permission bits
            mode = stat_module.S_IMODE(mode)

            resolved.mkdir(mode=mode, parents=True, exist_ok=False)
            logger.info(f"Created directory via SFTP: {path}")
            return SFTP_OK

        except FileExistsError:
            return SFTP_PERMISSION_DENIED
        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except OSError as e:
            logger.error(f"mkdir error: {e}")
            return SFTP_NO_SUCH_FILE

    def rmdir(self, path: str) -> int:
        """
        Remove a directory.

        Args:
            path: Directory path to remove

        Returns:
            SFTP_OK on success, error code on failure
        """
        try:
            resolved = self._validate_path(path)
            if not resolved.exists():
                return SFTP_NO_SUCH_FILE
            if not resolved.is_dir():
                return SFTP_PERMISSION_DENIED

            resolved.rmdir()
            logger.info(f"Removed directory via SFTP: {path}")
            return SFTP_OK

        except PermissionError:
            return SFTP_PERMISSION_DENIED
        except OSError as e:
            logger.error(f"rmdir error: {e}")
            return SFTP_NO_SUCH_FILE

    def session_started(self):
        """Called when SFTP session starts."""
        logger.info("SFTP session started")

    def session_ended(self):
        """Called when SFTP session ends."""
        logger.info("SFTP session ended")
