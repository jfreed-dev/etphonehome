"""Tests for client capabilities detection."""

import base64
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from client.capabilities import detect_capabilities, get_ssh_key_fingerprint


class TestDetectCapabilities:
    """Tests for detect_capabilities function."""

    def test_returns_list(self):
        """Capabilities should return a list."""
        caps = detect_capabilities()
        assert isinstance(caps, list)

    def test_includes_python_version(self):
        """Should include current Python version."""
        caps = detect_capabilities()
        expected = f"python{sys.version_info.major}.{sys.version_info.minor}"
        assert expected in caps

    def test_list_is_sorted(self):
        """Capabilities list should be sorted."""
        caps = detect_capabilities()
        assert caps == sorted(caps)

    def test_no_duplicates(self):
        """Capabilities list should have no duplicates."""
        caps = detect_capabilities()
        assert len(caps) == len(set(caps))

    @patch("shutil.which")
    def test_detects_docker(self, mock_which):
        """Should detect Docker when available."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        caps = detect_capabilities()
        assert "docker" in caps

    @patch("shutil.which")
    def test_detects_git(self, mock_which):
        """Should detect Git when available."""
        mock_which.side_effect = lambda cmd: "/usr/bin/git" if cmd == "git" else None
        caps = detect_capabilities()
        assert "git" in caps

    @patch("shutil.which")
    def test_detects_nvidia_gpu_via_path(self, mock_which):
        """Should detect NVIDIA GPU via /usr/bin/nvidia-smi path."""
        mock_which.return_value = None

        # Mock the Path class to make specific paths exist
        original_exists = Path.exists

        def mock_exists(path_self):
            if str(path_self) == "/usr/bin/nvidia-smi":
                return True
            return original_exists(path_self)

        with patch.object(Path, "exists", mock_exists):
            caps = detect_capabilities()
        assert "nvidia-gpu" in caps

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    def test_detects_nvidia_gpu_via_which(self, mock_exists, mock_which):
        """Should detect NVIDIA GPU via which command."""
        mock_exists.return_value = False
        mock_which.side_effect = lambda cmd: "/usr/bin/nvidia-smi" if cmd == "nvidia-smi" else None
        caps = detect_capabilities()
        assert "nvidia-gpu" in caps

    @patch("shutil.which")
    def test_detects_amd_gpu(self, mock_which):
        """Should detect AMD GPU via /opt/rocm path."""
        mock_which.return_value = None

        # Mock the Path class to make specific paths exist
        original_exists = Path.exists

        def mock_exists(path_self):
            if str(path_self) == "/opt/rocm":
                return True
            return original_exists(path_self)

        with patch.object(Path, "exists", mock_exists):
            caps = detect_capabilities()
        assert "amd-gpu" in caps

    @patch("shutil.which")
    def test_detects_apt_package_manager(self, mock_which):
        """Should detect apt package manager."""
        mock_which.side_effect = lambda cmd: "/usr/bin/apt" if cmd == "apt" else None
        caps = detect_capabilities()
        assert "apt" in caps

    @patch("shutil.which")
    def test_detects_homebrew(self, mock_which):
        """Should detect Homebrew."""
        mock_which.side_effect = lambda cmd: "/opt/homebrew/bin/brew" if cmd == "brew" else None
        caps = detect_capabilities()
        assert "homebrew" in caps

    @patch("shutil.which")
    def test_detects_node(self, mock_which):
        """Should detect Node.js."""
        mock_which.side_effect = lambda cmd: "/usr/bin/node" if cmd == "node" else None
        caps = detect_capabilities()
        assert "node" in caps

    @patch("shutil.which")
    def test_detects_rust(self, mock_which):
        """Should detect Rust via cargo."""
        mock_which.side_effect = lambda cmd: "/usr/bin/cargo" if cmd == "cargo" else None
        caps = detect_capabilities()
        assert "rust" in caps

    @patch("shutil.which")
    def test_detects_c_compiler_gcc(self, mock_which):
        """Should detect C compiler via gcc."""
        mock_which.side_effect = lambda cmd: "/usr/bin/gcc" if cmd == "gcc" else None
        caps = detect_capabilities()
        assert "c-compiler" in caps

    @patch("shutil.which")
    def test_detects_c_compiler_clang(self, mock_which):
        """Should detect C compiler via clang."""
        mock_which.side_effect = lambda cmd: "/usr/bin/clang" if cmd == "clang" else None
        caps = detect_capabilities()
        assert "c-compiler" in caps

    @patch("shutil.which")
    def test_detects_kubernetes_tools(self, mock_which):
        """Should detect kubectl and helm."""

        def which_mock(cmd):
            if cmd == "kubectl":
                return "/usr/bin/kubectl"
            if cmd == "helm":
                return "/usr/bin/helm"
            return None

        mock_which.side_effect = which_mock
        caps = detect_capabilities()
        assert "kubectl" in caps
        assert "helm" in caps

    @patch("shutil.which")
    def test_detects_cloud_clis(self, mock_which):
        """Should detect cloud provider CLIs."""

        def which_mock(cmd):
            if cmd == "aws":
                return "/usr/bin/aws"
            if cmd == "gcloud":
                return "/usr/bin/gcloud"
            if cmd == "az":
                return "/usr/bin/az"
            return None

        mock_which.side_effect = which_mock
        caps = detect_capabilities()
        assert "aws-cli" in caps
        assert "gcloud" in caps
        assert "azure-cli" in caps

    @patch("shutil.which")
    def test_detects_systemd(self, mock_which):
        """Should detect systemd."""
        mock_which.side_effect = lambda cmd: "/usr/bin/systemctl" if cmd == "systemctl" else None
        caps = detect_capabilities()
        assert "systemd" in caps


class TestGetSshKeyFingerprint:
    """Tests for get_ssh_key_fingerprint function."""

    def test_valid_key(self, tmp_path):
        """Should compute fingerprint for valid SSH key."""
        # Create a mock SSH public key
        key_type = "ssh-ed25519"
        # This is a valid base64-encoded key blob
        key_data = base64.b64encode(b"fake-key-data-for-testing").decode()
        pub_key_content = f"{key_type} {key_data} test@example.com\n"

        key_path = tmp_path / "id_ed25519"
        pub_path = tmp_path / "id_ed25519.pub"
        pub_path.write_text(pub_key_content)

        fingerprint = get_ssh_key_fingerprint(key_path)

        assert fingerprint.startswith("SHA256:")
        assert len(fingerprint) > 10

    def test_fingerprint_is_consistent(self, tmp_path):
        """Same key should produce same fingerprint."""
        key_data = base64.b64encode(b"consistent-key-data").decode()
        pub_key_content = f"ssh-ed25519 {key_data} test@example.com\n"

        key_path = tmp_path / "id_ed25519"
        pub_path = tmp_path / "id_ed25519.pub"
        pub_path.write_text(pub_key_content)

        fp1 = get_ssh_key_fingerprint(key_path)
        fp2 = get_ssh_key_fingerprint(key_path)

        assert fp1 == fp2

    def test_different_keys_different_fingerprints(self, tmp_path):
        """Different keys should produce different fingerprints."""
        key1_data = base64.b64encode(b"key-data-one").decode()
        key2_data = base64.b64encode(b"key-data-two").decode()

        key1_path = tmp_path / "key1"
        key2_path = tmp_path / "key2"

        (tmp_path / "key1.pub").write_text(f"ssh-ed25519 {key1_data} test\n")
        (tmp_path / "key2.pub").write_text(f"ssh-ed25519 {key2_data} test\n")

        fp1 = get_ssh_key_fingerprint(key1_path)
        fp2 = get_ssh_key_fingerprint(key2_path)

        assert fp1 != fp2

    def test_missing_public_key_raises(self, tmp_path):
        """Should raise FileNotFoundError for missing public key."""
        key_path = tmp_path / "nonexistent"

        with pytest.raises(FileNotFoundError):
            get_ssh_key_fingerprint(key_path)

    def test_invalid_key_format_raises(self, tmp_path):
        """Should raise ValueError for invalid key format."""
        key_path = tmp_path / "invalid"
        pub_path = tmp_path / "invalid.pub"
        pub_path.write_text("not-a-valid-key\n")

        with pytest.raises(ValueError, match="Invalid public key format"):
            get_ssh_key_fingerprint(key_path)

    def test_key_with_full_path_pub_suffix(self, tmp_path):
        """Should handle keys where .pub is appended to full path."""
        key_data = base64.b64encode(b"test-key-data").decode()

        # Key path that doesn't have a suffix
        key_path = tmp_path / "mykey"
        pub_path = tmp_path / "mykey.pub"
        pub_path.write_text(f"ssh-ed25519 {key_data} comment\n")

        fingerprint = get_ssh_key_fingerprint(key_path)
        assert fingerprint.startswith("SHA256:")
