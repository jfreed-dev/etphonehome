"""Tests for GitHub Secrets configuration.

This module verifies that all required secrets are configured in GitHub Secrets
before deployment. Run with GITHUB_TOKEN environment variable set.
"""

import os
import subprocess

import pytest

# Required secrets for deployment
REQUIRED_SECRETS = [
    # Cloudflare R2 Storage
    "REACH_R2_ACCOUNT_ID",
    "REACH_R2_ACCESS_KEY",
    "REACH_R2_SECRET_KEY",
    "REACH_R2_BUCKET",
    "REACH_R2_REGION",
    # Infrastructure
    "CF_DNS_API_TOKEN",
    "REACH_API_KEY",
    "REACH_R2_API_TOKEN",
    "TRAEFIK_DASHBOARD_AUTH",
    "REACH_GH_TOKEN",
    # Hostinger deployment
    "HOSTINGER_API_KEY",
    "HOSTINGER_SERVER_IP",
    "SSH_PRIVATE_KEY",
    "SSH_PUBLIC_KEY",
]

GITHUB_REPO = "jfreed-dev/reach"


def get_github_secrets():
    """Get list of secret names from GitHub using gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "secret", "list", "--repo", GITHUB_REPO],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse output: "SECRET_NAME\tDATE"
        secrets = []
        for line in result.stdout.strip().split("\n"):
            if line:
                secrets.append(line.split("\t")[0])
        return secrets
    except subprocess.CalledProcessError as e:
        pytest.skip(f"Cannot access GitHub secrets: {e}")
    except FileNotFoundError:
        pytest.skip("gh CLI not installed")


class TestGitHubSecrets:
    """Tests for GitHub Secrets configuration."""

    @pytest.fixture
    def github_secrets(self):
        """Get current GitHub secrets."""
        return get_github_secrets()

    def test_all_required_secrets_exist(self, github_secrets):
        """Verify all required secrets are configured in GitHub."""
        missing = [s for s in REQUIRED_SECRETS if s not in github_secrets]
        assert not missing, f"Missing GitHub secrets: {missing}"

    @pytest.mark.parametrize("secret_name", REQUIRED_SECRETS)
    def test_individual_secret_exists(self, github_secrets, secret_name):
        """Verify each required secret exists."""
        assert secret_name in github_secrets, f"Secret {secret_name} not found"


class TestEnvironmentSecrets:
    """Tests for secrets available via environment variables.

    These tests verify secrets are properly injected during CI/CD.
    Only run in GitHub Actions environment.
    """

    @pytest.fixture
    def is_ci(self):
        """Check if running in CI environment."""
        return os.environ.get("CI") == "true"

    def test_r2_secrets_in_environment(self, is_ci):
        """Verify R2 secrets are available in CI environment."""
        if not is_ci:
            pytest.skip("Not running in CI environment")

        r2_secrets = [
            "REACH_R2_ACCOUNT_ID",
            "REACH_R2_ACCESS_KEY",
            "REACH_R2_SECRET_KEY",
            "REACH_R2_BUCKET",
        ]
        for secret in r2_secrets:
            assert os.environ.get(secret), f"{secret} not set in environment"

    def test_api_key_in_environment(self, is_ci):
        """Verify API key is available in CI environment."""
        if not is_ci:
            pytest.skip("Not running in CI environment")

        assert os.environ.get("REACH_API_KEY"), "API key not set"
