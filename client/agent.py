"""Local agent that handles requests from the server."""

import logging
import stat
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paramiko

from client.metrics import collect_metrics, get_metrics_summary
from shared.protocol import (
    ERR_COMMAND_FAILED,
    ERR_FILE_NOT_FOUND,
    ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
    ERR_PATH_DENIED,
    METHOD_GET_METRICS,
    METHOD_HEARTBEAT,
    METHOD_LIST_FILES,
    METHOD_READ_FILE,
    METHOD_RUN_COMMAND,
    METHOD_SSH_SESSION_CLOSE,
    METHOD_SSH_SESSION_COMMAND,
    METHOD_SSH_SESSION_LIST,
    METHOD_SSH_SESSION_OPEN,
    METHOD_WRITE_FILE,
    Request,
    Response,
)

logger = logging.getLogger(__name__)


class SSHSessionManager:
    """Manage persistent SSH sessions to remote hosts."""

    def __init__(self):
        """Initialize the session manager."""
        self._clients: dict[str, paramiko.SSHClient] = {}
        self._shells: dict[str, paramiko.Channel] = {}
        self._session_info: dict[str, dict] = {}

    def open_session(
        self,
        host: str,
        username: str,
        password: str | None = None,
        key_file: str | None = None,
        port: int = 22,
    ) -> dict:
        """
        Open a new persistent SSH session.

        Args:
            host: Target hostname or IP
            username: SSH username
            password: SSH password (optional if using key)
            key_file: Path to private key file (optional if using password)
            port: SSH port (default 22)

        Returns:
            dict with session_id and connection info
        """
        session_id = str(uuid.uuid4())[:8]

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Build connection kwargs
            connect_kwargs = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": 30,
                "allow_agent": True,
                "look_for_keys": True,
            }

            if password:
                connect_kwargs["password"] = password
            if key_file:
                key_path = Path(key_file).expanduser()
                if not key_path.exists():
                    raise FileNotFoundError(f"Key file not found: {key_file}")
                connect_kwargs["key_filename"] = str(key_path)

            logger.info(f"Opening SSH session to {username}@{host}:{port}")
            client.connect(**connect_kwargs)

            # Enable keepalive
            transport = client.get_transport()
            if transport:
                transport.set_keepalive(30)

            # Create interactive shell
            shell = client.invoke_shell(term="xterm", width=200, height=50)
            shell.settimeout(0.1)  # Non-blocking reads

            # Wait for initial prompt
            time.sleep(0.5)
            initial_output = self._read_available(shell)

            # Store session
            self._clients[session_id] = client
            self._shells[session_id] = shell
            self._session_info[session_id] = {
                "host": host,
                "port": port,
                "username": username,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"SSH session {session_id} opened to {host}")
            return {
                "session_id": session_id,
                "host": host,
                "port": port,
                "username": username,
                "initial_output": initial_output,
            }

        except paramiko.AuthenticationException as e:
            logger.error(f"SSH authentication failed for {username}@{host}: {e}")
            raise ValueError(f"Authentication failed: {e}")
        except paramiko.SSHException as e:
            logger.error(f"SSH error connecting to {host}: {e}")
            raise ConnectionError(f"SSH connection failed: {e}")
        except Exception as e:
            logger.error(f"Failed to open SSH session to {host}: {e}")
            raise

    def send_command(
        self,
        session_id: str,
        command: str,
        timeout: float = 300.0,
    ) -> dict:
        """
        Send a command to an existing SSH session.

        Args:
            session_id: Session ID from open_session
            command: Command to execute
            timeout: Maximum time to wait for output (default 300s)

        Returns:
            dict with stdout output
        """
        if session_id not in self._shells:
            raise KeyError(f"Session not found: {session_id}")

        shell = self._shells[session_id]

        # Clear any pending output first
        self._read_available(shell)

        # Send command
        logger.debug(f"Session {session_id}: sending command: {command}")
        shell.send(command + "\n")

        # Read output until we see the prompt or timeout
        output = ""
        deadline = time.time() + timeout
        last_output_time = time.time()

        while time.time() < deadline:
            chunk = self._read_available(shell)
            if chunk:
                output += chunk
                last_output_time = time.time()
            else:
                # No new output - check if command seems complete
                # Wait a bit for more output, but if nothing for 2 seconds, assume done
                if time.time() - last_output_time > 2.0:
                    break
                time.sleep(0.1)

        # Clean up output: remove the echoed command from the start
        lines = output.split("\n")
        if lines and command in lines[0]:
            lines = lines[1:]
        output = "\n".join(lines)

        logger.debug(f"Session {session_id}: command complete, {len(output)} bytes output")
        return {
            "session_id": session_id,
            "stdout": output.strip(),
        }

    def close_session(self, session_id: str) -> dict:
        """
        Close an SSH session.

        Args:
            session_id: Session ID to close

        Returns:
            dict confirming closure
        """
        if session_id not in self._shells:
            raise KeyError(f"Session not found: {session_id}")

        info = self._session_info.get(session_id, {})

        # Close shell
        if session_id in self._shells:
            try:
                self._shells[session_id].close()
            except Exception as e:
                logger.warning(f"Error closing shell {session_id}: {e}")
            del self._shells[session_id]

        # Close client
        if session_id in self._clients:
            try:
                self._clients[session_id].close()
            except Exception as e:
                logger.warning(f"Error closing client {session_id}: {e}")
            del self._clients[session_id]

        # Remove info
        if session_id in self._session_info:
            del self._session_info[session_id]

        logger.info(f"SSH session {session_id} closed")
        return {
            "session_id": session_id,
            "closed": True,
            "host": info.get("host"),
        }

    def list_sessions(self) -> dict:
        """
        List all active SSH sessions.

        Returns:
            dict with list of sessions
        """
        sessions = []
        for session_id, info in self._session_info.items():
            sessions.append(
                {
                    "session_id": session_id,
                    "host": info.get("host"),
                    "port": info.get("port"),
                    "username": info.get("username"),
                    "created_at": info.get("created_at"),
                }
            )
        return {
            "sessions": sessions,
            "count": len(sessions),
        }

    def close_all(self) -> None:
        """Close all SSH sessions (called on agent shutdown)."""
        for session_id in list(self._shells.keys()):
            try:
                self.close_session(session_id)
            except Exception as e:
                logger.warning(f"Error closing session {session_id}: {e}")

    def _read_available(self, shell: paramiko.Channel) -> str:
        """Read all available data from shell without blocking."""
        output = ""
        try:
            while shell.recv_ready():
                chunk = shell.recv(4096)
                if chunk:
                    output += chunk.decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug(f"Error reading from shell: {e}")
        return output


class Agent:
    """Handles incoming requests from the server."""

    def __init__(self, allowed_paths: list[str] | None = None):
        """
        Initialize the agent.

        Args:
            allowed_paths: List of allowed path prefixes. If None, all paths allowed.
        """
        self.allowed_paths = allowed_paths
        self.ssh_sessions = SSHSessionManager()

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
            elif request.method == METHOD_GET_METRICS:
                result = self._get_metrics(request.params)
            elif request.method == METHOD_SSH_SESSION_OPEN:
                result = self._ssh_session_open(request.params)
            elif request.method == METHOD_SSH_SESSION_COMMAND:
                result = self._ssh_session_command(request.params)
            elif request.method == METHOD_SSH_SESSION_CLOSE:
                result = self._ssh_session_close(request.params)
            elif request.method == METHOD_SSH_SESSION_LIST:
                result = self._ssh_session_list(request.params)
            else:
                return Response.error_response(
                    ERR_METHOD_NOT_FOUND, f"Unknown method: {request.method}", request.id
                )
            return Response.success(result, request.id)
        except PermissionError as e:
            return Response.error_response(ERR_PATH_DENIED, str(e), request.id)
        except FileNotFoundError as e:
            return Response.error_response(ERR_FILE_NOT_FOUND, str(e), request.id)
        except KeyError as e:
            return Response.error_response(
                ERR_INVALID_PARAMS, f"Missing required parameter: {e}", request.id
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
            # shell=True is intentional - this is a remote command execution tool
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,  # nosec B602
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "returncode": -1,
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
                "binary": True,
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
                entries.append(
                    {
                        "name": entry.name,
                        "type": "dir" if entry.is_dir() else "file",
                        "size": st.st_size if entry.is_file() else 0,
                        "mode": stat.filemode(st.st_mode),
                        "mtime": st.st_mtime,
                    }
                )
            except PermissionError:
                entries.append(
                    {"name": entry.name, "type": "unknown", "error": "permission denied"}
                )

        return {"path": str(path), "entries": entries}

    def _get_metrics(self, params: dict) -> dict:
        """Collect system health metrics."""
        summary_only = params.get("summary", False)

        if summary_only:
            return get_metrics_summary()
        else:
            metrics = collect_metrics()
            return metrics.to_dict()

    def _ssh_session_open(self, params: dict) -> dict:
        """Open a persistent SSH session to a remote host."""
        host = params["host"]
        username = params["username"]
        password = params.get("password")
        key_file = params.get("key_file")
        port = params.get("port", 22)

        logger.info(f"Opening SSH session to {username}@{host}:{port}")
        return self.ssh_sessions.open_session(
            host=host,
            username=username,
            password=password,
            key_file=key_file,
            port=port,
        )

    def _ssh_session_command(self, params: dict) -> dict:
        """Send a command to an existing SSH session."""
        session_id = params["session_id"]
        command = params["command"]
        timeout = params.get("timeout", 300)

        logger.info(f"SSH session {session_id}: executing command")
        return self.ssh_sessions.send_command(
            session_id=session_id,
            command=command,
            timeout=timeout,
        )

    def _ssh_session_close(self, params: dict) -> dict:
        """Close an SSH session."""
        session_id = params["session_id"]

        logger.info(f"Closing SSH session {session_id}")
        return self.ssh_sessions.close_session(session_id)

    def _ssh_session_list(self, params: dict) -> dict:
        """List all active SSH sessions."""
        return self.ssh_sessions.list_sessions()
