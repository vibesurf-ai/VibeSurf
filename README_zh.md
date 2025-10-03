# VibeSurf：强大的浏览器助手，用于氛围冲浪

[![Discord](https://img.shields.io/discord/1303749220842340412?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://discord.gg/EZ2YnUXP)
[![WarmShao](https://img.shields.io/twitter/follow/warmshao?style=social)](https://x.com/warmshao)

VibeSurf 是一个开源的 AI 代理浏览器，它革新了浏览器自动化和研究。

如果你和我一样对开源 AI 浏览感到兴奋，请给它一个 star！⭐

[中文](README_zh.md) | [English](README.md)

## ✨ 主要特性

- 🧠 **高级 AI 自动化**：超越浏览器自动化，VibeSurf 执行深度研究、智能爬取、内容摘要等，以进行探索。

- 🚀 **多代理并行处理**：在不同的浏览器标签页中同时运行多个 AI 代理，实现深度研究和广泛研究，大幅提升效率。

- 🥷 **隐身优先架构**：使用 Chrome DevTools 协议（CDP）而不是 Playwright，提供卓越的隐身能力，防止机器人检测。

- 🎨 **无缝的 Chrome 扩展 UI**：原生浏览器集成，无需切换应用程序，提供直观的界面，感觉就像浏览器的一部分。

- 🔒 **隐私优先的 LLM 支持**：支持本地 LLM（Ollama 等）和自定义 LLM API，确保在氛围冲浪期间您的浏览数据保持私密和安全。

## 🛠️ 安装

### 第一步：安装 uv
从 [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/) 安装 uv：

```bash
# 在 macOS 和 Linux 上
curl -LsSf https://astral.sh/uv/install.sh | sh

# 在 Windows 上
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 第二步：设置和安装
```bash
uv venv --python 3.12
uv pip install vibesurf -U
```

### 第三步：启动
```bash
uv run vibesurf
```

## 👩‍💻 对贡献者

想为 VibeSurf 做贡献？以下是设置开发环境的两种方法：

### 方法 1：直接运行服务器
使用 uvicorn 直接运行后端服务器：
```bash
uvicorn vibe_surf.backend.main:app --host 127.0.0.1 --port 9335
```

### 方法 2：可编辑安装
以可编辑模式安装包并使用 CLI 运行：
```bash
uv pip install -e .
uv run vibesurf
```

选择最适合您开发工作流程的方法！

## 🗺️ 路线图

我们正在构建 VibeSurf，使其成为您终极的 AI 浏览器伴侣。以下是接下来的计划：

- [x] **智能技能系统**：添加 `/search` 用于快速信息搜索，`/crawl` 用于自动网站数据提取
- [ ] **强大的编码代理**：构建一个全面的编码助手，用于在浏览器中直接进行数据处理和分析
- [ ] **第三方集成**：与 n8n 工作流和其他工具连接，将浏览与自动化结合
- [ ] **自定义工作流模板**：创建可重用的模板，用于自动登录、数据收集和复杂的浏览器自动化
- [ ] **智能交互功能**：文本选择用于翻译/问答、截图分析和语音阅读功能
- [ ] **实时对话和记忆**：添加持久聊天功能和全局记忆，使 VibeSurf 真正理解您

## 🎬 演示

### 如何使用？
<video src="https://github.com/user-attachments/assets/0a4650c0-c4ed-423e-9e16-7889e9f9816d" controls="controls">您的浏览器不支持播放此视频！</video>

### 在浏览器中运行数十个代理
<video src="https://github.com/user-attachments/assets/9c461a6e-5d97-4335-ba09-59e8ec4ad47b" controls="controls">您的浏览器不支持播放此视频！</video>

## 📝 许可证

本仓库采用 [VibeSurf 开源许可证](./LICENSE)，基于 Apache 2.0 并附加额外条款。

## 👏 致谢

VibeSurf 建立在其他优秀的开源项目之上：

- [Browser Use](https://github.com/browser-use/browser-use)
- [LangGraph](https://github.com/langchain-ai/langgraph)

非常感谢他们的创作者和贡献者！