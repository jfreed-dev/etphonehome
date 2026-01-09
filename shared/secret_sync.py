"""Automatic secret synchronization from GitHub Secrets to local environment."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from shared.secrets_manager import GitHubSecretsManager, R2SecretsManager

logger = logging.getLogger(__name__)


class SecretSyncManager:
    """Manages automatic synchronization of secrets from GitHub to local environment."""

    def __init__(
        self,
        github_manager: GitHubSecretsManager,
        sync_interval: int = 3600,
        cache_file: Path | None = None,
    ):
        """
        Initialize secret sync manager.

        Args:
            github_manager: GitHubSecretsManager instance
            sync_interval: Seconds between sync attempts (default: 3600 = 1 hour)
            cache_file: Path to cache file (default: ~/.etphonehome/secret_cache.env)
        """
        self.github_manager = github_manager
        self.sync_interval = sync_interval

        if cache_file is None:
            cache_file = Path.home() / ".etphonehome" / "secret_cache.env"

        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        self._sync_task: asyncio.Task | None = None
        self._running = False

    def load_cached_secrets(self) -> dict[str, str]:
        """
        Load secrets from local cache.

        Returns:
            Dict of secret name -> value
        """
        if not self.cache_file.exists():
            return {}

        secrets = {}
        try:
            for line in self.cache_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    secrets[key] = value
        except Exception as e:
            logger.error(f"Failed to load cached secrets: {e}")

        return secrets

    def save_secrets_to_cache(self, secrets: dict[str, str]) -> None:
        """
        Save secrets to local cache file.

        Args:
            secrets: Dict of secret name -> value
        """
        try:
            lines = [
                "# ET Phone Home Secret Cache",
                f"# Updated: {datetime.now(timezone.utc).isoformat()}",
                "# DO NOT COMMIT THIS FILE",
                "",
            ]

            for key, value in secrets.items():
                lines.append(f"{key}={value}")

            self.cache_file.write_text("\n".join(lines))
            self.cache_file.chmod(0o600)

            logger.info(f"Saved {len(secrets)} secrets to cache")

        except Exception as e:
            logger.error(f"Failed to save secrets to cache: {e}")

    def inject_secrets_to_env(self, secrets: dict[str, str]) -> None:
        """
        Inject secrets into current process environment.

        Args:
            secrets: Dict of secret name -> value
        """
        for key, value in secrets.items():
            os.environ[key] = value
            logger.debug(f"Injected secret: {key}")

        logger.info(f"Injected {len(secrets)} secrets into environment")

    async def fetch_r2_secrets_from_github(self) -> dict[str, str]:
        """
        Fetch R2 secrets from GitHub Secrets API.

        Note: GitHub Secrets API doesn't allow reading secret values directly.
        This is a limitation - we can only update, not retrieve.

        This method is a placeholder for future enhancement if GitHub adds
        value retrieval capability, or for integration with other secret managers.

        Returns:
            Empty dict (GitHub doesn't support secret value retrieval)
        """
        logger.warning(
            "GitHub Secrets API does not support reading secret values. "
            "Use GitHub Actions to inject secrets as environment variables, "
            "or configure secrets manually in local environment."
        )

        # We can only verify that secrets exist, not read their values
        r2_secrets = R2SecretsManager(self.github_manager)
        exists = r2_secrets.verify_r2_secrets_exist()

        if exists:
            logger.info("Verified R2 secrets exist in GitHub")
        else:
            logger.warning("Some R2 secrets are missing in GitHub")

        return {}

    def load_secrets_from_local_sources(self) -> dict[str, str]:
        """
        Load secrets from local sources in priority order.

        Priority:
        1. Current environment variables
        2. Cached secrets file
        3. server.env file

        Returns:
            Dict of secret name -> value
        """
        secrets = {}

        # Priority 1: Current environment
        r2_vars = [
            "ETPHONEHOME_R2_ACCOUNT_ID",
            "ETPHONEHOME_R2_ACCESS_KEY",
            "ETPHONEHOME_R2_SECRET_KEY",
            "ETPHONEHOME_R2_BUCKET",
            "ETPHONEHOME_R2_REGION",
        ]

        for var in r2_vars:
            value = os.getenv(var)
            if value:
                secrets[var] = value

        if secrets:
            logger.info(f"Loaded {len(secrets)} secrets from environment")
            return secrets

        # Priority 2: Cached secrets
        cached = self.load_cached_secrets()
        if cached:
            logger.info(f"Loaded {len(cached)} secrets from cache")
            return cached

        # Priority 3: server.env file
        env_files = [
            Path("/etc/etphonehome/server.env"),
            Path.home() / ".etphonehome" / "server.env",
        ]

        for env_file in env_files:
            if env_file.exists():
                try:
                    for line in env_file.read_text().splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            # Remove quotes if present
                            value = value.strip('"').strip("'")
                            if key in r2_vars:
                                secrets[key] = value

                    if secrets:
                        logger.info(f"Loaded {len(secrets)} secrets from {env_file}")
                        return secrets

                except Exception as e:
                    logger.error(f"Failed to load secrets from {env_file}: {e}")

        return secrets

    async def sync_secrets_once(self) -> bool:
        """
        Perform one-time secret synchronization.

        Returns:
            True if sync successful, False otherwise
        """
        try:
            logger.info("Starting secret synchronization...")

            # Load secrets from local sources
            secrets = self.load_secrets_from_local_sources()

            if not secrets:
                logger.warning("No secrets found in any local source")
                return False

            # Inject into environment
            self.inject_secrets_to_env(secrets)

            # Save to cache for next startup
            self.save_secrets_to_cache(secrets)

            logger.info("Secret synchronization completed successfully")
            return True

        except Exception as e:
            logger.error(f"Secret synchronization failed: {e}")
            return False

    async def sync_loop(self) -> None:
        """Background task that periodically syncs secrets."""
        logger.info(f"Starting secret sync loop (interval: {self.sync_interval}s)")

        while self._running:
            await self.sync_secrets_once()

            # Wait for next sync
            await asyncio.sleep(self.sync_interval)

    async def start(self) -> None:
        """Start background secret synchronization."""
        if self._running:
            logger.warning("Secret sync already running")
            return

        self._running = True

        # Perform initial sync
        await self.sync_secrets_once()

        # Start background sync loop
        self._sync_task = asyncio.create_task(self.sync_loop())

        logger.info("Secret sync manager started")

    async def stop(self) -> None:
        """Stop background secret synchronization."""
        if not self._running:
            return

        self._running = False

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        logger.info("Secret sync manager stopped")


async def initialize_secret_sync(
    enabled: bool = True,
    sync_interval: int = 3600,
) -> SecretSyncManager | None:
    """
    Initialize and start secret synchronization.

    Args:
        enabled: Whether to enable secret sync (default: True)
        sync_interval: Seconds between sync attempts (default: 3600)

    Returns:
        SecretSyncManager instance if enabled and configured, None otherwise
    """
    if not enabled:
        logger.info("Secret sync disabled")
        return None

    # Check if GitHub is configured
    github_manager = GitHubSecretsManager.from_env(use_local_storage=True)
    if github_manager is None:
        logger.warning(
            "GitHub Secrets Manager not configured - secret sync disabled. "
            "Falling back to environment variables only."
        )
        return None

    # Create sync manager
    sync_manager = SecretSyncManager(github_manager, sync_interval=sync_interval)

    # Start syncing
    await sync_manager.start()

    return sync_manager


def load_secrets_synchronously() -> dict[str, str]:
    """
    Synchronously load secrets (for use before asyncio event loop).

    Returns:
        Dict of secret name -> value
    """
    # Try environment first
    r2_vars = [
        "ETPHONEHOME_R2_ACCOUNT_ID",
        "ETPHONEHOME_R2_ACCESS_KEY",
        "ETPHONEHOME_R2_SECRET_KEY",
        "ETPHONEHOME_R2_BUCKET",
        "ETPHONEHOME_R2_REGION",
    ]

    secrets = {}
    for var in r2_vars:
        value = os.getenv(var)
        if value:
            secrets[var] = value

    if secrets:
        return secrets

    # Try cache file
    cache_file = Path.home() / ".etphonehome" / "secret_cache.env"
    if cache_file.exists():
        try:
            for line in cache_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if key in r2_vars:
                        secrets[key] = value
        except Exception:
            pass

    return secrets


def inject_secrets_to_env_sync(secrets: dict[str, str]) -> None:
    """
    Synchronously inject secrets into environment.

    Args:
        secrets: Dict of secret name -> value
    """
    for key, value in secrets.items():
        os.environ[key] = value
