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
    from mcp_agent.core.fastagent import FastAgent
    from mcp_agent.core.request_params import RequestParams
    from version import __version__
except ImportError as e:
    logging.error(f"Failed to import local modules: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.ERROR,  # Show errors and critical messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logging.getLogger("google_genai.models").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("mcp_agent").setLevel(logging.ERROR)

"""
Smart Multi-Agent Coordinator

High-performance tauricus that detects intent and routes to specialized agents:
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
        secrets_file = Path('fastagent.secrets.yaml')
        if not secrets_file.exists():
            return {}
        
        try:
            with open(secrets_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
            return {}

config_manager = ConfigManager()

fast = FastAgent("Tauricus")

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
    servers=["filesystem", "tavily", "terminal", "memory", "gmail", "github"],
    model="google.gemini-2.0-flash-exp",
    request_params=RequestParams(
        temperature=0.1,      # Lower temperature for faster, more deterministic responses
        maxTokens=4000       # Reasonable limit to prevent long responses
    ),
)
async def tauricus():
    pass

def setup_f1_split_terminal():
    """Set up 2-pane terminal: coordinator (left), F1 display (right)"""
    try:
        subprocess.run(['tmux', '-V'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("tmux not available - F1 split disabled")
        return False
    
    if os.environ.get('TMUX'):
        try:
            subprocess.run([
                'tmux', 'split-window', '-h', '-c', str(PROJECT_ROOT / 'f1-mcp')
            ], check=True)
            
            subprocess.run([
                'tmux', 'send-keys', '-t', '1', './f1_display.sh', 'C-m'
            ], check=True)
            
            subprocess.run([
                'tmux', 'select-pane', '-t', '0', '-T', 'MCP Coordinator'
            ], check=True)
            subprocess.run([
                'tmux', 'select-pane', '-t', '1', '-T', 'F1 Display'  
            ], check=True)
            
            subprocess.run(['tmux', 'select-pane', '-t', '0'], check=True)
            
            print("F1 display started in right pane!")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up F1 split: {e}")
            return False
    
    else:
        try:
            subprocess.run(['tmux', 'kill-session', '-t', 'f1-tauricus'], 
                         capture_output=True)
            
            env = os.environ.copy()
            env['F1_SPLIT_CREATED'] = '1'
            
            os.execvpe('tmux', [
                'tmux', 'new-session', '-s', 'f1-tauricus',
                '-c', str(PROJECT_ROOT),
                f'uv run {__file__}',
                ';', 'split-window', '-h', '-c', str(PROJECT_ROOT / 'f1-mcp'),
                './f1_display.sh',
                ';', 'select-pane', '-t', '0',
                ';', 'set-option', 'remain-on-exit', 'off',
                ';', 'set-hook', '-g', 'pane-exited', 'kill-session'
            ], env)
            
        except Exception as e:
            logger.error(f"Failed to create F1 tmux session: {e}")
            print("Falling back to tauricus without split terminal")
            return False

async def startup_tasks():
    tasks = []
    
    if os.environ.get('TMUX') and not os.environ.get('F1_SPLIT_CREATED'):
        try:
            result = subprocess.run(['tmux', 'list-panes', '-F', '#{pane_id}'], 
                                  capture_output=True, text=True)
            pane_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            if pane_count == 1:
                f1_split_enabled = setup_f1_split_terminal()
                if f1_split_enabled:
                    pass
        except Exception as e:
            logger.error(f"Error checking panes: {e}")
    elif os.environ.get('F1_SPLIT_CREATED'):
        pass

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Startup task {i} failed: {result}")
            else:
                logger.info(f"Startup task {i} completed successfully")
    else:
        pass

async def main():
    try:        
        weather_info = get_simple_weather()
        print(f"Tauricus — built on FastAgent MCP v{__version__} | {weather_info}")
        print()
        
        if not os.environ.get('TMUX') and not os.environ.get('F1_SPLIT_DISABLED'):
            f1_split_result = setup_f1_split_terminal()
            if f1_split_result:
                return
        
        await startup_tasks()
        
        async with fast.run() as agent:
            await agent.interactive()
            
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        pass

if __name__ == "__main__":
    asyncio.run(main())