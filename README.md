# VibeSurf: A powerful browser assistant for vibe surfing
[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/EZ2YnUXP)
[![WarmShao](https://img.shields.io/twitter/follow/warmshao?style=social)](https://x.com/warmshao)
[![PyPI Downloads](https://img.shields.io/pypi/dm/vibesurf?label=PyPI%20Downloads)](https://pypi.org/project/vibesurf/)

VibeSurf is an open-source AI agentic browser that revolutionizes browser automation and research.

If you're as excited about open-source AI browsing as I am, give it a star! ⭐

[中文](README_zh.md) | [English](README.md)

## ✨ Key Features

- 🧠 **Advanced AI Automation**: Beyond browser automation, VibeSurf performs deep research, intelligent crawling, content summarization, and more to exploration.

- 🚀 **Multi-Agent Parallel Processing**: Run multiple AI agents simultaneously in different browser tabs, enabling both deep research and wide research with massive efficiency gains.

- 🥷 **Stealth-First Architecture**: Uses Chrome DevTools Protocol (CDP) instead of Playwright for superior stealth capabilities, preventing bot detection.

- 🎨 **Seamless Chrome Extension UI**: Native browser integration without switching applications, providing an intuitive interface that feels like part of your browser.

- 🔒 **Privacy-First LLM Support**: Supports local LLMs (Ollama, etc.) and custom LLM APIs to ensure your browsing data stays private and secure during vibe surfing.

## 🛠️ Installation

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

### 2. Setup Environment
Install VibeSurf

```bash
uv pip install vibesurf -U
```

### 3. Launch VibeSurf
Start the VibeSurf browser assistant

```bash
uv run vibesurf
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

**Windows**
```bash
uv venv --python 3.12
.venv\Scripts\activate
uv pip install -e .
```

### 3. Start Debugging
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

- [ ] **Agentic Browser Workflow** - *In Progress*
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

Huge thanks to their creators and contributors!

