"""R2-based release management for ET Phone Home client updates."""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .r2_client import R2Client, R2Config

logger = logging.getLogger(__name__)

# R2 public URL - uses custom domain for cleaner URLs
# Override with ETPHONEHOME_R2_PUBLIC_URL environment variable if needed
R2_PUBLIC_URL_TEMPLATE = os.getenv(
    "ETPHONEHOME_R2_PUBLIC_URL",
    "https://<UPDATE_DOMAIN>",
)


class ReleaseManager:
    """Manages release uploads to R2 for client auto-updates."""

    RELEASES_PREFIX = "releases"

    def __init__(self, r2_client: R2Client):
        """
        Initialize release manager.

        Args:
            r2_client: R2Client instance
        """
        self.r2 = r2_client
        self._public_url_base = self._get_public_url_base()

    def _get_public_url_base(self) -> str:
        """Get the public URL base for R2 objects."""
        template = R2_PUBLIC_URL_TEMPLATE
        if "{account_id}" in template:
            template = template.format(account_id=self.r2.config.account_id)
        return template.rstrip("/")

    def get_public_url(self, key: str) -> str:
        """
        Get public URL for an R2 object.

        Args:
            key: Object key in R2

        Returns:
            Public URL string
        """
        return f"{self._public_url_base}/{key}"

    def upload_release(
        self,
        version: str,
        artifacts: dict[str, Path],
        changelog: str = "",
    ) -> dict:
        """
        Upload a release to R2.

        Args:
            version: Version string (e.g., "0.1.10")
            artifacts: Dict mapping platform keys to file paths
                       e.g., {"linux-x86_64": Path("dist/phonehome-linux-x86_64.tar.gz")}
            changelog: Optional changelog text

        Returns:
            dict with release info including version.json content and URLs
        """
        version_clean = version.lstrip("v")
        release_prefix = f"{self.RELEASES_PREFIX}/v{version_clean}"
        release_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        downloads = {}
        uploaded_files = []

        for platform, local_path in artifacts.items():
            local_path = Path(local_path)
            if not local_path.exists():
                logger.warning(f"Artifact not found, skipping: {local_path}")
                continue

            # Calculate SHA256
            sha256 = hashlib.sha256(local_path.read_bytes()).hexdigest()
            size = local_path.stat().st_size
            filename = local_path.name

            # Upload to R2
            key = f"{release_prefix}/{filename}"
            logger.info(f"Uploading {platform}: {local_path} -> {key}")

            self.r2.upload_file(
                local_path,
                key,
                metadata={
                    "version": version_clean,
                    "platform": platform,
                    "sha256": sha256,
                },
            )

            public_url = self.get_public_url(key)
            downloads[platform] = {
                "url": public_url,
                "sha256": sha256,
                "size": size,
            }
            uploaded_files.append({"platform": platform, "key": key, "url": public_url})

        if not downloads:
            raise ValueError("No artifacts were uploaded")

        # Create version.json
        version_json = {
            "version": version_clean,
            "release_date": release_date,
            "downloads": downloads,
            "changelog": changelog,
        }

        # Upload version.json to version directory
        version_json_key = f"{release_prefix}/version.json"
        self._upload_json(version_json, version_json_key)

        # Upload version.json to latest directory
        latest_json_key = f"{self.RELEASES_PREFIX}/latest/version.json"
        self._upload_json(version_json, latest_json_key)

        logger.info(f"Release v{version_clean} published to R2")

        return {
            "version": version_clean,
            "release_date": release_date,
            "version_json": version_json,
            "version_json_url": self.get_public_url(latest_json_key),
            "release_url": self.get_public_url(release_prefix),
            "uploaded_files": uploaded_files,
        }

    def _upload_json(self, data: dict, key: str) -> None:
        """Upload JSON data to R2."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f, indent=2)
            f.flush()
            temp_path = Path(f.name)

        try:
            self.r2.upload_file(
                temp_path,
                key,
                metadata={"content-type": "application/json"},
            )
        finally:
            temp_path.unlink()

    def list_releases(self) -> list[dict]:
        """
        List all releases in R2.

        Returns:
            List of release info dicts
        """
        try:
            response = self.r2.client.list_objects_v2(
                Bucket=self.r2.config.bucket,
                Prefix=f"{self.RELEASES_PREFIX}/v",
                Delimiter="/",
            )

            releases = []
            for prefix in response.get("CommonPrefixes", []):
                version_dir = prefix["Prefix"].rstrip("/")
                version = version_dir.split("/")[-1]
                releases.append(
                    {
                        "version": version,
                        "prefix": version_dir,
                        "url": self.get_public_url(version_dir),
                    }
                )

            return sorted(releases, key=lambda x: x["version"], reverse=True)

        except Exception as e:
            logger.error(f"Failed to list releases: {e}")
            return []

    def get_latest_version(self) -> dict | None:
        """
        Get the latest version info from R2.

        Returns:
            version.json content or None if not found
        """
        key = f"{self.RELEASES_PREFIX}/latest/version.json"
        try:
            response = self.r2.client.get_object(
                Bucket=self.r2.config.bucket,
                Key=key,
            )
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to get latest version: {e}")
            return None

    def delete_release(self, version: str) -> dict:
        """
        Delete a release from R2.

        Args:
            version: Version to delete (e.g., "0.1.9")

        Returns:
            dict with deletion results
        """
        version_clean = version.lstrip("v")
        prefix = f"{self.RELEASES_PREFIX}/v{version_clean}/"

        # List all objects with this prefix
        response = self.r2.client.list_objects_v2(
            Bucket=self.r2.config.bucket,
            Prefix=prefix,
        )

        deleted = []
        for obj in response.get("Contents", []):
            self.r2.delete_object(obj["Key"])
            deleted.append(obj["Key"])

        logger.info(f"Deleted release v{version_clean}: {len(deleted)} objects")
        return {"version": version_clean, "deleted": deleted}


def create_release_manager() -> ReleaseManager | None:
    """
    Create release manager from environment variables.

    Returns:
        ReleaseManager if R2 is configured, None otherwise
    """
    config = R2Config.from_env()
    if config is None:
        logger.warning("R2 not configured for releases")
        return None

    try:
        client = R2Client(config)
        # Test connectivity
        client.client.list_objects_v2(Bucket=config.bucket, MaxKeys=1)
        return ReleaseManager(client)
    except Exception as e:
        logger.error(f"Failed to create release manager: {e}")
        return None
