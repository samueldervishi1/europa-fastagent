#!/usr/bin/env python3

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from ..monitoring import error_tracker, metrics_collector

    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False


class PersistentLogger:
    """
    Persistent logging service that ensures errors and warnings are saved to files
    even if the application crashes or exits unexpectedly.
    """

    _instance: Optional["PersistentLogger"] = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            PersistentLogger._initialized = True

    def _setup_logging(self):
        """Initialize the persistent logging system"""
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)

        self.app_logger = logging.getLogger("europa_app")
        self.app_logger.setLevel(logging.DEBUG)

        self.error_logger = logging.getLogger("europa_errors")
        self.error_logger.setLevel(logging.ERROR)

        self.mcp_logger = logging.getLogger("europa_mcp")
        self.mcp_logger.setLevel(logging.WARNING)

        for logger in [self.app_logger, self.error_logger, self.mcp_logger]:
            logger.handlers.clear()
            logger.propagate = False

        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        error_formatter = logging.Formatter(
            "%(asctime)s - EUROPA ERROR - %(levelname)s\n"
            "File: %(filename)s:%(lineno)d\n"
            "Function: %(funcName)s\n"
            "Message: %(message)s\n"
            '{"separator": "="*80}\n',
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        app_handler = RotatingFileHandler(
            self.logs_dir / "europa_app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        app_handler.setLevel(logging.DEBUG)
        app_handler.setFormatter(detailed_formatter)

        error_handler = RotatingFileHandler(
            self.logs_dir / "europa_errors.log",
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=10,
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(error_formatter)

        mcp_handler = RotatingFileHandler(
            self.logs_dir / "europa_mcp.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=3,
        )
        mcp_handler.setLevel(logging.WARNING)
        mcp_handler.setFormatter(detailed_formatter)

        self.app_logger.addHandler(app_handler)
        self.error_logger.addHandler(error_handler)
        self.mcp_logger.addHandler(mcp_handler)

        self.app_logger.addHandler(error_handler)

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_log = self.logs_dir / f"session_{self.session_id}.log"

        session_handler = logging.FileHandler(self.session_log)
        session_handler.setLevel(logging.INFO)
        session_handler.setFormatter(detailed_formatter)
        self.app_logger.addHandler(session_handler)

        self.log_startup()

    def log_startup(self):
        """Log startup information"""
        self.app_logger.info("=" * 80)
        self.app_logger.info("EUROPA STARTUP - Session %s", self.session_id)
        self.app_logger.info("=" * 80)
        self.app_logger.info("Python: %s", os.sys.version)
        self.app_logger.info("Working Directory: %s", os.getcwd())

        # Log only essential environment variables to prevent memory leaks
        essential_env = {
            "PATH": os.environ.get("PATH", "")[:200],  # Truncate long PATH
            "HOME": os.environ.get("HOME", ""),
            "USER": os.environ.get("USER", ""),
            "SHELL": os.environ.get("SHELL", ""),
            "TERM": os.environ.get("TERM", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV", ""),
        }
        # Remove empty values
        essential_env = {k: v for k, v in essential_env.items() if v}
        self.app_logger.info("Essential Environment: %s", essential_env)

    def log_error(self, message: str, exception: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        """Log an error with full context"""
        error_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "message": message,
            "context": context or {},
        }

        if exception:
            error_data["exception"] = {"type": type(exception).__name__, "message": str(exception), "args": exception.args}

            self.error_logger.error(message, exc_info=exception, extra={"error_data": error_data})
            self.app_logger.error(message, exc_info=exception, extra={"error_data": error_data})

            # Track error in monitoring system
            if MONITORING_AVAILABLE and exception:
                asyncio.create_task(error_tracker.track_error(exception, context))
                metrics_collector.increment_counter("errors_total", labels={"type": type(exception).__name__})
        else:
            self.error_logger.error(message, extra={"error_data": error_data})
            self.app_logger.error(message, extra={"error_data": error_data})

            # Track generic error in monitoring system
            if MONITORING_AVAILABLE:
                generic_error = Exception(message)
                asyncio.create_task(error_tracker.track_error(generic_error, context))
                metrics_collector.increment_counter("errors_total", labels={"type": "generic"})

        self._write_json_error(error_data)

    def log_warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a warning"""
        warning_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "message": message,
            "context": context or {},
        }

        self.app_logger.warning(message, extra={"warning_data": warning_data})

    def log_info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an info message"""
        self.app_logger.info(message, extra={"context": context or {}})

    def log_mcp_error(self, server_name: str, message: str, exception: Optional[Exception] = None):
        """Log MCP server specific errors"""
        mcp_context = {"server": server_name, "timestamp": datetime.now(timezone.utc).isoformat(), "session_id": self.session_id}

        error_msg = f"MCP Server '{server_name}': {message}"

        if exception:
            self.mcp_logger.error(error_msg, exc_info=exception, extra={"mcp_context": mcp_context})
            self.error_logger.error(error_msg, exc_info=exception, extra={"mcp_context": mcp_context})
        else:
            self.mcp_logger.error(error_msg, extra={"mcp_context": mcp_context})

    def _write_json_error(self, error_data: Dict[str, Any]):
        """Write error to JSON file for structured analysis"""
        json_error_file = self.logs_dir / "errors.jsonl"

        try:
            with open(json_error_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(error_data) + "\n")
        except Exception as e:
            print(f"CRITICAL: Failed to write error to JSON log: {e}")
            print(f"Original error data: {error_data}")

    def log_shutdown(self, reason: str = "normal", exit_code: int = 0):
        """Log shutdown information"""
        shutdown_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "reason": reason,
            "exit_code": exit_code,
            "session_duration": self._get_session_duration(),
        }

        self.app_logger.info("=" * 80)
        self.app_logger.info("EUROPA SHUTDOWN - Reason: %s, Exit Code: %d", reason, exit_code)
        self.app_logger.info("Session Duration: %s", shutdown_data["session_duration"])
        self.app_logger.info("=" * 80)

        json_shutdown_file = self.logs_dir / "sessions.jsonl"
        try:
            with open(json_shutdown_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(shutdown_data) + "\n")
        except Exception as e:
            print(f"Failed to write shutdown data: {e}")

    def _get_session_duration(self) -> str:
        """Calculate session duration"""
        try:
            start_time = datetime.strptime(self.session_id, "%Y%m%d_%H%M%S")
            duration = datetime.now() - start_time
            return str(duration)
        except Exception:
            return "unknown"

    def create_error_summary(self) -> str:
        """Create a summary of recent errors for display"""
        try:
            error_file = self.logs_dir / "europa_errors.log"
            if not error_file.exists():
                return "No errors logged in this session."

            with open(error_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            recent_errors = lines[-20:] if len(lines) > 20 else lines
            return "".join(recent_errors)

        except Exception as e:
            return f"Error reading error log: {e}"

    def get_log_files(self) -> Dict[str, Path]:
        """Get paths to all log files"""
        return {
            "app_log": self.logs_dir / "europa_app.log",
            "error_log": self.logs_dir / "europa_errors.log",
            "mcp_log": self.logs_dir / "europa_mcp.log",
            "session_log": self.session_log,
            "json_errors": self.logs_dir / "errors.jsonl",
            "json_sessions": self.logs_dir / "sessions.jsonl",
        }


persistent_logger = PersistentLogger()


def log_error(message: str, exception: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
    """Global function to log errors"""
    persistent_logger.log_error(message, exception, context)


def log_warning(message: str, context: Optional[Dict[str, Any]] = None):
    """Global function to log warnings"""
    persistent_logger.log_warning(message, context)


def log_info(message: str, context: Optional[Dict[str, Any]] = None):
    """Global function to log info"""
    persistent_logger.log_info(message, context)


def log_mcp_error(server_name: str, message: str, exception: Optional[Exception] = None):
    """Global function to log MCP errors"""
    persistent_logger.log_mcp_error(server_name, message, exception)


async def graceful_shutdown_delay(seconds: int = 3):
    """Provide delay before shutdown to allow log writing and user to see errors"""
    print(f"\n{'=' * 60}")
    print("ERROR DETECTED - Logs saved to logs/ directory")
    print("Recent errors:")
    print(persistent_logger.create_error_summary())
    print(f"{'=' * 60}")
    print(f"Shutting down in {seconds} seconds...")

    for i in range(seconds, 0, -1):
        print(f"  {i}...", end=" ", flush=True)
        await asyncio.sleep(1)

    print("\nShutdown complete.")
    persistent_logger.log_shutdown("error", 1)
