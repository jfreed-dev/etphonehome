"""Auto-detect system capabilities for client identity."""

import os
import shutil
import sys
from pathlib import Path


def detect_capabilities() -> list[str]:
    """
    Auto-detect system capabilities.

    Returns a list of capability strings like:
    - "python3.12" - Python version
    - "docker" - Docker available
    - "nvidia-gpu" - NVIDIA GPU present
    - "apt", "homebrew" - Package managers
    - "git" - Git available
    - "node" - Node.js available
    """
    caps = []

    # Python version
    caps.append(f"python{sys.version_info.major}.{sys.version_info.minor}")

    # Docker
    if shutil.which("docker"):
        caps.append("docker")

    # Podman
    if shutil.which("podman"):
        caps.append("podman")

    # GPU detection
    if Path("/usr/bin/nvidia-smi").exists() or shutil.which("nvidia-smi"):
        caps.append("nvidia-gpu")

    # AMD GPU
    if Path("/opt/rocm").exists():
        caps.append("amd-gpu")

    # Package managers
    if shutil.which("apt") or shutil.which("apt-get"):
        caps.append("apt")
    if shutil.which("brew"):
        caps.append("homebrew")
    if shutil.which("dnf"):
        caps.append("dnf")
    if shutil.which("pacman"):
        caps.append("pacman")
    if shutil.which("choco"):
        caps.append("chocolatey")

    # Development tools
    if shutil.which("git"):
        caps.append("git")
    if shutil.which("node") or shutil.which("nodejs"):
        caps.append("node")
    if shutil.which("npm"):
        caps.append("npm")
    if shutil.which("cargo"):
        caps.append("rust")
    if shutil.which("go"):
        caps.append("go")
    if shutil.which("java"):
        caps.append("java")

    # Build tools
    if shutil.which("make"):
        caps.append("make")
    if shutil.which("cmake"):
        caps.append("cmake")
    if shutil.which("gcc") or shutil.which("clang"):
        caps.append("c-compiler")

    # Kubernetes
    if shutil.which("kubectl"):
        caps.append("kubectl")
    if shutil.which("helm"):
        caps.append("helm")

    # Cloud CLIs
    if shutil.which("aws"):
        caps.append("aws-cli")
    if shutil.which("gcloud"):
        caps.append("gcloud")
    if shutil.which("az"):
        caps.append("azure-cli")

    # SSH
    if shutil.which("ssh"):
        caps.append("ssh")

    # Systemd (Linux service management)
    if shutil.which("systemctl"):
        caps.append("systemd")

    return sorted(caps)


def get_ssh_key_fingerprint(key_path: Path) -> str:
    """
    Get SHA256 fingerprint of an SSH public key.

    Args:
        key_path: Path to the private key (will read .pub file)

    Returns:
        SHA256 fingerprint string like "SHA256:abc123..."
    """
    import hashlib
    import base64

    pub_path = key_path.with_suffix(".pub")
    if not pub_path.exists():
        # Try adding .pub to the full path
        pub_path = Path(str(key_path) + ".pub")

    if not pub_path.exists():
        raise FileNotFoundError(f"Public key not found: {pub_path}")

    # Read public key
    content = pub_path.read_text().strip()

    # Parse: "ssh-ed25519 AAAA... comment"
    parts = content.split()
    if len(parts) < 2:
        raise ValueError(f"Invalid public key format: {pub_path}")

    key_data = base64.b64decode(parts[1])
    fingerprint = hashlib.sha256(key_data).digest()
    fp_b64 = base64.b64encode(fingerprint).decode("ascii").rstrip("=")

    return f"SHA256:{fp_b64}"
