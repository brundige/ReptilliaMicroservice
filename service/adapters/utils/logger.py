# adapters/utils/logger.py

"""
Simple logger that writes to both stdout and a log file.
This allows the API to stream logs via SSE while maintaining console output.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class DualLogger:
    """
    Logger that writes to both stdout and a file.

    Usage:
        log = DualLogger()
        log("Starting application...")
        log.info("Connected to database")
        log.error("Failed to connect to sensor")
    """

    def __init__(self, log_file: str | None = None):
        """
        Initialize the logger.

        Args:
            log_file: Path to log file. If None, uses LOG_FILE env var.
                      If neither is set, only writes to stdout.
        """
        self.log_file = log_file or os.getenv("LOG_FILE")
        self._file_handle = None

        if self.log_file:
            # Create directory if needed
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
            # Open file for appending
            self._file_handle = open(self.log_file, "a", buffering=1)  # Line buffered

    def __call__(self, message: str = ""):
        """Log a message (same as print)."""
        self._write(message)

    def _write(self, message: str, level: str = ""):
        """Write to stdout and file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Format with level if provided
        if level:
            formatted = f"[{timestamp}] [{level}] {message}"
        else:
            formatted = message

        # Write to stdout
        print(message, flush=True)

        # Write formatted version to file
        if self._file_handle:
            self._file_handle.write(f"{formatted}\n")
            self._file_handle.flush()

    def info(self, message: str):
        """Log info level message."""
        self._write(message, "INFO")

    def warning(self, message: str):
        """Log warning level message."""
        self._write(message, "WARN")

    def error(self, message: str):
        """Log error level message."""
        self._write(message, "ERROR")

    def debug(self, message: str):
        """Log debug level message."""
        self._write(message, "DEBUG")

    def close(self):
        """Close the log file."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None


# Global logger instance
_logger: DualLogger | None = None


def get_logger() -> DualLogger:
    """Get or create the global logger instance."""
    global _logger
    if _logger is None:
        _logger = DualLogger()
    return _logger


def log(message: str = ""):
    """Convenience function to log a message."""
    get_logger()(message)