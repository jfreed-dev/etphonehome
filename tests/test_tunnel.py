"""Tests for SSH tunnel management."""

from unittest.mock import MagicMock, patch

import pytest

from client.tunnel import ReverseTunnel, generate_ssh_keypair


class TestGenerateSshKeypair:
    """Tests for generate_ssh_keypair function."""

    def test_generates_keypair(self, tmp_path):
        """Should generate private and public key files."""
        key_path = tmp_path / "id_ed25519"

        result = generate_ssh_keypair(key_path)

        assert result == key_path
        assert key_path.exists()
        assert key_path.with_suffix(".pub").exists()

    def test_private_key_permissions(self, tmp_path):
        """Private key should have 600 permissions."""
        key_path = tmp_path / "id_ed25519"

        generate_ssh_keypair(key_path)

        # Check permissions (0o600 = owner read/write only)
        mode = key_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_private_key_format(self, tmp_path):
        """Private key should be in OpenSSH format."""
        key_path = tmp_path / "id_ed25519"

        generate_ssh_keypair(key_path)

        content = key_path.read_text()
        assert "-----BEGIN OPENSSH PRIVATE KEY-----" in content  # pragma: allowlist secret
        assert "-----END OPENSSH PRIVATE KEY-----" in content

    def test_public_key_format(self, tmp_path):
        """Public key should be in OpenSSH format."""
        key_path = tmp_path / "id_ed25519"

        generate_ssh_keypair(key_path)

        pub_content = key_path.with_suffix(".pub").read_text()
        assert pub_content.startswith("ssh-ed25519 ")

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent directories if needed."""
        key_path = tmp_path / "subdir" / "nested" / "id_ed25519"

        generate_ssh_keypair(key_path)

        assert key_path.exists()
        assert key_path.with_suffix(".pub").exists()

    def test_unique_keys_each_time(self, tmp_path):
        """Each generation should produce unique keys."""
        key1_path = tmp_path / "key1"
        key2_path = tmp_path / "key2"

        generate_ssh_keypair(key1_path)
        generate_ssh_keypair(key2_path)

        pub1 = key1_path.with_suffix(".pub").read_text()
        pub2 = key2_path.with_suffix(".pub").read_text()

        assert pub1 != pub2


class TestReverseTunnelInit:
    """Tests for ReverseTunnel initialization."""

    def test_init_stores_config(self):
        """Should store configuration values."""
        config = MagicMock()
        config.server_host = "example.com"
        config.server_port = 2222
        config.server_user = "etphonehome"
        config.key_file = "/path/to/key"

        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)

        assert tunnel.server_host == "example.com"
        assert tunnel.server_port == 2222
        assert tunnel.server_user == "etphonehome"
        assert tunnel.client_id == "client-123"
        assert tunnel.request_handler is handler

    def test_init_default_state(self):
        """Should initialize with default state."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)

        assert tunnel.ssh_client is None
        assert tunnel.transport is None
        assert tunnel.tunnel_port == 0
        assert tunnel.running is False


class TestReverseTunnelConnect:
    """Tests for ReverseTunnel.connect method."""

    def test_connect_missing_key_raises(self, tmp_path):
        """Should raise FileNotFoundError for missing SSH key."""
        config = MagicMock()
        config.key_file = str(tmp_path / "nonexistent_key")
        config.server_host = "example.com"
        config.server_port = 22
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)

        with pytest.raises(FileNotFoundError, match="SSH key not found"):
            tunnel.connect()

    @patch("client.tunnel.detect_capabilities")
    @patch("client.tunnel.get_ssh_key_fingerprint")
    @patch("client.tunnel.paramiko")
    def test_connect_loads_key(self, mock_paramiko, mock_fingerprint, mock_caps, tmp_path):
        """Should load SSH key from file."""
        # Create a valid key
        key_path = tmp_path / "id_ed25519"
        generate_ssh_keypair(key_path)

        config = MagicMock()
        config.key_file = str(key_path)
        config.server_host = "example.com"
        config.server_port = 22
        config.server_user = "user"
        config.uuid = "test-uuid"
        config.display_name = "Test"
        config.purpose = "Testing"
        config.tags = []
        handler = MagicMock()

        # Mock helper functions
        mock_fingerprint.return_value = "SHA256:test"
        mock_caps.return_value = ["python3.12"]

        # Mock paramiko
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_transport.request_port_forward.return_value = 12345
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        # Mock exec_command for registration
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"registered"
        mock_client.exec_command.return_value = (MagicMock(), mock_stdout, MagicMock())

        mock_paramiko.SSHClient.return_value = mock_client

        tunnel = ReverseTunnel(config, "client-123", handler)

        try:
            port = tunnel.connect()
            assert port == 12345
            mock_paramiko.Ed25519Key.from_private_key_file.assert_called_with(str(key_path))
        finally:
            tunnel.disconnect()


class TestReverseTunnelDisconnect:
    """Tests for ReverseTunnel.disconnect method."""

    def test_disconnect_sets_running_false(self):
        """Should set running to False."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)
        tunnel.running = True

        tunnel.disconnect()

        assert tunnel.running is False

    def test_disconnect_closes_socket(self):
        """Should close agent socket."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)
        mock_socket = MagicMock()
        tunnel._agent_socket = mock_socket

        tunnel.disconnect()

        mock_socket.close.assert_called_once()

    def test_disconnect_closes_transport(self):
        """Should cancel port forward and close client."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)
        mock_transport = MagicMock()
        mock_client = MagicMock()
        tunnel.transport = mock_transport
        tunnel.ssh_client = mock_client
        tunnel.tunnel_port = 12345

        tunnel.disconnect()

        mock_transport.cancel_port_forward.assert_called_with("127.0.0.1", 12345)
        mock_client.close.assert_called_once()


class TestReverseTunnelIsConnected:
    """Tests for ReverseTunnel.is_connected method."""

    def test_not_connected_when_no_transport(self):
        """Should return False when transport is None."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)

        assert tunnel.is_connected() is False

    def test_connected_when_transport_active(self):
        """Should return True when transport is active."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        tunnel.transport = mock_transport

        assert tunnel.is_connected() is True

    def test_not_connected_when_transport_inactive(self):
        """Should return False when transport is inactive."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = False
        tunnel.transport = mock_transport

        assert tunnel.is_connected() is False


class TestReverseTunnelHeartbeat:
    """Tests for ReverseTunnel.send_heartbeat method."""

    def test_heartbeat_success(self):
        """Should return True on successful heartbeat."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)
        mock_transport = MagicMock()
        tunnel.transport = mock_transport

        result = tunnel.send_heartbeat()

        assert result is True
        mock_transport.send_ignore.assert_called_once()

    def test_heartbeat_failure(self):
        """Should return False when heartbeat fails."""
        config = MagicMock()
        config.key_file = "/path/to/key"
        handler = MagicMock()

        tunnel = ReverseTunnel(config, "client-123", handler)
        mock_transport = MagicMock()
        mock_transport.send_ignore.side_effect = Exception("Connection lost")
        tunnel.transport = mock_transport

        result = tunnel.send_heartbeat()

        assert result is False
