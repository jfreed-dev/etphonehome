#!/usr/bin/env python3
"""Generate SSH keypair for ET Phone Home client."""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.tunnel import generate_ssh_keypair
from client.config import DEFAULT_KEY_FILE, ensure_config_dir


def main():
    parser = argparse.ArgumentParser(
        description="Generate SSH keypair for ET Phone Home"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=DEFAULT_KEY_FILE,
        help=f"Output path for private key (default: {DEFAULT_KEY_FILE})"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Overwrite existing key"
    )

    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(f"Error: Key already exists: {args.output}")
        print("Use -f to overwrite")
        return 1

    ensure_config_dir()
    generate_ssh_keypair(args.output)

    pub_path = args.output.with_suffix(".pub")
    print(f"Generated SSH keypair:")
    print(f"  Private key: {args.output}")
    print(f"  Public key:  {pub_path}")
    print()
    print("Add this public key to your server's authorized_keys:")
    print()
    print(pub_path.read_text())

    return 0


if __name__ == "__main__":
    sys.exit(main())
