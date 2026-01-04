# VibeSurf: A powerful browser assistant for vibe surfing
[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/86SPfhRVbk)
[![WeChat](https://img.shields.io/badge/WeChat-Group-07C160?logo=wechat&logoColor=white)](#-join-our-community)
[![WarmShao](https://img.shields.io/twitter/follow/warmshao?style=social)](https://x.com/warmshao)

VibeSurf is an open-source AI agentic browser that revolutionizes browser automation and research.

If you're as excited about open-source AI browsing as I am, give it a star! ⭐

[中文](README_zh.md) | [English](README.md)

## ✨ Key Features

- 🧠 **Advanced AI Automation**: Beyond browser automation, VibeSurf performs deep research, intelligent crawling, content summarization, and more to exploration.

- 🚀 **Multi-Agent Parallel Processing**: Run multiple AI agents simultaneously in different browser tabs, enabling both deep research and wide research with massive efficiency gains.

- 🔄 **Agentic Browser Workflow**: Create custom drag-and-drop and conversation-based workflows that combine deterministic automation with AI intelligence - perfect for repetitive tasks like auto-login, data collection, and social media posting.

- 🎨 **Seamless Chrome Extension UI**: Native browser integration without switching applications, providing an intuitive interface that feels like part of your browser.

- 🔒 **Privacy-First LLM Support**: Supports local LLMs (Ollama, etc.) and custom LLM APIs to ensure your browsing data stays private and secure during vibe surfing.

## 🚀 Browser Workflow Magic

### Why Browser Workflow Matters

🎯 **Efficiency First**: Most browser operations follow predictable patterns - why rebuild them every time with agents? Workflows let you define once, run forever.

💰 **Token Savings**: Workflows consume virtually zero tokens, only using them when dynamic information retrieval is needed. Save costs while maintaining intelligence.

⚡ **Speed & Reliability**: Deterministic workflows deliver consistent, fast, and highly accurate results. No more waiting for agents to "think" through repetitive steps.

<video src="https://github.com/user-attachments/assets/5e50de7a-02e7-44e0-a95b-98d1a3eab66e" controls="controls">Your browser does not support playing this video!</video>

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

### 3. Launch VibeSurf
Start the VibeSurf browser assistant

```bash
vibesurf
```

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
