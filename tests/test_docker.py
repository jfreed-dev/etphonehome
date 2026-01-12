"""
Tests for Docker deployment configurations.

These tests validate:
- Dockerfile syntax and best practices
- docker-compose configuration validity
- Container runtime behavior (requires Docker daemon)
"""

import subprocess
from pathlib import Path

import pytest
import yaml

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DOCKER_DIR = PROJECT_ROOT / "deploy" / "docker"
WEB_DIR = PROJECT_ROOT / "web"


def docker_available() -> bool:
    """Check if Docker daemon is available."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# Skip markers
requires_docker = pytest.mark.skipif(
    not docker_available(),
    reason="Docker daemon not available",
)


class TestDockerfileStructure:
    """Test Dockerfile structure and best practices."""

    @pytest.fixture
    def dockerfiles(self) -> list[Path]:
        """Get all Dockerfiles in the project."""
        files = list(DOCKER_DIR.glob("Dockerfile.*"))
        if (WEB_DIR / "Dockerfile").exists():
            files.append(WEB_DIR / "Dockerfile")
        return files

    def test_dockerfiles_exist(self, dockerfiles):
        """Verify Dockerfiles exist."""
        assert len(dockerfiles) >= 1, "No Dockerfiles found"

    @pytest.mark.parametrize(
        "dockerfile_name",
        ["Dockerfile.simple", "Dockerfile.server", "Dockerfile.client"],
    )
    def test_dockerfile_exists(self, dockerfile_name):
        """Test that expected Dockerfiles exist."""
        dockerfile = DOCKER_DIR / dockerfile_name
        assert dockerfile.exists(), f"{dockerfile_name} not found"

    def test_dockerfile_has_from(self, dockerfiles):
        """Verify all Dockerfiles have FROM instruction."""
        for dockerfile in dockerfiles:
            content = dockerfile.read_text()
            assert "FROM " in content, f"{dockerfile.name} missing FROM instruction"

    def test_dockerfile_has_nonroot_user(self, dockerfiles):
        """Verify Dockerfiles create and use non-root user."""
        for dockerfile in dockerfiles:
            content = dockerfile.read_text()
            # Check for user creation
            has_useradd = "useradd" in content or "adduser" in content
            has_user = "USER " in content
            assert has_useradd, f"{dockerfile.name} should create a non-root user"
            assert has_user, f"{dockerfile.name} should switch to non-root user"

    def test_dockerfile_has_healthcheck(self):
        """Verify server Dockerfiles have HEALTHCHECK."""
        for name in ["Dockerfile.simple", "Dockerfile.server"]:
            dockerfile = DOCKER_DIR / name
            if dockerfile.exists():
                content = dockerfile.read_text()
                assert "HEALTHCHECK" in content, f"{name} should have HEALTHCHECK"

    def test_dockerfile_no_latest_tag(self, dockerfiles):
        """Verify FROM doesn't use :latest tag."""
        for dockerfile in dockerfiles:
            content = dockerfile.read_text()
            lines = content.split("\n")
            for line in lines:
                if line.strip().startswith("FROM "):
                    assert ":latest" not in line, f"{dockerfile.name} should not use :latest tag"

    def test_dockerfile_apt_no_install_recommends(self, dockerfiles):
        """Verify apt-get uses --no-install-recommends."""
        for dockerfile in dockerfiles:
            content = dockerfile.read_text()
            if "apt-get install" in content:
                # Find all apt-get install lines
                for line in content.split("\n"):
                    if "apt-get install" in line and "--no-install-recommends" not in line:
                        # Allow if it's in a continuation or the flag is on previous line
                        if "nodejs" in line:
                            # Special case for nodesource setup
                            continue
                        pytest.fail(
                            f"{dockerfile.name}: apt-get install should use --no-install-recommends"
                        )

    def test_dockerfile_cleanup_apt_lists(self, dockerfiles):
        """Verify apt lists are cleaned up."""
        for dockerfile in dockerfiles:
            content = dockerfile.read_text()
            if "apt-get install" in content:
                assert (
                    "rm -rf /var/lib/apt/lists/*" in content
                ), f"{dockerfile.name} should clean apt lists"

    def test_dockerfile_python_unbuffered(self):
        """Verify Python containers set PYTHONUNBUFFERED."""
        for name in ["Dockerfile.simple", "Dockerfile.server", "Dockerfile.client"]:
            dockerfile = DOCKER_DIR / name
            if dockerfile.exists():
                content = dockerfile.read_text()
                assert (
                    "PYTHONUNBUFFERED" in content
                ), f"{name} should set PYTHONUNBUFFERED for proper logging"


class TestDockerComposeConfig:
    """Test docker-compose configuration files."""

    @pytest.fixture
    def compose_files(self) -> list[Path]:
        """Get all docker-compose files."""
        return list(DOCKER_DIR.glob("docker-compose*.yml"))

    def test_compose_files_exist(self, compose_files):
        """Verify docker-compose files exist."""
        assert len(compose_files) >= 1, "No docker-compose files found"

    def test_compose_valid_yaml(self, compose_files):
        """Verify docker-compose files are valid YAML."""
        for compose_file in compose_files:
            try:
                content = yaml.safe_load(compose_file.read_text())
                assert content is not None, f"{compose_file.name} is empty"
                assert "services" in content, f"{compose_file.name} missing services key"
            except yaml.YAMLError as e:
                pytest.fail(f"{compose_file.name} is not valid YAML: {e}")

    def test_compose_services_have_image_or_build(self, compose_files):
        """Verify services have image or build directive."""
        for compose_file in compose_files:
            content = yaml.safe_load(compose_file.read_text())
            services = content.get("services", {})
            for service_name, service_config in services.items():
                has_image = "image" in service_config
                has_build = "build" in service_config
                assert (
                    has_image or has_build
                ), f"{compose_file.name}: service '{service_name}' needs image or build"

    def test_compose_no_privileged(self, compose_files):
        """Verify no services run in privileged mode."""
        for compose_file in compose_files:
            content = yaml.safe_load(compose_file.read_text())
            services = content.get("services", {})
            for service_name, service_config in services.items():
                assert (
                    service_config.get("privileged") is not True
                ), f"{compose_file.name}: service '{service_name}' should not be privileged"

    def test_compose_has_healthcheck(self, compose_files):
        """Verify main services have healthcheck."""
        for compose_file in compose_files:
            content = yaml.safe_load(compose_file.read_text())
            services = content.get("services", {})
            # Check main service (etphonehome, server, or backend)
            main_services = ["etphonehome", "server", "backend"]
            for service_name in main_services:
                if service_name in services:
                    service = services[service_name]
                    assert (
                        "healthcheck" in service
                    ), f"{compose_file.name}: {service_name} should have healthcheck"

    def test_compose_simple_has_network_host(self):
        """Verify docker-compose.simple.yml uses host network."""
        simple_file = DOCKER_DIR / "docker-compose.simple.yml"
        if simple_file.exists():
            content = yaml.safe_load(simple_file.read_text())
            services = content.get("services", {})
            main_service = services.get("etphonehome", {})
            assert (
                main_service.get("network_mode") == "host"
            ), "docker-compose.simple.yml should use network_mode: host"


class TestHadolintConfig:
    """Test hadolint configuration."""

    def test_hadolint_config_exists(self):
        """Verify hadolint config exists."""
        config = DOCKER_DIR / ".hadolint.yaml"
        assert config.exists(), ".hadolint.yaml should exist"

    def test_hadolint_config_valid(self):
        """Verify hadolint config is valid YAML."""
        config = DOCKER_DIR / ".hadolint.yaml"
        if config.exists():
            try:
                content = yaml.safe_load(config.read_text())
                assert content is not None
            except yaml.YAMLError as e:
                pytest.fail(f".hadolint.yaml is not valid YAML: {e}")


@requires_docker
class TestDockerBuild:
    """Test Docker image builds (requires Docker daemon)."""

    def test_build_simple(self):
        """Test building Dockerfile.simple."""
        result = subprocess.run(
            [
                "docker",
                "build",
                "-t",
                "etphonehome-test-simple:pytest",
                "-f",
                str(DOCKER_DIR / "Dockerfile.simple"),
                str(PROJECT_ROOT),
            ],
            capture_output=True,
            timeout=600,  # 10 minutes
        )
        assert result.returncode == 0, f"Build failed: {result.stderr.decode()}"

    def test_build_server(self):
        """Test building Dockerfile.server."""
        result = subprocess.run(
            [
                "docker",
                "build",
                "-t",
                "etphonehome-test-server:pytest",
                "-f",
                str(DOCKER_DIR / "Dockerfile.server"),
                str(PROJECT_ROOT),
            ],
            capture_output=True,
            timeout=600,
        )
        assert result.returncode == 0, f"Build failed: {result.stderr.decode()}"


@requires_docker
class TestDockerComposeValidation:
    """Test docker-compose configuration validation (requires Docker)."""

    @pytest.fixture
    def compose_files(self) -> list[Path]:
        """Get all docker-compose files."""
        return list(DOCKER_DIR.glob("docker-compose*.yml"))

    def test_compose_config_valid(self, compose_files):
        """Test docker compose config validation."""
        for compose_file in compose_files:
            result = subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "config", "--quiet"],
                capture_output=True,
                timeout=30,
            )
            assert (
                result.returncode == 0
            ), f"{compose_file.name} config invalid: {result.stderr.decode()}"


@requires_docker
class TestContainerRuntime:
    """Test container runtime behavior (requires Docker daemon)."""

    @pytest.fixture(scope="class")
    def test_image(self):
        """Build test image if not exists."""
        image_name = "etphonehome-test-simple:pytest"

        # Check if image exists
        result = subprocess.run(
            ["docker", "image", "inspect", image_name],
            capture_output=True,
        )

        if result.returncode != 0:
            # Build image
            subprocess.run(
                [
                    "docker",
                    "build",
                    "-t",
                    image_name,
                    "-f",
                    str(DOCKER_DIR / "Dockerfile.simple"),
                    str(PROJECT_ROOT),
                ],
                check=True,
                timeout=600,
            )

        return image_name

    def test_container_starts(self, test_image):
        """Test container can start."""
        container_name = "etphonehome-pytest-start"

        # Cleanup
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

        try:
            # Start container
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-e",
                    "HOME=/data",
                    test_image,
                ],
                capture_output=True,
                timeout=30,
            )
            assert result.returncode == 0, f"Container failed to start: {result.stderr.decode()}"

            # Give it time to start
            import time

            time.sleep(3)

            # Check container is running
            result = subprocess.run(
                ["docker", "ps", "-q", "-f", f"name={container_name}"],
                capture_output=True,
            )
            assert result.stdout.strip(), "Container is not running"

        finally:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

    def test_container_nonroot(self, test_image):
        """Test container runs as non-root."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-e",
                "HOME=/data",
                test_image,
                "id",
                "-u",
            ],
            capture_output=True,
            timeout=30,
        )
        uid = result.stdout.decode().strip()
        assert uid != "0", "Container should not run as root"

    def test_container_arbitrary_uid(self, test_image):
        """Test container can run as arbitrary UID."""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--user",
                "1001:1001",
                "-e",
                "HOME=/data",
                "--entrypoint",
                "python",
                test_image,
                "-c",
                "print('ok')",
            ],
            capture_output=True,
            timeout=30,
        )
        assert (
            result.returncode == 0
        ), f"Container should run as arbitrary UID: {result.stderr.decode()}"
