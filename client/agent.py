"""Local agent that handles requests from the server."""

import logging
import re
import stat
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paramiko

from client.metrics import collect_metrics, get_metrics_summary
from client.ssh_session_store import SSHSessionStore
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
    METHOD_SSH_SESSION_READ,
    METHOD_SSH_SESSION_RESTORE,
    METHOD_SSH_SESSION_SEND,
    METHOD_WRITE_FILE,
    Request,
    Response,
)

logger = logging.getLogger(__name__)


class JumpHost:
    """Configuration for a jump/bastion host."""

    def __init__(
        self,
        host: str,
        username: str,
        port: int = 22,
        password: str | None = None,
        key_file: str | None = None,
    ):
        self.host = host
        self.username = username
        self.port = port
        self.password = password
        self.key_file = key_file

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "username": self.username,
            "port": self.port,
            "password": self.password,
            "key_file": self.key_file,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JumpHost":
        return cls(
            host=data["host"],
            username=data["username"],
            port=data.get("port", 22),
            password=data.get("password"),
            key_file=data.get("key_file"),
        )


class PromptDetector:
    """Detect common shell prompts for command completion."""

    # Common prompt patterns
    DEFAULT_PATTERNS = [
        r"[\$#>]\s*$",  # Basic: $ or # or >
        r"\[\w+@[\w\-\.]+\s+[^\]]+\][\$#]\s*$",  # Bash: [user@host dir]$
        r"\w+@[\w\-\.]+:[\~\/][^\s]*[\$#]\s*$",  # Bash: user@host:dir$
        r"%\s*$",  # zsh default
        r">>>\s*$",  # Python REPL
        r"\([\w\-]+\)\s*[\$#]\s*$",  # virtualenv prefix
        r"PS\s*[A-Za-z]:\\[^>]*>\s*$",  # PowerShell: PS C:\Users>
    ]

    def __init__(self, custom_patterns: list[str] | None = None):
        """
        Initialize the prompt detector.

        Args:
            custom_patterns: Additional regex patterns to detect prompts
        """
        patterns = self.DEFAULT_PATTERNS + (custom_patterns or [])
        self._patterns = [re.compile(p) for p in patterns]
        self._last_prompt: str | None = None

    def detect_prompt(self, output: str) -> str | None:
        """
        Check if output ends with a prompt pattern.

        Args:
            output: Command output to check

        Returns:
            The matched prompt string, or None if no prompt detected
        """
        # Check last 200 chars for prompt
        tail = output[-200:] if len(output) > 200 else output
        lines = tail.split("\n")

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            for pattern in self._patterns:
                if pattern.search(line):
                    self._last_prompt = line
                    return line
        return None

    def is_complete(self, output: str) -> bool:
        """Check if command output appears complete (ends with prompt)."""
        return self.detect_prompt(output) is not None

    @property
    def last_prompt(self) -> str | None:
        """Return the last detected prompt."""
        return self._last_prompt


class SSHSessionCleanup:
    """Background cleanup of idle SSH sessions."""

    def __init__(
        self,
        session_manager: "SSHSessionManager",
        idle_timeout_minutes: int = 30,
        check_interval_seconds: int = 60,
    ):
        """
        Initialize the cleanup thread.

        Args:
            session_manager: The SSHSessionManager to monitor
            idle_timeout_minutes: Close sessions idle longer than this (default 30)
            check_interval_seconds: How often to check for idle sessions (default 60)
        """
        self._manager = session_manager
        self._idle_timeout = timedelta(minutes=idle_timeout_minutes)
        self._check_interval = check_interval_seconds
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the cleanup background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._thread.start()
        logger.info(f"SSH session cleanup started (idle_timeout={self._idle_timeout})")

    def stop(self) -> None:
        """Stop the cleanup thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("SSH session cleanup stopped")

    def _cleanup_loop(self) -> None:
        """Main cleanup loop."""
        while self._running:
            try:
                self._check_idle_sessions()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

            # Sleep in small increments for responsive shutdown
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _check_idle_sessions(self) -> None:
        """Close sessions that have been idle too long."""
        now = datetime.now(timezone.utc)

        for session_id in list(self._manager._session_info.keys()):
            info = self._manager._session_info.get(session_id)
            if not info:
                continue

            last_activity_str = info.get("last_activity")
            if not last_activity_str:
                continue

            # Parse ISO timestamp
            last_activity = datetime.fromisoformat(last_activity_str.replace("Z", "+00:00"))
            idle_time = now - last_activity

            if idle_time > self._idle_timeout:
                logger.info(
                    f"Closing idle SSH session {session_id} "
                    f"(idle for {idle_time.total_seconds() / 60:.1f} minutes)"
                )
                try:
                    self._manager.close_session(session_id)
                except Exception as e:
                    logger.warning(f"Error closing idle session {session_id}: {e}")


class SSHSessionManager:
    """Manage persistent SSH sessions to remote hosts."""

    def __init__(self, persist_sessions: bool = True):
        """
        Initialize the session manager.

        Args:
            persist_sessions: Enable session persistence to disk for restoration
        """
        self._clients: dict[str, paramiko.SSHClient] = {}
        self._shells: dict[str, paramiko.Channel] = {}
        self._session_info: dict[str, dict] = {}

        # Session persistence
        self._persist = persist_sessions
        self._store = SSHSessionStore() if persist_sessions else None

    def open_session(
        self,
        host: str,
        username: str,
        password: str | None = None,
        key_file: str | None = None,
        port: int = 22,
        jump_hosts: list[dict] | None = None,
    ) -> dict:
        """
        Open a new persistent SSH session.

        Args:
            host: Target hostname or IP
            username: SSH username
            password: SSH password (optional if using key)
            key_file: Path to private key file (optional if using password)
            port: SSH port (default 22)
            jump_hosts: List of jump host configs for proxied connection

        Returns:
            dict with session_id and connection info
        """
        session_id = str(uuid.uuid4())[:8]

        try:
            if jump_hosts:
                # Use paramiko-jump for proxied connection
                client, shell = self._open_proxied_session(
                    host, username, password, key_file, port, jump_hosts
                )
            else:
                # Direct connection
                client, shell = self._open_direct_session(host, username, password, key_file, port)

            # Wait for initial prompt
            time.sleep(0.5)
            initial_output = self._read_available(shell)

            # Store session
            now = datetime.now(timezone.utc).isoformat()
            self._clients[session_id] = client
            self._shells[session_id] = shell
            self._session_info[session_id] = {
                "host": host,
                "port": port,
                "username": username,
                "key_file": key_file,
                "jump_hosts": [
                    jh if isinstance(jh, dict) else jh.to_dict() for jh in (jump_hosts or [])
                ],
                "created_at": now,
                "last_activity": now,
            }

            # Persist session metadata (excluding password for security)
            if self._store:
                self._store.save_session(
                    session_id=session_id,
                    host=host,
                    port=port,
                    username=username,
                    key_file=key_file,
                    jump_hosts=jump_hosts,
                    created_at=self._session_info[session_id]["created_at"],
                    last_activity=self._session_info[session_id]["last_activity"],
                )

            jump_info = f" via {len(jump_hosts)} jump host(s)" if jump_hosts else ""
            logger.info(f"SSH session {session_id} opened to {host}{jump_info}")
            return {
                "session_id": session_id,
                "host": host,
                "port": port,
                "username": username,
                "initial_output": initial_output,
                "proxied": bool(jump_hosts),
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

    def _open_direct_session(
        self,
        host: str,
        username: str,
        password: str | None,
        key_file: str | None,
        port: int,
    ) -> tuple[paramiko.SSHClient, paramiko.Channel]:
        """Open a direct SSH connection."""
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

        logger.info(f"Opening direct SSH session to {username}@{host}:{port}")
        client.connect(**connect_kwargs)

        # Enable keepalive
        transport = client.get_transport()
        if transport:
            transport.set_keepalive(30)

        # Create interactive shell
        shell = client.invoke_shell(term="xterm", width=200, height=50)
        shell.settimeout(0.1)  # Non-blocking reads

        return client, shell

    def _open_proxied_session(
        self,
        host: str,
        username: str,
        password: str | None,
        key_file: str | None,
        port: int,
        jump_hosts: list[dict],
    ) -> tuple:
        """Open SSH connection through jump hosts using paramiko-jump."""
        try:
            from paramiko_jump import SSHJumpClient
        except ImportError:
            raise ImportError(
                "paramiko-jump is required for jump host support. "
                "Install with: pip install paramiko-jump"
            )

        # Build jump chain
        jump_client = None

        for i, jh_config in enumerate(jump_hosts):
            jh = JumpHost.from_dict(jh_config) if isinstance(jh_config, dict) else jh_config

            if i == 0:
                # First jump host - direct connection
                jump_client = SSHJumpClient()
                jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            else:
                # Chain through previous jump host
                jump_client = SSHJumpClient(jump_session=jump_client)
                jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": jh.host,
                "port": jh.port,
                "username": jh.username,
                "timeout": 30,
            }

            if jh.password:
                connect_kwargs["password"] = jh.password
            if jh.key_file:
                key_path = Path(jh.key_file).expanduser()
                if key_path.exists():
                    connect_kwargs["key_filename"] = str(key_path)

            logger.info(f"Connecting to jump host {i+1}: {jh.username}@{jh.host}:{jh.port}")
            jump_client.connect(**connect_kwargs)

        # Final connection to target through the jump chain
        final_client = SSHJumpClient(jump_session=jump_client)
        final_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        final_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 30,
        }

        if password:
            final_kwargs["password"] = password
        if key_file:
            key_path = Path(key_file).expanduser()
            if key_path.exists():
                final_kwargs["key_filename"] = str(key_path)

        logger.info(f"Connecting to target {username}@{host}:{port} via jump chain")
        final_client.connect(**final_kwargs)

        # Enable keepalive
        transport = final_client.get_transport()
        if transport:
            transport.set_keepalive(30)

        # Create interactive shell
        shell = final_client.invoke_shell(term="xterm", width=200, height=50)
        shell.settimeout(0.1)

        return final_client, shell

    def send_command(
        self,
        session_id: str,
        command: str,
        timeout: float = 300.0,
        wait_for_prompt: bool = True,
        prompt_patterns: list[str] | None = None,
    ) -> dict:
        """
        Send a command to an existing SSH session.

        Args:
            session_id: Session ID from open_session
            command: Command to execute
            timeout: Maximum time to wait for output (default 300s)
            wait_for_prompt: Use prompt detection (default True, falls back to timeout)
            prompt_patterns: Custom prompt patterns to detect

        Returns:
            dict with stdout output and prompt_detected flag
        """
        if session_id not in self._shells:
            raise KeyError(f"Session not found: {session_id}")

        shell = self._shells[session_id]
        detector = PromptDetector(prompt_patterns) if wait_for_prompt else None

        # Clear any pending output first
        self._read_available(shell)

        # Send command
        logger.debug(f"Session {session_id}: sending command: {command}")
        shell.send(command + "\n")

        # Read output until we see the prompt or timeout
        output = ""
        deadline = time.time() + timeout
        last_output_time = time.time()
        prompt_detected = False
        silence_threshold = 2.0  # Fallback timeout

        while time.time() < deadline:
            chunk = self._read_available(shell)
            if chunk:
                output += chunk
                last_output_time = time.time()

                # Check for prompt if detection enabled
                if detector and detector.is_complete(output):
                    logger.debug(f"Session {session_id}: prompt detected")
                    prompt_detected = True
                    break
            else:
                # No new output - use silence detection as fallback
                if time.time() - last_output_time > silence_threshold:
                    break
                time.sleep(0.1)

        # Update last_activity
        self._session_info[session_id]["last_activity"] = datetime.now(timezone.utc).isoformat()

        # Clean up output: remove the echoed command from the start
        lines = output.split("\n")
        if lines and command in lines[0]:
            lines = lines[1:]
        output = "\n".join(lines)

        logger.debug(f"Session {session_id}: command complete, {len(output)} bytes output")
        return {
            "session_id": session_id,
            "stdout": output.strip(),
            "prompt_detected": prompt_detected,
        }

    def send_raw(
        self,
        session_id: str,
        text: str,
        send_newline: bool = True,
    ) -> dict:
        """
        Send raw input to an existing SSH session without waiting for output.

        Use for interactive prompts like sudo passwords, y/n confirmations.

        Args:
            session_id: Session ID from open_session
            text: Raw text to send
            send_newline: Whether to append newline (default True)

        Returns:
            dict with session_id and confirmation
        """
        if session_id not in self._shells:
            raise KeyError(f"Session not found: {session_id}")

        shell = self._shells[session_id]
        data = text + ("\n" if send_newline else "")

        logger.debug(f"Session {session_id}: sending raw input: {text[:50]}...")
        shell.send(data)

        # Update last_activity
        self._session_info[session_id]["last_activity"] = datetime.now(timezone.utc).isoformat()

        return {
            "session_id": session_id,
            "sent": True,
            "bytes_sent": len(data),
        }

    def read_output(
        self,
        session_id: str,
        timeout: float = 0.5,
    ) -> dict:
        """
        Read pending output from an SSH session without sending a command.

        Use after send_raw() or to poll for asynchronous output.

        Args:
            session_id: Session ID from open_session
            timeout: Maximum time to wait for initial output (default 0.5s)

        Returns:
            dict with session_id, stdout output, and has_more flag
        """
        if session_id not in self._shells:
            raise KeyError(f"Session not found: {session_id}")

        shell = self._shells[session_id]

        # Wait briefly for any incoming data
        output = ""
        deadline = time.time() + timeout

        while time.time() < deadline:
            chunk = self._read_available(shell)
            if chunk:
                output += chunk
                # Got some output, wait a bit more for completion
                time.sleep(0.1)
            else:
                if output:  # Have output and no more coming
                    break
                time.sleep(0.05)

        # Update last_activity
        self._session_info[session_id]["last_activity"] = datetime.now(timezone.utc).isoformat()

        logger.debug(f"Session {session_id}: read {len(output)} bytes pending output")
        return {
            "session_id": session_id,
            "stdout": output,
            "has_more": shell.recv_ready(),
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

        # Remove from persistent store
        if self._store:
            self._store.remove_session(session_id)

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
            dict with list of sessions including last_activity
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
                    "last_activity": info.get("last_activity"),
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

    def restore_sessions(self) -> dict:
        """
        Attempt to restore sessions from persistent storage.

        Note: Only key-based authentication can be restored automatically.
        Password-authenticated sessions will be listed as needing manual reconnect.

        Returns:
            dict with restored, failed, and manual_required session lists
        """
        if not self._store:
            return {
                "restored": [],
                "failed": [],
                "manual_required": [],
                "message": "Session persistence is disabled",
            }

        restorable = self._store.get_restorable_sessions()
        manual = self._store.get_manual_sessions()

        restored = []
        failed = []
        manual_required = []

        # Sessions that need manual reconnection (password auth)
        for session in manual:
            manual_required.append(
                {
                    "session_id": session.session_id,
                    "host": session.host,
                    "username": session.username,
                    "reason": "password_auth_not_persisted",
                }
            )

        # Attempt to restore key-authenticated sessions
        for session in restorable:
            try:
                result = self.open_session(
                    host=session.host,
                    username=session.username,
                    key_file=session.key_file,
                    port=session.port,
                    jump_hosts=session.jump_hosts,
                )

                # Update store with new session ID
                self._store.mark_restored(session.session_id, result["session_id"])

                restored.append(
                    {
                        "old_session_id": session.session_id,
                        "new_session_id": result["session_id"],
                        "host": session.host,
                    }
                )

            except Exception as e:
                failed.append(
                    {
                        "session_id": session.session_id,
                        "host": session.host,
                        "error": str(e),
                    }
                )
                # Remove failed session from store
                self._store.remove_session(session.session_id)

        logger.info(
            f"Session restore: {len(restored)} restored, "
            f"{len(failed)} failed, {len(manual_required)} need manual reconnect"
        )

        return {
            "restored": restored,
            "failed": failed,
            "manual_required": manual_required,
        }

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

    def __init__(
        self,
        allowed_paths: list[str] | None = None,
        enable_session_cleanup: bool = True,
        idle_timeout_minutes: int = 30,
    ):
        """
        Initialize the agent.

        Args:
            allowed_paths: List of allowed path prefixes. If None, all paths allowed.
            enable_session_cleanup: Enable background cleanup of idle SSH sessions
            idle_timeout_minutes: Close SSH sessions idle longer than this (default 30)
        """
        self.allowed_paths = allowed_paths
        self.ssh_sessions = SSHSessionManager()

        # Initialize session cleanup thread
        self._session_cleanup: SSHSessionCleanup | None = None
        if enable_session_cleanup:
            self._session_cleanup = SSHSessionCleanup(
                self.ssh_sessions,
                idle_timeout_minutes=idle_timeout_minutes,
            )
            self._session_cleanup.start()

    def shutdown(self) -> None:
        """Clean shutdown of agent resources."""
        if self._session_cleanup:
            self._session_cleanup.stop()
        self.ssh_sessions.close_all()
        logger.info("Agent shutdown complete")

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
            elif request.method == METHOD_SSH_SESSION_SEND:
                result = self._ssh_session_send(request.params)
            elif request.method == METHOD_SSH_SESSION_READ:
                result = self._ssh_session_read(request.params)
            elif request.method == METHOD_SSH_SESSION_RESTORE:
                result = self._ssh_session_restore(request.params)
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
        jump_hosts = params.get("jump_hosts")

        jump_info = f" via {len(jump_hosts)} jump host(s)" if jump_hosts else ""
        logger.info(f"Opening SSH session to {username}@{host}:{port}{jump_info}")
        return self.ssh_sessions.open_session(
            host=host,
            username=username,
            password=password,
            key_file=key_file,
            port=port,
            jump_hosts=jump_hosts,
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

    def _ssh_session_send(self, params: dict) -> dict:
        """Send raw input to an SSH session."""
        session_id = params["session_id"]
        text = params["text"]
        send_newline = params.get("send_newline", True)

        logger.info(f"SSH session {session_id}: sending raw input")
        return self.ssh_sessions.send_raw(
            session_id=session_id,
            text=text,
            send_newline=send_newline,
        )

    def _ssh_session_read(self, params: dict) -> dict:
        """Read pending output from an SSH session."""
        session_id = params["session_id"]
        timeout = params.get("timeout", 0.5)

        logger.info(f"SSH session {session_id}: reading output")
        return self.ssh_sessions.read_output(
            session_id=session_id,
            timeout=timeout,
        )

    def _ssh_session_restore(self, params: dict) -> dict:
        """Restore SSH sessions from persistent storage."""
        logger.info("SSH session restore requested")
        return self.ssh_sessions.restore_sessions()
