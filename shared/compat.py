"""Backwards-compatibility helpers for the ET Phone Home → Reach rename."""

import os
import shutil
from pathlib import Path


def env(new: str, old: str, default=None) -> str | None:
    """Read an environment variable with fallback to the old name.

    During the transition period, deployments may still export the old
    ``ETPHONEHOME_*`` / ``PHONEHOME_*`` variable names.  This helper
    checks the new ``REACH_*`` name first, then falls back to the old
    name, and finally returns *default*.
    """
    return os.environ.get(new) or os.environ.get(old) or default


def migrate_config_dir(new_dir: Path, old_dir: Path) -> None:
    """Copy an old config directory to the new location if needed.

    If *new_dir* already exists the migration is skipped.  The old
    directory is left in place so older client versions still work.
    """
    if new_dir.exists() or not old_dir.exists():
        return

    shutil.copytree(old_dir, new_dir)
