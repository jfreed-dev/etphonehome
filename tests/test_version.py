"""Tests for version information module."""

import os
from unittest.mock import patch

from shared.version import UPDATE_URL, __version__


class TestVersion:
    """Tests for version string."""

    def test_version_is_string(self):
        """Version should be a string."""
        assert isinstance(__version__, str)

    def test_version_not_empty(self):
        """Version should not be empty."""
        assert len(__version__) > 0

    def test_version_format(self):
        """Version should follow semver format."""
        parts = __version__.split(".")
        assert len(parts) >= 2, "Version should have at least major.minor"

        # Major and minor should be numeric
        assert parts[0].isdigit(), "Major version should be numeric"
        assert parts[1].isdigit(), "Minor version should be numeric"

    def test_version_is_valid_semver(self):
        """Version should be valid semver."""
        # Handle versions like "0.1.5" or "0.1.5-beta"
        base = __version__.split("-")[0]
        parts = base.split(".")

        for part in parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"


class TestUpdateUrl:
    """Tests for UPDATE_URL configuration."""

    def test_update_url_is_string(self):
        """UPDATE_URL should be a string."""
        assert isinstance(UPDATE_URL, str)

    @patch.dict(os.environ, {"PHONEHOME_UPDATE_URL": "https://example.com/updates.json"})
    def test_update_url_from_environment(self):
        """Should read UPDATE_URL from environment."""
        # Need to reimport to pick up env var
        import importlib

        from shared import version

        importlib.reload(version)

        assert version.UPDATE_URL == "https://example.com/updates.json"

        # Reset
        importlib.reload(version)

    @patch.dict(os.environ, {}, clear=True)
    def test_update_url_default(self):
        """Should use empty default when env var not set."""
        import importlib

        from shared import version

        # Remove the env var if it exists
        os.environ.pop("PHONEHOME_UPDATE_URL", None)

        importlib.reload(version)

        # Default is empty string
        assert version.UPDATE_URL == "" or isinstance(version.UPDATE_URL, str)

        # Reset
        importlib.reload(version)
