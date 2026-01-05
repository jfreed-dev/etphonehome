"""Tests for client/config.py - YAML configuration management."""

import yaml

from client.config import Config, ensure_config_dir, generate_client_id


class TestConfig:
    """Tests for Config dataclass."""

    def test_default_values(self):
        config = Config()
        assert config.server_host == "localhost"
        assert config.server_port == 443
        assert config.server_user == "etphonehome"
        assert config.uuid is None
        assert config.display_name is None
        assert config.purpose == ""
        assert config.tags == []
        assert config.reconnect_delay == 5
        assert config.max_reconnect_delay == 300
        assert config.allowed_paths == []
        assert config.log_level == "INFO"

    def test_custom_values(self):
        config = Config(
            server_host="example.com",
            server_port=2222,
            server_user="admin",
            uuid="test-uuid",
            display_name="My Client",
            purpose="Development",
            tags=["dev", "test"],
            reconnect_delay=10,
            allowed_paths=["/home", "/tmp"],
            log_level="DEBUG",
        )
        assert config.server_host == "example.com"
        assert config.server_port == 2222
        assert config.uuid == "test-uuid"
        assert config.tags == ["dev", "test"]
        assert config.allowed_paths == ["/home", "/tmp"]


class TestConfigLoad:
    """Tests for Config.load()."""

    def test_load_nonexistent_file(self, tmp_path):
        config = Config.load(tmp_path / "nonexistent.yaml")
        # Should return default config
        assert config.server_host == "localhost"
        assert config.server_port == 443

    def test_load_empty_file(self, tmp_path):
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        config = Config.load(config_file)
        # Should return default config
        assert config.server_host == "localhost"

    def test_load_partial_config(self, tmp_path):
        config_file = tmp_path / "partial.yaml"
        config_file.write_text("server_host: myserver.com\nserver_port: 8080\n")
        config = Config.load(config_file)
        assert config.server_host == "myserver.com"
        assert config.server_port == 8080
        # Defaults should still apply
        assert config.server_user == "etphonehome"
        assert config.log_level == "INFO"

    def test_load_full_config(self, tmp_path):
        config_file = tmp_path / "full.yaml"
        data = {
            "server_host": "full.example.com",
            "server_port": 3333,
            "server_user": "fulluser",
            "key_file": "/path/to/key",
            "uuid": "full-uuid",
            "display_name": "Full Config Client",
            "purpose": "Testing",
            "tags": ["full", "config"],
            "client_id": "full-client",
            "agent_port": 5555,
            "reconnect_delay": 15,
            "max_reconnect_delay": 600,
            "allowed_paths": ["/home/user"],
            "log_level": "WARNING",
        }
        config_file.write_text(yaml.dump(data))
        config = Config.load(config_file)

        assert config.server_host == "full.example.com"
        assert config.server_port == 3333
        assert config.uuid == "full-uuid"
        assert config.display_name == "Full Config Client"
        assert config.tags == ["full", "config"]
        assert config.max_reconnect_delay == 600
        assert config.log_level == "WARNING"


class TestConfigSave:
    """Tests for Config.save()."""

    def test_save_creates_file(self, tmp_path):
        config = Config(server_host="saved.example.com")
        config_file = tmp_path / "saved.yaml"
        config.save(config_file)
        assert config_file.exists()

    def test_save_creates_parent_dirs(self, tmp_path):
        config = Config()
        config_file = tmp_path / "deep" / "nested" / "config.yaml"
        config.save(config_file)
        assert config_file.exists()

    def test_save_content(self, tmp_path):
        config = Config(
            server_host="content.example.com",
            server_port=4444,
            uuid="save-uuid",
            tags=["saved", "test"],
        )
        config_file = tmp_path / "content.yaml"
        config.save(config_file)

        # Read back the file
        with open(config_file) as f:
            data = yaml.safe_load(f)

        assert data["server_host"] == "content.example.com"
        assert data["server_port"] == 4444
        assert data["uuid"] == "save-uuid"
        assert data["tags"] == ["saved", "test"]

    def test_roundtrip(self, tmp_path):
        original = Config(
            server_host="roundtrip.example.com",
            server_port=5555,
            server_user="roundtrip",
            uuid="roundtrip-uuid",
            display_name="Roundtrip Test",
            purpose="Integration",
            tags=["round", "trip"],
            reconnect_delay=20,
            max_reconnect_delay=400,
            allowed_paths=["/var/log"],
            log_level="ERROR",
        )
        config_file = tmp_path / "roundtrip.yaml"
        original.save(config_file)
        restored = Config.load(config_file)

        assert restored.server_host == original.server_host
        assert restored.server_port == original.server_port
        assert restored.uuid == original.uuid
        assert restored.display_name == original.display_name
        assert restored.tags == original.tags
        assert restored.allowed_paths == original.allowed_paths
        assert restored.log_level == original.log_level


class TestEnsureConfigDir:
    """Tests for ensure_config_dir()."""

    def test_creates_directory(self, tmp_path, monkeypatch):
        # Patch the default config dir
        test_dir = tmp_path / ".etphonehome"
        monkeypatch.setattr("client.config.DEFAULT_CONFIG_DIR", test_dir)

        result = ensure_config_dir()
        assert result == test_dir
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_idempotent(self, tmp_path, monkeypatch):
        test_dir = tmp_path / ".etphonehome"
        monkeypatch.setattr("client.config.DEFAULT_CONFIG_DIR", test_dir)

        # Call twice
        ensure_config_dir()
        ensure_config_dir()

        # Should still exist
        assert test_dir.exists()


class TestGenerateClientId:
    """Tests for generate_client_id()."""

    def test_returns_string(self):
        client_id = generate_client_id()
        assert isinstance(client_id, str)

    def test_contains_hostname(self):
        import socket

        hostname = socket.gethostname()
        client_id = generate_client_id()
        assert hostname in client_id

    def test_unique_ids(self):
        id1 = generate_client_id()
        id2 = generate_client_id()
        assert id1 != id2

    def test_format(self):
        client_id = generate_client_id()
        # Should be hostname-uuid format
        parts = client_id.rsplit("-", 1)
        assert len(parts) == 2
        # UUID part should be 8 hex characters
        assert len(parts[1]) == 8
        assert all(c in "0123456789abcdef" for c in parts[1])
