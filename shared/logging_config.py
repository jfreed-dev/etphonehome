"""Centralized logging configuration with file rotation support."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Default settings
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5


def setup_logging(
    name: str,
    level: str = "INFO",
    log_file: str | Path | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    stream: object = None,
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> logging.Logger:
    """
    Configure logging with optional file rotation.

    Args:
        name: Logger name (e.g., 'phonehome', 'etphonehome')
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. If None, only console logging.
        max_bytes: Maximum size of each log file before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        stream: Stream for console logging (default: stderr for server, stdout for client)
        log_format: Log message format
        date_format: Timestamp format

    Returns:
        Configured logger instance
    """
    # Get or create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Console handler
    console_handler = logging.StreamHandler(stream or sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (if log file specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_default_log_dir(component: str = "client") -> Path:
    """
    Get the default log directory for a component.

    Args:
        component: 'client' or 'server'

    Returns:
        Path to log directory
    """
    if component == "server":
        # Server logs go to /var/log if running as service, else ~/.etphonehome/logs
        var_log = Path("/var/log/etphonehome")
        if var_log.exists() or os.geteuid() == 0:
            return var_log
        return Path.home() / ".etphonehome" / "logs"
    else:
        # Client logs go to ~/.etphonehome/logs
        return Path.home() / ".etphonehome" / "logs"


def get_default_log_file(component: str = "client") -> Path:
    """
    Get the default log file path for a component.

    Args:
        component: 'client' or 'server'

    Returns:
        Path to log file
    """
    log_dir = get_default_log_dir(component)
    if component == "server":
        return log_dir / "server.log"
    return log_dir / "client.log"
