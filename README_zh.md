# VibeSurf：强大的浏览器助手，用于氛围冲浪

[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/86SPfhRVbk)
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

**Windows 用户**: 您也可以下载并运行我们的一键安装包：[VibeSurf-Installer.exe](https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/VibeSurf-Installer.exe)

仅需三个简单步骤即可启动并运行 VibeSurf。无需复杂配置。

### 1. 安装 uv
从官方网站安装 uv 包管理器

**MacOS/Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows**
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 设置环境
安装 VibeSurf

```bash
uv pip install vibesurf -U
```

### 3. 启动 VibeSurf
启动 VibeSurf 浏览器助手

```bash
uv run vibesurf
```

**注意**：从 Chrome 142 开始，不再支持 `--load-extension` 标志，这意味着 VibeSurf 无法自动加载扩展。如果启动 VibeSurf 后找不到 VibeSurf 扩展，请从[这里](https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/vibesurf-extension.zip)手动下载并按照以下步骤操作：

- 解压下载的 zip 文件
- 打开 chrome://extensions
- 启用开发者模式
- 点击"加载已解压的扩展程序"并选择解压后的文件夹

### 4. 开始使用

<video src="https://github.com/user-attachments/assets/86dba2e4-3f33-4ccf-b400-d07cf1a481a0" controls="controls">Your browser does not support playing this video!</video>


## 👩‍💻 贡献者指南

想为 VibeSurf 做贡献？请按照以下步骤设置您的开发环境：

### 1. 克隆仓库
```bash
git clone https://github.com/vibesurf-ai/VibeSurf.git
cd VibeSurf
```

### 2. 设置环境
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

### 3. 构建前端（可选）
如果您正在进行前端更改，需要构建前端并将其复制到后端目录：

```bash
# 导航到前端目录
cd vibe_surf/frontend

# 安装前端依赖
npm ci

# 构建前端
npm run build

# 将构建输出复制到后端目录
mkdir -p ../backend/frontend
cp -r build/* ../backend/frontend/
```

### 4. 开始调试
**选项 1：直接服务器**
```bash
uvicorn vibe_surf.backend.main:app --host 127.0.0.1 --port 9335
```

**选项 2：CLI 入口**
```bash
uv run vibesurf
```

## 🗺️ 路线图

我们正在构建 VibeSurf，使其成为您终极的 AI 浏览器伴侣。以下是接下来的计划：

- [x] **智能技能系统** - *已完成*
  添加 `/search` 用于快速信息搜索，`/crawl` 用于自动网站数据提取, `/code`用于页面自动执行js code。集成了小红书、抖音、微博和 YouTube 的原生 API。

- [x] **第三方集成** - *已完成*
  通过 Composio 集成连接数百种常用工具，包括 Gmail、Notion、Google Calendar、Slack、Trello、GitHub 等，将浏览与强大的自动化功能相结合

- [x] **智能浏览器工作流** - *已完成*
  创建自定义拖拽式和对话式工作流，用于自动登录、数据收集和复杂的浏览器自动化任务

- [ ] **强大的编码代理** - *进行中*
  构建一个全面的编码助手，用于在浏览器中直接进行数据处理和分析

- [ ] **智能记忆与个性化** - *计划中*
  将 VibeSurf 转变为真正的人性化伴侣，具备持久记忆功能，能够学习您的偏好、习惯和浏览模式

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
- [Langflow](https://github.com/langflow-ai/langflow)

非常感谢他们的创作者和贡献者！