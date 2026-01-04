"""Tests for shared/protocol.py - JSON-RPC message encoding/decoding."""

import json

import pytest

from shared.protocol import (
    ERR_COMMAND_FAILED,
    ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
    ERR_PATH_DENIED,
    ClientIdentity,
    ClientInfo,
    Request,
    Response,
    decode_message,
    encode_message,
)


class TestRequest:
    """Tests for Request dataclass."""

    def test_to_json_basic(self):
        req = Request(method="run_command", params={"cmd": "ls"}, id="1")
        result = json.loads(req.to_json())
        assert result["method"] == "run_command"
        assert result["params"] == {"cmd": "ls"}
        assert result["id"] == "1"

    def test_to_json_no_params(self):
        req = Request(method="heartbeat", id="2")
        result = json.loads(req.to_json())
        assert result["method"] == "heartbeat"
        assert result["params"] == {}
        assert result["id"] == "2"

    def test_from_json_full(self):
        data = '{"method": "read_file", "params": {"path": "/tmp/test"}, "id": "3"}'
        req = Request.from_json(data)
        assert req.method == "read_file"
        assert req.params == {"path": "/tmp/test"}
        assert req.id == "3"

    def test_from_json_minimal(self):
        data = '{"method": "heartbeat"}'
        req = Request.from_json(data)
        assert req.method == "heartbeat"
        assert req.params == {}
        assert req.id is None

    def test_roundtrip(self):
        original = Request(method="write_file", params={"path": "/a", "content": "b"}, id="42")
        json_str = original.to_json()
        restored = Request.from_json(json_str)
        assert restored.method == original.method
        assert restored.params == original.params
        assert restored.id == original.id


class TestResponse:
    """Tests for Response dataclass."""

    def test_success_response(self):
        resp = Response.success({"stdout": "hello", "returncode": 0}, id="1")
        result = json.loads(resp.to_json())
        assert result["id"] == "1"
        assert result["result"] == {"stdout": "hello", "returncode": 0}
        assert "error" not in result

    def test_error_response(self):
        resp = Response.error_response(ERR_PATH_DENIED, "Access denied", id="2")
        result = json.loads(resp.to_json())
        assert result["id"] == "2"
        assert result["error"]["code"] == ERR_PATH_DENIED
        assert result["error"]["message"] == "Access denied"
        assert "result" not in result

    def test_from_json_success(self):
        data = '{"id": "1", "result": {"status": "ok"}}'
        resp = Response.from_json(data)
        assert resp.id == "1"
        assert resp.result == {"status": "ok"}
        assert resp.error is None

    def test_from_json_error(self):
        data = '{"id": "2", "error": {"code": -32601, "message": "Method not found"}}'
        resp = Response.from_json(data)
        assert resp.id == "2"
        assert resp.result is None
        assert resp.error["code"] == ERR_METHOD_NOT_FOUND

    def test_roundtrip_success(self):
        original = Response.success({"data": [1, 2, 3]}, id="test")
        restored = Response.from_json(original.to_json())
        assert restored.id == original.id
        assert restored.result == original.result

    def test_roundtrip_error(self):
        original = Response.error_response(ERR_COMMAND_FAILED, "timeout", id="err")
        restored = Response.from_json(original.to_json())
        assert restored.id == original.id
        assert restored.error == original.error


class TestClientIdentity:
    """Tests for ClientIdentity dataclass."""

    def test_to_dict(self):
        identity = ClientIdentity(
            uuid="abc-123",
            display_name="Test Client",
            purpose="Testing",
            tags=["test", "dev"],
            capabilities=["python3.10"],
            public_key_fingerprint="SHA256:xyz",
            first_seen="2024-01-01T00:00:00Z",
        )
        result = identity.to_dict()
        assert result["uuid"] == "abc-123"
        assert result["display_name"] == "Test Client"
        assert result["tags"] == ["test", "dev"]
        assert result["key_mismatch"] is False

    def test_from_dict(self):
        data = {
            "uuid": "def-456",
            "display_name": "Another Client",
            "purpose": "Production",
            "tags": ["prod"],
            "capabilities": ["docker"],
            "public_key_fingerprint": "SHA256:abc",
            "first_seen": "2024-01-02T00:00:00Z",
        }
        identity = ClientIdentity.from_dict(data)
        assert identity.uuid == "def-456"
        assert identity.display_name == "Another Client"
        assert identity.created_by == "auto"  # Default
        assert identity.key_mismatch is False  # Default

    def test_from_dict_with_optionals(self):
        data = {
            "uuid": "ghi-789",
            "display_name": "Full Client",
            "purpose": "CI",
            "tags": [],
            "capabilities": [],
            "public_key_fingerprint": "SHA256:full",
            "first_seen": "2024-01-03T00:00:00Z",
            "created_by": "manual",
            "key_mismatch": True,
            "previous_fingerprint": "SHA256:old",
        }
        identity = ClientIdentity.from_dict(data)
        assert identity.created_by == "manual"
        assert identity.key_mismatch is True
        assert identity.previous_fingerprint == "SHA256:old"


class TestClientInfo:
    """Tests for ClientInfo dataclass."""

    def test_to_dict(self):
        info = ClientInfo(
            client_id="test-123",
            hostname="testhost",
            platform="Linux 5.10",
            username="testuser",
            tunnel_port=12345,
            connected_at="2024-01-01T00:00:00Z",
            last_heartbeat="2024-01-01T00:01:00Z",
        )
        result = info.to_dict()
        assert result["client_id"] == "test-123"
        assert result["hostname"] == "testhost"
        assert result["tunnel_port"] == 12345

    def test_from_dict(self):
        data = {
            "client_id": "prod-456",
            "hostname": "prodhost",
            "platform": "Windows 10",
            "username": "admin",
            "tunnel_port": 54321,
            "connected_at": "2024-01-02T00:00:00Z",
            "last_heartbeat": "2024-01-02T00:01:00Z",
        }
        info = ClientInfo.from_dict(data)
        assert info.client_id == "prod-456"
        assert info.platform == "Windows 10"
        assert info.identity_uuid is None  # Default

    def test_from_dict_with_identity_uuid(self):
        data = {
            "client_id": "linked-789",
            "hostname": "linkedhost",
            "platform": "macOS",
            "username": "user",
            "tunnel_port": 11111,
            "connected_at": "2024-01-03T00:00:00Z",
            "last_heartbeat": "2024-01-03T00:01:00Z",
            "identity_uuid": "uuid-abc",
        }
        info = ClientInfo.from_dict(data)
        assert info.identity_uuid == "uuid-abc"

    def test_create_local(self):
        info = ClientInfo.create_local("my-client", 9999, "my-uuid")
        assert info.client_id == "my-client"
        assert info.tunnel_port == 9999
        assert info.identity_uuid == "my-uuid"
        assert info.hostname  # Should be set to local hostname
        assert info.platform  # Should be set to local platform
        assert info.username  # Should be set to local username
        assert info.connected_at  # Should be set
        assert info.last_heartbeat  # Should be set


class TestMessageEncoding:
    """Tests for length-prefixed message encoding/decoding."""

    def test_encode_simple(self):
        msg = "hello"
        encoded = encode_message(msg)
        # 4 bytes length + 5 bytes "hello"
        assert len(encoded) == 9
        assert encoded[:4] == b"\x00\x00\x00\x05"
        assert encoded[4:] == b"hello"

    def test_encode_unicode(self):
        msg = "こんにちは"
        encoded = encode_message(msg)
        # UTF-8 encoded Japanese is 15 bytes
        assert encoded[:4] == b"\x00\x00\x00\x0f"

    def test_decode_simple(self):
        data = b"\x00\x00\x00\x05hello"
        msg, remaining = decode_message(data)
        assert msg == "hello"
        assert remaining == b""

    def test_decode_with_remaining(self):
        data = b"\x00\x00\x00\x05helloextra"
        msg, remaining = decode_message(data)
        assert msg == "hello"
        assert remaining == b"extra"

    def test_decode_incomplete_header(self):
        data = b"\x00\x00"
        with pytest.raises(ValueError, match="Incomplete message header"):
            decode_message(data)

    def test_decode_incomplete_body(self):
        data = b"\x00\x00\x00\x10short"  # Claims 16 bytes but only has 5
        with pytest.raises(ValueError, match="Incomplete message body"):
            decode_message(data)

    def test_roundtrip(self):
        original = '{"method": "test", "params": {"key": "value"}, "id": "123"}'
        encoded = encode_message(original)
        decoded, remaining = decode_message(encoded)
        assert decoded == original
        assert remaining == b""

    def test_multiple_messages(self):
        msg1 = encode_message("first")
        msg2 = encode_message("second")
        combined = msg1 + msg2

        decoded1, remaining = decode_message(combined)
        assert decoded1 == "first"

        decoded2, remaining = decode_message(remaining)
        assert decoded2 == "second"
        assert remaining == b""


class TestErrorCodes:
    """Tests to verify error code constants."""

    def test_error_codes_are_negative(self):
        assert ERR_INVALID_PARAMS < 0
        assert ERR_METHOD_NOT_FOUND < 0
        assert ERR_PATH_DENIED < 0
        assert ERR_COMMAND_FAILED < 0

    def test_json_rpc_standard_codes(self):
        # JSON-RPC 2.0 standard error codes are in -32600 to -32700 range
        assert ERR_INVALID_PARAMS == -32602
        assert ERR_METHOD_NOT_FOUND == -32601
