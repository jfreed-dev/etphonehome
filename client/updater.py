"""Client auto-update mechanism."""

import hashlib
import json
import logging
import os
import platform
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

from shared.version import __version__, UPDATE_URL

logger = logging.getLogger(__name__)


def get_current_version() -> str:
    """Return current client version."""
    return __version__


def get_platform_key() -> str:
    """Return platform key for downloads (e.g., 'linux-x86_64')."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x86_64"
        elif machine in ("aarch64", "arm64"):
            return "linux-aarch64"
    elif system == "windows":
        return "windows-amd64"
    elif system == "darwin":
        if machine in ("x86_64", "amd64"):
            return "darwin-x86_64"
        elif machine in ("aarch64", "arm64"):
            return "darwin-aarch64"

    raise RuntimeError(f"Unsupported platform: {system}-{machine}")


def _compare_versions(v1: str, v2: str) -> int:
    """Compare version strings. Returns >0 if v1 > v2, <0 if v1 < v2, 0 if equal."""
    def parse(v):
        # Handle versions like "0.1.0" or "0.1.0-beta"
        base = v.split("-")[0]
        return tuple(int(x) for x in base.split("."))

    p1, p2 = parse(v1), parse(v2)
    if p1 > p2:
        return 1
    elif p1 < p2:
        return -1
    return 0


def check_for_update(url: str = UPDATE_URL) -> Optional[dict]:
    """Check if a newer version is available.

    Returns update info dict if update available, None otherwise.
    """
    try:
        logger.debug(f"Checking for updates at {url}")
        req = urllib.request.Request(url, headers={"User-Agent": f"phonehome/{__version__}"})
        with urllib.request.urlopen(req, timeout=10) as response:
            manifest = json.loads(response.read().decode("utf-8"))

        remote_version = manifest["version"]
        logger.debug(f"Remote version: {remote_version}, local version: {__version__}")

        if _compare_versions(remote_version, __version__) > 0:
            platform_key = get_platform_key()
            if platform_key in manifest["downloads"]:
                return {
                    "version": remote_version,
                    "download": manifest["downloads"][platform_key],
                    "changelog": manifest.get("changelog", ""),
                }
            else:
                logger.warning(f"No download available for platform: {platform_key}")
    except Exception as e:
        logger.warning(f"Update check failed: {e}")

    return None


def _get_install_dir() -> Path:
    """Get the installation directory based on platform."""
    system = platform.system().lower()

    if system == "linux":
        return Path.home() / ".local" / "share" / "phonehome"
    elif system == "windows":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "phonehome"
    elif system == "darwin":
        return Path.home() / "Library" / "Application Support" / "phonehome"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def perform_update(update_info: dict) -> bool:
    """Download and install update.

    Returns True if update was successful and restart is needed.
    """
    download = update_info["download"]
    url = download["url"]
    expected_hash = download.get("sha256")

    logger.info(f"Downloading update v{update_info['version']} from {url}")

    # Download to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"phonehome/{__version__}"})
            with urllib.request.urlopen(req, timeout=300) as response:
                shutil.copyfileobj(response, tmp)
            tmp_path = Path(tmp.name)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    try:
        # Verify checksum if provided
        if expected_hash and expected_hash != "placeholder":
            actual_hash = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                logger.error(f"Checksum mismatch: expected {expected_hash}, got {actual_hash}")
                return False
            logger.debug("Checksum verified")

        # Platform-specific update
        system = platform.system().lower()
        if system == "linux":
            return _update_linux(tmp_path)
        elif system == "windows":
            return _update_windows(tmp_path, update_info["version"])
        elif system == "darwin":
            return _update_linux(tmp_path)  # Same process as Linux
        else:
            logger.error(f"Unsupported platform for update: {system}")
            return False
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


def _update_linux(archive_path: Path) -> bool:
    """Update on Linux - extract and replace installation."""
    import tarfile

    install_dir = _get_install_dir()

    logger.info(f"Updating installation at {install_dir}")

    # Extract to temp directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(tmp_path)
        except Exception as e:
            logger.error(f"Failed to extract archive: {e}")
            return False

        extracted = tmp_path / "phonehome"
        if not extracted.exists():
            logger.error("Invalid archive: phonehome directory not found")
            return False

        # Backup current installation
        backup_dir = install_dir.parent / f"phonehome.backup.{os.getpid()}"
        if install_dir.exists():
            try:
                shutil.move(str(install_dir), str(backup_dir))
            except Exception as e:
                logger.error(f"Failed to backup current installation: {e}")
                return False

        # Install new version
        try:
            shutil.copytree(extracted, install_dir)
        except Exception as e:
            logger.error(f"Failed to install new version: {e}")
            # Restore backup
            if backup_dir.exists():
                shutil.move(str(backup_dir), str(install_dir))
            return False

        # Remove backup on success
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)

    logger.info("Update installed successfully")
    return True


def _update_windows(archive_path: Path, version: str) -> bool:
    """Update on Windows - extract and replace installation."""
    import zipfile

    install_dir = _get_install_dir()

    logger.info(f"Updating installation at {install_dir}")

    # Extract to temp directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(tmp_path)
        except Exception as e:
            logger.error(f"Failed to extract archive: {e}")
            return False

        extracted = tmp_path / "phonehome"
        if not extracted.exists():
            logger.error("Invalid archive: phonehome directory not found")
            return False

        # On Windows, we can't replace running executables directly
        # Create an update script that runs after we exit
        update_script = install_dir.parent / "phonehome_update.cmd"
        script_content = f"""@echo off
timeout /t 2 /nobreak > nul
rmdir /s /q "{install_dir}"
xcopy /e /i /y "{extracted}" "{install_dir}"
rmdir /s /q "{tmp_path}"
del "%~f0"
"""
        try:
            update_script.write_text(script_content)
            # Schedule the script to run
            os.system(f'start /min cmd /c "{update_script}"')
        except Exception as e:
            logger.error(f"Failed to create update script: {e}")
            return False

    logger.info("Update scheduled - restart required")
    return True


def auto_update() -> bool:
    """Check for updates and apply if available.

    Returns True if an update was applied (restart needed).
    """
    # Skip if updates are disabled
    if os.environ.get("PHONEHOME_NO_UPDATE"):
        logger.debug("Auto-update disabled via PHONEHOME_NO_UPDATE")
        return False

    update_info = check_for_update()
    if not update_info:
        logger.debug("No update available")
        return False

    logger.info(f"Update available: {update_info['version']} (current: {__version__})")

    if perform_update(update_info):
        return True

    return False
