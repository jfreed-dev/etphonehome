"""Tests for SSH Session Management Phase 2-3 features."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from client.agent import (
    Agent,
    JumpHost,
    PromptDetector,
    SSHSessionCleanup,
    SSHSessionManager,
)
from client.ssh_session_store import SSHSessionStore, StoredSession


class TestPromptDetector:
    """Tests for PromptDetector class."""

    def test_detect_bash_dollar_prompt(self):
        detector = PromptDetector()
        assert detector.detect_prompt("user@host:~$ ") is not None

    def test_detect_bash_hash_prompt(self):
        detector = PromptDetector()
        assert detector.detect_prompt("[root@server /]# ") is not None

    def test_detect_zsh_percent_prompt(self):
        detector = PromptDetector()
        assert detector.detect_prompt("% ") is not None

    def test_detect_python_repl(self):
        detector = PromptDetector()
        assert detector.detect_prompt(">>> ") is not None

    def test_detect_powershell_prompt(self):
        detector = PromptDetector()
        assert detector.detect_prompt("PS C:\\Users\\Admin> ") is not None

    def test_no_prompt_in_output(self):
        detector = PromptDetector()
        assert detector.detect_prompt("Hello World\nSome output") is None

    def test_is_complete_true(self):
        detector = PromptDetector()
        assert detector.is_complete("some output\nuser@host:~$ ") is True

    def test_is_complete_false(self):
        detector = PromptDetector()
        assert detector.is_complete("command running...") is False

    def test_custom_pattern(self):
        detector = PromptDetector(custom_patterns=[r"custom>\s*$"])
        assert detector.detect_prompt("custom> ") is not None

    def test_last_prompt_property(self):
        detector = PromptDetector()
        detector.detect_prompt("user@host:~$ ")
        assert detector.last_prompt is not None


class TestJumpHost:
    """Tests for JumpHost class."""

    def test_init_minimal(self):
        jh = JumpHost(host="bastion.example.com", username="admin")
        assert jh.host == "bastion.example.com"
        assert jh.username == "admin"
        assert jh.port == 22
        assert jh.password is None
        assert jh.key_file is None

    def test_init_full(self):
        jh = JumpHost(
            host="bastion.example.com",
            username="admin",
            port=2222,
            password="secret",  # pragma: allowlist secret
            key_file="~/.ssh/id_rsa",
        )
        assert jh.port == 2222
        assert jh.password == "secret"  # pragma: allowlist secret
        assert jh.key_file == "~/.ssh/id_rsa"

    def test_to_dict(self):
        jh = JumpHost(host="bastion", username="admin")
        d = jh.to_dict()
        assert d["host"] == "bastion"
        assert d["username"] == "admin"
        assert d["port"] == 22

    def test_from_dict(self):
        data = {"host": "bastion", "username": "admin", "port": 2222}
        jh = JumpHost.from_dict(data)
        assert jh.host == "bastion"
        assert jh.username == "admin"
        assert jh.port == 2222


class TestSSHSessionManagerPhase2:
    """Tests for Phase 2 SSHSessionManager features."""

    @patch("client.agent.paramiko.SSHClient")
    @patch("client.ssh_session_store.SSHSessionStore")
    def test_open_session_includes_last_activity(self, mock_store, mock_ssh):
        """Test that open_session includes last_activity in session info."""
        # Mock SSH client
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_shell = MagicMock()
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager(persist_sessions=False)
        result = manager.open_session(
            host="test.example.com",
            username="testuser",
            password="testpass",  # pragma: allowlist secret
        )

        session_id = result["session_id"]
        info = manager._session_info[session_id]
        assert "last_activity" in info
        assert "created_at" in info

    @patch("client.agent.paramiko.SSHClient")
    def test_send_raw_method(self, mock_ssh):
        """Test send_raw sends text without waiting for output."""
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_shell = MagicMock()
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager(persist_sessions=False)
        result = manager.open_session(
            host="test.example.com",
            username="testuser",
            password="testpass",  # pragma: allowlist secret
        )
        session_id = result["session_id"]

        # Test send_raw
        send_result = manager.send_raw(session_id, "password123")

        assert send_result["session_id"] == session_id
        assert send_result["sent"] is True
        assert send_result["bytes_sent"] == len("password123\n")
        mock_shell.send.assert_called()

    @patch("client.agent.paramiko.SSHClient")
    def test_send_raw_without_newline(self, mock_ssh):
        """Test send_raw without appending newline."""
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_shell = MagicMock()
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager(persist_sessions=False)
        result = manager.open_session(
            host="test.example.com",
            username="testuser",
            password="testpass",  # pragma: allowlist secret
        )
        session_id = result["session_id"]

        # Test send_raw without newline
        send_result = manager.send_raw(session_id, "y", send_newline=False)

        assert send_result["bytes_sent"] == 1  # Just "y", no newline

    @patch("client.agent.paramiko.SSHClient")
    def test_read_output_method(self, mock_ssh):
        """Test read_output reads pending output."""
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_shell = MagicMock()
        mock_client.invoke_shell.return_value = mock_shell
        # Always return False for recv_ready - simulates no data available
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager(persist_sessions=False)
        result = manager.open_session(
            host="test.example.com",
            username="testuser",
            password="testpass",  # pragma: allowlist secret
        )
        session_id = result["session_id"]

        # read_output will find no data, but should still return valid result
        read_result = manager.read_output(session_id, timeout=0.2)

        assert read_result["session_id"] == session_id
        assert "stdout" in read_result
        assert "has_more" in read_result
        assert read_result["has_more"] is False

    def test_send_raw_invalid_session(self):
        """Test send_raw with invalid session raises KeyError."""
        manager = SSHSessionManager(persist_sessions=False)
        with pytest.raises(KeyError):
            manager.send_raw("invalid-session", "text")

    def test_read_output_invalid_session(self):
        """Test read_output with invalid session raises KeyError."""
        manager = SSHSessionManager(persist_sessions=False)
        with pytest.raises(KeyError):
            manager.read_output("invalid-session")

    @patch("client.agent.paramiko.SSHClient")
    def test_list_sessions_includes_last_activity(self, mock_ssh):
        """Test list_sessions includes last_activity."""
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_shell = MagicMock()
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager(persist_sessions=False)
        manager.open_session(
            host="test.example.com",
            username="testuser",
            password="testpass",  # pragma: allowlist secret
        )

        result = manager.list_sessions()
        assert result["count"] == 1
        session = result["sessions"][0]
        assert "last_activity" in session


class TestSSHSessionStore:
    """Tests for SSHSessionStore class."""

    def test_init_creates_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_sessions.json"
            store = SSHSessionStore(store_path)
            assert store.store_path == store_path

    def test_save_and_load_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_sessions.json"
            store = SSHSessionStore(store_path)

            store.save_session(
                session_id="test-123",
                host="test.example.com",
                port=22,
                username="testuser",
                key_file="~/.ssh/id_rsa",
            )

            # Create new store to test loading
            store2 = SSHSessionStore(store_path)
            restorable = store2.get_restorable_sessions()
            assert len(restorable) == 1
            assert restorable[0].session_id == "test-123"
            assert restorable[0].host == "test.example.com"

    def test_remove_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_sessions.json"
            store = SSHSessionStore(store_path)

            store.save_session(
                session_id="test-123",
                host="test.example.com",
                port=22,
                username="testuser",
                key_file="~/.ssh/id_rsa",
            )
            store.remove_session("test-123")

            assert len(store.get_restorable_sessions()) == 0

    def test_get_manual_sessions(self):
        """Test that password-auth sessions are returned as manual."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_sessions.json"
            store = SSHSessionStore(store_path)

            # Password-only session (no key_file)
            store.save_session(
                session_id="password-session",
                host="test.example.com",
                port=22,
                username="testuser",
                key_file=None,
            )

            manual = store.get_manual_sessions()
            assert len(manual) == 1
            assert manual[0].session_id == "password-session"

    def test_clear_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_sessions.json"
            store = SSHSessionStore(store_path)

            store.save_session(
                session_id="test-1",
                host="host1",
                port=22,
                username="user1",
                key_file="~/.ssh/id_rsa",
            )
            store.save_session(
                session_id="test-2",
                host="host2",
                port=22,
                username="user2",
                key_file="~/.ssh/id_rsa",
            )
            store.clear_all()

            assert len(store.get_restorable_sessions()) == 0


class TestStoredSession:
    """Tests for StoredSession dataclass."""

    def test_to_dict(self):
        session = StoredSession(
            session_id="test-123",
            host="test.example.com",
            port=22,
            username="testuser",
            key_file="~/.ssh/id_rsa",
            jump_hosts=None,
            created_at="2024-01-01T00:00:00Z",
            last_activity="2024-01-01T01:00:00Z",
        )
        d = session.to_dict()
        assert d["session_id"] == "test-123"
        assert d["host"] == "test.example.com"

    def test_from_dict(self):
        data = {
            "session_id": "test-123",
            "host": "test.example.com",
            "port": 22,
            "username": "testuser",
            "key_file": "~/.ssh/id_rsa",
            "jump_hosts": None,
            "created_at": "2024-01-01T00:00:00Z",
            "last_activity": "2024-01-01T01:00:00Z",
        }
        session = StoredSession.from_dict(data)
        assert session.session_id == "test-123"
        assert session.auto_restore is True  # Default


class TestSSHSessionCleanup:
    """Tests for SSHSessionCleanup class."""

    def test_init(self):
        manager = SSHSessionManager(persist_sessions=False)
        cleanup = SSHSessionCleanup(manager, idle_timeout_minutes=30)
        assert cleanup._idle_timeout.total_seconds() == 30 * 60

    def test_start_stop(self):
        manager = SSHSessionManager(persist_sessions=False)
        cleanup = SSHSessionCleanup(manager, idle_timeout_minutes=30, check_interval_seconds=1)
        cleanup.start()
        assert cleanup._running is True
        cleanup.stop()
        assert cleanup._running is False


class TestAgentSSHSessionPhase2Handlers:
    """Tests for Agent SSH session Phase 2 handlers."""

    @patch("client.agent.paramiko.SSHClient")
    def test_agent_ssh_session_send(self, mock_ssh):
        """Test Agent ssh_session_send handler."""
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_shell = MagicMock()
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        agent = Agent(enable_session_cleanup=False)

        # Open session first
        from shared.protocol import METHOD_SSH_SESSION_OPEN, METHOD_SSH_SESSION_SEND, Request

        open_request = Request(
            method=METHOD_SSH_SESSION_OPEN,
            params={
                "host": "test.com",
                "username": "user",
                "password": "pass",  # pragma: allowlist secret
            },
            id="1",
        )
        open_response = agent.handle_request(open_request)
        session_id = open_response.result["session_id"]

        # Test send
        send_request = Request(
            method=METHOD_SSH_SESSION_SEND,
            params={"session_id": session_id, "text": "password123"},
            id="2",
        )
        send_response = agent.handle_request(send_request)
        assert send_response.result["sent"] is True

    @patch("client.agent.paramiko.SSHClient")
    def test_agent_ssh_session_read(self, mock_ssh):
        """Test Agent ssh_session_read handler."""
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_shell = MagicMock()
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        agent = Agent(enable_session_cleanup=False)

        # Open session first
        from shared.protocol import METHOD_SSH_SESSION_OPEN, METHOD_SSH_SESSION_READ, Request

        open_request = Request(
            method=METHOD_SSH_SESSION_OPEN,
            params={
                "host": "test.com",
                "username": "user",
                "password": "pass",  # pragma: allowlist secret
            },
            id="1",
        )
        open_response = agent.handle_request(open_request)
        session_id = open_response.result["session_id"]

        # Test read
        read_request = Request(
            method=METHOD_SSH_SESSION_READ,
            params={"session_id": session_id, "timeout": 0.1},
            id="2",
        )
        read_response = agent.handle_request(read_request)
        assert "stdout" in read_response.result

    def test_agent_ssh_session_restore(self):
        """Test Agent ssh_session_restore handler."""
        from shared.protocol import METHOD_SSH_SESSION_RESTORE, Request

        agent = Agent(enable_session_cleanup=False)

        restore_request = Request(
            method=METHOD_SSH_SESSION_RESTORE,
            params={},
            id="1",
        )
        restore_response = agent.handle_request(restore_request)

        # Should return empty results (no sessions to restore)
        assert "restored" in restore_response.result
        assert "failed" in restore_response.result
        assert "manual_required" in restore_response.result
