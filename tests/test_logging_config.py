"""Tests for centralized logging configuration."""

import io
import logging
from pathlib import Path
from unittest.mock import patch

from shared.logging_config import (
    DEFAULT_BACKUP_COUNT,
    DEFAULT_LOG_FORMAT,
    DEFAULT_MAX_BYTES,
    get_default_log_dir,
    get_default_log_file,
    setup_logging,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_returns_logger(self):
        """Should return a logger instance."""
        logger = setup_logging("test_logger")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"

    def test_sets_log_level(self):
        """Should set the specified log level."""
        logger = setup_logging("test_level", level="DEBUG")
        assert logger.level == logging.DEBUG

        logger = setup_logging("test_level2", level="WARNING")
        assert logger.level == logging.WARNING

    def test_case_insensitive_level(self):
        """Should handle case-insensitive log levels."""
        logger = setup_logging("test_case", level="debug")
        assert logger.level == logging.DEBUG

        logger = setup_logging("test_case2", level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_console_handler_added(self):
        """Should add console handler."""
        logger = setup_logging("test_console")

        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_file_handler_added(self, tmp_path):
        """Should add file handler when log_file specified."""
        log_file = tmp_path / "test.log"
        logger = setup_logging("test_file", log_file=log_file)

        from logging.handlers import RotatingFileHandler

        file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1

    def test_creates_log_directory(self, tmp_path):
        """Should create log directory if it doesn't exist."""
        log_file = tmp_path / "subdir" / "nested" / "test.log"

        setup_logging("test_mkdir", log_file=log_file)

        assert log_file.parent.exists()

    def test_clears_existing_handlers(self):
        """Should clear existing handlers on reconfiguration."""
        logger = setup_logging("test_clear")
        initial_count = len(logger.handlers)

        # Reconfigure
        setup_logging("test_clear")
        final_count = len(logger.handlers)

        assert final_count == initial_count  # Should not accumulate

    def test_custom_format(self):
        """Should use custom format when specified."""
        custom_format = "%(levelname)s - %(message)s"
        stream = io.StringIO()

        logger = setup_logging("test_format", log_format=custom_format, stream=stream)
        logger.info("test message")

        stream.seek(0)
        output = stream.read()
        assert "INFO - test message" in output

    def test_custom_stream(self):
        """Should log to custom stream."""
        stream = io.StringIO()
        logger = setup_logging("test_stream", stream=stream)

        logger.info("Hello, World!")

        stream.seek(0)
        assert "Hello, World!" in stream.read()

    def test_no_propagation(self):
        """Should disable propagation to root logger."""
        logger = setup_logging("test_propagate")

        assert logger.propagate is False

    def test_file_rotation_settings(self, tmp_path):
        """Should apply rotation settings."""
        log_file = tmp_path / "test.log"
        logger = setup_logging("test_rotation", log_file=log_file, max_bytes=1024, backup_count=3)

        from logging.handlers import RotatingFileHandler

        file_handler = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))

        assert file_handler.maxBytes == 1024
        assert file_handler.backupCount == 3

    def test_writes_to_file(self, tmp_path):
        """Should write logs to file."""
        log_file = tmp_path / "test.log"
        logger = setup_logging("test_write", log_file=log_file)

        logger.info("Test log message")

        # Force flush
        for handler in logger.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "Test log message" in content


class TestGetDefaultLogDir:
    """Tests for get_default_log_dir function."""

    def test_client_log_dir(self):
        """Should return client log directory."""
        log_dir = get_default_log_dir("client")

        assert "etphonehome" in str(log_dir).lower()
        assert "logs" in str(log_dir)

    @patch("os.geteuid")
    def test_server_log_dir_non_root(self, mock_geteuid):
        """Should return user directory for non-root server."""
        mock_geteuid.return_value = 1000  # Non-root

        log_dir = get_default_log_dir("server")

        # Should be in user's home directory
        assert Path.home() in log_dir.parents or str(Path.home()) in str(log_dir)

    @patch("os.geteuid")
    @patch("pathlib.Path.exists")
    def test_server_log_dir_root(self, mock_exists, mock_geteuid):
        """Should return /var/log for root server."""
        mock_geteuid.return_value = 0  # Root
        mock_exists.return_value = True

        log_dir = get_default_log_dir("server")

        assert str(log_dir) == "/var/log/etphonehome"


class TestGetDefaultLogFile:
    """Tests for get_default_log_file function."""

    def test_client_log_file(self):
        """Should return client.log for client."""
        log_file = get_default_log_file("client")

        assert log_file.name == "client.log"

    def test_server_log_file(self):
        """Should return server.log for server."""
        log_file = get_default_log_file("server")

        assert log_file.name == "server.log"

    def test_log_file_in_log_dir(self):
        """Log file should be inside log directory."""
        log_file = get_default_log_file("client")
        log_dir = get_default_log_dir("client")

        assert log_file.parent == log_dir


class TestDefaultConstants:
    """Tests for default constant values."""

    def test_default_max_bytes(self):
        """Default max bytes should be 10MB."""
        assert DEFAULT_MAX_BYTES == 10 * 1024 * 1024

    def test_default_backup_count(self):
        """Default backup count should be 5."""
        assert DEFAULT_BACKUP_COUNT == 5

    def test_default_format_contains_elements(self):
        """Default format should contain essential elements."""
        assert "%(asctime)s" in DEFAULT_LOG_FORMAT
        assert "%(levelname)s" in DEFAULT_LOG_FORMAT
        assert "%(name)s" in DEFAULT_LOG_FORMAT
        assert "%(message)s" in DEFAULT_LOG_FORMAT
