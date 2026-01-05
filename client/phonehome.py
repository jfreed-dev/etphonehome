#!/usr/bin/env python3
"""
ET Phone Home - Client Application

Creates a reverse SSH tunnel to the server, allowing remote access to this machine.
"""

import argparse
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid as uuid_mod
from pathlib import Path

from client.agent import Agent
from client.config import DEFAULT_KEY_FILE, Config, ensure_config_dir, generate_client_id
from client.tunnel import ReverseTunnel, generate_ssh_keypair
from client.updater import auto_update, get_current_version

logger = logging.getLogger("phonehome")


def setup_logging(level: str):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(
        description="ET Phone Home - Connect to remote Claude CLI instance"
    )
    parser.add_argument("-c", "--config", type=Path, help="Path to config file")
    parser.add_argument("-s", "--server", help="Server host (overrides config)")
    parser.add_argument("-p", "--port", type=int, help="Server port (overrides config)")
    parser.add_argument("-u", "--user", help="Server username (overrides config)")
    parser.add_argument("-k", "--key", type=Path, help="SSH private key file (overrides config)")
    parser.add_argument("-i", "--client-id", help="Client ID (overrides config)")
    parser.add_argument("--generate-key", action="store_true", help="Generate SSH keypair and exit")
    parser.add_argument(
        "--init", action="store_true", help="Initialize config directory with defaults"
    )
    parser.add_argument("--name", help="Display name for this client")
    parser.add_argument(
        "--purpose", help="Purpose/role of this client (e.g., 'Development', 'Production')"
    )
    parser.add_argument("--tags", nargs="+", help="Tags for this client")
    parser.add_argument("--show-uuid", action="store_true", help="Show client UUID and exit")
    parser.add_argument("--list-clients", action="store_true", help="List all clients on the server")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Handle --generate-key
    if args.generate_key:
        key_path = args.key or DEFAULT_KEY_FILE
        ensure_config_dir()
        generate_ssh_keypair(key_path)
        pub_path = key_path.with_suffix(".pub")
        print("Generated SSH keypair:")
        print(f"  Private: {key_path}")
        print(f"  Public:  {pub_path}")
        print("\nAdd this public key to your server's authorized_keys:")
        print(pub_path.read_text())
        return 0

    # Handle --init
    if args.init:
        config_dir = ensure_config_dir()
        config = Config()
        config.client_id = generate_client_id()
        config.uuid = str(uuid_mod.uuid4())

        # Required: display_name
        if args.name:
            config.display_name = args.name
        else:
            while not config.display_name:
                config.display_name = input("Display name (e.g., 'My Laptop'): ").strip()
                if not config.display_name:
                    print("Display name is required.")

        # Required: purpose
        if args.purpose:
            config.purpose = args.purpose
        else:
            while not config.purpose:
                config.purpose = input(
                    "Purpose (e.g., 'Development', 'CI Runner', 'Production'): "
                ).strip()
                if not config.purpose:
                    print("Purpose is required.")

        # Optional: tags
        if args.tags:
            config.tags = args.tags
        else:
            tags_input = input("Tags (comma-separated, optional): ").strip()
            config.tags = [t.strip() for t in tags_input.split(",") if t.strip()]

        config.save()
        print(f"\nInitialized config directory: {config_dir}")
        print(f"Config file: {config_dir / 'config.yaml'}")
        print("\nClient identity:")
        print(f"  UUID: {config.uuid}")
        print(f"  Name: {config.display_name}")
        print(f"  Purpose: {config.purpose}")
        if config.tags:
            print(f"  Tags: {', '.join(config.tags)}")
        print("\nNext steps:")
        print("1. Edit the config file with your server details")
        print("2. Run: phonehome --generate-key")
        print("3. Add the public key to your server")
        print("4. Run: phonehome")
        return 0

    # Handle --show-uuid
    if args.show_uuid:
        config = Config.load(args.config)
        if config.uuid:
            print(f"UUID: {config.uuid}")
            print(f"Name: {config.display_name or '(not set)'}")
            print(f"Purpose: {config.purpose or '(not set)'}")
            if config.tags:
                print(f"Tags: {', '.join(config.tags)}")
        else:
            print("No UUID assigned. Run 'phonehome --init' first.")
        return 0

    # Handle --list-clients
    if args.list_clients:
        config = Config.load(args.config)
        if not config.server_host:
            print("Error: No server configured. Run 'phonehome --init' first.")
            return 1

        key_path = Path(config.key_file)
        if not key_path.exists():
            print(f"Error: SSH key not found: {key_path}")
            return 1

        # Find a free local port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            local_port = s.getsockname()[1]

        # Start SSH tunnel in background
        ssh_cmd = [
            "ssh",
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-i", str(key_path),
            "-p", str(config.server_port),
            "-L", f"{local_port}:127.0.0.1:8765",
            f"{config.server_user}@{config.server_host}",
            "-N",
        ]

        ssh_proc = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        try:
            # Wait for tunnel to establish
            time.sleep(2)

            if ssh_proc.poll() is not None:
                stderr = ssh_proc.stderr.read().decode() if ssh_proc.stderr else ""
                print(f"Error: SSH tunnel failed: {stderr}")
                return 1

            # Query the clients endpoint
            url = f"http://127.0.0.1:{local_port}/clients"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            # Display results
            clients = data.get("clients", [])
            online = data.get("online_count", 0)
            total = data.get("total_count", 0)

            print(f"Clients: {online} online / {total} total\n")

            if not clients:
                print("No clients registered.")
            else:
                for client in clients:
                    status = "ONLINE" if client.get("online") else "offline"
                    name = client.get("display_name", "unnamed")
                    uuid = client.get("uuid", "?")[:8]
                    purpose = client.get("purpose", "")
                    tags = client.get("tags", [])

                    status_icon = "\033[32m●\033[0m" if client.get("online") else "\033[90m○\033[0m"
                    print(f"  {status_icon} {name} ({uuid}...)")
                    if purpose:
                        print(f"      Purpose: {purpose}")
                    if tags:
                        print(f"      Tags: {', '.join(tags)}")
                    last_seen = client.get("last_seen", "")
                    if last_seen and not client.get("online"):
                        print(f"      Last seen: {last_seen}")
                    print()

        except urllib.error.URLError as e:
            print(f"Error: Could not connect to server API: {e}")
            return 1
        except Exception as e:
            print(f"Error: {e}")
            return 1
        finally:
            ssh_proc.terminate()
            ssh_proc.wait(timeout=5)

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
    if args.name:
        config.display_name = args.name
    if args.purpose:
        config.purpose = args.purpose
    if args.tags:
        config.tags = args.tags
    if args.verbose:
        config.log_level = "DEBUG"

    # Ensure client ID exists
    if not config.client_id:
        config.client_id = generate_client_id()
        config.save()

    setup_logging(config.log_level)

    logger.info(f"ET Phone Home v{get_current_version()}")

    # Check for updates
    if auto_update():
        logger.info("Update installed. Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # Check for SSH key
    key_path = Path(config.key_file)
    if not key_path.exists():
        logger.error(f"SSH key not found: {key_path}")
        logger.error("Run 'phonehome --generate-key' to create one")
        return 1

    # Create agent
    agent = Agent(allowed_paths=config.allowed_paths if config.allowed_paths else None)

    # Ensure UUID exists for identity tracking
    if not config.uuid:
        config.uuid = str(uuid_mod.uuid4())
        config.save()
        logger.info(f"Generated new UUID: {config.uuid}")

    # Create tunnel
    tunnel = ReverseTunnel(
        config=config,
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
