"""Tests for SSH session management in client/agent.py."""

from unittest.mock import MagicMock, patch

import pytest

from client.agent import Agent, SSHSessionManager
from shared.protocol import (
    METHOD_SSH_SESSION_CLOSE,
    METHOD_SSH_SESSION_COMMAND,
    METHOD_SSH_SESSION_LIST,
    METHOD_SSH_SESSION_OPEN,
    Request,
)


class TestSSHSessionManagerInit:
    """Tests for SSHSessionManager initialization."""

    def test_init_empty(self):
        manager = SSHSessionManager()
        assert manager._clients == {}
        assert manager._shells == {}
        assert manager._session_info == {}

    def test_list_sessions_empty(self):
        manager = SSHSessionManager()
        result = manager.list_sessions()
        assert result["sessions"] == []
        assert result["count"] == 0


class TestSSHSessionManagerOpenSession:
    """Tests for opening SSH sessions."""

    @patch("client.agent.paramiko.SSHClient")
    def test_open_session_with_password(self, mock_ssh_client_class):
        """Test opening a session with password auth."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager()
        result = manager.open_session(
            host="testhost",
            username="testuser",
            password="testpass",
            port=22,
        )

        assert "session_id" in result
        assert result["host"] == "testhost"
        assert result["username"] == "testuser"
        assert result["port"] == 22

        # Verify SSH client was configured correctly
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once()
        mock_transport.set_keepalive.assert_called_with(30)

    @patch("client.agent.paramiko.SSHClient")
    def test_open_session_with_key_file(self, mock_ssh_client_class, tmp_path):
        """Test opening a session with key file auth."""
        # Create a fake key file
        key_file = tmp_path / "id_rsa"
        key_file.write_text("fake key content")

        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager()
        result = manager.open_session(
            host="testhost",
            username="testuser",
            key_file=str(key_file),
            port=22,
        )

        assert "session_id" in result
        # Verify key_filename was passed to connect
        call_kwargs = mock_client.connect.call_args[1]
        assert call_kwargs["key_filename"] == str(key_file)

    @patch("client.agent.paramiko.SSHClient")
    def test_open_session_auth_failure(self, mock_ssh_client_class):
        """Test handling authentication failure."""
        import paramiko

        mock_client = MagicMock()
        mock_ssh_client_class.return_value = mock_client
        mock_client.connect.side_effect = paramiko.AuthenticationException("Auth failed")

        manager = SSHSessionManager()
        with pytest.raises(ValueError, match="Authentication failed"):
            manager.open_session(
                host="testhost",
                username="testuser",
                password="wrongpass",
            )

    @patch("client.agent.paramiko.SSHClient")
    def test_open_session_connection_failure(self, mock_ssh_client_class):
        """Test handling connection failure."""
        import paramiko

        mock_client = MagicMock()
        mock_ssh_client_class.return_value = mock_client
        mock_client.connect.side_effect = paramiko.SSHException("Connection refused")

        manager = SSHSessionManager()
        with pytest.raises(ConnectionError, match="SSH connection failed"):
            manager.open_session(
                host="testhost",
                username="testuser",
                password="testpass",
            )

    def test_open_session_missing_key_file(self):
        """Test error when key file doesn't exist."""
        manager = SSHSessionManager()
        with pytest.raises(FileNotFoundError, match="Key file not found"):
            manager.open_session(
                host="testhost",
                username="testuser",
                key_file="/nonexistent/path/id_rsa",
            )


class TestSSHSessionManagerSendCommand:
    """Tests for sending commands to SSH sessions."""

    @patch("client.agent.paramiko.SSHClient")
    def test_send_command_success(self, mock_ssh_client_class):
        """Test sending a command successfully."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell

        # Simulate shell output
        output_data = [b"command output\n", b"more output\n"]
        mock_shell.recv_ready.side_effect = [False] + [True, True, False, False, False]
        mock_shell.recv.side_effect = output_data

        manager = SSHSessionManager()
        result = manager.open_session(
            host="testhost",
            username="testuser",
            password="testpass",
        )
        session_id = result["session_id"]

        # Reset mock for command
        mock_shell.recv_ready.side_effect = [True, True, False, False, False]
        mock_shell.recv.side_effect = output_data

        cmd_result = manager.send_command(session_id, "ls -la", timeout=5)

        assert cmd_result["session_id"] == session_id
        assert "stdout" in cmd_result
        mock_shell.send.assert_called_with("ls -la\n")

    def test_send_command_invalid_session(self):
        """Test sending command to non-existent session."""
        manager = SSHSessionManager()
        with pytest.raises(KeyError, match="Session not found"):
            manager.send_command("invalid-session-id", "ls")


class TestSSHSessionManagerCloseSession:
    """Tests for closing SSH sessions."""

    @patch("client.agent.paramiko.SSHClient")
    def test_close_session_success(self, mock_ssh_client_class):
        """Test closing a session successfully."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager()
        result = manager.open_session(
            host="testhost",
            username="testuser",
            password="testpass",
        )
        session_id = result["session_id"]

        # Verify session exists
        assert session_id in manager._shells
        assert session_id in manager._clients

        # Close session
        close_result = manager.close_session(session_id)
        assert close_result["session_id"] == session_id
        assert close_result["closed"] is True
        assert close_result["host"] == "testhost"

        # Verify session was removed
        assert session_id not in manager._shells
        assert session_id not in manager._clients
        assert session_id not in manager._session_info

        # Verify close was called on resources
        mock_shell.close.assert_called_once()
        mock_client.close.assert_called_once()

    def test_close_session_invalid(self):
        """Test closing a non-existent session."""
        manager = SSHSessionManager()
        with pytest.raises(KeyError, match="Session not found"):
            manager.close_session("invalid-session-id")


class TestSSHSessionManagerListSessions:
    """Tests for listing SSH sessions."""

    @patch("client.agent.paramiko.SSHClient")
    def test_list_multiple_sessions(self, mock_ssh_client_class):
        """Test listing multiple sessions."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager()

        # Open two sessions
        _result1 = manager.open_session(host="host1", username="user1", password="pass1")
        _result2 = manager.open_session(host="host2", username="user2", password="pass2")

        # List sessions
        list_result = manager.list_sessions()
        assert list_result["count"] == 2
        assert len(list_result["sessions"]) == 2

        hosts = [s["host"] for s in list_result["sessions"]]
        assert "host1" in hosts
        assert "host2" in hosts


class TestSSHSessionManagerCloseAll:
    """Tests for closing all sessions."""

    @patch("client.agent.paramiko.SSHClient")
    def test_close_all_sessions(self, mock_ssh_client_class):
        """Test closing all sessions at once."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        manager = SSHSessionManager()

        # Open multiple sessions
        manager.open_session(host="host1", username="user1", password="pass1")
        manager.open_session(host="host2", username="user2", password="pass2")

        assert len(manager._shells) == 2

        # Close all
        manager.close_all()

        assert len(manager._shells) == 0
        assert len(manager._clients) == 0
        assert len(manager._session_info) == 0


class TestAgentSSHSessionHandlers:
    """Tests for Agent SSH session method handlers."""

    def test_agent_has_ssh_session_manager(self):
        """Test that Agent initializes SSHSessionManager."""
        agent = Agent()
        assert hasattr(agent, "ssh_sessions")
        assert isinstance(agent.ssh_sessions, SSHSessionManager)

    @patch("client.agent.paramiko.SSHClient")
    def test_agent_ssh_session_open(self, mock_ssh_client_class):
        """Test ssh_session_open through Agent."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        agent = Agent()
        req = Request(
            method=METHOD_SSH_SESSION_OPEN,
            params={
                "host": "testhost",
                "username": "testuser",
                "password": "testpass",
            },
            id="1",
        )
        resp = agent.handle_request(req)

        assert resp.error is None
        assert "session_id" in resp.result
        assert resp.result["host"] == "testhost"

    @patch("client.agent.paramiko.SSHClient")
    def test_agent_ssh_session_command(self, mock_ssh_client_class):
        """Test ssh_session_command through Agent."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.side_effect = [False] + [True, False, False, False]
        mock_shell.recv.return_value = b"output\n"

        agent = Agent()

        # First open a session
        open_req = Request(
            method=METHOD_SSH_SESSION_OPEN,
            params={"host": "testhost", "username": "testuser", "password": "testpass"},
            id="1",
        )
        open_resp = agent.handle_request(open_req)
        session_id = open_resp.result["session_id"]

        # Then send a command
        mock_shell.recv_ready.side_effect = [True, False, False, False]
        cmd_req = Request(
            method=METHOD_SSH_SESSION_COMMAND,
            params={"session_id": session_id, "command": "pwd"},
            id="2",
        )
        cmd_resp = agent.handle_request(cmd_req)

        assert cmd_resp.error is None
        assert cmd_resp.result["session_id"] == session_id
        assert "stdout" in cmd_resp.result

    @patch("client.agent.paramiko.SSHClient")
    def test_agent_ssh_session_list(self, mock_ssh_client_class):
        """Test ssh_session_list through Agent."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        agent = Agent()

        # Open a session
        open_req = Request(
            method=METHOD_SSH_SESSION_OPEN,
            params={"host": "testhost", "username": "testuser", "password": "testpass"},
            id="1",
        )
        agent.handle_request(open_req)

        # List sessions
        list_req = Request(method=METHOD_SSH_SESSION_LIST, params={}, id="2")
        list_resp = agent.handle_request(list_req)

        assert list_resp.error is None
        assert list_resp.result["count"] == 1
        assert len(list_resp.result["sessions"]) == 1

    @patch("client.agent.paramiko.SSHClient")
    def test_agent_ssh_session_close(self, mock_ssh_client_class):
        """Test ssh_session_close through Agent."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_shell = MagicMock()

        mock_ssh_client_class.return_value = mock_client
        mock_client.get_transport.return_value = mock_transport
        mock_client.invoke_shell.return_value = mock_shell
        mock_shell.recv_ready.return_value = False

        agent = Agent()

        # Open a session
        open_req = Request(
            method=METHOD_SSH_SESSION_OPEN,
            params={"host": "testhost", "username": "testuser", "password": "testpass"},
            id="1",
        )
        open_resp = agent.handle_request(open_req)
        session_id = open_resp.result["session_id"]

        # Close the session
        close_req = Request(
            method=METHOD_SSH_SESSION_CLOSE,
            params={"session_id": session_id},
            id="2",
        )
        close_resp = agent.handle_request(close_req)

        assert close_resp.error is None
        assert close_resp.result["closed"] is True

        # Verify session is gone
        list_req = Request(method=METHOD_SSH_SESSION_LIST, params={}, id="3")
        list_resp = agent.handle_request(list_req)
        assert list_resp.result["count"] == 0
