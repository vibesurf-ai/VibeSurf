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

### 🤖 Agent Enhancements

- **VibeSurf Agent Refactoring**: Remove LangGraph framework dependency to make the agent more flexible and powerful
- **Advanced Coding Agent**: Design a powerful coding agent capable of handling and analyzing complex data, generating charts and visualizations. Combined with VibeSurf agent, this will create a "local Manus" experience
- **Enhanced Report Writer Agent**: Optimize the report writer to generate more visually appealing reports with rich graphics and illustrations
- **Global Memory System**: Implement global memory capabilities to make VibeSurf understand and adapt to user preferences better

### 🧩 Extension Features

- **Enhanced Tab Management**: Add @specific tab handling with `/research` and `/deep_research` specialized task commands
- **Smart Text Processing**: Implement word/paragraph translation, summarization, and explanation features for selected content
- **Local Credential Management**: Add secure credential configuration system to keep your privacy data stored locally


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

