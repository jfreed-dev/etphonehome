"""Tests for client/agent.py - Agent request handlers."""

import base64

import pytest

from client.agent import Agent
from shared.protocol import (
    ERR_FILE_NOT_FOUND,
    ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
    ERR_PATH_DENIED,
    METHOD_HEARTBEAT,
    METHOD_LIST_FILES,
    METHOD_READ_FILE,
    METHOD_RUN_COMMAND,
    METHOD_WRITE_FILE,
    Request,
)


class TestAgentInit:
    """Tests for Agent initialization."""

    def test_init_no_restrictions(self):
        agent = Agent()
        assert agent.allowed_paths is None

    def test_init_with_allowed_paths(self):
        agent = Agent(allowed_paths=["/home", "/tmp"])
        assert agent.allowed_paths == ["/home", "/tmp"]

    def test_init_empty_allowed_paths(self):
        agent = Agent(allowed_paths=[])
        assert agent.allowed_paths == []


class TestAgentPathValidation:
    """Tests for path validation."""

    def test_validate_any_path_when_unrestricted(self, tmp_path):
        agent = Agent(allowed_paths=None)
        # Should not raise
        result = agent._validate_path(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_validate_allowed_path(self, tmp_path):
        agent = Agent(allowed_paths=[str(tmp_path)])
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = agent._validate_path(str(subdir))
        assert result == subdir.resolve()

    def test_validate_disallowed_path(self, tmp_path):
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        disallowed_dir = tmp_path / "disallowed"
        disallowed_dir.mkdir()

        agent = Agent(allowed_paths=[str(allowed_dir)])
        with pytest.raises(PermissionError, match="Path not in allowed list"):
            agent._validate_path(str(disallowed_dir))

    def test_validate_resolves_symlinks(self, tmp_path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real_dir)

        agent = Agent(allowed_paths=[str(real_dir)])
        # Should work because symlink resolves to allowed path
        result = agent._validate_path(str(link))
        assert result == real_dir.resolve()


class TestAgentHeartbeat:
    """Tests for heartbeat handling."""

    def test_heartbeat(self):
        agent = Agent()
        req = Request(method=METHOD_HEARTBEAT, id="1")
        resp = agent.handle_request(req)
        assert resp.id == "1"
        assert resp.result == {"status": "alive"}
        assert resp.error is None


class TestAgentRunCommand:
    """Tests for run_command method."""

    def test_run_simple_command(self):
        agent = Agent()
        req = Request(method=METHOD_RUN_COMMAND, params={"cmd": "echo hello"}, id="1")
        resp = agent.handle_request(req)
        assert resp.error is None
        assert resp.result["stdout"].strip() == "hello"
        assert resp.result["returncode"] == 0

    def test_run_command_with_stderr(self):
        agent = Agent()
        req = Request(method=METHOD_RUN_COMMAND, params={"cmd": "echo error >&2"}, id="2")
        resp = agent.handle_request(req)
        assert resp.error is None
        assert "error" in resp.result["stderr"]

    def test_run_command_failure(self):
        agent = Agent()
        req = Request(method=METHOD_RUN_COMMAND, params={"cmd": "exit 42"}, id="3")
        resp = agent.handle_request(req)
        assert resp.error is None
        assert resp.result["returncode"] == 42

    def test_run_command_with_cwd(self, tmp_path):
        agent = Agent()
        req = Request(
            method=METHOD_RUN_COMMAND, params={"cmd": "pwd", "cwd": str(tmp_path)}, id="4"
        )
        resp = agent.handle_request(req)
        assert resp.error is None
        assert str(tmp_path) in resp.result["stdout"]

    def test_run_command_timeout(self):
        agent = Agent()
        req = Request(
            method=METHOD_RUN_COMMAND,
            params={"cmd": "sleep 10", "timeout": 1},
            id="5",
        )
        resp = agent.handle_request(req)
        assert resp.error is None
        assert resp.result["returncode"] == -1
        assert "timed out" in resp.result["stderr"]

    def test_run_command_missing_cmd(self):
        agent = Agent()
        req = Request(method=METHOD_RUN_COMMAND, params={}, id="6")
        resp = agent.handle_request(req)
        assert resp.error is not None
        assert resp.error["code"] == ERR_INVALID_PARAMS


class TestAgentReadFile:
    """Tests for read_file method."""

    def test_read_text_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        agent = Agent()
        req = Request(method=METHOD_READ_FILE, params={"path": str(test_file)}, id="1")
        resp = agent.handle_request(req)

        assert resp.error is None
        assert resp.result["content"] == "Hello, World!"
        assert resp.result["size"] == 13
        assert resp.result["path"] == str(test_file)

    def test_read_binary_file(self, tmp_path):
        test_file = tmp_path / "test.bin"
        binary_data = bytes([0, 1, 2, 255, 254, 253])
        test_file.write_bytes(binary_data)

        agent = Agent()
        req = Request(method=METHOD_READ_FILE, params={"path": str(test_file)}, id="2")
        resp = agent.handle_request(req)

        assert resp.error is None
        assert resp.result["binary"] is True
        decoded = base64.b64decode(resp.result["content"])
        assert decoded == binary_data

    def test_read_nonexistent_file(self, tmp_path):
        agent = Agent()
        req = Request(
            method=METHOD_READ_FILE,
            params={"path": str(tmp_path / "nonexistent.txt")},
            id="3",
        )
        resp = agent.handle_request(req)
        assert resp.error is not None
        assert resp.error["code"] == ERR_FILE_NOT_FOUND

    def test_read_directory_fails(self, tmp_path):
        agent = Agent()
        req = Request(method=METHOD_READ_FILE, params={"path": str(tmp_path)}, id="4")
        resp = agent.handle_request(req)
        assert resp.error is not None
        # Should fail because it's not a file

    def test_read_restricted_path(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        restricted = tmp_path / "restricted"
        restricted.mkdir()
        (restricted / "secret.txt").write_text("secret")

        agent = Agent(allowed_paths=[str(allowed)])
        req = Request(
            method=METHOD_READ_FILE,
            params={"path": str(restricted / "secret.txt")},
            id="5",
        )
        resp = agent.handle_request(req)
        assert resp.error is not None
        assert resp.error["code"] == ERR_PATH_DENIED


class TestAgentWriteFile:
    """Tests for write_file method."""

    def test_write_text_file(self, tmp_path):
        test_file = tmp_path / "output.txt"

        agent = Agent()
        req = Request(
            method=METHOD_WRITE_FILE,
            params={"path": str(test_file), "content": "Written content"},
            id="1",
        )
        resp = agent.handle_request(req)

        assert resp.error is None
        assert test_file.read_text() == "Written content"
        assert resp.result["size"] == 15

    def test_write_binary_file(self, tmp_path):
        test_file = tmp_path / "output.bin"
        binary_data = bytes([10, 20, 30, 40])
        encoded = base64.b64encode(binary_data).decode("ascii")

        agent = Agent()
        req = Request(
            method=METHOD_WRITE_FILE,
            params={"path": str(test_file), "content": encoded, "binary": True},
            id="2",
        )
        resp = agent.handle_request(req)

        assert resp.error is None
        assert test_file.read_bytes() == binary_data

    def test_write_creates_parent_dirs(self, tmp_path):
        test_file = tmp_path / "deep" / "nested" / "file.txt"

        agent = Agent()
        req = Request(
            method=METHOD_WRITE_FILE,
            params={"path": str(test_file), "content": "Nested content"},
            id="3",
        )
        resp = agent.handle_request(req)

        assert resp.error is None
        assert test_file.exists()
        assert test_file.read_text() == "Nested content"

    def test_write_restricted_path(self, tmp_path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        restricted = tmp_path / "restricted"
        restricted.mkdir()

        agent = Agent(allowed_paths=[str(allowed)])
        req = Request(
            method=METHOD_WRITE_FILE,
            params={"path": str(restricted / "hack.txt"), "content": "bad"},
            id="4",
        )
        resp = agent.handle_request(req)
        assert resp.error is not None
        assert resp.error["code"] == ERR_PATH_DENIED


class TestAgentListFiles:
    """Tests for list_files method."""

    def test_list_empty_directory(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        agent = Agent()
        req = Request(method=METHOD_LIST_FILES, params={"path": str(empty_dir)}, id="1")
        resp = agent.handle_request(req)

        assert resp.error is None
        assert resp.result["path"] == str(empty_dir)
        assert resp.result["entries"] == []

    def test_list_directory_with_files(self, tmp_path):
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        agent = Agent()
        req = Request(method=METHOD_LIST_FILES, params={"path": str(tmp_path)}, id="2")
        resp = agent.handle_request(req)

        assert resp.error is None
        entries = resp.result["entries"]
        names = [e["name"] for e in entries]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

        # Check types
        for entry in entries:
            if entry["name"] == "subdir":
                assert entry["type"] == "dir"
            else:
                assert entry["type"] == "file"

    def test_list_nonexistent_directory(self, tmp_path):
        agent = Agent()
        req = Request(
            method=METHOD_LIST_FILES,
            params={"path": str(tmp_path / "nonexistent")},
            id="3",
        )
        resp = agent.handle_request(req)
        assert resp.error is not None
        assert resp.error["code"] == ERR_FILE_NOT_FOUND

    def test_list_file_fails(self, tmp_path):
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")

        agent = Agent()
        req = Request(method=METHOD_LIST_FILES, params={"path": str(test_file)}, id="4")
        resp = agent.handle_request(req)
        assert resp.error is not None
        # Should fail because it's not a directory


class TestAgentUnknownMethod:
    """Tests for unknown method handling."""

    def test_unknown_method(self):
        agent = Agent()
        req = Request(method="unknown_method", params={}, id="1")
        resp = agent.handle_request(req)
        assert resp.error is not None
        assert resp.error["code"] == ERR_METHOD_NOT_FOUND
        assert "unknown_method" in resp.error["message"]
