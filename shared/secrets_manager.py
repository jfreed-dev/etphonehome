"""GitHub Secrets Manager for secure credential storage and rotation."""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from github import Github, GithubException
from nacl import encoding, public

logger = logging.getLogger(__name__)


class SecureLocalStorage:
    """Secure local storage for GitHub token using encrypted file."""

    def __init__(self, storage_path: Path | None = None):
        """
        Initialize secure storage.

        Args:
            storage_path: Path to encrypted storage file (default: ~/.etphonehome/github_token.enc)
        """
        if storage_path is None:
            storage_path = Path.home() / ".etphonehome" / "github_token.enc"

        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Derive encryption key from machine-specific data
        self._key = self._derive_encryption_key()

    def _derive_encryption_key(self) -> bytes:
        """
        Derive encryption key from machine-specific identifier.

        Uses machine ID as salt for PBKDF2 key derivation.
        """
        # Get machine-specific identifier
        machine_id = self._get_machine_id()

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=machine_id.encode(),
            iterations=100000,
        )
        password = b"etphonehome-github-token"  # Static password, security is in machine_id salt
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key

    def _get_machine_id(self) -> str:
        """Get machine-specific identifier."""
        # Try /etc/machine-id (Linux)
        machine_id_file = Path("/etc/machine-id")
        if machine_id_file.exists():
            return machine_id_file.read_text().strip()

        # Try /var/lib/dbus/machine-id (Linux alternative)
        dbus_machine_id = Path("/var/lib/dbus/machine-id")
        if dbus_machine_id.exists():
            return dbus_machine_id.read_text().strip()

        # Fallback: use hostname + user
        import getpass
        import socket

        return f"{socket.gethostname()}-{getpass.getuser()}"

    def store_token(self, token: str) -> None:
        """
        Encrypt and store GitHub token locally.

        Args:
            token: GitHub personal access token
        """
        fernet = Fernet(self._key)
        encrypted = fernet.encrypt(token.encode())

        # Write with restrictive permissions
        self.storage_path.write_bytes(encrypted)
        self.storage_path.chmod(0o600)

        logger.info(f"GitHub token stored securely at {self.storage_path}")

    def load_token(self) -> str | None:
        """
        Load and decrypt GitHub token from local storage.

        Returns:
            Decrypted GitHub token, or None if not found
        """
        if not self.storage_path.exists():
            return None

        try:
            encrypted = self.storage_path.read_bytes()
            fernet = Fernet(self._key)
            decrypted = fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt GitHub token: {e}")
            return None

    def delete_token(self) -> None:
        """Delete stored token."""
        if self.storage_path.exists():
            self.storage_path.unlink()
            logger.info("GitHub token deleted from local storage")


class GitHubSecretsManager:
    """Manage secrets in GitHub repository using GitHub Secrets API."""

    def __init__(
        self,
        repo_name: str,
        github_token: str | None = None,
        use_local_storage: bool = True,
    ):
        """
        Initialize GitHub Secrets Manager.

        Args:
            repo_name: Repository name in format "owner/repo"
            github_token: GitHub personal access token (or None to load from storage)
            use_local_storage: Whether to use secure local storage for token
        """
        self.repo_name = repo_name
        self.use_local_storage = use_local_storage

        # Load token from storage if not provided
        if github_token is None and use_local_storage:
            storage = SecureLocalStorage()
            github_token = storage.load_token()

        if github_token is None:
            raise ValueError(
                "GitHub token not provided and not found in local storage. "
                "Set via ETPHONEHOME_GITHUB_TOKEN or store with: "
                "python -m shared.secrets_manager store-token <token>"
            )

        self.github_token = github_token
        self._github = Github(github_token)
        self._repo = self._github.get_repo(repo_name)

        logger.info(f"GitHub Secrets Manager initialized for {repo_name}")

    @classmethod
    def from_env(cls, use_local_storage: bool = True) -> Optional["GitHubSecretsManager"]:
        """
        Create manager from environment variables.

        Environment variables:
            ETPHONEHOME_GITHUB_REPO: Repository name (owner/repo)
            ETPHONEHOME_GITHUB_TOKEN: GitHub token (optional if stored locally)

        Returns:
            GitHubSecretsManager or None if not configured
        """
        repo_name = os.getenv("ETPHONEHOME_GITHUB_REPO")
        if not repo_name:
            logger.warning("ETPHONEHOME_GITHUB_REPO not set")
            return None

        github_token = os.getenv("ETPHONEHOME_GITHUB_TOKEN")

        try:
            return cls(repo_name, github_token, use_local_storage)
        except ValueError as e:
            logger.error(f"Failed to initialize GitHub Secrets Manager: {e}")
            return None

    def _encrypt_secret(self, secret_value: str) -> str:
        """
        Encrypt a secret value for GitHub using repository public key.

        Args:
            secret_value: Plain text secret value

        Returns:
            Base64-encoded encrypted secret
        """
        # Get repository public key
        public_key = self._repo.get_public_key()

        # Encrypt using NaCl
        public_key_obj = public.PublicKey(public_key.key.encode(), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode())

        # Return base64-encoded
        return base64.b64encode(encrypted).decode()

    def set_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Set or update a secret in GitHub repository.

        Args:
            secret_name: Name of the secret (e.g., "R2_ACCESS_KEY")
            secret_value: Secret value to store

        Raises:
            GithubException: If GitHub API call fails
        """
        try:
            # Create or update secret (PyGithub handles encryption automatically)
            self._repo.create_secret(
                secret_name=secret_name,
                unencrypted_value=secret_value,
                secret_type="actions",  # Repository secret  # pragma: allowlist secret
            )

            logger.info(f"Secret '{secret_name}' set in {self.repo_name}")

        except GithubException as e:
            logger.error(f"Failed to set secret '{secret_name}': {e}")  # pragma: allowlist secret
            raise

    def get_secret_metadata(self, secret_name: str) -> dict | None:
        """
        Get metadata about a secret (not the value itself - GitHub doesn't allow retrieval).

        Args:
            secret_name: Name of the secret

        Returns:
            Dict with metadata (name, created_at, updated_at) or None if not found
        """
        try:
            secret = self._repo.get_secret(secret_name)
            return {
                "name": secret.name,
                "created_at": secret.created_at.isoformat() if secret.created_at else None,
                "updated_at": secret.updated_at.isoformat() if secret.updated_at else None,
            }
        except GithubException as e:
            if e.status == 404:
                return None
            logger.error(f"Failed to get secret metadata '{secret_name}': {e}")
            raise

    def delete_secret(self, secret_name: str) -> bool:
        """
        Delete a secret from GitHub repository.

        Args:
            secret_name: Name of the secret to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            self._repo.delete_secret(secret_name)
            logger.info(f"Secret '{secret_name}' deleted from {self.repo_name}")
            return True
        except GithubException as e:
            if e.status == 404:
                logger.warning(f"Secret '{secret_name}' not found")
                return False
            logger.error(f"Failed to delete secret '{secret_name}': {e}")
            raise

    def list_secrets(self) -> list[str]:
        """
        List all secret names in the repository.

        Returns:
            List of secret names
        """
        try:
            secrets = self._repo.get_secrets()
            return [secret.name for secret in secrets]
        except GithubException as e:
            logger.error(f"Failed to list secrets: {e}")
            raise

    def secret_exists(self, secret_name: str) -> bool:
        """
        Check if a secret exists.

        Args:
            secret_name: Name of the secret

        Returns:
            True if secret exists, False otherwise
        """
        return self.get_secret_metadata(secret_name) is not None


class R2SecretsManager:
    """High-level manager for R2 credentials in GitHub Secrets."""

    # Secret names used in GitHub  # pragma: allowlist secret
    SECRET_ACCOUNT_ID = "ETPHONEHOME_R2_ACCOUNT_ID"  # pragma: allowlist secret
    SECRET_ACCESS_KEY = "ETPHONEHOME_R2_ACCESS_KEY"  # pragma: allowlist secret
    SECRET_SECRET_KEY = "ETPHONEHOME_R2_SECRET_KEY"  # pragma: allowlist secret
    SECRET_BUCKET = "ETPHONEHOME_R2_BUCKET"  # pragma: allowlist secret
    SECRET_REGION = "ETPHONEHOME_R2_REGION"  # pragma: allowlist secret

    def __init__(self, github_manager: GitHubSecretsManager):  # pragma: allowlist secret
        """
        Initialize R2 secrets manager.

        Args:
            github_manager: GitHubSecretsManager instance  # pragma: allowlist secret
        """
        self.gh = github_manager

    def store_r2_credentials(
        self,
        account_id: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "auto",
    ) -> None:
        """
        Store complete R2 credentials in GitHub Secrets.

        Args:
            account_id: Cloudflare account ID
            access_key: R2 access key ID
            secret_key: R2 secret access key
            bucket: R2 bucket name
            region: R2 region (default: auto)
        """
        logger.info("Storing R2 credentials in GitHub Secrets...")

        self.gh.set_secret(self.SECRET_ACCOUNT_ID, account_id)
        self.gh.set_secret(self.SECRET_ACCESS_KEY, access_key)
        self.gh.set_secret(self.SECRET_SECRET_KEY, secret_key)
        self.gh.set_secret(self.SECRET_BUCKET, bucket)
        self.gh.set_secret(self.SECRET_REGION, region)

        logger.info("R2 credentials stored successfully")

    def update_r2_keys(self, access_key: str, secret_key: str) -> None:
        """
        Update only R2 access keys (for rotation).

        Args:
            access_key: New R2 access key ID
            secret_key: New R2 secret access key
        """
        logger.info("Updating R2 keys in GitHub Secrets...")

        self.gh.set_secret(self.SECRET_ACCESS_KEY, access_key)
        self.gh.set_secret(self.SECRET_SECRET_KEY, secret_key)

        logger.info("R2 keys updated successfully")

    def get_r2_credentials_metadata(self) -> dict:
        """
        Get metadata about stored R2 credentials.

        Returns:
            Dict with metadata for each secret
        """
        result = {}
        for secret_name in [
            self.SECRET_ACCOUNT_ID,
            self.SECRET_ACCESS_KEY,
            self.SECRET_SECRET_KEY,
            self.SECRET_BUCKET,
            self.SECRET_REGION,
        ]:
            result[secret_name] = self.gh.get_secret_metadata(secret_name)
        return result

    def verify_r2_secrets_exist(self) -> bool:
        """
        Verify all required R2 secrets exist in GitHub.

        Returns:
            True if all required secrets exist, False otherwise
        """
        required = [
            self.SECRET_ACCOUNT_ID,
            self.SECRET_ACCESS_KEY,
            self.SECRET_SECRET_KEY,
            self.SECRET_BUCKET,
        ]

        for secret_name in required:
            if not self.gh.secret_exists(secret_name):
                logger.warning(f"Required R2 secret '{secret_name}' not found")
                return False

        return True

    def delete_all_r2_secrets(self) -> None:
        """Delete all R2 credentials from GitHub Secrets (use with caution)."""
        logger.warning("Deleting all R2 secrets from GitHub...")

        for secret_name in [
            self.SECRET_ACCOUNT_ID,
            self.SECRET_ACCESS_KEY,
            self.SECRET_SECRET_KEY,
            self.SECRET_BUCKET,
            self.SECRET_REGION,
        ]:
            self.gh.delete_secret(secret_name)

        logger.info("All R2 secrets deleted")


def main():
    """CLI for secrets management."""
    import argparse

    parser = argparse.ArgumentParser(description="ET Phone Home Secrets Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Store GitHub token
    store_parser = subparsers.add_parser("store-token", help="Store GitHub token locally")
    store_parser.add_argument("token", help="GitHub personal access token")

    # List secrets
    list_parser = subparsers.add_parser("list", help="List all secrets")
    list_parser.add_argument("--repo", required=True, help="Repository (owner/repo)")

    # Set secret
    set_parser = subparsers.add_parser("set", help="Set a secret")
    set_parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    set_parser.add_argument("name", help="Secret name")
    set_parser.add_argument("value", help="Secret value")

    # Store R2 credentials
    r2_parser = subparsers.add_parser("store-r2", help="Store R2 credentials")
    r2_parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    r2_parser.add_argument("--account-id", required=True, help="Cloudflare account ID")
    r2_parser.add_argument("--access-key", required=True, help="R2 access key ID")
    r2_parser.add_argument("--secret-key", required=True, help="R2 secret access key")
    r2_parser.add_argument("--bucket", required=True, help="R2 bucket name")
    r2_parser.add_argument("--region", default="auto", help="R2 region (default: auto)")

    # Verify R2 secrets
    verify_parser = subparsers.add_parser("verify-r2", help="Verify R2 secrets exist")
    verify_parser.add_argument("--repo", required=True, help="Repository (owner/repo)")

    args = parser.parse_args()

    if args.command == "store-token":
        storage = SecureLocalStorage()
        storage.store_token(args.token)
        print("✓ GitHub token stored securely")

    elif args.command == "list":
        manager = GitHubSecretsManager(args.repo)
        secrets = manager.list_secrets()
        print(f"Secrets in {args.repo}:")
        for secret in secrets:
            print(f"  - {secret}")

    elif args.command == "set":
        manager = GitHubSecretsManager(args.repo)
        manager.set_secret(args.name, args.value)
        print(f"✓ Secret '{args.name}' set")

    elif args.command == "store-r2":
        manager = GitHubSecretsManager(args.repo)
        r2_manager = R2SecretsManager(manager)
        r2_manager.store_r2_credentials(
            account_id=args.account_id,
            access_key=args.access_key,
            secret_key=args.secret_key,
            bucket=args.bucket,
            region=args.region,
        )
        print(f"✓ R2 credentials stored in {args.repo}")

    elif args.command == "verify-r2":
        manager = GitHubSecretsManager(args.repo)
        r2_manager = R2SecretsManager(manager)
        if r2_manager.verify_r2_secrets_exist():
            print("✓ All required R2 secrets exist")
        else:
            print("✗ Some R2 secrets are missing")
            exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
