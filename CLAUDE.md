# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VibeSurf is an AI agentic browser built with Python (backend) and React/TypeScript (frontend). It combines browser automation with AI intelligence through a multi-agent system, visual workflow builder, and Chrome extension integration.

**Core Stack:**
- Backend: FastAPI, LangGraph/LangChain, browser-use, SQLAlchemy, Uvicorn
- Frontend: React 18, TypeScript, Vite, Tailwind CSS, XYFlow (ReactFlow)
- Browser: Chrome DevTools Protocol (CDP), Playwright
- Python: 3.11+ (recommended 3.12)
- Package Manager: uv (0.7.20)

## Development Commands

### Backend Development

```bash
# Install dependencies (development mode)
uv venv --python 3.12
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
uv pip install -e .

# Start backend server (option 1 - direct)
uvicorn vibe_surf.backend.main:app --host 127.0.0.1 --port 9335

# Start backend server (option 2 - CLI)
uv run vibesurf

# For production users (no install)
uvx vibesurf
```

### Frontend Development

```bash
cd vibe_surf/frontend

# Install dependencies
npm ci

# Development server (proxies to backend at port 7860)
npm start

# Build for production
npm run build

# Copy build to backend directory
mkdir -p ../backend/frontend
cp -r build/* ../backend/frontend/

# Run tests
npm test
npm run test:coverage
npm run test:watch

# Linting and formatting
npm run format              # Auto-fix with Biome
npm run check-format        # Check only
npm run type-check          # TypeScript type checking
```

### Database Migrations

VibeSurf uses Alembic for database migrations (Langflow integration):

```bash
# Location: vibe_surf/langflow/alembic/
# Migrations run automatically on backend startup
# Database: SQLite at {workspace}/langflow.db
```

## Architecture

### Multi-Agent System

VibeSurf orchestrates multiple AI agents using LangGraph state machines:

1. **VibeSurfAgent** (`vibe_surf/agents/vibe_surf_agent.py`)
   - Main orchestrator that coordinates multiple browser agents
   - Manages parallel execution across browser tabs
   - Built on LangGraph for state management

2. **BrowserUseAgent** (`vibe_surf/agents/browser_use_agent.py`)
   - Extends browser-use's Agent class
   - Handles individual browser automation tasks
   - Integrates custom tools and file system access

3. **ReportWriterAgent** (`vibe_surf/agents/report_writer_agent.py`)
   - Specialized for content summarization and report generation

### Backend API Structure

The FastAPI backend (`vibe_surf/backend/main.py`) is organized into routers:

- `/api/task` - Task execution and management
- `/api/agent` - Agent operations and lifecycle
- `/api/browser` - Browser control and session management
- `/api/config` - LLM and voice profile configuration
- `/api/composio` - Third-party app integrations (100+ tools)
- `/api/skill` - AI skills registry (search, crawl, code execution)
- `/api/vibesurf` - Core VibeSurf operations
- `/api/schedule` - Scheduled task management
- `/api/files` - File operations
- `/api/activity` - Activity logging
- `/api/voices` - Voice model (ASR/TTS) management

### Browser Architecture

**AgentBrowserSession** manages browser instances with:
- Chrome DevTools Protocol (CDP) for low-level control
- Profile isolation per agent
- Watchdog monitoring for health checks
- Extension loading (when Chrome version < 142)

**Extension Integration:**
- Location: `vibe_surf/chrome_extension/`
- Manifest V3 with side panel UI
- WebSocket communication with backend
- Background service worker + content scripts

### Langflow Integration

VibeSurf embeds a fork of Langflow for visual workflow creation:

- Location: `vibe_surf/langflow/`
- 100+ pre-built components in `components/` directory
- Frontend at `vibe_surf/frontend/` (shared with VibeSurf UI)
- Database migrations in `alembic/`
- Component types: LLMs, agents, tools, data sources, embeddings

### Workflow System

Pre-built workflow templates in `vibe_surf/workflows/`:
- Categories: AIGC, Browser, FileSystem, Integrations, VibeSurf
- Combine deterministic automation with AI intelligence
- Minimize token consumption for repetitive tasks

### Tools and Skills

**Core Tools** (`vibe_surf/tools/`):
- `browser_use_tools.py` - Browser automation primitives
- `vibesurf_tools.py` - Search, crawl, JS code execution
- `file_system.py` - File operations
- `composio_client.py` - Integration with external apps
- `website_api/` - Native APIs for social platforms (Xiaohongshu, Douyin, Weibo, YouTube)
- `aigc/` - AI generation tools

**Skills** are higher-level capabilities registered via `/api/skill`:
- `/search` - Quick information retrieval
- `/crawl` - Website data extraction
- `/code` - Execute JavaScript in browser context

### Database Models

SQLAlchemy models (`vibe_surf/backend/database/models.py`):

- **Task**: Execution records with status (pending, running, paused, completed, failed, stopped)
- **LLMProfile**: LLM configurations with encrypted API keys
- **VoiceProfile**: ASR/TTS model configurations

Database location: `{workspace}/langflow.db` (SQLite)

### LLM Provider Support

Multi-provider architecture with unified interface:
- OpenAI, Anthropic, Google (Gemini), Azure OpenAI
- DeepSeek, Mistral, Ollama (local)
- Dashscope (Alibaba), Moonshot, SiliconFlow
- IBM WatsonX, Groq, Cohere, HuggingFace

Configuration via environment variables or LLMProfile database records.

## Environment Configuration

Create `.env` file based on `.env.example`:

**Critical Variables:**
- LLM API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- `VIBESURF_BACKEND_PORT` - Backend server port (default: 9335)
- `VIBESURF_EXTENSION` - Path to Chrome extension
- `VIBESURF_WORKSPACE` - Data directory location
- `BROWSER_EXECUTION_PATH` - Browser executable path
- `ANONYMIZED_TELEMETRY` - Enable/disable telemetry (default: false)
- `BROWSER_USE_LOGGING_LEVEL` - Logging verbosity (result | info | debug)

**Configuration Priority:**
1. `{workspace}/envs.json` (runtime configuration)
2. Environment variables
3. Defaults in code

Workspace directory determined by `vibe_surf/common.py:get_workspace_dir()`.

## Key Implementation Patterns

### Agent State Management

Agents use LangGraph's StateGraph for execution flow:
- Nodes represent agent actions
- Edges define state transitions
- Checkpointers enable pause/resume
- Streaming for real-time updates

### Browser Session Lifecycle

```python
# 1. BrowserManager creates isolated profiles
# 2. AgentBrowserSession wraps CDP connection
# 3. Watchdog monitors health
# 4. Session cleanup on completion/failure
```

### Tool Integration

Tools follow LangChain's structured tool pattern:
- Type-hinted parameters with Pydantic models
- Async execution for I/O operations
- Error handling with context preservation

### Frontend-Backend Communication

- REST API for CRUD operations
- WebSocket for streaming agent outputs
- Server-Sent Events (SSE) for workflow execution updates

## Common Workflows

### Adding a New LLM Provider

1. Create provider client in `vibe_surf/llm/`
2. Add to LLMProfile enum in `vibe_surf/backend/database/models.py`
3. Update provider factory in relevant agent code
4. Add API key to `.env.example`

### Creating a Custom Tool

1. Define tool in `vibe_surf/tools/`
2. Implement async function with Pydantic model for parameters
3. Register with `@tool` decorator (LangChain)
4. Add to agent's tool list in `vibe_surf/agents/`

### Building a New Workflow Template

1. Create workflow JSON in `vibe_surf/workflows/{category}/`
2. Use Langflow components from `vibe_surf/langflow/components/`
3. Test in workflow builder UI
4. Export and commit workflow file

## Testing

**Frontend Tests:**
```bash
cd vibe_surf/frontend
npm test                    # Run Jest tests
npm run test:coverage       # With coverage report
npm run test:watch          # Watch mode
```

**Backend Tests:**
No pytest configuration found - tests likely run via individual test files or manual testing.

## Platform-Specific Notes

**Windows:**
- DLL dependencies for torch/onnxruntime: Install [Visual C++ Redistributable](https://aka.ms/vc14/vc_redist.x64.exe)
- One-click installer available: `VibeSurf-Installer.exe`
- Use backslash paths or raw strings for file operations

**Chrome Extension Loading:**
- Chrome 142+ removed `--load-extension` flag
- Manual loading required: chrome://extensions → Developer mode → Load unpacked
- Extension location: `vibe_surf/chrome_extension/`

**Docker:**
- Set `IN_DOCKER=true` for optimized browser configuration
- Playwright browsers need proper installation in container

## Debugging

**Backend Debug Mode:**
```bash
# Enable verbose logging
export VIBESURF_DEBUG=true
export BROWSER_USE_LOGGING_LEVEL=debug

# Start with debugger support
python -m pdb -m vibe_surf.cli
```

**Frontend Debug:**
- React DevTools for component inspection
- Network tab for API calls (proxied to backend)
- Console for workflow execution logs

**Browser Automation:**
- Set `BROWSER_USE_LOGGING_LEVEL=debug` for detailed browser actions
- CDP messages logged when debug enabled
- Browser stays open on error for inspection

## Package Structure

```
vibe_surf/
├── agents/              # AI agent implementations
├── backend/             # FastAPI server
│   ├── api/            # API routers
│   ├── database/       # SQLAlchemy models
│   └── frontend/       # Built React app (copied from vibe_surf/frontend/build)
├── browser/            # Browser management
├── chrome_extension/   # Chrome extension (Manifest V3)
├── frontend/           # React TypeScript app (source)
├── langflow/          # Workflow builder (Langflow fork)
│   ├── alembic/       # Database migrations
│   ├── components/    # 100+ workflow components
│   └── services/      # Langflow backend services
├── llm/               # LLM provider integrations
├── tools/             # Agent tools
├── workflows/         # Pre-built workflow templates
├── cli.py            # CLI entry point
└── common.py         # Shared utilities
```

## Telemetry

VibeSurf collects anonymous usage data by default for product improvement:
- CLI startup events
- Agent execution metrics
- Error reporting via Sentry (if configured)

**Disable:**
```bash
export ANONYMIZED_TELEMETRY=false
# or in .env
ANONYMIZED_TELEMETRY=false
```

## Version Management

- Version determined by git tags via `setuptools-scm`
- Written to `vibe_surf/_version.py` on build
- CLI displays version from `vibe_surf.__version__`
