"""Cloudflare R2 storage client for file transfers."""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class R2Config:
    """Configuration for R2 storage."""

    def __init__(
        self,
        account_id: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "auto",
    ):
        """
        Initialize R2 configuration.

        Args:
            account_id: Cloudflare account ID
            access_key: R2 access key ID
            secret_key: R2 secret access key
            bucket: R2 bucket name
            region: R2 region (default: auto)
        """
        self.account_id = account_id
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.region = region

    @classmethod
    def from_env(cls) -> Optional["R2Config"]:
        """
        Load R2 configuration from environment variables.

        Environment variables:
            ETPHONEHOME_R2_ACCOUNT_ID
            ETPHONEHOME_R2_ACCESS_KEY
            ETPHONEHOME_R2_SECRET_KEY
            ETPHONEHOME_R2_BUCKET
            ETPHONEHOME_R2_REGION (optional, default: auto)

        Returns:
            R2Config if all required env vars are set, None otherwise
        """
        account_id = os.getenv("ETPHONEHOME_R2_ACCOUNT_ID")
        access_key = os.getenv("ETPHONEHOME_R2_ACCESS_KEY")
        secret_key = os.getenv("ETPHONEHOME_R2_SECRET_KEY")
        bucket = os.getenv("ETPHONEHOME_R2_BUCKET")
        region = os.getenv("ETPHONEHOME_R2_REGION", "auto")

        if not all([account_id, access_key, secret_key, bucket]):
            return None

        return cls(account_id, access_key, secret_key, bucket, region)

    @classmethod
    def from_github_action_env(cls) -> Optional["R2Config"]:
        """
        Load R2 configuration from GitHub Actions environment.

        This method reads secrets that have been injected as environment
        variables by GitHub Actions workflow.

        Returns:
            R2Config if all required env vars are set, None otherwise
        """
        # In GitHub Actions, secrets are available as environment variables
        # after being referenced in the workflow yaml
        return cls.from_env()

    @property
    def endpoint_url(self) -> str:
        """Get the R2 endpoint URL."""
        return f"https://{self.account_id}.r2.cloudflarestorage.com"


class R2Client:
    """Client for interacting with Cloudflare R2 storage."""

    def __init__(self, config: R2Config):
        """
        Initialize R2 client.

        Args:
            config: R2 configuration
        """
        self.config = config
        self._client = None

    @property
    def client(self):
        """Get or create boto3 S3 client for R2."""
        if self._client is None:
            boto_config = Config(
                signature_version="s3v4",
                region_name=self.config.region,
            )
            self._client = boto3.client(
                "s3",
                endpoint_url=self.config.endpoint_url,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                config=boto_config,
            )
        return self._client

    def upload_file(
        self,
        local_path: Path | str,
        key: str,
        metadata: dict | None = None,
    ) -> dict:
        """
        Upload a file to R2.

        Args:
            local_path: Path to local file
            key: Object key in R2 (e.g., "transfers/uuid/file.txt")
            metadata: Optional metadata dict to attach to object

        Returns:
            dict with upload info (key, size, etag)

        Raises:
            FileNotFoundError: If local file doesn't exist
            ClientError: If upload fails
        """
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        file_size = local_path.stat().st_size

        extra_args = {}
        if metadata:
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

        try:
            logger.info(f"Uploading {local_path} to R2 key: {key} ({file_size} bytes)")
            self.client.upload_file(
                str(local_path),
                self.config.bucket,
                key,
                ExtraArgs=extra_args,
            )

            # Get ETag for verification
            response = self.client.head_object(Bucket=self.config.bucket, Key=key)
            etag = response["ETag"].strip('"')

            logger.info(f"Upload complete: {key} (ETag: {etag})")
            return {
                "key": key,
                "size": file_size,
                "etag": etag,
                "bucket": self.config.bucket,
            }

        except ClientError as e:
            logger.error(f"Upload failed: {e}")
            raise

    def download_file(
        self,
        key: str,
        local_path: Path | str,
    ) -> dict:
        """
        Download a file from R2.

        Args:
            key: Object key in R2
            local_path: Destination path for downloaded file

        Returns:
            dict with download info (key, size, local_path)

        Raises:
            ClientError: If download fails
        """
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Downloading R2 key: {key} to {local_path}")

            # Get object metadata first
            response = self.client.head_object(Bucket=self.config.bucket, Key=key)
            size = response["ContentLength"]
            metadata = response.get("Metadata", {})

            # Download file
            self.client.download_file(
                self.config.bucket,
                key,
                str(local_path),
            )

            logger.info(f"Download complete: {local_path} ({size} bytes)")
            return {
                "key": key,
                "size": size,
                "local_path": str(local_path),
                "metadata": metadata,
            }

        except ClientError as e:
            logger.error(f"Download failed: {e}")
            raise

    def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        operation: str = "get_object",
    ) -> str:
        """
        Generate a presigned URL for temporary access to an object.

        Args:
            key: Object key in R2
            expires_in: URL expiration time in seconds (default: 3600 = 1 hour)
            operation: S3 operation (default: get_object)

        Returns:
            Presigned URL string

        Raises:
            ClientError: If URL generation fails
        """
        try:
            params = {
                "Bucket": self.config.bucket,
                "Key": key,
            }

            url = self.client.generate_presigned_url(
                operation,
                Params=params,
                ExpiresIn=expires_in,
            )

            logger.info(f"Generated presigned URL for {key} (expires in {expires_in}s)")
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def list_transfers(
        self,
        prefix: str = "transfers/",
        max_keys: int = 1000,
    ) -> list[dict]:
        """
        List transfer objects in R2.

        Args:
            prefix: Key prefix to filter (default: "transfers/")
            max_keys: Maximum number of keys to return

        Returns:
            List of dicts with object info (key, size, last_modified, metadata)
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.config.bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            objects = []
            for obj in response.get("Contents", []):
                # Get metadata for each object
                head = self.client.head_object(Bucket=self.config.bucket, Key=obj["Key"])

                objects.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "etag": obj["ETag"].strip('"'),
                        "metadata": head.get("Metadata", {}),
                    }
                )

            logger.info(f"Listed {len(objects)} transfers with prefix: {prefix}")
            return objects

        except ClientError as e:
            logger.error(f"Failed to list transfers: {e}")
            raise

    def delete_object(self, key: str) -> dict:
        """
        Delete an object from R2.

        Args:
            key: Object key to delete

        Returns:
            dict with deletion info (key, deleted)

        Raises:
            ClientError: If deletion fails
        """
        try:
            logger.info(f"Deleting R2 key: {key}")
            self.client.delete_object(Bucket=self.config.bucket, Key=key)

            return {
                "key": key,
                "deleted": True,
            }

        except ClientError as e:
            logger.error(f"Failed to delete object: {e}")
            raise

    def get_object_metadata(self, key: str) -> dict:
        """
        Get metadata for an object without downloading it.

        Args:
            key: Object key

        Returns:
            dict with object metadata

        Raises:
            ClientError: If object doesn't exist or request fails
        """
        try:
            response = self.client.head_object(Bucket=self.config.bucket, Key=key)

            return {
                "key": key,
                "size": response["ContentLength"],
                "last_modified": response["LastModified"].isoformat(),
                "etag": response["ETag"].strip('"'),
                "metadata": response.get("Metadata", {}),
                "content_type": response.get("ContentType"),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"Object not found: {key}")
            logger.error(f"Failed to get object metadata: {e}")
            raise

    def object_exists(self, key: str) -> bool:
        """
        Check if an object exists in R2.

        Args:
            key: Object key to check

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.config.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise


class TransferManager:
    """High-level manager for file transfers via R2."""

    def __init__(self, r2_client: R2Client):
        """
        Initialize transfer manager.

        Args:
            r2_client: R2Client instance
        """
        self.r2 = r2_client

    def upload_for_transfer(
        self,
        local_path: Path | str,
        source_client: str,
        dest_client: str | None = None,
        expires_hours: int = 12,
    ) -> dict:
        """
        Upload a file for transfer and generate a presigned download URL.

        Args:
            local_path: Path to local file
            source_client: Source client UUID
            dest_client: Destination client UUID (optional)
            expires_hours: URL expiration time in hours (default: 12)

        Returns:
            dict with transfer info (transfer_id, download_url, expires_at, size)
        """
        local_path = Path(local_path)
        filename = local_path.name
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        transfer_id = f"{source_client}_{timestamp}_{filename}"

        # Object key with prefix for lifecycle policy
        key = f"transfers/{source_client}/{transfer_id}"

        # Metadata to attach
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=expires_hours)
        metadata = {
            "source_client": source_client,
            "uploaded_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "filename": filename,
        }
        if dest_client:
            metadata["dest_client"] = dest_client

        # Upload file
        upload_result = self.r2.upload_file(local_path, key, metadata)

        # Generate presigned URL
        expires_seconds = expires_hours * 3600
        download_url = self.r2.generate_presigned_url(key, expires_in=expires_seconds)

        return {
            "transfer_id": transfer_id,
            "key": key,
            "download_url": download_url,
            "expires_at": expires_at.isoformat(),
            "size": upload_result["size"],
            "filename": filename,
            "source_client": source_client,
            "dest_client": dest_client,
        }

    def download_from_url(
        self,
        download_url: str,
        local_path: Path | str,
    ) -> dict:
        """
        Download a file from a presigned URL.

        Args:
            download_url: Presigned URL
            local_path: Destination path

        Returns:
            dict with download info
        """
        import httpx

        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading from presigned URL to {local_path}")

        with httpx.stream("GET", download_url) as response:
            response.raise_for_status()

            size = 0
            with open(local_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    size += len(chunk)

        logger.info(f"Download complete: {local_path} ({size} bytes)")
        return {
            "local_path": str(local_path),
            "size": size,
        }

    def list_pending_transfers(
        self,
        client_id: str | None = None,
    ) -> list[dict]:
        """
        List pending transfers, optionally filtered by client.

        Args:
            client_id: Filter by source client UUID (optional)

        Returns:
            List of pending transfers
        """
        prefix = f"transfers/{client_id}/" if client_id else "transfers/"
        return self.r2.list_transfers(prefix=prefix)

    def delete_transfer(self, transfer_id: str, source_client: str) -> dict:
        """
        Delete a transfer.

        Args:
            transfer_id: Transfer ID
            source_client: Source client UUID

        Returns:
            dict with deletion result
        """
        key = f"transfers/{source_client}/{transfer_id}"
        return self.r2.delete_object(key)


def create_r2_client() -> R2Client | None:
    """
    Create R2 client from environment variables.

    Returns:
        R2Client if configured, None otherwise
    """
    config = R2Config.from_env()
    if config is None:
        logger.warning("R2 not configured (missing environment variables)")
        return None

    try:
        client = R2Client(config)
        # Test connectivity by listing objects in the bucket (R2 doesn't support list_buckets)
        client.client.list_objects_v2(Bucket=config.bucket, MaxKeys=1)
        logger.info(f"R2 client initialized (bucket: {config.bucket})")
        return client
    except NoCredentialsError:
        logger.error("R2 credentials invalid")
        return None
    except ClientError as e:
        logger.error(f"Failed to initialize R2 client: {e}")
        return None
