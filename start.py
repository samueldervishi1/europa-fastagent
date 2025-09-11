#!/usr/bin/env python3

import asyncio
import logging
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

try:
    from weather import get_simple_weather
except ImportError:

    def get_simple_weather():
        return "Weather module unavailable"


PROJECT_ROOT = Path(__file__).parent.resolve()

path_str = str(PROJECT_ROOT)
if path_str not in sys.path:
    sys.path.insert(0, path_str)

try:
    from src.mcp_agent.logging.error_handler import catch_and_log, setup_global_exception_handler
    from src.mcp_agent.logging.log_manager import log_manager
    from src.mcp_agent.logging.persistent_logger import log_error, log_info, log_warning, persistent_logger
except ImportError as e:
    print(f"Warning: Could not import logging modules: {e}")

    def log_error(msg, exception=None, context=None):
        print(f"ERROR: {msg}")
        if exception:
            print(f"Exception: {exception}")

    def log_warning(msg, context=None):
        print(f"WARNING: {msg}")

    def log_info(msg, context=None):
        print(f"INFO: {msg}")

    def catch_and_log(func=None, **kwargs):
        return func if func else lambda f: f

    def setup_global_exception_handler():
        pass


try:
    from mcp_agent.core.fastagent import FastAgent
    from mcp_agent.core.request_params import RequestParams
    from version import __version__
except ImportError as e:
    log_error("Failed to import local modules", exception=e)
    print(f"CRITICAL: Failed to import core modules: {e}")
    sys.exit(1)

setup_global_exception_handler()

logging.basicConfig(
    level=logging.CRITICAL,  # Only show critical messages from external libs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

for logger_name in ["google_genai.models", "httpx", "mcp_agent", "urllib3", "asyncio"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

"""
Smart Multi-Agent Coordinator

High-performance maestro that detects intent and routes to specialized agents:
- File operations → Filesystem MCP server

Optimized for speed with caching, connection pooling, and async operations.

Usage:
    uv run start.py
"""


class ConfigManager:
    _instance = None
    _config_cache: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @lru_cache(maxsize=1)
    def get_secrets(self) -> Dict[str, Any]:
        secrets_file = Path("fastagent.secrets.yaml")
        if not secrets_file.exists():
            log_warning("No fastagent.secrets.yaml found - some features may not work")
            return {}

        try:
            with open(secrets_file, "r", encoding="utf-8") as f:
                secrets = yaml.safe_load(f) or {}
                log_info("Successfully loaded secrets configuration")
                return secrets
        except Exception as e:
            log_error("Failed to load secrets file", exception=e, context={"file": str(secrets_file)})
            return {}


config_manager = ConfigManager()

fast = FastAgent("Europa")


@fast.agent(
    name="maestro",
    instruction="""You are a high-performance smart maestro that efficiently detects user intent and routes to specialized solutions.

IMPORTANT: When users ask about personal information (name, preferences, past conversations), ALWAYS search memory first using the Memory MCP server before responding.

OPTIMIZED ROUTING LOGIC:

1. File Operations (Async I/O):
   - Keywords: "file", "directory", "save", "read", "list", "organize"
   - Action: Use Filesystem MCP server with async file operations

2. Web Search & Research:
   - Keywords: "search", "find", "lookup", "research", "web", "news"
   - Action: Use Tavily AI search server optimized for AI agents and LLMs

3. Terminal Operations:
   - Keywords: "run", "execute", "command", "terminal", "bash", "shell", "ls", "cat"
   - Action: Use secure terminal controller for safe command execution

4. Memory & Knowledge:
   - Keywords: "remember", "store", "recall", "forget", "what did I", "my preferences", "save this", "my name", "who am I"
   - Action: Use Memory MCP server - ALWAYS search memory first for user info, then store new information

5. Email & Communication:
   - Keywords: "email", "send", "inbox", "gmail", "unread", "message", "compose", "meeting", "schedule"
   - Action: Use Gmail MCP server for email management, sending, and scheduling

6. GitHub & Repository Management:
   - Keywords: "repo", "repository", "github", "commit", "push", "branch", "issue", "pull request", "PR", "create repo"
   - Action: Use GitHub MCP server for repository creation, file management, and GitHub operations

PERFORMANCE OPTIMIZATIONS:
- Concurrent operation handling
- Response caching for repeated requests
- Connection pooling for databases and APIs
- Lazy loading of heavy resources
- Efficient memory usage patterns
""",
    servers=["filesystem", "tavily", "terminal", "memory", "gmail", "github", "spring-boot-generator"],
    model="google.gemini-2.0-flash-exp",
    request_params=RequestParams(
        temperature=0.1,  # Lower temperature for faster, more deterministic responses
        maxTokens=4000,  # Reasonable limit to prevent long responses
    ),
)
async def europa():
    pass


def setup_f1_split_terminal():
    """Set up 2-pane terminal: coordinator (left), F1 display (right)"""
    try:
        subprocess.run(["tmux", "-V"], capture_output=True, check=True)
        log_info("tmux detected - setting up F1 split terminal")
    except (subprocess.CalledProcessError, FileNotFoundError):
        log_warning("tmux not available - F1 split disabled")
        print("tmux not available - F1 split disabled")
        return False

    if os.environ.get("TMUX"):
        try:
            f1_path = PROJECT_ROOT / "f1-mcp"
            if not f1_path.exists():
                log_warning("f1-mcp directory not found - F1 split disabled")
                return False

            subprocess.run(["tmux", "split-window", "-h", "-c", str(f1_path)], check=True)

            subprocess.run(["tmux", "send-keys", "-t", "1", "./f1_display.sh", "C-m"], check=True)

            subprocess.run(["tmux", "select-pane", "-t", "0", "-T", "MCP Coordinator"], check=True)
            subprocess.run(["tmux", "select-pane", "-t", "1", "-T", "F1 Display"], check=True)

            subprocess.run(["tmux", "select-pane", "-t", "0"], check=True)

            log_info("F1 display started successfully in right pane")
            print("F1 display started in right pane!")
            return True

        except subprocess.CalledProcessError as e:
            log_error("Failed to set up F1 split terminal", exception=e)
            return False

    else:
        try:
            subprocess.run(["tmux", "kill-session", "-t", "f1-europa"], capture_output=True)

            env = os.environ.copy()
            env["F1_SPLIT_CREATED"] = "1"

            f1_path = PROJECT_ROOT / "f1-mcp"
            if not f1_path.exists():
                log_warning("f1-mcp directory not found - creating tmux session without F1 split")
                os.execvpe("tmux", ["tmux", "new-session", "-s", "f1-europa", "-c", str(PROJECT_ROOT), f"uv run {__file__}"], env)
            else:
                os.execvpe(
                    "tmux",
                    [
                        "tmux",
                        "new-session",
                        "-s",
                        "f1-europa",
                        "-c",
                        str(PROJECT_ROOT),
                        f"uv run {__file__}",
                        ";",
                        "split-window",
                        "-h",
                        "-c",
                        str(f1_path),
                        "./f1_display.sh",
                        ";",
                        "select-pane",
                        "-t",
                        "0",
                        ";",
                        "set-option",
                        "remain-on-exit",
                        "off",
                        ";",
                        "set-hook",
                        "-g",
                        "pane-exited",
                        "kill-session",
                    ],
                    env,
                )

        except Exception as e:
            log_error("Failed to create F1 tmux session", exception=e)
            print("Falling back to europa without split terminal")
            return False


@catch_and_log(shutdown_on_error=False)
async def startup_tasks():
    """Perform startup tasks with error handling"""
    tasks = []

    log_info("Starting Europa startup tasks")

    try:
        log_manager.rotate_logs(max_age_days=7, max_size_mb=50)
        log_info("Log rotation completed")
    except Exception as e:
        log_warning("Log rotation failed", context={"error": str(e)})

    if os.environ.get("TMUX") and not os.environ.get("F1_SPLIT_CREATED"):
        try:
            result = subprocess.run(["tmux", "list-panes", "-F", "#{pane_id}"], capture_output=True, text=True)
            pane_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
            if pane_count == 1:
                log_info("Single tmux pane detected - attempting F1 split")
                f1_split_enabled = setup_f1_split_terminal()
                if f1_split_enabled:
                    log_info("F1 split terminal setup successful")
                else:
                    log_warning("F1 split terminal setup failed")
        except Exception as e:
            log_error("Error during F1 pane setup", exception=e)
    elif os.environ.get("F1_SPLIT_CREATED"):
        log_info("F1 split already created in previous session")

    if tasks:
        log_info(f"Running {len(tasks)} startup tasks")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log_error(f"Startup task {i} failed", exception=result)
            else:
                log_info(f"Startup task {i} completed successfully")

    log_info("Startup tasks completed")


@catch_and_log(shutdown_on_error=True, delay_seconds=5)
async def main():
    """Main application entry point with comprehensive error handling"""
    try:
        weather_info = get_simple_weather()
        startup_msg = f"Europa — built on FastAgent MCP v{__version__} | {weather_info}"
        print(startup_msg)
        print()

        log_info("Europa starting up", context={"version": __version__, "weather": weather_info})

        if not os.environ.get("TMUX") and not os.environ.get("F1_SPLIT_DISABLED"):
            log_info("Not in tmux - attempting to create new session")
            f1_split_result = setup_f1_split_terminal()
            if f1_split_result:
                log_info("Successfully created tmux session - exiting current process")
                return

        await startup_tasks()

        health_report = log_manager.generate_health_report()
        log_info("Generated health report", context={"report_lines": len(health_report.split("\n"))})

        log_info("Starting FastAgent interactive session")
        async with fast.run() as agent:
            log_info("FastAgent session established - entering interactive mode")
            await agent.interactive()

    except KeyboardInterrupt:
        log_info("Received KeyboardInterrupt - shutting down gracefully")
        print("\nGoodbye!")
        persistent_logger.log_shutdown("keyboard_interrupt", 0)
    except Exception as e:
        log_error("Fatal error in main application", exception=e)
        persistent_logger.log_shutdown("fatal_error", 1)
        raise
    finally:
        log_info("Main application cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
