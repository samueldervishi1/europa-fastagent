#!/usr/bin/env python3

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

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
    # Import monitoring for potential future use (referenced in persistent_logger)
    import src.mcp_agent.monitoring  # noqa: F401
    from src.mcp_agent.logging.error_handler import catch_and_log, setup_global_exception_handler
    from src.mcp_agent.logging.log_manager import log_manager
    from src.mcp_agent.logging.persistent_logger import log_error, log_info, log_warning, persistent_logger

    MONITORING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import logging modules: {e}")
    MONITORING_AVAILABLE = False

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
    import importlib.util
    import shutil

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
    _secrets_cache: Optional[Dict[str, Any]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_secrets(self) -> Dict[str, Any]:
        if self._secrets_cache is not None:
            return self._secrets_cache

        secrets_file = Path("fastagent.secrets.yaml")
        if not secrets_file.exists():
            log_warning("No fastagent.secrets.yaml found - some features may not work")
            self._secrets_cache = {}
            return self._secrets_cache

        try:
            stat_info = secrets_file.stat()
            if stat_info.st_mode & 0o077:
                log_warning("Secrets file has unsafe permissions - should be 600")

            with open(secrets_file, "r", encoding="utf-8") as f:
                secrets = yaml.safe_load(f) or {}

                if not isinstance(secrets, dict):
                    log_error("Invalid secrets file format - must be a YAML dictionary")
                    return {}

                cleaned_secrets = {}
                for key, value in secrets.items():
                    if value is not None and value != "":
                        cleaned_secrets[key] = value

                log_info("Successfully loaded secrets configuration", context={"keys_count": len(cleaned_secrets)})
                self._secrets_cache = cleaned_secrets
                return self._secrets_cache

        except yaml.YAMLError as e:
            log_error("Failed to parse YAML secrets file", exception=e, context={"file": str(secrets_file)})
            self._secrets_cache = {}
            return self._secrets_cache
        except Exception as e:
            log_error("Failed to load secrets file", exception=e, context={"file": str(secrets_file)})
            self._secrets_cache = {}
            return self._secrets_cache


config_manager = ConfigManager()


def validate_mcp_dependencies() -> Dict[str, Dict[str, bool]]:
    """Validate dependencies for MCP servers and return status."""
    dependencies = {
        "spotify": {
            "cryptography": True,
            "requests": True,
            "yaml": True,
        },
        # "google-calendar": {
        #     "cryptography": True,
        #     "requests": True,
        #     "yaml": True,
        #     "dateutil": bool(importlib.util.find_spec("dateutil")),
        # },
        "spring-boot-generator": {
            "requests": True,
            "yaml": True,
            "openapi-generator-cli": bool(shutil.which("openapi-generator-cli")),
            "npm": bool(shutil.which("npm")),
        },
        "time-tracker": {
            "json": True,
            "uuid": True,
            "datetime": True,
        },
        "terminal": {
            "uvx": bool(shutil.which("uvx")) or bool(shutil.which("uv")),
        },
        "memory": {
            "npm": bool(shutil.which("npm")),
        },
        "tavily": {
            "npm": bool(shutil.which("npm")),
        },
        # "gmail": {
        #     "npm": bool(shutil.which("npm")),
        # },
        "github": {
            "npm": bool(shutil.which("npm")),
        },
        "filesystem": {
            "npm": bool(shutil.which("npm")),
        },
    }

    for server, deps in dependencies.items():
        for dep, status in list(deps.items()):
            if dep in ["cryptography", "requests", "yaml", "dateutil"]:
                if dep == "yaml":
                    deps[dep] = bool(importlib.util.find_spec("yaml"))
                elif dep == "requests":
                    deps[dep] = bool(importlib.util.find_spec("requests"))

    return dependencies


def validate_config_structure() -> bool:
    """Validate the structure of fastagent.config.yaml"""
    config_file = Path("fastagent.config.yaml")
    if not config_file.exists():
        log_warning("Configuration file fastagent.config.yaml not found")
        return False

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            log_error("Configuration file must contain a YAML dictionary")
            return False

        required_fields = ["default_model", "mcp"]
        for field in required_fields:
            if field not in config:
                log_warning(f"Missing required configuration field: {field}")

        if "default_model" in config:
            model = config["default_model"]
            if not isinstance(model, str) or not model.strip():
                log_warning("default_model should be a non-empty string")

        if "mcp" in config:
            mcp_config = config["mcp"]
            if not isinstance(mcp_config, dict):
                log_error("mcp section must be a dictionary")
                return False

            if "servers" in mcp_config:
                servers = mcp_config["servers"]
                if not isinstance(servers, dict):
                    log_error("mcp.servers must be a dictionary")
                    return False

                for server_name, server_config in servers.items():
                    if not isinstance(server_config, dict):
                        log_warning(f"Server '{server_name}' configuration must be a dictionary")
                        continue

                    if "command" not in server_config:
                        log_warning(f"Server '{server_name}' missing required 'command' field")

                    if "args" not in server_config:
                        log_warning(f"Server '{server_name}' missing 'args' field")

                    if "args" in server_config and not isinstance(server_config["args"], list):
                        log_warning(f"Server '{server_name}' args must be a list")

        log_info("Configuration validation completed")
        return True

    except yaml.YAMLError as e:
        log_error("Configuration file contains invalid YAML", exception=e)
        return False
    except Exception as e:
        log_error("Failed to validate configuration file", exception=e)
        return False


def log_dependency_status():
    """Log the status of MCP server dependencies."""
    deps = validate_mcp_dependencies()

    missing_deps = []
    warnings = []

    for server, server_deps in deps.items():
        missing = [dep for dep, available in server_deps.items() if not available]
        if missing:
            missing_deps.append(f"{server}: {', '.join(missing)}")

            if server == "spring-boot-generator" and "openapi-generator-cli" in missing:
                warnings.append("Spring Boot Generator may fail - install with: npm install -g @openapitools/openapi-generator-cli")

            # if server == "google-calendar" and "dateutil" in missing:
            #     warnings.append("Google Calendar date parsing will be limited - install with: pip install python-dateutil")

    if missing_deps:
        log_warning("Some MCP servers have missing dependencies", context={"missing": missing_deps})
        for warning in warnings:
            log_warning(warning)
    else:
        log_info("All MCP server dependencies are available")


fast = FastAgent("Europa")


@fast.agent(
    name="maestro",
    instruction="""You are a high-performance smart maestro that efficiently detects user intent and routes to specialized solutions.

CRITICAL MEMORY HANDLING:
- The user's name is Samuel - remember this and use it consistently
- When users ask "what is your name" or "my name", respond with "Your name is Samuel" (not gemini or any model name)
- ALWAYS search memory first using the Memory MCP server before responding to personal questions
- Store important user information in memory for future reference
- Distinguish between: USER (Samuel) vs AI MODEL (gemini-2.0-flash-exp) vs SYSTEM (Europa)

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

5. GitHub & Repository Management:
   - Keywords: "repo", "repository", "github", "commit", "push", "branch", "issue", "pull request", "PR", "create repo"
   - Action: Use GitHub MCP server for repository creation, file management, and GitHub operations

6. Music Control:
   - Keywords: "play", "music", "song", "spotify", "skip", "pause", "volume", "track", "artist", "album", "playlist"
   - Action: Use Spotify MCP server for music playback control, search, and playlist management

7. Time Tracking:
   - Keywords: "timer", "time", "hours", "log", "track", "start", "stop", "work", "project", "timesheet", "summary"
   - Action: Use Time Tracker MCP server for work hour logging, timer management, and reporting

8. Spring Boot Development:
   - Keywords: "spring boot", "java", "generate", "project", "maven", "openapi", "swagger"
   - Action: Use Spring Boot Generator MCP server for project scaffolding and code generation

PERFORMANCE OPTIMIZATIONS:
- Concurrent operation handling
- Response caching for repeated requests
- Connection pooling for databases and APIs
- Lazy loading of heavy resources
- Efficient memory usage patterns
""",
    servers=[
        "filesystem",
        "tavily",
        "terminal",
        "memory",
        "github",
        "spring-boot-generator",
        "spotify",
        "time-tracker",
    ],
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


async def async_validate_config_structure():
    """Async wrapper for config validation"""
    return validate_config_structure()


async def async_log_dependency_status():
    """Async wrapper for dependency validation"""
    return log_dependency_status()


@catch_and_log(shutdown_on_error=False)
async def startup_tasks():
    """Perform startup tasks with error handling"""
    log_info("Starting Europa startup tasks")

    # Run validation tasks concurrently
    validation_tasks = [
        asyncio.create_task(async_validate_config_structure()),
        asyncio.create_task(async_log_dependency_status()),
    ]

    # Execute validation tasks concurrently
    validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)

    # Process results
    for i, result in enumerate(validation_results):
        task_name = ["config_validation", "dependency_validation"][i]
        if isinstance(result, Exception):
            log_warning(f"{task_name} failed", context={"error": str(result)})
        else:
            log_info(f"{task_name} completed successfully")

    # Add log rotation to async tasks
    async def async_log_rotation():
        """Async wrapper for log rotation"""
        try:
            log_manager.rotate_logs(max_age_days=1, max_size_mb=50)
            log_info("Log rotation completed")
            return True
        except Exception as e:
            log_warning("Log rotation failed", context={"error": str(e)})
            return False

    # Run log rotation concurrently with other tasks
    maintenance_tasks = [asyncio.create_task(async_log_rotation())]

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

    # Run maintenance tasks concurrently
    if maintenance_tasks:
        log_info(f"Running {len(maintenance_tasks)} maintenance tasks")
        maintenance_results = await asyncio.gather(*maintenance_tasks, return_exceptions=True)

        for i, result in enumerate(maintenance_results):
            task_name = ["log_rotation"][i]
            if isinstance(result, Exception):
                log_error(f"Maintenance task {task_name} failed", exception=result)
            else:
                log_info(f"Maintenance task {task_name} completed successfully")

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

        # F1 split disabled - running coordinator only
        # if not os.environ.get("TMUX") and not os.environ.get("F1_SPLIT_DISABLED"):
        #     log_info("Not in tmux - attempting to create new session")
        #     f1_split_result = setup_f1_split_terminal()
        #     if f1_split_result:
        #         log_info("Successfully created tmux session - exiting current process")
        #         return

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
