# VibeSurf: A powerful browser assistant for vibe surfing
[![Discord](https://img.shields.io/discord/1303749220842340412?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://discord.gg/TXNnP9gJ)
[![WarmShao](https://img.shields.io/twitter/follow/warmshao?style=social)](https://x.com/warmshao)

VibeSurf is an open-source AI agentic browser that revolutionizes browser automation and research.

If you're as excited about open-source AI browsing as I am, give it a star! ⭐

## ✨ Key Features

- 🧠 **Advanced AI Automation**: Beyond browser automation, VibeSurf performs deep research, intelligent crawling, content summarization, and more to exploration.

- 🚀 **Multi-Agent Parallel Processing**: Run multiple AI agents simultaneously in different browser tabs, enabling both deep research and wide research with massive efficiency gains.

- 🥷 **Stealth-First Architecture**: Uses Chrome DevTools Protocol (CDP) instead of Playwright for superior stealth capabilities, preventing bot detection.

- 🎨 **Seamless Chrome Extension UI**: Native browser integration without switching applications, providing an intuitive interface that feels like part of your browser.

- 🔒 **Privacy-First LLM Support**: Supports local LLMs (Ollama, etc.) and custom LLM APIs to ensure your browsing data stays private and secure during vibe surfing.

## 🛠️ Installation

### Step 1: Install uv
Install uv from [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/):

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 2: Setup and Install
```bash
uv venv --python 3.12
uv pip install vibesurf -U
```

### Step 3: Launch
```bash
uv run vibesurf
```

## 🗺️ Roadmap

We're building VibeSurf to be your ultimate AI browser companion. Here's what's coming next:

- [ ] **Smart Skills System**: Add `/search` for quick information search and `/crawl` for automatic website data extraction
- [ ] **Powerful Coding Agent**: Build a comprehensive coding assistant for data processing and analysis directly in your browser
- [ ] **Third-Party Integrations**: Connect with n8n workflows and other tools to combine browsing with automation
- [ ] **Custom Workflow Templates**: Create reusable templates for auto-login, data collection, and complex browser automation
- [ ] **Smart Interaction Features**: Text selection for translation/Q&A, screenshot analysis, and voice reading capabilities
- [ ] **Real-Time Conversation & Memory**: Add persistent chat functionality with global memory to make VibeSurf truly understand you


## 🎬 Demo

### How to use?
<video src="https://github.com/user-attachments/assets/0a4650c0-c4ed-423e-9e16-7889e9f9816d" controls="controls">Your browser does not support playing this video!</video>

### Dozens of agent running in on browser
<video src="https://github.com/user-attachments/assets/9c461a6e-5d97-4335-ba09-59e8ec4ad47b" controls="controls">Your browser does not support playing this video!</video>


## 📝 License

Licensed under the [Apache License 2.0](LICENSE).

## 👏 Acknowledgments

VibeSurf builds on top of other awesome open-source projects:

- [Browser Use](https://github.com/browser-use/browser-use)
- [LangGraph](https://github.com/langchain-ai/langgraph)

Huge thanks to their creators and contributors!

