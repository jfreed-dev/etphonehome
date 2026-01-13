#!/usr/bin/env python3
"""
Publish ET Phone Home release to Cloudflare R2.

This script uploads build artifacts to R2 and creates the version.json manifest
for client auto-updates.

Usage:
    python scripts/publish_release_r2.py [--version VERSION] [--changelog TEXT]

Environment variables required:
    ETPHONEHOME_R2_ACCOUNT_ID
    ETPHONEHOME_R2_ACCESS_KEY
    ETPHONEHOME_R2_SECRET_KEY
    ETPHONEHOME_R2_BUCKET

Optional:
    ETPHONEHOME_R2_PUBLIC_URL - Custom public URL base (default: R2 public bucket URL)
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.r2_releases import create_release_manager  # noqa: E402
from shared.version import __version__  # noqa: E402


def get_artifacts(dist_dir: Path) -> dict[str, Path]:
    """Find build artifacts in dist directory."""
    artifacts = {}

    # Define expected artifact patterns
    patterns = {
        "linux-x86_64": "phonehome-linux-x86_64.tar.gz",
        "linux-aarch64": "phonehome-linux-aarch64.tar.gz",
        "windows-amd64": "phonehome-windows-amd64.zip",
        "darwin-x86_64": "phonehome-darwin-x86_64.tar.gz",
        "darwin-aarch64": "phonehome-darwin-aarch64.tar.gz",
    }

    for platform, filename in patterns.items():
        artifact_path = dist_dir / filename
        if artifact_path.exists():
            artifacts[platform] = artifact_path
            print(f"  Found: {filename}")
        else:
            print(f"  Missing: {filename}")

    return artifacts


def main():
    parser = argparse.ArgumentParser(
        description="Publish ET Phone Home release to R2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--version",
        "-v",
        default=__version__,
        help=f"Version to publish (default: {__version__})",
    )
    parser.add_argument(
        "--changelog",
        "-c",
        default="",
        help="Changelog text for this release",
    )
    parser.add_argument(
        "--dist-dir",
        "-d",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="Directory containing build artifacts (default: dist/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        dest="list_releases",
        help="List existing releases in R2",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Show the current latest version in R2",
    )

    args = parser.parse_args()

    # Check R2 configuration
    required_vars = [
        "ETPHONEHOME_R2_ACCOUNT_ID",
        "ETPHONEHOME_R2_ACCESS_KEY",
        "ETPHONEHOME_R2_SECRET_KEY",
        "ETPHONEHOME_R2_BUCKET",
    ]

    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print("Error: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nSet these variables or source your .env file:")
        print("  source deploy/docker/.env")
        sys.exit(1)

    # Create release manager
    manager = create_release_manager()
    if manager is None:
        print("Error: Failed to initialize R2 release manager")
        sys.exit(1)

    # Handle list/latest commands
    if args.list_releases:
        print("\nReleases in R2:")
        releases = manager.list_releases()
        if not releases:
            print("  (none)")
        for r in releases:
            print(f"  {r['version']}: {r['url']}")
        return

    if args.latest:
        print("\nLatest version in R2:")
        latest = manager.get_latest_version()
        if latest:
            import json

            print(json.dumps(latest, indent=2))
        else:
            print("  (not found)")
        return

    # Find artifacts
    print(f"\nSearching for artifacts in: {args.dist_dir}")
    artifacts = get_artifacts(args.dist_dir)

    if not artifacts:
        print("\nError: No build artifacts found!")
        print("Run the build first:")
        print("  ./build/portable/package_linux.sh")
        sys.exit(1)

    print(f"\nFound {len(artifacts)} artifact(s)")

    if args.dry_run:
        print("\n[DRY RUN] Would upload:")
        for platform, path in artifacts.items():
            print(f"  {platform}: {path}")
        print(f"\nVersion: {args.version}")
        print(f"Changelog: {args.changelog or '(none)'}")
        return

    # Upload release
    print(f"\nPublishing release v{args.version} to R2...")
    try:
        result = manager.upload_release(
            version=args.version,
            artifacts=artifacts,
            changelog=args.changelog,
        )

        print("\n" + "=" * 60)
        print("Release published successfully!")
        print("=" * 60)
        print(f"\nVersion: {result['version']}")
        print(f"Release date: {result['release_date']}")
        print("\nUpdate URL (for clients):")
        print(f"  {result['version_json_url']}")
        print("\nRelease directory:")
        print(f"  {result['release_url']}")
        print("\nUploaded files:")
        for f in result["uploaded_files"]:
            print(f"  {f['platform']}: {f['url']}")

        print("\n" + "-" * 60)
        print("To configure clients to use this update server, set:")
        print(f"  PHONEHOME_UPDATE_URL={result['version_json_url']}")
        print("-" * 60)

    except Exception as e:
        print(f"\nError: Failed to publish release: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
