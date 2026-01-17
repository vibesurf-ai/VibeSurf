# VibeSurf：强大的浏览器助手，用于氛围冲浪

[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/86SPfhRVbk)
[![微信群](https://img.shields.io/badge/WeChat-微信群-07C160?logo=wechat&logoColor=white)](#-加入我们的社区)
[![WarmShao](https://img.shields.io/twitter/follow/warmshao?style=social)](https://x.com/warmshao)

VibeSurf 是一个开源的 AI 代理浏览器，它革新了浏览器自动化和研究。

如果你和我一样对开源 AI 浏览感到兴奋，请给它一个 star！⭐

[中文](README_zh.md) | [English](README.md)

## ✨ 主要特性

- 🧠 **高级 AI 自动化**：超越浏览器自动化，VibeSurf 执行深度研究、智能爬取、内容摘要等，以进行探索。

- 🚀 **多代理并行处理**：在不同的浏览器标签页中同时运行多个 AI 代理，实现深度研究和广泛研究，大幅提升效率。

- 🔄 **智能浏览器工作流**：创建自定义拖拽式和对话式工作流，将确定性自动化与 AI 智能相结合 - 非常适合自动登录、数据收集和社交媒体发布等重复性任务。

- 🎨 **无缝的 Chrome 扩展 UI**：原生浏览器集成，无需切换应用程序，提供直观的界面，感觉就像浏览器的一部分。

- 🔒 **隐私优先的 LLM 支持**：支持本地 LLM（Ollama 等）和自定义 LLM API，确保在氛围冲浪期间您的浏览数据保持私密和安全。

## 🚀 浏览器工作流的魔力

### 为什么浏览器工作流如此重要

🎯 **效率优先**：大多数浏览器操作都遵循可预测的模式 - 为什么每次都要用代理重新构建？工作流让您定义一次，永久运行。

💰 **节省 Token**：工作流几乎不消耗 token，仅在需要动态信息检索时使用。在保持智能的同时节省成本。

⚡ **速度与可靠性**：确定性工作流提供一致、快速且高度准确的结果。不再需要等待代理"思考"重复的步骤。

<video src="https://github.com/user-attachments/assets/5e50de7a-02e7-44e0-a95b-98d1a3eab66e" controls="controls">Your browser does not support playing this video!</video>

👉 [**探索工作流模板**](https://vibe-surf.com/workflows) - 从预构建的常用任务工作流开始！

## 🛠️ 安装

**Windows 用户**: 您也可以下载并运行我们的一键安装包：[VibeSurf-Installer.exe](https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/VibeSurf-Installer.exe)

> **注意**：如果在安装过程中遇到 torch c10.so 或 onnxruntime 找不到 DLL 的问题，请下载并安装 [Microsoft Visual C++ Redistributable](https://aka.ms/vc14/vc_redist.x64.exe)。

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

### 2. 安装 VibeSurf
将 VibeSurf 安装为工具

```bash
uv tool install vibesurf
```

> **提示**：使用 `uv tool upgrade vibesurf` 可升级到最新版本。

### 3. 启动 VibeSurf
启动 VibeSurf 浏览器助手

```bash
vibesurf
```

**注意**：从 Chrome 142 开始，不再支持 `--load-extension` 标志。首次启动 VibeSurf 时，**浏览器会弹出一个窗口显示扩展的路径**。手动加载扩展的步骤：

- 打开 chrome://extensions
- 启用开发者模式
- 点击"加载已解压的扩展程序"并导航到扩展文件夹

**常见扩展位置：**
- **Windows**: `C:\Users\<用户名>\AppData\Roaming\uv\tools\vibesurf\Lib\site-packages\vibe_surf\chrome_extension`
- **macOS**: `~/.local/share/uv/tools/vibesurf/lib/python3.<version>/site-packages/vibe_surf/chrome_extension`（将 `<version>` 替换为您的 Python 版本，例如 `python3.12`）

  > **提示**：除了弹窗显示的路径，您还可以在命令行启动日志中找到扩展路径。macOS 用户可以在 Finder 中按 `Cmd+Shift+G`，粘贴路径后按回车即可直接导航到该文件夹。

### 4. 开始使用

<video src="https://github.com/user-attachments/assets/86dba2e4-3f33-4ccf-b400-d07cf1a481a0" controls="controls">Your browser does not support playing this video!</video>

## 🐳 Docker（备选方案）

您也可以使用 Docker 运行 VibeSurf，并通过浏览器 VNC 访问：

### 方式 1: 使用 docker-compose（推荐）

```bash
# 1. 编辑 docker-compose.yml 添加您的 API keys（可选）
# 或创建 .env 文件配置环境变量

# 2. 启动 VibeSurf
docker-compose up -d

# 3. 访问 VibeSurf
# - 后端: http://localhost:9335
# - 浏览器 VNC (Web): http://localhost:6080 (密码: vibesurf)
```

> **提示**：中国用户可以在 `docker-compose.yml` 中设置 `USE_CHINA_MIRROR: true` 来使用国内镜像源加速构建。

### 方式 2: 使用 docker run

```bash
# 拉取镜像
docker pull ghcr.io/vibesurf-ai/vibesurf:latest

# 运行容器
docker run --name vibesurf -d --restart unless-stopped \
  -p 9335:9335 \
  -p 6080:6080 \
  -p 5901:5901 \
  -v ./data:/data \
  -e IN_DOCKER=true \
  -e VIBESURF_WORKSPACE=/data/vibesurf_workspace \
  -e VNC_PASSWORD=vibesurf \
  --shm-size=4g \
  --cap-add=SYS_ADMIN \
  ghcr.io/vibesurf-ai/vibesurf:latest
```

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

## 💬 加入我们的社区

欢迎加入我们的微信群讨论！

<img src="./vibe_surf/chrome_extension/icons/wx.png" width="300" alt="微信群">