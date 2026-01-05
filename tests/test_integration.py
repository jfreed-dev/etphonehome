"""Integration tests for ET Phone Home components."""

import json
from datetime import datetime, timezone

import pytest

from client.agent import Agent
from client.config import Config
from client.metrics import collect_metrics
from server.client_registry import ClientRegistry
from server.client_store import ClientStore
from shared.protocol import (
    ClientIdentity,
    ClientInfo,
    Request,
    Response,
    decode_message,
    encode_message,
)


class TestAgentProtocolIntegration:
    """Integration tests for Agent with protocol messages."""

    def test_full_request_response_cycle(self):
        """Should handle complete request/response cycle."""
        agent = Agent()

        # Create request
        request = Request(method="heartbeat", params={}, id="test-123")

        # Handle request
        response = agent.handle_request(request)

        # Verify response
        assert response.id == "test-123"
        assert response.error is None
        assert response.result["status"] == "alive"

    def test_request_serialization_roundtrip(self):
        """Request should survive JSON serialization."""
        original = Request(method="run_command", params={"cmd": "ls -la"}, id="req-1")

        # Serialize and deserialize
        json_str = original.to_json()
        restored = Request.from_json(json_str)

        assert restored.method == original.method
        assert restored.params == original.params
        assert restored.id == original.id

    def test_response_serialization_roundtrip(self):
        """Response should survive JSON serialization."""
        original = Response.success(
            {"stdout": "output", "returncode": 0},
            id="resp-1",
        )

        # Serialize and deserialize
        json_str = original.to_json()
        restored = Response.from_json(json_str)

        assert restored.id == original.id
        assert restored.result == original.result
        assert restored.error is None

    def test_message_encoding_roundtrip(self):
        """Messages should survive encoding/decoding."""
        original = '{"method": "test", "params": {"key": "value"}, "id": "1"}'

        # Encode
        encoded = encode_message(original)

        # Decode
        decoded, remaining = decode_message(encoded)

        assert decoded == original
        assert remaining == b""


class TestAgentFileOperations:
    """Integration tests for Agent file operations."""

    def test_write_then_read_file(self, tmp_path):
        """Should be able to write and then read a file."""
        agent = Agent(allowed_paths=[str(tmp_path)])

        test_file = tmp_path / "test.txt"
        content = "Hello, World!"

        # Write
        write_req = Request(
            method="write_file",
            params={"path": str(test_file), "content": content},
            id="1",
        )
        write_resp = agent.handle_request(write_req)
        assert write_resp.error is None

        # Read
        read_req = Request(method="read_file", params={"path": str(test_file)}, id="2")
        read_resp = agent.handle_request(read_req)

        assert read_resp.error is None
        assert read_resp.result["content"] == content

    def test_list_after_create(self, tmp_path):
        """Should list files after creating them."""
        agent = Agent(allowed_paths=[str(tmp_path)])

        # Create files
        for name in ["a.txt", "b.txt", "c.txt"]:
            req = Request(
                method="write_file",
                params={"path": str(tmp_path / name), "content": name},
                id=name,
            )
            agent.handle_request(req)

        # List
        list_req = Request(method="list_files", params={"path": str(tmp_path)}, id="list")
        list_resp = agent.handle_request(list_req)

        assert list_resp.error is None
        names = [e["name"] for e in list_resp.result["entries"]]
        assert "a.txt" in names
        assert "b.txt" in names
        assert "c.txt" in names


class TestRegistryStoreIntegration:
    """Integration tests for ClientRegistry with ClientStore."""

    @pytest.mark.asyncio
    async def test_register_persists_to_store(self, tmp_path):
        """Registering client should persist to store."""
        store = ClientStore(tmp_path / "clients.json")
        registry = ClientRegistry(store)

        # Create registration data
        identity = ClientIdentity(
            uuid="test-uuid-123",
            display_name="Test Client",
            purpose="Testing",
            tags=["test"],
            capabilities=["python3.12"],
            public_key_fingerprint="SHA256:test",
            first_seen=datetime.now(timezone.utc).isoformat(),
        )

        client_info = ClientInfo.create_local("client-1", 12345, identity.uuid)

        registration = {"identity": identity.to_dict(), "client_info": client_info.to_dict()}

        # Register
        await registry.register(registration)

        # Verify in store
        stored = store.get_by_uuid("test-uuid-123")
        assert stored is not None
        assert stored.identity.display_name == "Test Client"

    @pytest.mark.asyncio
    async def test_find_clients_searches_store(self, tmp_path):
        """Finding clients should search the store."""
        store = ClientStore(tmp_path / "clients.json")
        registry = ClientRegistry(store)

        # Add clients directly to store
        for i, purpose in enumerate(["Development", "Production", "Testing"]):
            identity = ClientIdentity(
                uuid=f"uuid-{i}",
                display_name=f"Client {i}",
                purpose=purpose,
                tags=[],
                capabilities=[],
                public_key_fingerprint=f"SHA256:key{i}",
                first_seen=datetime.now(timezone.utc).isoformat(),
            )
            store.upsert(identity)

        # Find by purpose
        results = await registry.find_clients(purpose="Development")

        assert len(results) == 1
        assert results[0]["purpose"] == "Development"


class TestConfigIntegration:
    """Integration tests for Config module."""

    def test_config_save_and_load(self, tmp_path):
        """Config should save and load correctly."""
        config_file = tmp_path / "config.yaml"

        # Create and save
        config = Config()
        config.server_host = "test.example.com"
        config.server_port = 2222
        config.display_name = "Test Machine"
        config.purpose = "Testing"
        config.tags = ["test", "dev"]
        config.save(config_file)

        # Load
        loaded = Config.load(config_file)

        assert loaded.server_host == "test.example.com"
        assert loaded.server_port == 2222
        assert loaded.display_name == "Test Machine"
        assert loaded.tags == ["test", "dev"]

    def test_config_with_logging_settings(self, tmp_path):
        """Config should handle logging settings."""
        config_file = tmp_path / "config.yaml"

        config = Config()
        config.log_level = "DEBUG"
        config.log_max_bytes = 5 * 1024 * 1024
        config.log_backup_count = 3
        config.save(config_file)

        loaded = Config.load(config_file)

        assert loaded.log_level == "DEBUG"
        assert loaded.log_max_bytes == 5 * 1024 * 1024
        assert loaded.log_backup_count == 3


class TestMetricsIntegration:
    """Integration tests for metrics collection."""

    def test_metrics_via_agent(self):
        """Should collect metrics through agent interface."""
        agent = Agent()

        # Request full metrics
        req = Request(method="get_metrics", params={}, id="1")
        resp = agent.handle_request(req)

        assert resp.error is None
        result = resp.result

        # Verify structure
        assert "timestamp" in result
        assert "cpu" in result
        assert "memory" in result
        assert "uptime_seconds" in result

    def test_metrics_summary_via_agent(self):
        """Should collect metrics summary through agent interface."""
        agent = Agent()

        # Request summary
        req = Request(method="get_metrics", params={"summary": True}, id="1")
        resp = agent.handle_request(req)

        assert resp.error is None
        result = resp.result

        # Summary has different structure
        assert "cpu_percent" in result
        assert "memory_percent" in result
        assert "cpu" not in result  # Full metrics key should not be present

    def test_metrics_json_serializable(self):
        """Collected metrics should be JSON serializable."""
        metrics = collect_metrics()
        metrics_dict = metrics.to_dict()

        # Should not raise
        json_str = json.dumps(metrics_dict)
        parsed = json.loads(json_str)

        assert parsed["hostname"] == metrics.hostname


class TestProtocolMessageFlow:
    """Integration tests for protocol message flow."""

    def test_multiple_messages_in_buffer(self):
        """Should handle multiple messages in a buffer."""
        msg1 = '{"method": "heartbeat", "params": {}, "id": "1"}'
        msg2 = '{"method": "heartbeat", "params": {}, "id": "2"}'

        # Encode both messages
        buffer = encode_message(msg1) + encode_message(msg2)

        # Decode first
        decoded1, remaining = decode_message(buffer)
        assert decoded1 == msg1
        assert len(remaining) > 0

        # Decode second
        decoded2, remaining = decode_message(remaining)
        assert decoded2 == msg2
        assert remaining == b""

    def test_partial_message_handling(self):
        """Should raise on incomplete messages."""
        msg = '{"method": "test"}'
        encoded = encode_message(msg)

        # Try to decode partial header
        with pytest.raises(ValueError, match="Incomplete message header"):
            decode_message(encoded[:2])

        # Try to decode partial body
        with pytest.raises(ValueError, match="Incomplete message body"):
            decode_message(encoded[:6])


class TestClientInfoCreation:
    """Integration tests for ClientInfo creation."""

    def test_create_local_with_identity(self):
        """Should create ClientInfo with identity UUID."""
        identity_uuid = "test-identity-uuid"
        info = ClientInfo.create_local("client-1", 12345, identity_uuid)

        assert info.client_id == "client-1"
        assert info.tunnel_port == 12345
        assert info.identity_uuid == identity_uuid
        assert info.hostname  # Should be set
        assert info.platform  # Should be set
        assert info.username  # Should be set

    def test_client_info_roundtrip(self):
        """ClientInfo should survive to_dict/from_dict cycle."""
        original = ClientInfo.create_local("client-1", 12345, "uuid-123")

        # Convert to dict and back
        data = original.to_dict()
        restored = ClientInfo.from_dict(data)

        assert restored.client_id == original.client_id
        assert restored.tunnel_port == original.tunnel_port
        assert restored.identity_uuid == original.identity_uuid
        assert restored.hostname == original.hostname


class TestEndToEndAgentWorkflow:
    """End-to-end tests simulating real agent workflows."""

    def test_typical_session_workflow(self, tmp_path):
        """Simulate a typical agent session."""
        agent = Agent(allowed_paths=[str(tmp_path)])

        # 1. Heartbeat to verify connection
        heartbeat = agent.handle_request(Request(method="heartbeat", params={}, id="1"))
        assert heartbeat.result["status"] == "alive"

        # 2. Get system metrics
        metrics = agent.handle_request(
            Request(method="get_metrics", params={"summary": True}, id="2")
        )
        assert metrics.error is None
        assert "cpu_percent" in metrics.result

        # 3. Create a working directory
        work_dir = tmp_path / "workspace"
        run_mkdir = agent.handle_request(
            Request(
                method="run_command",
                params={"cmd": f"mkdir -p {work_dir}"},
                id="3",
            )
        )
        assert run_mkdir.result["returncode"] == 0

        # 4. Write a file
        test_file = work_dir / "script.py"
        write_resp = agent.handle_request(
            Request(
                method="write_file",
                params={"path": str(test_file), "content": "print('hello')"},
                id="4",
            )
        )
        assert write_resp.error is None

        # 5. Run the script
        run_script = agent.handle_request(
            Request(
                method="run_command",
                params={"cmd": f"python3 {test_file}"},
                id="5",
            )
        )
        assert run_script.result["returncode"] == 0
        assert "hello" in run_script.result["stdout"]

        # 6. List files
        list_resp = agent.handle_request(
            Request(method="list_files", params={"path": str(work_dir)}, id="6")
        )
        assert any(e["name"] == "script.py" for e in list_resp.result["entries"])

        # 7. Read the file back
        read_resp = agent.handle_request(
            Request(method="read_file", params={"path": str(test_file)}, id="7")
        )
        assert read_resp.result["content"] == "print('hello')"
