# VibeSurf: A powerful browser assistant for vibe surfing
[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/86SPfhRVbk)
[![WeChat](https://img.shields.io/badge/WeChat-Group-07C160?logo=wechat&logoColor=white)](#-join-our-community)
[![WarmShao](https://img.shields.io/twitter/follow/warmshao?style=social)](https://x.com/warmshao)

> **Note**: VibeSurf can be used in Claude Code for control and real-time preview of browsers. For more details, see the [claude-surf plugin](https://github.com/vibesurf-ai/claude-surf).
>
> **Note**: VibeSurf is also available in Open-Claw. Install with: `npx clawhub@latest install vibesurf`. For more details, see [claw-surf](https://github.com/vibesurf-ai/claw-surf).

**VibeSurf** is the first open-source AI agentic browser that combines **workflow automation** with **intelligent AI agents** - delivering browser automation that's **faster**, **cheaper**, and **smarter** than traditional solutions.

🎯 **Why VibeSurf?** Save 99% of token costs with workflows, run parallel AI agents across tabs, and keep your data private with local LLM support - all through a seamless Chrome extension.

🐳 **Quick Start with Docker**: Get up and running in seconds with our [Docker image](#-docker-alternative) - no complex setup required!

If you're as excited about open-source AI browsing as I am, give it a star! ⭐

[中文](README_zh.md) | [English](README.md)

## ✨ Key Features

- 🔄 **Revolutionary Browser Workflows**: Create drag-and-drop workflows that consume virtually zero tokens - define once, run forever. Perfect for auto-login, data collection, and repetitive tasks with 100x speed boost.

- 🚀 **Multi-Agent Parallel Processing**: Run multiple AI agents simultaneously across different browser tabs for massive efficiency gains in both deep and wide research.

- 🧠 **Intelligent AI Automation**: Beyond basic automation - perform deep research, intelligent crawling, content summarization, and adaptive browsing with AI decision-making.

- 🔒 **Privacy-First Architecture**: Full support for local LLMs (Ollama, etc.) and custom APIs - your browsing data never leaves your machine during vibe surfing.

- 🎨 **Seamless Chrome Extension**: Native browser integration without switching applications - feels like a natural part of your browser with intuitive UI.

- 🐳 **One-Click Docker Deployment**: Get started instantly with our [Docker image](#-docker-alternative) - includes VNC access for remote browsing and easy scaling.

## 🚀 Browser Workflow Magic

### Why Browser Workflow Matters

🎯 **Efficiency First**: Most browser operations follow predictable patterns - why rebuild them every time with agents? Workflows let you define once, run forever.

💰 **Token Savings**: Workflows consume virtually zero tokens, only using them when dynamic information retrieval is needed. Save costs while maintaining intelligence.

⚡ **Speed & Reliability**: Deterministic workflows deliver consistent, fast, and highly accurate results. No more waiting for agents to "think" through repetitive steps.

[![Tutorial: Build Browser Automation Workflow and Deploy as API](https://img.youtube.com/vi/N9VMzLMKKpk/maxresdefault.jpg)](https://www.youtube.com/watch?v=N9VMzLMKKpk)

*A tutorial that step-by-step guides you from scratch on using VibeSurf to build a browser automation workflow that searches X and extracts results. Beyond the basics, it demonstrates how to transform this workflow into a deployable API and integrate it as a custom Skill within Claude Code.*

👉 [**Explore Workflow Templates**](https://vibe-surf.com/workflows) - Get started with pre-built workflows for common tasks!

## 🛠️ Installation

**For Windows users**: You can also download and run our one-click installer: [VibeSurf-Installer.exe](https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/VibeSurf-Installer.exe)

> **Note**: If you encounter DLL errors related to torch c10.so or onnxruntime during installation, please download and install the [Microsoft Visual C++ Redistributable](https://aka.ms/vc14/vc_redist.x64.exe).

Get VibeSurf up and running in just three simple steps. No complex configuration required.

### 1. Install uv
Install uv package manager from the official website

**MacOS/Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows**
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install VibeSurf
Install VibeSurf as a tool

```bash
uv tool install vibesurf
```

> **Tip**: Use `uv tool upgrade vibesurf` to upgrade to the latest version.
>
> **Full Installation**: To install with all optional features (including PyTorch, OCR, and advanced document processing), use `uv tool install vibesurf[full]`.

### 3. Launch VibeSurf
Start the VibeSurf browser assistant

```bash
vibesurf
```

> **Note**: To run in headless browser mode without a visible GUI, use the `--headless` flag:
> ```bash
> vibesurf --headless
> ```

**Note**: Starting from Chrome 142, the `--load-extension` flag is no longer supported. When you first start VibeSurf, **the browser will show a popup displaying the extension path**. To manually load the extension:

- Open chrome://extensions
- Enable Developer mode
- Click "Load unpacked" and navigate to the extension folder

**Typical Extension Locations:**
- **Windows**: `C:\Users\<username>\AppData\Roaming\uv\tools\vibesurf\Lib\site-packages\vibe_surf\chrome_extension`
- **macOS**: `~/.local/share/uv/tools/vibesurf/lib/python3.<version>/site-packages/vibe_surf/chrome_extension` (replace `<version>` with your Python version, e.g., `python3.12`)

  > **Tip**: Besides the popup, you can also find the extension path in the command line startup logs. For macOS users, press `Cmd+Shift+G` in Finder, paste the path, and press Enter to navigate directly to the folder.

### 4. Start to Use

<video src="https://github.com/user-attachments/assets/86dba2e4-3f33-4ccf-b400-d07cf1a481a0" controls="controls">Your browser does not support playing this video!</video>

## 🐳 Docker (Alternative)

You can also run VibeSurf in Docker with browser VNC access:

### Option 1: Using docker-compose (Recommended)

```bash
# 1. Clone VibeSurf Repo
git clone https://github.com/vibesurf-ai/VibeSurf
cd VibeSurf
# Optional: Edit docker-compose.yml to modify envs

# 2. Start VibeSurf
docker-compose up -d

# 3. Access VibeSurf
# - Backend: http://localhost:9335
# - Browser VNC (Web): http://localhost:6080 (default password: vibesurf)
```

> **Note**: The VNC browser environment defaults to English input. Press `Ctrl + Space` to switch to Chinese Pinyin input method.

> **Note**: To use a proxy, set the `HTTP_PROXY` and `HTTPS_PROXY` environment variables in `docker-compose.yml` (e.g., `HTTP_PROXY: http://proxy.example.com:8080`).

### Option 2: Using docker run

```bash
# Pull the image
docker pull ghcr.io/vibesurf-ai/vibesurf:latest

# Run the container
docker run --name vibesurf -d --restart unless-stopped \
  -p 9335:9335 \
  -p 6080:6080 \
  -p 5901:5901 \
  -v ./data:/data \
  -e IN_DOCKER=true \
  -e VIBESURF_BACKEND_PORT=9335 \
  -e VIBESURF_WORKSPACE=/data/vibesurf_workspace \
  -e RESOLUTION=1440x900x24 \
  -e VNC_PASSWORD=vibesurf \
  --shm-size=4g \
  --cap-add=SYS_ADMIN \
  ghcr.io/vibesurf-ai/vibesurf:latest
```

## 👩‍💻 For Contributors

Want to contribute to VibeSurf? Follow these steps to set up your development environment:

### 1. Clone Repository
```bash
git clone https://github.com/vibesurf-ai/VibeSurf.git
cd VibeSurf
```

### 2. Setup Environment
**MacOS/Linux**
```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

**Full Installation (with all optional features)**
```bash
uv pip install -e ".[full]"
```

**Windows**
```bash
uv venv --python 3.12
.venv\Scripts\activate
uv pip install -e .
```

### 3. Build Frontend (Optional)
If you're working on frontend changes, you need to build and copy the frontend to the backend directory:

```bash
# Navigate to frontend directory
cd vibe_surf/frontend

# Install frontend dependencies
npm ci

# Build the frontend
npm run build

# Copy build output to backend directory
mkdir -p ../backend/frontend
cp -r build/* ../backend/frontend/
```

### 4. Start Debugging
**Option 1: Direct Server**
```bash
uvicorn vibe_surf.backend.main:app --host 127.0.0.1 --port 9335
```

**Option 2: CLI Entry**
```bash
uv run vibesurf
```
## 🗺️ Roadmap

We're building VibeSurf to be your ultimate AI browser companion. Here's what's coming next:

- [x] **Smart Skills System** - *Completed*
  Add `/search` for quick information search, `/crawl` for automatic website data extraction and `/code` for webpage js code execution. Integrated native APIs for Xiaohongshu, Douyin, Weibo, and YouTube.

- [x] **Third-Party Integrations** - *Completed*
  Connect with hundreds of popular tools including Gmail, Notion, Google Calendar, Slack, Trello, GitHub, and more through Composio integration to combine browsing with powerful automation capabilities

- [x] **Agentic Browser Workflow** - *Completed*
  Create custom drag-and-drop and conversation-based workflows for auto-login, data collection, and complex browser automation tasks

- [ ] **Powerful Coding Agent** - *In Progress*
  Build a comprehensive coding assistant for data processing and analysis directly in your browser

- [ ] **Intelligent Memory & Personalization** - *Planned*
  Transform VibeSurf into a truly human-like companion with persistent memory that learns your preferences, habits, and browsing patterns over time


## 🎬 Demo

### How to use?
<video src="https://github.com/user-attachments/assets/0a4650c0-c4ed-423e-9e16-7889e9f9816d" controls="controls">Your browser does not support playing this video!</video>

### Dozens of agent running in on browser
<video src="https://github.com/user-attachments/assets/9c461a6e-5d97-4335-ba09-59e8ec4ad47b" controls="controls">Your browser does not support playing this video!</video>


## 📝 License

This repository is licensed under the [VibeSurf Open Source License](./LICENSE), based on Apache 2.0 with additional conditions.

## 👏 Acknowledgments

VibeSurf builds on top of other awesome open-source projects:

- [Browser Use](https://github.com/browser-use/browser-use)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [Langflow](https://github.com/langflow-ai/langflow)

Huge thanks to their creators and contributors!



## 💬 Join Our Community

Welcome to join our WeChat group for discussions!

<img src="./vibe_surf/chrome_extension/icons/wx.png" width="300" alt="WeChat Group">
