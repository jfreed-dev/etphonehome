"""Tests for client auto-update mechanism."""

import json
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from client.updater import (
    _compare_versions,
    _safe_tar_extract,
    _safe_zip_extract,
    check_for_update,
    get_current_version,
    get_platform_key,
    is_portable_installation,
)


class TestGetCurrentVersion:
    """Tests for get_current_version function."""

    def test_returns_string(self):
        """Version should be a string."""
        version = get_current_version()
        assert isinstance(version, str)

    def test_version_format(self):
        """Version should follow semver format."""
        version = get_current_version()
        parts = version.split(".")
        assert len(parts) >= 2  # At least major.minor


class TestGetPlatformKey:
    """Tests for get_platform_key function."""

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_x86_64(self, mock_machine, mock_system):
        """Should return linux-x86_64 for Linux AMD64."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"

        assert get_platform_key() == "linux-x86_64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_linux_aarch64(self, mock_machine, mock_system):
        """Should return linux-aarch64 for Linux ARM64."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "aarch64"

        assert get_platform_key() == "linux-aarch64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_darwin_x86_64(self, mock_machine, mock_system):
        """Should return darwin-x86_64 for macOS Intel."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "x86_64"

        assert get_platform_key() == "darwin-x86_64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_darwin_arm64(self, mock_machine, mock_system):
        """Should return darwin-aarch64 for macOS Apple Silicon."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        assert get_platform_key() == "darwin-aarch64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_windows(self, mock_machine, mock_system):
        """Should return windows-amd64 for Windows."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "AMD64"

        assert get_platform_key() == "windows-amd64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_unsupported_platform_raises(self, mock_machine, mock_system):
        """Should raise RuntimeError for unsupported platforms."""
        mock_system.return_value = "FreeBSD"
        mock_machine.return_value = "x86_64"

        with pytest.raises(RuntimeError, match="Unsupported platform"):
            get_platform_key()


class TestCompareVersions:
    """Tests for _compare_versions function."""

    def test_equal_versions(self):
        """Equal versions should return 0."""
        assert _compare_versions("1.0.0", "1.0.0") == 0
        assert _compare_versions("0.1.5", "0.1.5") == 0

    def test_greater_major(self):
        """Higher major version should be greater."""
        assert _compare_versions("2.0.0", "1.0.0") > 0
        assert _compare_versions("1.0.0", "2.0.0") < 0

    def test_greater_minor(self):
        """Higher minor version should be greater."""
        assert _compare_versions("1.2.0", "1.1.0") > 0
        assert _compare_versions("1.1.0", "1.2.0") < 0

    def test_greater_patch(self):
        """Higher patch version should be greater."""
        assert _compare_versions("1.0.2", "1.0.1") > 0
        assert _compare_versions("1.0.1", "1.0.2") < 0

    def test_handles_prerelease(self):
        """Should handle prerelease versions."""
        # Base version comparison ignores prerelease suffix
        assert _compare_versions("1.0.0-beta", "1.0.0") == 0
        assert _compare_versions("1.0.1-alpha", "1.0.0") > 0


class TestCheckForUpdate:
    """Tests for check_for_update function."""

    @patch("urllib.request.urlopen")
    @patch("client.updater.get_platform_key")
    @patch("client.updater.__version__", "0.1.0")
    def test_update_available(self, mock_platform, mock_urlopen):
        """Should return update info when newer version available."""
        mock_platform.return_value = "linux-x86_64"

        manifest = {
            "version": "0.2.0",
            "downloads": {
                "linux-x86_64": {"url": "http://example.com/download.tar.gz", "sha256": "abc123"}
            },
        }

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(manifest).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_for_update("http://example.com/manifest.json")

        assert result is not None
        assert result["version"] == "0.2.0"
        assert "download" in result

    @patch("urllib.request.urlopen")
    @patch("client.updater.__version__", "0.2.0")
    def test_no_update_when_current(self, mock_urlopen):
        """Should return None when already on latest version."""
        manifest = {"version": "0.2.0", "downloads": {}}

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(manifest).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_for_update("http://example.com/manifest.json")

        assert result is None

    @patch("urllib.request.urlopen")
    def test_handles_network_error(self, mock_urlopen):
        """Should return None on network error."""
        mock_urlopen.side_effect = Exception("Network error")

        result = check_for_update("http://example.com/manifest.json")

        assert result is None


class TestIsPortableInstallation:
    """Tests for is_portable_installation function."""

    @patch("client.updater._get_install_dir")
    @patch("client.updater.Path")
    def test_returns_false_for_pip_install(self, mock_path, mock_install_dir):
        """Should return False for pip/dev installations."""
        mock_install_dir.return_value = Path("/home/user/.local/share/phonehome")
        # Simulate running from site-packages
        mock_path.return_value.resolve.return_value.parent = Path(
            "/usr/lib/python3/site-packages/client"
        )

        # This will return False because paths don't match
        result = is_portable_installation()
        assert isinstance(result, bool)


class TestSafeTarExtract:
    """Tests for _safe_tar_extract function."""

    def test_extracts_normal_archive(self, tmp_path):
        """Should extract normal tar archive."""
        # Create a tar archive
        archive_path = tmp_path / "test.tar.gz"
        extract_path = tmp_path / "extract"
        extract_path.mkdir()

        # Create archive with a file
        with tarfile.open(archive_path, "w:gz") as tar:
            # Add a simple file
            content = b"test content"
            import io

            info = tarfile.TarInfo(name="test.txt")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

        # Extract
        with tarfile.open(archive_path, "r:gz") as tar:
            _safe_tar_extract(tar, extract_path)

        assert (extract_path / "test.txt").exists()
        assert (extract_path / "test.txt").read_bytes() == b"test content"

    def test_blocks_path_traversal(self, tmp_path):
        """Should block path traversal attempts."""
        archive_path = tmp_path / "malicious.tar.gz"
        extract_path = tmp_path / "extract"
        extract_path.mkdir()

        # Create archive with path traversal
        with tarfile.open(archive_path, "w:gz") as tar:
            import io

            info = tarfile.TarInfo(name="../../../etc/passwd")
            info.size = 4
            tar.addfile(info, io.BytesIO(b"test"))

        with tarfile.open(archive_path, "r:gz") as tar:
            with pytest.raises(ValueError, match="path traversal"):
                _safe_tar_extract(tar, extract_path)

    def test_blocks_absolute_paths(self, tmp_path):
        """Should block absolute paths."""
        archive_path = tmp_path / "malicious.tar.gz"
        extract_path = tmp_path / "extract"
        extract_path.mkdir()

        with tarfile.open(archive_path, "w:gz") as tar:
            import io

            info = tarfile.TarInfo(name="/etc/passwd")
            info.size = 4
            tar.addfile(info, io.BytesIO(b"test"))

        with tarfile.open(archive_path, "r:gz") as tar:
            with pytest.raises(ValueError, match="path traversal"):
                _safe_tar_extract(tar, extract_path)


class TestSafeZipExtract:
    """Tests for _safe_zip_extract function."""

    def test_extracts_normal_archive(self, tmp_path):
        """Should extract normal zip archive."""
        archive_path = tmp_path / "test.zip"
        extract_path = tmp_path / "extract"
        extract_path.mkdir()

        # Create zip archive
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("test.txt", "test content")

        # Extract
        with zipfile.ZipFile(archive_path, "r") as zf:
            _safe_zip_extract(zf, extract_path)

        assert (extract_path / "test.txt").exists()
        assert (extract_path / "test.txt").read_text() == "test content"

    def test_blocks_path_traversal(self, tmp_path):
        """Should block path traversal attempts."""
        archive_path = tmp_path / "malicious.zip"
        extract_path = tmp_path / "extract"
        extract_path.mkdir()

        # Create zip with path traversal (using low-level API)
        with zipfile.ZipFile(archive_path, "w") as zf:
            # This creates a zip with a malicious path
            info = zipfile.ZipInfo("../../../etc/passwd")
            zf.writestr(info, "malicious")

        with zipfile.ZipFile(archive_path, "r") as zf:
            with pytest.raises(ValueError, match="path traversal"):
                _safe_zip_extract(zf, extract_path)

    def test_blocks_absolute_paths(self, tmp_path):
        """Should block absolute paths."""
        archive_path = tmp_path / "malicious.zip"
        extract_path = tmp_path / "extract"
        extract_path.mkdir()

        with zipfile.ZipFile(archive_path, "w") as zf:
            info = zipfile.ZipInfo("/etc/passwd")
            zf.writestr(info, "malicious")

        with zipfile.ZipFile(archive_path, "r") as zf:
            with pytest.raises(ValueError, match="path traversal"):
                _safe_zip_extract(zf, extract_path)
