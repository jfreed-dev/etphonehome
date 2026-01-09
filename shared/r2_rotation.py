"""Cloudflare R2 API token rotation and management."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from shared.secrets_manager import GitHubSecretsManager, R2SecretsManager

logger = logging.getLogger(__name__)


class CloudflareAPIClient:
    """Client for Cloudflare API operations."""

    API_BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_token: str, account_id: str):
        """
        Initialize Cloudflare API client.

        Args:
            api_token: Cloudflare API token with R2 permissions
            account_id: Cloudflare account ID
        """
        self.api_token = api_token
        self.account_id = account_id
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def create_r2_token(
        self,
        name: str,
        permissions: list[str] | None = None,
    ) -> dict:
        """
        Create a new R2 API token.

        Args:
            name: Token name/description
            permissions: List of permissions (default: ["read", "write"])

        Returns:
            Dict with access_key_id and secret_access_key

        Raises:
            httpx.HTTPError: If API request fails
        """
        if permissions is None:
            permissions = ["read", "write"]

        url = f"{self.API_BASE_URL}/accounts/{self.account_id}/r2/credentials"

        payload = {
            "name": name,
            "permissions": permissions,
        }

        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=self.headers, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        if not result.get("success"):
            error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
            raise RuntimeError(f"Failed to create R2 token: {error_msg}")

        token_data = result["result"]
        logger.info(f"Created R2 token: {name} (ID: {token_data['access_key_id']})")

        return {
            "access_key_id": token_data["access_key_id"],
            "secret_access_key": token_data["secret_access_key"],
        }

    def list_r2_tokens(self) -> list[dict]:
        """
        List all R2 API tokens for the account.

        Returns:
            List of token metadata dicts
        """
        url = f"{self.API_BASE_URL}/accounts/{self.account_id}/r2/credentials"

        with httpx.Client() as client:
            response = client.get(url, headers=self.headers, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        if not result.get("success"):
            error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
            raise RuntimeError(f"Failed to list R2 tokens: {error_msg}")

        return result["result"]

    def delete_r2_token(self, access_key_id: str) -> None:
        """
        Delete an R2 API token.

        Args:
            access_key_id: Access key ID of token to delete
        """
        url = f"{self.API_BASE_URL}/accounts/{self.account_id}/r2/credentials/{access_key_id}"

        with httpx.Client() as client:
            response = client.delete(url, headers=self.headers, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        if not result.get("success"):
            error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
            raise RuntimeError(f"Failed to delete R2 token: {error_msg}")

        logger.info(f"Deleted R2 token: {access_key_id}")


class R2KeyRotationManager:
    """Manages R2 API token rotation with GitHub Secrets integration."""

    def __init__(
        self,
        cloudflare_api_token: str,
        account_id: str,
        github_manager: GitHubSecretsManager,
    ):
        """
        Initialize rotation manager.

        Args:
            cloudflare_api_token: Cloudflare API token with R2 permissions
            account_id: Cloudflare account ID
            github_manager: GitHub Secrets Manager instance
        """
        self.cf_client = CloudflareAPIClient(cloudflare_api_token, account_id)
        self.account_id = account_id
        self.r2_secrets = R2SecretsManager(github_manager)

    @classmethod
    def from_env(cls) -> Optional["R2KeyRotationManager"]:
        """
        Create rotation manager from environment variables.

        Environment variables:
            ETPHONEHOME_CLOUDFLARE_API_TOKEN: Cloudflare API token
            ETPHONEHOME_R2_ACCOUNT_ID: Cloudflare account ID
            ETPHONEHOME_GITHUB_REPO: GitHub repository (owner/repo)

        Returns:
            R2KeyRotationManager or None if not configured
        """
        cf_token = os.getenv("ETPHONEHOME_CLOUDFLARE_API_TOKEN")
        account_id = os.getenv("ETPHONEHOME_R2_ACCOUNT_ID")
        github_repo = os.getenv("ETPHONEHOME_GITHUB_REPO")

        if not all([cf_token, account_id, github_repo]):
            missing = []
            if not cf_token:
                missing.append("ETPHONEHOME_CLOUDFLARE_API_TOKEN")
            if not account_id:
                missing.append("ETPHONEHOME_R2_ACCOUNT_ID")
            if not github_repo:
                missing.append("ETPHONEHOME_GITHUB_REPO")

            logger.error(f"Missing required environment variables: {', '.join(missing)}")
            return None

        github_manager = GitHubSecretsManager.from_env()
        if github_manager is None:
            return None

        return cls(cf_token, account_id, github_manager)

    def rotate_r2_keys(
        self,
        old_access_key_id: str | None = None,
        delete_old: bool = True,
    ) -> dict:
        """
        Rotate R2 API keys: create new token, update GitHub Secrets, delete old token.

        Args:
            old_access_key_id: Access key ID of old token to delete (optional)
            delete_old: Whether to delete the old token (default: True)

        Returns:
            Dict with new credentials and rotation info
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        token_name = f"etphonehome-r2-{timestamp}"

        logger.info("Starting R2 key rotation...")

        # Step 1: Create new token
        logger.info(f"Creating new R2 token: {token_name}")
        new_token = self.cf_client.create_r2_token(
            name=token_name,
            permissions=["read", "write"],
        )

        new_access_key = new_token["access_key_id"]
        new_secret_key = new_token["secret_access_key"]

        # Step 2: Update GitHub Secrets
        logger.info("Updating GitHub Secrets with new R2 keys...")
        self.r2_secrets.update_r2_keys(new_access_key, new_secret_key)

        # Step 3: Delete old token (if provided and requested)
        if delete_old and old_access_key_id:
            logger.info(f"Deleting old R2 token: {old_access_key_id}")
            try:
                self.cf_client.delete_r2_token(old_access_key_id)
            except Exception as e:
                logger.warning(f"Failed to delete old token (continuing anyway): {e}")

        rotation_result = {
            "new_access_key_id": new_access_key,
            "rotated_at": datetime.now(timezone.utc).isoformat(),
            "old_access_key_id": old_access_key_id,
            "old_token_deleted": delete_old and old_access_key_id is not None,
            "token_name": token_name,
        }

        logger.info("R2 key rotation completed successfully")
        return rotation_result

    def list_active_tokens(self) -> list[dict]:
        """
        List all active R2 tokens for the account.

        Returns:
            List of token metadata
        """
        return self.cf_client.list_r2_tokens()

    def cleanup_old_tokens(self, keep_latest: int = 2) -> int:
        """
        Clean up old R2 tokens, keeping only the most recent ones.

        Args:
            keep_latest: Number of latest tokens to keep (default: 2)

        Returns:
            Number of tokens deleted
        """
        tokens = self.list_active_tokens()

        # Sort by creation date (newest first)
        # Note: Cloudflare API should return them sorted, but we sort to be safe
        tokens_sorted = sorted(
            tokens,
            key=lambda t: t.get("created_on", ""),
            reverse=True,
        )

        # Keep the latest N tokens
        tokens_to_delete = tokens_sorted[keep_latest:]

        deleted_count = 0
        for token in tokens_to_delete:
            access_key_id = token["access_key_id"]
            logger.info(f"Deleting old token: {access_key_id} (created: {token.get('created_on')})")
            try:
                self.cf_client.delete_r2_token(access_key_id)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete token {access_key_id}: {e}")

        logger.info(f"Cleaned up {deleted_count} old R2 tokens")
        return deleted_count

    def verify_new_token_works(self, access_key_id: str, secret_access_key: str) -> bool:
        """
        Verify that a new R2 token works by attempting to list buckets.

        Args:
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key

        Returns:
            True if token works, False otherwise
        """
        import boto3
        from botocore.exceptions import ClientError

        try:
            endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
            s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )

            # Try to list buckets
            s3_client.list_buckets()
            logger.info("✓ New R2 token verified successfully")
            return True

        except ClientError as e:
            logger.error(f"✗ New R2 token verification failed: {e}")
            return False


class RotationScheduler:
    """Scheduler for periodic R2 key rotation."""

    def __init__(self, rotation_manager: R2KeyRotationManager, rotation_days: int = 90):
        """
        Initialize rotation scheduler.

        Args:
            rotation_manager: R2KeyRotationManager instance
            rotation_days: Days between rotations (default: 90)
        """
        self.rotation_manager = rotation_manager
        self.rotation_days = rotation_days
        self.last_rotation_file = Path.home() / ".etphonehome" / "last_r2_rotation.txt"
        self.last_rotation_file.parent.mkdir(parents=True, exist_ok=True)

    def get_last_rotation_date(self) -> datetime | None:
        """
        Get the date of the last rotation.

        Returns:
            Datetime of last rotation, or None if never rotated
        """
        if not self.last_rotation_file.exists():
            return None

        try:
            timestamp_str = self.last_rotation_file.read_text().strip()
            return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning(f"Failed to read last rotation date: {e}")
            return None

    def record_rotation(self) -> None:
        """Record the current time as the last rotation time."""
        now = datetime.now(timezone.utc)
        self.last_rotation_file.write_text(now.isoformat())
        logger.info(f"Recorded rotation at {now.isoformat()}")

    def should_rotate(self) -> bool:
        """
        Check if keys should be rotated based on the schedule.

        Returns:
            True if rotation is due, False otherwise
        """
        last_rotation = self.get_last_rotation_date()

        if last_rotation is None:
            logger.info("No previous rotation found - rotation recommended")
            return True

        days_since_rotation = (datetime.now(timezone.utc) - last_rotation).days

        if days_since_rotation >= self.rotation_days:
            logger.info(
                f"Rotation due: {days_since_rotation} days since last rotation "
                f"(threshold: {self.rotation_days} days)"
            )
            return True

        logger.info(
            f"Rotation not due: {days_since_rotation} days since last rotation "
            f"(next rotation in {self.rotation_days - days_since_rotation} days)"
        )
        return False

    def rotate_if_due(self, old_access_key_id: str | None = None) -> dict | None:
        """
        Rotate keys if rotation is due according to schedule.

        Args:
            old_access_key_id: Access key ID of old token to delete (optional)

        Returns:
            Rotation result dict if rotated, None if not due
        """
        if not self.should_rotate():
            return None

        logger.info("Performing scheduled R2 key rotation...")
        result = self.rotation_manager.rotate_r2_keys(old_access_key_id=old_access_key_id)
        self.record_rotation()

        return result


def main():
    """CLI for R2 key rotation."""
    import argparse

    parser = argparse.ArgumentParser(description="ET Phone Home R2 Key Rotation CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Rotate keys
    rotate_parser = subparsers.add_parser("rotate", help="Rotate R2 API keys")
    rotate_parser.add_argument(
        "--old-key", help="Old access key ID to delete (optional)", default=None
    )
    rotate_parser.add_argument(
        "--keep-old",
        action="store_true",
        help="Keep old token (don't delete)",
    )

    # List tokens
    _ = subparsers.add_parser("list", help="List active R2 tokens")

    # Cleanup old tokens
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old R2 tokens")
    cleanup_parser.add_argument(
        "--keep",
        type=int,
        default=2,
        help="Number of latest tokens to keep (default: 2)",
    )

    # Check rotation schedule
    check_parser = subparsers.add_parser("check", help="Check if rotation is due")
    check_parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Rotation interval in days (default: 90)",
    )

    # Rotate if due
    auto_parser = subparsers.add_parser("auto", help="Rotate if due according to schedule")
    auto_parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Rotation interval in days (default: 90)",
    )
    auto_parser.add_argument(
        "--old-key",
        help="Old access key ID to delete (optional)",
        default=None,
    )

    args = parser.parse_args()

    # Initialize rotation manager
    rotation_manager = R2KeyRotationManager.from_env()
    if rotation_manager is None:
        print("✗ Failed to initialize R2 rotation manager")
        print(
            "  Check environment variables: ETPHONEHOME_CLOUDFLARE_API_TOKEN, "
            "ETPHONEHOME_R2_ACCOUNT_ID, ETPHONEHOME_GITHUB_REPO"
        )
        exit(1)

    if args.command == "rotate":
        result = rotation_manager.rotate_r2_keys(
            old_access_key_id=args.old_key,
            delete_old=not args.keep_old,
        )
        print("✓ R2 keys rotated successfully")
        print(f"  New access key: {result['new_access_key_id']}")
        print(f"  Rotated at: {result['rotated_at']}")
        if result["old_token_deleted"]:
            print(f"  Old token deleted: {result['old_access_key_id']}")

    elif args.command == "list":
        tokens = rotation_manager.list_active_tokens()
        print(f"Active R2 tokens ({len(tokens)}):")
        for token in tokens:
            print(f"  - {token['access_key_id']} (created: {token.get('created_on', 'unknown')})")

    elif args.command == "cleanup":
        deleted = rotation_manager.cleanup_old_tokens(keep_latest=args.keep)
        print(f"✓ Cleaned up {deleted} old R2 token(s)")

    elif args.command == "check":
        scheduler = RotationScheduler(rotation_manager, rotation_days=args.days)
        last_rotation = scheduler.get_last_rotation_date()

        if last_rotation:
            days_ago = (datetime.now(timezone.utc) - last_rotation).days
            print(f"Last rotation: {last_rotation.isoformat()} ({days_ago} days ago)")
        else:
            print("No previous rotation found")

        if scheduler.should_rotate():
            print("✓ Rotation is DUE")
        else:
            days_until = args.days - days_ago if last_rotation else 0
            print(f"✗ Rotation not due (next rotation in {days_until} days)")

    elif args.command == "auto":
        scheduler = RotationScheduler(rotation_manager, rotation_days=args.days)
        result = scheduler.rotate_if_due(old_access_key_id=args.old_key)

        if result:
            print("✓ Scheduled rotation completed")
            print(f"  New access key: {result['new_access_key_id']}")
        else:
            print("✗ Rotation not due (skipped)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
