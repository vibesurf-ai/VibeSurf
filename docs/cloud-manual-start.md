# 云端手动启动 VibeSurf 指南

## 问题说明

在云端容器环境（如 Kubernetes、Docker Compose）中，使用 supervisord 自动启动时，可能会遇到浏览器启动超时的问题。这是因为：

- **Xvfb（虚拟显示器）** 启动较慢
- **vibesurf** 在 Xvfb 准备好之前就尝试启动浏览器
- 导致 `DISPLAY=:99` 不可用，浏览器启动失败

而 `--headless` 模式不依赖 X11，所以能正常工作。

## 快速开始（推荐）

使用一键安装脚本：

```bash
# 下载并运行安装脚本
curl -fsSL https://raw.githubusercontent.com/vibesurf-ai/VibeSurf/main/scripts/setup-vibesurf-cloud.sh | sudo bash

# 或者先下载再运行
wget https://raw.githubusercontent.com/vibesurf-ai/VibeSurf/main/scripts/setup-vibesurf-cloud.sh
sudo bash setup-vibesurf-cloud.sh
```

安装完成后，只需运行：
```bash
# 启动 GUI 环境（包含 Xvfb + x11vnc + noVNC + fcitx5）
start-vibesurf-gui
```

然后在另一个终端：
```bash
# 启动 vibesurf
export DISPLAY=:99
vibesurf
```

## 手动安装

如果无法使用脚本，可以手动安装和配置：

### 1. 进入容器

```bash
docker exec -it vibesurf bash
# 或者 kubectl exec -it <pod-name> -- bash
```

### 2. 停止自动启动的服务（可选）

如果 supervisord 已经启动了部分服务，先停止：

```bash
pkill -9 Xvfb
pkill -9 x11vnc
pkill -f novnc_proxy
```

### 3. 启动 Xvfb（虚拟显示器）

```bash
export DISPLAY=:99
export RESOLUTION=${RESOLUTION:-1440x900x24}

Xvfb :99 -screen 0 $RESOLUTION -ac +extension GLX +render -noreset &

# 等待启动完成
sleep 2

# 验证
xdpyinfo -display :99 | head -5
```

### 4. 设置 VNC 密码

```bash
# 创建密码文件
mkdir -p ~/.vnc

# 方式1：使用 vncpasswd 工具（推荐）
echo "your_password" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# 方式2：直接设置（密码为 "vibesurf"）
# echo -n "vibesurf" | vncpasswd -f > ~/.vnc/passwd
# chmod 600 ~/.vnc/passwd
```

### 5. 启动 x11vnc（VNC 服务器）

```bash
x11vnc -display :99 \
  -forever \
  -shared \
  -noprimary \
  -rfbauth ~/.vnc/passwd \
  -rfbport 5901 &

# 等待启动
sleep 2

# 验证端口
netstat -tlnp | grep 5901
```

### 6. 启动 noVNC（Web VNC 客户端）

```bash
cd /opt/novnc

./utils/novnc_proxy \
  --vnc localhost:5901 \
  --listen 0.0.0.0:6080 \
  --web /opt/novnc
```

### 7. 启动 VibeSurf

在另一个终端窗口（或后台运行）：

```bash
export DISPLAY=:99
export IN_DOCKER=true

# 如果使用预装浏览器
export BROWSER_EXECUTION_PATH=$(find /ms-browsers/chromium-*/chrome-linux*/chrome 2>/dev/null | head -1)

vibesurf --no_select_browser --host 0.0.0.0
```

## 一键启动脚本

将以下内容保存为 `start-vibesurf.sh`：

```bash
#!/bin/bash
set -e

# 环境变量
export DISPLAY=:99
export RESOLUTION=${RESOLUTION:-1440x900x24}
export VNC_PASSWORD=${VNC_PASSWORD:-vibesurf}

# 清理旧进程
echo "[1/5] 清理旧进程..."
pkill -9 Xvfb 2>/dev/null || true
pkill -9 x11vnc 2>/dev/null || true
pkill -f novnc_proxy 2>/dev/null || true
sleep 1

# 启动 Xvfb
echo "[2/5] 启动 Xvfb..."
Xvfb :99 -screen 0 $RESOLUTION -ac +extension GLX +render -noreset &
sleep 2

# 验证 Xvfb
if ! xdpyinfo -display :99 >/dev/null 2>&1; then
    echo "错误: Xvfb 启动失败"
    exit 1
fi
echo "✓ Xvfb 启动成功"

# 设置 VNC 密码
echo "[3/5] 设置 VNC 密码..."
mkdir -p ~/.vnc
echo "$VNC_PASSWORD" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# 启动 x11vnc
echo "[4/5] 启动 x11vnc..."
x11vnc -display :99 -forever -shared -noprimary -rfbauth ~/.vnc/passwd -rfbport 5901 &
sleep 2

echo "✓ x11vnc 启动成功 (端口: 5901)"

# 启动 noVNC
echo "[5/5] 启动 noVNC..."
cd /opt/novnc
nohup ./utils/novnc_proxy --vnc localhost:5901 --listen 0.0.0.0:6080 --web /opt/novnc > /var/log/novnc.log 2>&1 &
sleep 1

echo "✓ noVNC 启动成功"
echo ""
echo "========================================"
echo "访问地址: http://$(hostname -I | awk '{print $1}'):6080/vnc.html"
echo "VNC 密码: $VNC_PASSWORD"
echo "========================================"
echo ""
echo "现在可以启动 vibesurf 了:"
echo "  export DISPLAY=:99"
echo "  vibesurf --no_select_browser --host 0.0.0.0"
```

赋予执行权限并运行：

```bash
chmod +x start-vibesurf.sh
./start-vibesurf.sh
```

## 访问方式

| 服务 | 地址 | 说明 |
|------|------|------|
| VibeSurf API | `http://<服务器IP>:9335` | REST API 和 WebSocket |
| noVNC (Web) | `http://<服务器IP>:6080/vnc.html` | 浏览器访问，输入 VNC 密码 |
| VNC 客户端 | `<服务器IP>:5901` | 使用 VNC Viewer 等客户端 |

## 常见问题

### 1. Xvfb 启动失败

```bash
# 检查是否已存在
telnet localhost 99

# 换一个 display 号
Xvfb :100 -screen 0 1440x900x24 -ac +extension GLX +render -noreset &
export DISPLAY=:100
```

### 2. noVNC 连接被拒绝

确保 x11vnc 先于 noVNC 启动，并且 5901 端口在监听：

```bash
netstat -tlnp | grep 5901
```

### 3. 浏览器显示空白

检查 vibesurf 是否使用了正确的 DISPLAY：

```bash
echo $DISPLAY  # 应该输出 :99
```

### 4. 中文输入法不工作

确保 fcitx5 已启动：

```bash
fcitx5 --replace &
```

## 与 supervisord 共存

如果容器使用 supervisord，可以修改 `supervisord.conf` 给 vibesurf 添加更长的等待时间：

```ini
[program:vibesurf]
command=bash -c "sleep 15 && vibesurf --no_select_browser --host 0.0.0.0"
startsecs=15
```

或者禁用自动启动，完全使用手动方式。
