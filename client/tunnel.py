"""SSH tunnel management for reverse connections."""

import json
import socket
import threading
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

import paramiko

from shared.protocol import ClientInfo, Request, Response, encode_message, decode_message
from client.capabilities import detect_capabilities, get_ssh_key_fingerprint

if TYPE_CHECKING:
    from client.config import Config

logger = logging.getLogger(__name__)


class ReverseTunnel:
    """Manages a reverse SSH tunnel to the server."""

    def __init__(
        self,
        config: "Config",
        client_id: str,
        request_handler: Callable[[Request], Response],
    ):
        self.config = config
        self.server_host = config.server_host
        self.server_port = config.server_port
        self.server_user = config.server_user
        self.key_file = Path(config.key_file)
        self.client_id = client_id
        self.request_handler = request_handler

        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.transport: Optional[paramiko.Transport] = None
        self.tunnel_port: int = 0
        self.running = False
        self._agent_thread: Optional[threading.Thread] = None
        self._agent_socket: Optional[socket.socket] = None

    def connect(self) -> int:
        """
        Establish SSH connection and create reverse tunnel.

        Returns:
            The tunnel port number on the server.
        """
        logger.info(f"Connecting to {self.server_host}:{self.server_port}")

        # Load private key
        if not self.key_file.exists():
            raise FileNotFoundError(f"SSH key not found: {self.key_file}")

        pkey = paramiko.Ed25519Key.from_private_key_file(str(self.key_file))

        # Create SSH client
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.ssh_client.connect(
            hostname=self.server_host,
            port=self.server_port,
            username=self.server_user,
            pkey=pkey,
            look_for_keys=False,
            allow_agent=False,
        )

        self.transport = self.ssh_client.get_transport()
        if not self.transport:
            raise RuntimeError("Failed to get SSH transport")

        # Start local agent server
        self._start_agent_server()

        # Request reverse port forwarding
        # The server will connect to our agent through this tunnel
        self.tunnel_port = self.transport.request_port_forward("127.0.0.1", 0)
        logger.info(f"Reverse tunnel established on server port {self.tunnel_port}")

        # Start handling incoming connections
        self.running = True
        self._tunnel_thread = threading.Thread(target=self._accept_tunnel_connections, daemon=True)
        self._tunnel_thread.start()

        # Register with server
        self._register()

        return self.tunnel_port

    def _start_agent_server(self):
        """Start local socket server for agent connections."""
        self._agent_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._agent_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._agent_socket.bind(("127.0.0.1", 0))
        self._agent_socket.listen(5)
        self._agent_port = self._agent_socket.getsockname()[1]
        logger.debug(f"Agent server listening on port {self._agent_port}")

    def _accept_tunnel_connections(self):
        """Accept connections from the SSH tunnel and handle them."""
        while self.running:
            try:
                chan = self.transport.accept(timeout=1)
                if chan is None:
                    continue

                logger.debug("Accepted tunnel connection")
                thread = threading.Thread(
                    target=self._handle_channel,
                    args=(chan,),
                    daemon=True
                )
                thread.start()
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting tunnel connection: {e}")

    def _handle_channel(self, chan: paramiko.Channel):
        """Handle a single channel connection."""
        buffer = b""
        try:
            while self.running:
                data = chan.recv(4096)
                if not data:
                    break

                buffer += data

                # Try to decode messages
                while len(buffer) >= 4:
                    try:
                        msg, buffer = decode_message(buffer)
                        request = Request.from_json(msg)
                        logger.debug(f"Received request: {request.method}")

                        response = self.request_handler(request)
                        response_data = encode_message(response.to_json())
                        chan.sendall(response_data)
                    except ValueError:
                        # Incomplete message, wait for more data
                        break
        except Exception as e:
            logger.error(f"Error handling channel: {e}")
        finally:
            chan.close()

    def _register(self):
        """Register this client with the server, including full identity."""
        # Get SSH key fingerprint
        try:
            fingerprint = get_ssh_key_fingerprint(self.key_file)
        except Exception as e:
            logger.warning(f"Could not get key fingerprint: {e}")
            fingerprint = ""

        # Detect system capabilities
        capabilities = detect_capabilities()

        # Build identity payload
        now = datetime.utcnow().isoformat() + "Z"
        identity = {
            "uuid": self.config.uuid or "",
            "display_name": self.config.display_name or socket.gethostname(),
            "purpose": self.config.purpose or "",
            "tags": self.config.tags or [],
            "capabilities": capabilities,
            "public_key_fingerprint": fingerprint,
            "first_seen": now,  # Server will use stored value if exists
            "created_by": "auto",
        }

        # Build client info
        client_info = ClientInfo.create_local(
            self.client_id,
            self.tunnel_port,
            identity_uuid=self.config.uuid
        )

        # Build full registration payload
        registration = {
            "identity": identity,
            "client_info": client_info.to_dict()
        }

        # Send registration via SSH exec channel
        stdin, stdout, stderr = self.ssh_client.exec_command(
            f"register {json.dumps(registration)}"
        )
        result = stdout.read().decode().strip()
        logger.info(f"Registration result: {result}")

    def disconnect(self):
        """Close the tunnel and SSH connection."""
        self.running = False

        if self._agent_socket:
            try:
                self._agent_socket.close()
            except Exception:
                pass

        if self.transport:
            try:
                self.transport.cancel_port_forward("127.0.0.1", self.tunnel_port)
            except Exception:
                pass

        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass

        logger.info("Disconnected from server")

    def is_connected(self) -> bool:
        """Check if the tunnel is still connected."""
        if not self.transport:
            return False
        return self.transport.is_active()

    def send_heartbeat(self) -> bool:
        """Send a heartbeat to verify connection."""
        try:
            self.transport.send_ignore()
            return True
        except Exception:
            return False


def generate_ssh_keypair(key_path: Path) -> Path:
    """Generate an Ed25519 SSH keypair."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key_path = Path(key_path)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate key
    private_key = Ed25519PrivateKey.generate()

    # Save private key
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption()
    )
    key_path.write_bytes(private_bytes)
    key_path.chmod(0o600)

    # Save public key
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    )
    pub_path = key_path.with_suffix(".pub")
    pub_path.write_bytes(public_bytes + b"\n")

    logger.info(f"Generated SSH keypair: {key_path}")
    return key_path
