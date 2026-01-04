#!/usr/bin/env python3
"""
ET Phone Home - Client Application

Creates a reverse SSH tunnel to the server, allowing remote access to this machine.
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from client.config import Config, ensure_config_dir, generate_client_id, DEFAULT_KEY_FILE
from client.agent import Agent
from client.tunnel import ReverseTunnel, generate_ssh_keypair

logger = logging.getLogger("phonehome")


def setup_logging(level: str):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    parser = argparse.ArgumentParser(
        description="ET Phone Home - Connect to remote Claude CLI instance"
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to config file"
    )
    parser.add_argument(
        "-s", "--server",
        help="Server host (overrides config)"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        help="Server port (overrides config)"
    )
    parser.add_argument(
        "-u", "--user",
        help="Server username (overrides config)"
    )
    parser.add_argument(
        "-k", "--key",
        type=Path,
        help="SSH private key file (overrides config)"
    )
    parser.add_argument(
        "-i", "--client-id",
        help="Client ID (overrides config)"
    )
    parser.add_argument(
        "--generate-key",
        action="store_true",
        help="Generate SSH keypair and exit"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize config directory with defaults"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Handle --generate-key
    if args.generate_key:
        key_path = args.key or DEFAULT_KEY_FILE
        ensure_config_dir()
        generate_ssh_keypair(key_path)
        pub_path = key_path.with_suffix(".pub")
        print(f"Generated SSH keypair:")
        print(f"  Private: {key_path}")
        print(f"  Public:  {pub_path}")
        print(f"\nAdd this public key to your server's authorized_keys:")
        print(pub_path.read_text())
        return 0

    # Handle --init
    if args.init:
        config_dir = ensure_config_dir()
        config = Config()
        config.client_id = generate_client_id()
        config.save()
        print(f"Initialized config directory: {config_dir}")
        print(f"Config file: {config_dir / 'config.yaml'}")
        print(f"\nNext steps:")
        print(f"1. Edit the config file with your server details")
        print(f"2. Run: phonehome --generate-key")
        print(f"3. Add the public key to your server")
        print(f"4. Run: phonehome")
        return 0

    # Load configuration
    config = Config.load(args.config)

    # Apply command-line overrides
    if args.server:
        config.server_host = args.server
    if args.port:
        config.server_port = args.port
    if args.user:
        config.server_user = args.user
    if args.key:
        config.key_file = str(args.key)
    if args.client_id:
        config.client_id = args.client_id
    if args.verbose:
        config.log_level = "DEBUG"

    # Ensure client ID exists
    if not config.client_id:
        config.client_id = generate_client_id()
        config.save()

    setup_logging(config.log_level)

    # Check for SSH key
    key_path = Path(config.key_file)
    if not key_path.exists():
        logger.error(f"SSH key not found: {key_path}")
        logger.error("Run 'phonehome --generate-key' to create one")
        return 1

    # Create agent
    agent = Agent(
        allowed_paths=config.allowed_paths if config.allowed_paths else None
    )

    # Create tunnel
    tunnel = ReverseTunnel(
        server_host=config.server_host,
        server_port=config.server_port,
        server_user=config.server_user,
        key_file=config.key_file,
        client_id=config.client_id,
        request_handler=agent.handle_request,
    )

    # Setup signal handlers
    shutdown_requested = False

    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        if shutdown_requested:
            logger.warning("Forced shutdown")
            sys.exit(1)
        shutdown_requested = True
        logger.info("Shutdown requested, disconnecting...")
        tunnel.disconnect()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Connection loop with reconnect
    reconnect_delay = config.reconnect_delay

    while not shutdown_requested:
        try:
            logger.info(f"Connecting to {config.server_host}:{config.server_port}")
            tunnel_port = tunnel.connect()
            logger.info(f"Connected! Tunnel port: {tunnel_port}")
            reconnect_delay = config.reconnect_delay  # Reset on success

            # Keep alive loop
            while tunnel.is_connected() and not shutdown_requested:
                time.sleep(5)
                if not tunnel.send_heartbeat():
                    logger.warning("Heartbeat failed, reconnecting...")
                    break

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Connection error: {e}")

        if not shutdown_requested:
            logger.info(f"Reconnecting in {reconnect_delay} seconds...")
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, config.max_reconnect_delay)

    tunnel.disconnect()
    logger.info("Goodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
