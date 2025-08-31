# VibeSurf: A powerful browser assistant for vibe surfing

VibeSurf is an open-source AI agentic browser that revolutionizes browser automation and research.

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
uv pip install vibesurf
```

### Step 3: Launch
```bash
vibesurf
```

## 🎬 Demo

<!-- VIDEO_PLACEHOLDER: Add demo video here -->

## 📝 License

Licensed under the [Apache License 2.0](LICENSE).

## 👏 Acknowledgments

VibeSurf builds on top of other awesome open-source projects:

- [Browser Use](https://github.com/browser-use/browser-use)
- [LangGraph](https://github.com/langchain-ai/langgraph)

Huge thanks to their creators and contributors!

