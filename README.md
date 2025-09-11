# Europa — built on FastAgent MCP

A high-performance AI automation platform powered by **Google Gemini 2.0 Flash Experimental** with intelligent MCP server coordination for seamless task automation.

## What This Project Does

This project creates a **smart AI coordinator** that efficiently handles:

- **File Operations** - Complete filesystem management with async I/O
- **Web Research** - Advanced web search using Tavily AI search engine
- **Terminal Operations** - Secure command execution with full output capture
- **Persistent Memory** - Cross-session knowledge storage and recall
- **Smart Task Routing** - Intelligent detection and routing to specialized solutions

## Key Features

### **High-Performance AI Engine**

- **Google Gemini 2.0 Flash Experimental** - Ultra-fast AI with latest capabilities
- **Low Temperature (0.1)** - Consistent, deterministic responses
- **Optimized Token Usage** - 4000 token limit for efficient processing

### **Persistent Memory System**

- **Cross-Session Memory** - Remember conversations between sessions
- **Knowledge Graph Storage** - Entities, relationships, and observations
- **Searchable History** - Find past information quickly
- **Personal Preferences** - Store user settings and preferences

### **Advanced Web Research**

- **Tavily AI Search** - Optimized search engine for AI agents and LLMs
- **Real-Time Information** - Access latest web information
- **Intelligent Summarization** - Extract relevant information automatically
- **Multi-Source Aggregation** - Combine information from multiple sources

### **Secure Terminal Operations**

- **Safe Command Execution** - Controlled terminal access
- **Real-Time Output** - Stream command results
- **Error Handling** - Comprehensive error reporting and debugging
- **Command Validation** - Security checks before execution

### **Advanced File Management**

- **Async File Operations** - High-performance file I/O
- **Directory Management** - Create, organize, and manage folders
- **File Permissions** - Configurable access controls
- **Batch Operations** - Process multiple files efficiently

### **🆕 Persistent Logging & Error Handling**

- **Comprehensive Logging** - All errors, warnings, and info logged to files
- **Graceful Shutdown** - 3-5 second delay on errors to view details before shutdown
- **Log Rotation** - Automatic cleanup and archiving of old logs
- **Error Analysis** - JSON structured logs for pattern analysis
- **Session Tracking** - Each session logged with detailed context
- **Health Reports** - System health monitoring and reporting

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 16+** (for MCP servers)
- **Git**
- **Google Gemini API Key** (required)
- **Tavily API Key** (for web search)

### 1. Clone the Repository

```bash
git clone <https://github.com/samueldervishi1/europa-fastagent>
cd mcp
```

### 2. Install Dependencies

```bash
# Install Python dependencies
uv sync

# Install terminal controller
uvx terminal_controller
```

### 3. Set Up Credentials

Create `fastagent.secrets.yaml`:

```yaml
# Google Gemini API Key (required)
google:
  api_key: "your-google-gemini-api-key-here"

# Tavily API Key (for web search)
TAVILY_API_KEY: "tvly-your-tavily-api-key-here"
```

### 4. Get Your API Keys

#### Google Gemini API Key (Required):

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a new API key
3. Add to `fastagent.secrets.yaml`

#### Tavily API Key (for Web Search):

1. Go to [Tavily Search](https://tavily.com/)
2. Sign up and get your API key
3. Add to `fastagent.secrets.yaml`

## How to Run

### **Start the Smart Coordinator**

The intelligent coordinator handles all operations automatically:

```bash
uv run start.py
```

You'll see:

```
Europa — built on FastAgent MCP

Type /help for commands, @agent to switch agent. Ctrl+T toggles multiline mode.

maestro >
```

## Project Structure

```
mcp/
├── src/
│   └── mcp_agent/                    # Core FastAgent framework
│       ├── core/                     # Core agent functionality
│       ├── cli/                      # Command line interface
│       ├── mcp/                      # MCP server implementations
│       └── logging/                  # 🆕 Persistent logging system
│           ├── persistent_logger.py   # Main logging service
│           ├── error_handler.py       # Graceful error handling
│           └── log_manager.py         # Log rotation & analysis
├── logs/                             # 🆕 Auto-created logs directory
│   ├── europa_app.log                # Application logs
│   ├── europa_errors.log             # Error-only logs
│   ├── europa_mcp.log                # MCP server logs
│   ├── session_*.log                 # Individual session logs
│   ├── errors.jsonl                  # Structured error data
│   └── sessions.jsonl                # Session metadata
├── start.py                          # Main coordinator entry point
├── version.py                        # Dynamic version management
├── fastagent.config.yaml            # MCP server configuration
├── fastagent.secrets.yaml          # API keys (create this file)
├── pyproject.toml                   # Project dependencies
└── README.md                        # This file
```

### **Smart Routing Logic**

The coordinator automatically detects user intent and routes to specialized MCP servers:

1. **File Operations** → Filesystem MCP (keywords: file, directory, save, read)
2. **Web Research** → Tavily AI Search (keywords: search, find, lookup, research)
3. **Commands** → Terminal Controller (keywords: run, execute, command)
4. **Memory** → Memory Server (keywords: remember, recall, store)

## 🆕 Logging & Error Management

### **Log Files Overview**

- **`europa_app.log`** - All application activity, warnings, and errors
- **`europa_errors.log`** - Errors only with full stack traces
- **`europa_mcp.log`** - MCP server specific issues
- **`session_*.log`** - Individual session logs for debugging
- **`errors.jsonl`** - Structured error data for analysis
- **`sessions.jsonl`** - Session metadata and durations

### **Error Handling Features**

- **Graceful Shutdown** - 3-5 second delay when errors occur
- **Error Preview** - Recent errors displayed before shutdown
- **Log Persistence** - All errors saved even if tmux/terminal closes
- **Context Capture** - Function names, arguments, and environment data
- **Session Tracking** - Each run gets a unique session ID

### **Log Management**

```bash
# View recent errors
tail -f logs/europa_errors.log

# Check application logs
tail -f logs/europa_app.log

# View session summary
cat logs/sessions.jsonl | jq .

# Analyze error patterns
cat logs/errors.jsonl | jq '.exception.type' | sort | uniq -c
```

## Troubleshooting

### Common Setup Issues

1. **MCP Server Installation Errors**

   ```bash
   # Install terminal controller
   uvx terminal_controller

   # Test MCP servers
   npx -y @modelcontextprotocol/server-filesystem --help
   npx -y @mcptools/mcp-tavily --help
   ```

2. **Python Environment Issues**

   ```bash
   # Reinstall dependencies
   uv sync --reinstall
   ```

3. **API Key Issues**

   - Verify Google Gemini API key in `fastagent.secrets.yaml`
   - Check Tavily API key for web search functionality
   - Ensure API keys have proper permissions and credits

4. **Memory Not Persisting**

   - Memory server creates local storage files
   - Check if agent is searching memory before responding
   - Memory should persist across sessions automatically

5. **Slow Performance**

   - Gemini 2.0 Flash is optimized for speed
   - Check network connectivity for MCP servers
   - Monitor token usage to stay within limits

### **🆕 Error Troubleshooting**

6. **Application Crashes**

   - **Check** `logs/europa_errors.log` for detailed error information
   - **Review** the last session log: `logs/session_*.log`
   - **Analyze** structured errors: `logs/errors.jsonl`

7. **tmux Session Issues**

   - Logs persist even if tmux closes unexpectedly
   - Look for shutdown reason in `logs/sessions.jsonl`
   - Check for F1 terminal setup issues in application logs

8. **Logging Issues**

   - Logs directory is auto-created if missing
   - Log rotation occurs automatically (7 days, 50MB max)
   - Old logs are archived to `logs/archived/`

### Performance Optimization

- **Low Temperature (0.1)**: Ensures consistent, deterministic responses
- **4000 Token Limit**: Prevents long responses and reduces costs
- **Async Operations**: Concurrent handling for faster execution
- **Response Caching**: Reduced API calls for repeated requests
- **Connection Pooling**: Efficient resource management
- **Comprehensive Logging**: Issues tracked without performance impact

## **Performance Metrics**

- **Agent Startup**: ~3-6 seconds
- **Web Search**: ~2-4 seconds per query
- **Terminal Commands**: ~1-3 seconds execution time
- **File Operations**: ~0.5-2 seconds per operation
- **Memory Operations**: ~1-2 seconds per query
- **Token Usage**: ~200-800 tokens per interaction
- **Log Processing**: ~0.1-0.5 seconds per error

## **Security Features**

- **Secure Credential Management** - Separate secrets file
- **Controlled File Access** - Configurable filesystem permissions
- **Safe Terminal Execution** - Command validation and sandboxing
- **API Key Protection** - Environment-based secret management
- **Memory Isolation** - Local knowledge graph storage
- **Audit Logging** - Complete session and error tracking

**Ready to experience high-performance AI coordination with persistent memory and robust error handling!**

For support, feature requests, or contributions, create an issue in the repository.