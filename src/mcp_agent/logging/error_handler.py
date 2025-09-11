#!/usr/bin/env python3

import asyncio
import functools
import signal
import sys
import traceback
from typing import Callable, Optional

from .persistent_logger import graceful_shutdown_delay, persistent_logger


class GracefulErrorHandler:
    """
    Error handler that ensures graceful shutdown with proper logging
    and time for user to see error messages before tmux closes.
    """

    def __init__(self):
        self.shutdown_initiated = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            if not self.shutdown_initiated:
                self.shutdown_initiated = True
                print(f"\nReceived signal {signum}")
                persistent_logger.log_warning(f"Received signal {signum}", {"signal": signum})
                asyncio.create_task(self._graceful_signal_shutdown(signum))

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    async def _graceful_signal_shutdown(self, signum: int):
        """Handle graceful shutdown from signals"""
        try:
            persistent_logger.log_shutdown(f"signal_{signum}", signum)
            await graceful_shutdown_delay(2)
        finally:
            sys.exit(signum)

    def catch_and_log_exceptions(self, func: Optional[Callable] = None, *, shutdown_on_error: bool = True, delay_seconds: int = 3):
        """
        Decorator to catch exceptions, log them, and optionally shutdown gracefully

        Args:
            func: Function to wrap (when used as decorator)
            shutdown_on_error: Whether to shutdown the application on error
            delay_seconds: Seconds to wait before shutdown
        """

        def decorator(f: Callable) -> Callable:
            if asyncio.iscoroutinefunction(f):

                @functools.wraps(f)
                async def async_wrapper(*args, **kwargs):
                    try:
                        return await f(*args, **kwargs)
                    except KeyboardInterrupt:
                        print("\n\nKeyboardInterrupt received")
                        persistent_logger.log_info("KeyboardInterrupt received - user requested shutdown")
                        persistent_logger.log_shutdown("keyboard_interrupt", 0)
                        print("Goodbye!")
                        sys.exit(0)
                    except Exception as e:
                        error_context = {
                            "function": f.__name__,
                            "module": f.__module__,
                            "args": str(args)[:200],  # Limit args logging
                            "kwargs": str(kwargs)[:200],
                        }

                        persistent_logger.log_error(f"Unhandled exception in {f.__name__}", exception=e, context=error_context)

                        if shutdown_on_error and not self.shutdown_initiated:
                            self.shutdown_initiated = True
                            await graceful_shutdown_delay(delay_seconds)
                            sys.exit(1)
                        else:
                            raise

                return async_wrapper
            else:

                @functools.wraps(f)
                def sync_wrapper(*args, **kwargs):
                    try:
                        return f(*args, **kwargs)
                    except KeyboardInterrupt:
                        print("\n\nKeyboardInterrupt received")
                        persistent_logger.log_info("KeyboardInterrupt received - user requested shutdown")
                        persistent_logger.log_shutdown("keyboard_interrupt", 0)
                        print("Goodbye!")
                        sys.exit(0)
                    except Exception as e:
                        error_context = {
                            "function": f.__name__,
                            "module": f.__module__,
                            "args": str(args)[:200],
                            "kwargs": str(kwargs)[:200],
                        }

                        persistent_logger.log_error(f"Unhandled exception in {f.__name__}", exception=e, context=error_context)

                        if shutdown_on_error and not self.shutdown_initiated:
                            self.shutdown_initiated = True
                            import time

                            print(f"\n{'=' * 60}")
                            print("ERROR DETECTED - Logs saved to logs/ directory")
                            print("Recent errors:")
                            print(persistent_logger.create_error_summary())
                            print(f"{'=' * 60}")
                            print(f"Shutting down in {delay_seconds} seconds...")

                            for i in range(delay_seconds, 0, -1):
                                print(f"  {i}...", end=" ", flush=True)
                                time.sleep(1)

                            print("\nShutdown complete.")
                            persistent_logger.log_shutdown("error", 1)
                            sys.exit(1)
                        else:
                            raise

                return sync_wrapper

        if func is None:
            return decorator
        else:
            return decorator(func)

    async def safe_task_run(self, coro, task_name: str = "unnamed_task"):
        """
        Run an async task with error handling and logging

        Args:
            coro: Coroutine to run
            task_name: Name for logging purposes
        """
        try:
            return await coro
        except Exception as e:
            persistent_logger.log_error(f"Task '{task_name}' failed", exception=e, context={"task": task_name})
            raise

    def log_and_reraise(self, message: str, context: Optional[dict] = None):
        """
        Context manager to log exceptions and re-raise them

        Usage:
            with error_handler.log_and_reraise("MCP connection failed"):
                # code that might fail
        """
        return _LogAndReraiseContext(message, context)


class _LogAndReraiseContext:
    """Context manager for logging and re-raising exceptions"""

    def __init__(self, message: str, context: Optional[dict] = None):
        self.message = message
        self.context = context or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            persistent_logger.log_error(self.message, exception=exc_val, context=self.context)
        return False


error_handler = GracefulErrorHandler()


def catch_and_log(func: Optional[Callable] = None, *, shutdown_on_error: bool = True, delay_seconds: int = 3):
    """Convenience decorator for catching and logging exceptions"""
    return error_handler.catch_and_log_exceptions(func, shutdown_on_error=shutdown_on_error, delay_seconds=delay_seconds)


def safe_async_task(task_name: str):
    """Decorator for safe async task execution with logging"""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await error_handler.safe_task_run(func(*args, **kwargs), task_name)

        return wrapper

    return decorator


def setup_global_exception_handler():
    """Setup global exception handler for uncaught exceptions"""

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            persistent_logger.log_info("KeyboardInterrupt - user requested shutdown")
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        persistent_logger.log_error(
            "Uncaught exception",
            exception=exc_value,
            context={"type": exc_type.__name__, "traceback": "".join(traceback.format_tb(exc_traceback))},
        )

        print(f"\n{'=' * 60}")
        print("FATAL ERROR - Check logs/europa_errors.log for details")
        print(f"{'=' * 60}")

        persistent_logger.log_shutdown("uncaught_exception", 1)
        sys.exit(1)

    sys.excepthook = handle_exception
