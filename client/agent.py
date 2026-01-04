"""Local agent that handles requests from the server."""

import os
import subprocess
import stat
from pathlib import Path
from typing import Any
import logging

from shared.protocol import (
    Request,
    Response,
    METHOD_RUN_COMMAND,
    METHOD_READ_FILE,
    METHOD_WRITE_FILE,
    METHOD_LIST_FILES,
    METHOD_HEARTBEAT,
    ERR_METHOD_NOT_FOUND,
    ERR_INVALID_PARAMS,
    ERR_PATH_DENIED,
    ERR_COMMAND_FAILED,
    ERR_FILE_NOT_FOUND,
)

logger = logging.getLogger(__name__)


class Agent:
    """Handles incoming requests from the server."""

    def __init__(self, allowed_paths: list[str] | None = None):
        """
        Initialize the agent.

        Args:
            allowed_paths: List of allowed path prefixes. If None, all paths allowed.
        """
        self.allowed_paths = allowed_paths

    def _validate_path(self, path: str) -> Path:
        """Validate and resolve a path, checking against allowed paths."""
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
                raise PermissionError(f"Path not in allowed list: {path}")

        return resolved

    def handle_request(self, request: Request) -> Response:
        """Process a request and return a response."""
        try:
            if request.method == METHOD_RUN_COMMAND:
                result = self._run_command(request.params)
            elif request.method == METHOD_READ_FILE:
                result = self._read_file(request.params)
            elif request.method == METHOD_WRITE_FILE:
                result = self._write_file(request.params)
            elif request.method == METHOD_LIST_FILES:
                result = self._list_files(request.params)
            elif request.method == METHOD_HEARTBEAT:
                result = {"status": "alive"}
            else:
                return Response.error_response(
                    ERR_METHOD_NOT_FOUND,
                    f"Unknown method: {request.method}",
                    request.id
                )
            return Response.success(result, request.id)
        except PermissionError as e:
            return Response.error_response(ERR_PATH_DENIED, str(e), request.id)
        except FileNotFoundError as e:
            return Response.error_response(ERR_FILE_NOT_FOUND, str(e), request.id)
        except KeyError as e:
            return Response.error_response(
                ERR_INVALID_PARAMS,
                f"Missing required parameter: {e}",
                request.id
            )
        except Exception as e:
            logger.exception("Error handling request")
            return Response.error_response(ERR_COMMAND_FAILED, str(e), request.id)

    def _run_command(self, params: dict) -> dict:
        """Execute a shell command."""
        cmd = params["cmd"]
        cwd = params.get("cwd")
        timeout = params.get("timeout", 300)

        if cwd:
            cwd = str(self._validate_path(cwd))

        logger.info(f"Running command: {cmd}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "returncode": -1
            }

    def _read_file(self, params: dict) -> dict:
        """Read a file's contents."""
        path = self._validate_path(params["path"])
        encoding = params.get("encoding", "utf-8")

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise ValueError(f"Not a file: {path}")

        # Check file size (limit to 10MB)
        size = path.stat().st_size
        if size > 10 * 1024 * 1024:
            raise ValueError(f"File too large: {size} bytes")

        try:
            content = path.read_text(encoding=encoding)
            return {"content": content, "size": size, "path": str(path)}
        except UnicodeDecodeError:
            # Try binary read
            content = path.read_bytes()
            import base64
            return {
                "content": base64.b64encode(content).decode("ascii"),
                "size": size,
                "path": str(path),
                "binary": True
            }

    def _write_file(self, params: dict) -> dict:
        """Write content to a file."""
        path = self._validate_path(params["path"])
        content = params["content"]
        encoding = params.get("encoding", "utf-8")
        binary = params.get("binary", False)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        if binary:
            import base64
            data = base64.b64decode(content)
            path.write_bytes(data)
        else:
            path.write_text(content, encoding=encoding)

        return {"path": str(path), "size": path.stat().st_size}

    def _list_files(self, params: dict) -> dict:
        """List files in a directory."""
        path = self._validate_path(params["path"])

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        entries = []
        for entry in path.iterdir():
            try:
                st = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": st.st_size if entry.is_file() else 0,
                    "mode": stat.filemode(st.st_mode),
                    "mtime": st.st_mtime
                })
            except PermissionError:
                entries.append({
                    "name": entry.name,
                    "type": "unknown",
                    "error": "permission denied"
                })

        return {"path": str(path), "entries": entries}
