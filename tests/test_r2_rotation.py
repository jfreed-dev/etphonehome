"""Tests for R2 key rotation functionality."""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from shared.r2_rotation import (
    CloudflareAPIClient,
    R2KeyRotationManager,
    RotationScheduler,
)


class TestCloudflareAPIClient:
    """Tests for CloudflareAPIClient."""

    def test_init(self):
        """Test client initialization."""
        client = CloudflareAPIClient(
            api_token="test_token",
            account_id="test_account",
        )
        assert client.api_token == "test_token"
        assert client.account_id == "test_account"
        assert "Bearer test_token" in client.headers["Authorization"]

    @patch("shared.r2_rotation.httpx.Client")
    def test_create_r2_token_success(self, mock_client_class):
        """Test successful R2 token creation."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "access_key_id": "new_access_key",
                "secret_access_key": "new_secret_key",  # pragma: allowlist secret
            },
        }
        mock_client.post.return_value = mock_response

        client = CloudflareAPIClient(
            api_token="test_token",
            account_id="test_account",
        )
        result = client.create_r2_token("test-token")

        assert result["access_key_id"] == "new_access_key"
        assert result["secret_access_key"] == "new_secret_key"  # pragma: allowlist secret

    @patch("shared.r2_rotation.httpx.Client")
    def test_create_r2_token_failure(self, mock_client_class):
        """Test R2 token creation failure."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "errors": [{"message": "Permission denied"}],
        }
        mock_client.post.return_value = mock_response

        client = CloudflareAPIClient(
            api_token="test_token",
            account_id="test_account",
        )

        with pytest.raises(RuntimeError, match="Permission denied"):
            client.create_r2_token("test-token")

    @patch("shared.r2_rotation.httpx.Client")
    def test_list_r2_tokens(self, mock_client_class):
        """Test listing R2 tokens."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "result": [
                {"access_key_id": "key1", "created_on": "2024-01-01T00:00:00Z"},
                {"access_key_id": "key2", "created_on": "2024-01-02T00:00:00Z"},
            ],
        }
        mock_client.get.return_value = mock_response

        client = CloudflareAPIClient(
            api_token="test_token",
            account_id="test_account",
        )
        result = client.list_r2_tokens()

        assert len(result) == 2
        assert result[0]["access_key_id"] == "key1"

    @patch("shared.r2_rotation.httpx.Client")
    def test_delete_r2_token(self, mock_client_class):
        """Test deleting R2 token."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_client.delete.return_value = mock_response

        client = CloudflareAPIClient(
            api_token="test_token",
            account_id="test_account",
        )
        # Should not raise
        client.delete_r2_token("key_to_delete")


class TestR2KeyRotationManager:
    """Tests for R2KeyRotationManager."""

    @patch.object(CloudflareAPIClient, "create_r2_token")
    @patch.object(CloudflareAPIClient, "delete_r2_token")
    def test_rotate_r2_keys(self, mock_delete, mock_create):
        """Test full key rotation flow."""
        mock_create.return_value = {
            "access_key_id": "new_key",
            "secret_access_key": "new_secret",  # pragma: allowlist secret
        }

        # Create mock GitHub manager
        mock_github = MagicMock()
        mock_r2_secrets = MagicMock()

        with patch("shared.r2_rotation.R2SecretsManager", return_value=mock_r2_secrets):
            manager = R2KeyRotationManager(
                cloudflare_api_token="cf_token",
                account_id="account_id",
                github_manager=mock_github,
            )

            result = manager.rotate_r2_keys(old_access_key_id="old_key")

        assert result["new_access_key_id"] == "new_key"
        assert result["old_access_key_id"] == "old_key"
        assert result["old_token_deleted"] is True

        # Verify GitHub secrets were updated
        mock_r2_secrets.update_r2_keys.assert_called_once_with("new_key", "new_secret")

        # Verify old token was deleted
        mock_delete.assert_called_once_with("old_key")

    @patch.object(CloudflareAPIClient, "create_r2_token")
    @patch.object(CloudflareAPIClient, "delete_r2_token")
    def test_rotate_r2_keys_keep_old(self, mock_delete, mock_create):
        """Test rotation without deleting old key."""
        mock_create.return_value = {
            "access_key_id": "new_key",
            "secret_access_key": "new_secret",  # pragma: allowlist secret
        }

        mock_github = MagicMock()
        mock_r2_secrets = MagicMock()

        with patch("shared.r2_rotation.R2SecretsManager", return_value=mock_r2_secrets):
            manager = R2KeyRotationManager(
                cloudflare_api_token="cf_token",
                account_id="account_id",
                github_manager=mock_github,
            )

            result = manager.rotate_r2_keys(old_access_key_id="old_key", delete_old=False)

        assert result["old_token_deleted"] is False
        mock_delete.assert_not_called()

    @patch.object(CloudflareAPIClient, "list_r2_tokens")
    @patch.object(CloudflareAPIClient, "delete_r2_token")
    def test_cleanup_old_tokens(self, mock_delete, mock_list):
        """Test cleaning up old tokens."""
        mock_list.return_value = [
            {"access_key_id": "key1", "created_on": "2024-01-03T00:00:00Z"},
            {"access_key_id": "key2", "created_on": "2024-01-02T00:00:00Z"},
            {"access_key_id": "key3", "created_on": "2024-01-01T00:00:00Z"},
        ]

        mock_github = MagicMock()

        with patch("shared.r2_rotation.R2SecretsManager"):
            manager = R2KeyRotationManager(
                cloudflare_api_token="cf_token",
                account_id="account_id",
                github_manager=mock_github,
            )

            deleted = manager.cleanup_old_tokens(keep_latest=2)

        assert deleted == 1
        mock_delete.assert_called_once_with("key3")


class TestRotationScheduler:
    """Tests for RotationScheduler."""

    def test_should_rotate_no_previous(self, tmp_path):
        """Test rotation is due when no previous rotation recorded."""
        mock_github = MagicMock()

        with patch("shared.r2_rotation.R2SecretsManager"):
            manager = R2KeyRotationManager(
                cloudflare_api_token="cf_token",
                account_id="account_id",
                github_manager=mock_github,
            )

            scheduler = RotationScheduler(manager, rotation_days=90)
            # Override the file path for testing
            scheduler.last_rotation_file = tmp_path / "last_rotation.txt"

            assert scheduler.should_rotate() is True

    def test_should_rotate_recent(self, tmp_path):
        """Test rotation is not due when recent rotation exists."""
        mock_github = MagicMock()

        with patch("shared.r2_rotation.R2SecretsManager"):
            manager = R2KeyRotationManager(
                cloudflare_api_token="cf_token",
                account_id="account_id",
                github_manager=mock_github,
            )

            scheduler = RotationScheduler(manager, rotation_days=90)
            scheduler.last_rotation_file = tmp_path / "last_rotation.txt"

            # Record a recent rotation
            now = datetime.now(timezone.utc)
            scheduler.last_rotation_file.write_text(now.isoformat())

            assert scheduler.should_rotate() is False

    def test_should_rotate_old(self, tmp_path):
        """Test rotation is due when last rotation is old."""
        mock_github = MagicMock()

        with patch("shared.r2_rotation.R2SecretsManager"):
            manager = R2KeyRotationManager(
                cloudflare_api_token="cf_token",
                account_id="account_id",
                github_manager=mock_github,
            )

            scheduler = RotationScheduler(manager, rotation_days=90)
            scheduler.last_rotation_file = tmp_path / "last_rotation.txt"

            # Record an old rotation (100 days ago)
            from datetime import timedelta

            old_date = datetime.now(timezone.utc) - timedelta(days=100)
            scheduler.last_rotation_file.write_text(old_date.isoformat())

            assert scheduler.should_rotate() is True


class TestR2KeyRotationManagerFromEnv:
    """Tests for R2KeyRotationManager.from_env()."""

    def test_from_env_missing_vars(self):
        """Test from_env returns None when variables are missing."""
        # Clear any existing env vars
        for var in [
            "ETPHONEHOME_CLOUDFLARE_API_TOKEN",
            "ETPHONEHOME_R2_ACCOUNT_ID",
            "ETPHONEHOME_GITHUB_REPO",
        ]:
            os.environ.pop(var, None)

        manager = R2KeyRotationManager.from_env()
        assert manager is None


# Integration tests (only run when credentials are available)
@pytest.mark.skipif(
    not all(
        [
            os.getenv("ETPHONEHOME_CLOUDFLARE_API_TOKEN"),
            os.getenv("ETPHONEHOME_R2_ACCOUNT_ID"),
        ]
    ),
    reason="Cloudflare credentials not available",
)
class TestR2RotationIntegration:
    """Integration tests that require real Cloudflare credentials."""

    def test_list_tokens(self):
        """Test listing R2 tokens with real credentials."""
        client = CloudflareAPIClient(
            api_token=os.environ["ETPHONEHOME_CLOUDFLARE_API_TOKEN"],
            account_id=os.environ["ETPHONEHOME_R2_ACCOUNT_ID"],
        )
        tokens = client.list_r2_tokens()
        assert isinstance(tokens, list)
        print(f"Found {len(tokens)} R2 tokens")
        for token in tokens:
            print(f"  - {token['access_key_id']} (created: {token.get('created_on')})")

    def test_create_and_delete_token(self):
        """Test creating and deleting an R2 token."""
        client = CloudflareAPIClient(
            api_token=os.environ["ETPHONEHOME_CLOUDFLARE_API_TOKEN"],
            account_id=os.environ["ETPHONEHOME_R2_ACCOUNT_ID"],
        )

        # Create a test token
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        token_name = f"etphonehome-test-{timestamp}"

        result = client.create_r2_token(token_name)
        assert "access_key_id" in result
        assert "secret_access_key" in result

        print(f"Created test token: {result['access_key_id']}")

        # Delete the test token
        client.delete_r2_token(result["access_key_id"])
        print(f"Deleted test token: {result['access_key_id']}")

    def test_verify_token_works(self):
        """Test verifying a token can access R2."""
        if not all(
            [
                os.getenv("ETPHONEHOME_R2_ACCESS_KEY"),
                os.getenv("ETPHONEHOME_R2_SECRET_KEY"),
            ]
        ):
            pytest.skip("R2 access keys not available")

        mock_github = MagicMock()

        with patch("shared.r2_rotation.R2SecretsManager"):
            manager = R2KeyRotationManager(
                cloudflare_api_token=os.environ["ETPHONEHOME_CLOUDFLARE_API_TOKEN"],
                account_id=os.environ["ETPHONEHOME_R2_ACCOUNT_ID"],
                github_manager=mock_github,
            )

            result = manager.verify_new_token_works(
                access_key_id=os.environ["ETPHONEHOME_R2_ACCESS_KEY"],
                secret_access_key=os.environ["ETPHONEHOME_R2_SECRET_KEY"],
            )

            assert result is True
