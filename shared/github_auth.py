"""GitHub Device Flow Authentication for secure token acquisition."""

import json
import time
import urllib.parse
import urllib.request

from shared.secrets_manager import SecureLocalStorage


class GitHubDeviceFlow:
    """Handle GitHub OAuth Device Flow authentication."""

    # GitHub OAuth App client ID for ET Phone Home
    # This is a public client ID and is safe to commit
    CLIENT_ID = "Ov23liXZQDbxJxQqYR7z"

    def __init__(self):
        """Initialize device flow handler."""
        self.device_code: str | None = None
        self.user_code: str | None = None
        self.verification_uri: str | None = None
        self.expires_in: int = 0
        self.interval: int = 5

    def _make_request(self, url: str, data: dict, headers: dict | None = None) -> dict:
        """Make HTTP POST request and return JSON response."""
        if headers is None:
            headers = {}

        headers["Accept"] = "application/json"
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        request = urllib.request.Request(url, data=encoded_data, headers=headers)
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def _make_get_request(self, url: str, headers: dict | None = None) -> dict:
        """Make HTTP GET request and return JSON response."""
        if headers is None:
            headers = {}

        headers["Accept"] = "application/json"
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def start_device_flow(self, scopes: list[str] | None = None) -> dict:
        """
        Start the device authorization flow.

        Args:
            scopes: List of OAuth scopes to request (default: ["repo"])

        Returns:
            dict with user_code, verification_uri, and expires_in

        Example:
            {
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900
            }
        """
        if scopes is None:
            scopes = ["repo"]  # Required for GitHub Secrets access

        data = self._make_request(
            "https://github.com/login/device/code",
            {
                "client_id": self.CLIENT_ID,
                "scope": " ".join(scopes),
            },
        )

        self.device_code = data["device_code"]
        self.user_code = data["user_code"]
        self.verification_uri = data["verification_uri"]
        self.expires_in = data["expires_in"]
        self.interval = data.get("interval", 5)

        return {
            "user_code": self.user_code,
            "verification_uri": self.verification_uri,
            "expires_in": self.expires_in,
        }

    def poll_for_token(self, timeout: int = 900) -> str | None:
        """
        Poll GitHub for access token after user authorization.

        Args:
            timeout: Maximum time to wait in seconds (default: 900 = 15 minutes)

        Returns:
            Access token if authorized, None if timeout or denied
        """
        if not self.device_code:
            raise RuntimeError("Device flow not started. Call start_device_flow() first.")

        start_time = time.time()
        while time.time() - start_time < timeout:
            data = self._make_request(
                "https://github.com/login/oauth/access_token",
                {
                    "client_id": self.CLIENT_ID,
                    "device_code": self.device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )

            if "access_token" in data:
                return data["access_token"]

            error = data.get("error")
            if error == "authorization_pending":
                # User hasn't authorized yet, keep polling
                time.sleep(self.interval)
                continue
            elif error == "slow_down":
                # Increase polling interval
                self.interval += 5
                time.sleep(self.interval)
                continue
            elif error == "expired_token":
                # Device code expired
                return None
            elif error == "access_denied":
                # User denied authorization
                return None
            else:
                # Unknown error
                raise RuntimeError(f"GitHub device flow error: {error}")

        # Timeout
        return None

    def authenticate_and_store(self) -> bool:
        """
        Complete full device flow and store token locally.

        Returns:
            True if successful, False otherwise
        """
        print("🔐 GitHub Device Flow Authentication")
        print("=" * 50)
        print()

        # Start device flow
        flow_data = self.start_device_flow()

        print(f"📱 Please visit: {flow_data['verification_uri']}")
        print(f"🔢 Enter code: {flow_data['user_code']}")
        print()
        print(f"⏱️  Code expires in {flow_data['expires_in'] // 60} minutes")
        print()
        print("Waiting for authorization...", end="", flush=True)

        # Poll for token
        token = self.poll_for_token()

        if token is None:
            print(" ❌ FAILED")
            print()
            print("Authorization failed, expired, or was denied.")
            return False

        print(" ✅ SUCCESS")
        print()

        # Verify token works
        print("Verifying token...", end="", flush=True)
        user_data = self._make_get_request(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}"},
        )

        username = user_data.get("login", "Unknown")
        print(" ✅ SUCCESS")
        print()
        print(f"👤 Authenticated as: {username}")
        print()

        # Store token securely
        print("Storing token securely...", end="", flush=True)
        storage = SecureLocalStorage()
        storage.store_token(token)
        print(" ✅ DONE")
        print()
        print(f"Token stored at: {storage.storage_path}")
        print("File permissions: 0600 (owner read/write only)")
        print()
        print("✅ Setup complete! You can now use GitHub Secrets integration.")
        print()

        return True


def main():
    """Interactive CLI for GitHub device flow authentication."""
    import sys

    flow = GitHubDeviceFlow()

    try:
        success = flow.authenticate_and_store()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print()
        print()
        print("❌ Authentication cancelled by user")
        sys.exit(1)
    except Exception as e:
        print()
        print()
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
