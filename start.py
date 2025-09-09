#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

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
    level=logging.CRITICAL,  # Only show critical errors
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logging.getLogger("google_genai.models").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("mcp_agent").setLevel(logging.CRITICAL)

"""
Smart Multi-Agent Coordinator

High-performance coordinator that detects intent and routes to specialized agents:
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

fast = FastAgent("Smart Agent Coordinator")

@fast.agent(
    name="coordinator",
    instruction="""You are a high-performance smart coordinator that efficiently detects user intent and routes to specialized solutions.

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

PERFORMANCE OPTIMIZATIONS:
- Concurrent operation handling
- Response caching for repeated requests
- Connection pooling for databases and APIs
- Lazy loading of heavy resources
- Efficient memory usage patterns
""",
    servers=["filesystem", "tavily", "terminal", "memory"],
    model="google.gemini-2.0-flash-exp",
    request_params=RequestParams(
        temperature=0.1,      # Lower temperature for faster, more deterministic responses
        maxTokens=4000       # Reasonable limit to prevent long responses
    ),
)
async def coordinator():
    pass

async def startup_tasks():
    tasks = []
    
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
        print(f"FastAgent Ultimate MCP Coordinator v{__version__}")
        print()
        
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