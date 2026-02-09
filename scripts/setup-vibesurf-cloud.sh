#!/bin/bash
#
# VibeSurf 云端环境安装脚本
# 用于在云端服务器（如 Ubuntu VM、K8s 容器）上安装 VibeSurf 所需的全部依赖
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的信息
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    error "请使用 root 用户运行此脚本"
    exit 1
fi

# 检测是否使用中国镜像
USE_CHINA_MIRROR=${USE_CHINA_MIRROR:-false}
if [ "$USE_CHINA_MIRROR" = "true" ]; then
    info "使用中国镜像源..."
    sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true
fi

# ============================================
# 1. 安装系统依赖
# ============================================
info "步骤 1/5: 安装系统依赖..."

apt-get update

apt-get install -y --no-install-recommends \
    # 基本工具
    wget \
    curl \
    git \
    unzip \
    vim \
    netcat-traditional \
    gnupg \
    ca-certificates \
    # 浏览器依赖
    xvfb \
    libxss1 \
    libnss3 \
    libnspr4 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    fonts-liberation \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fontconfig \
    # 中文字体
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    # 输入法框架和中文输入
    fcitx5 \
    fcitx5-chinese-addons \
    fcitx5-frontend-gtk3 \
    fcitx5-frontend-gtk2 \
    fcitx5-frontend-qt5 \
    fcitx5-config-qt \
    fcitx5-module-xorg \
    im-config \
    # VNC 依赖
    dbus \
    xauth \
    x11vnc \
    tigervnc-tools \
    # 进程管理
    supervisor \
    net-tools \
    procps \
    # Python numpy 依赖
    python3-numpy \
    # FFmpeg 视频处理
    ffmpeg

apt-get clean
rm -rf /var/lib/apt/lists/*

info "✓ 系统依赖安装完成"

# ============================================
# 2. 安装 noVNC
# ============================================
info "步骤 2/5: 安装 noVNC..."

if [ -d "/opt/novnc" ]; then
    warn "noVNC 已存在，跳过安装"
else
    if [ "$USE_CHINA_MIRROR" = "true" ]; then
        # 使用国内镜像加速
        git clone https://ghproxy.com/https://github.com/novnc/noVNC.git /opt/novnc || \
        git clone https://github.com/novnc/noVNC.git /opt/novnc
        git clone https://ghproxy.com/https://github.com/novnc/websockify /opt/novnc/utils/websockify || \
        git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify
    else
        git clone https://github.com/novnc/noVNC.git /opt/novnc
        git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify
    fi
    ln -sf /opt/novnc/vnc.html /opt/novnc/index.html
    info "✓ noVNC 安装完成"
fi

# ============================================
# 3. 配置 fcitx5 中文输入法
# ============================================
info "步骤 3/5: 配置 fcitx5 中文输入法..."

mkdir -p ~/.config/fcitx5

# 创建 fcitx5 profile 配置
cat > ~/.config/fcitx5/profile << 'EOF'
[Groups/0]
Name=Default
Default Layout=us
DefaultIM=pinyin

[Groups/0/Items/0]
Name=keyboard-us
Layout=

[Groups/0/Items/1]
Name=pinyin
Layout=

[GroupOrder]
0=Default
EOF

# 创建 fcitx5 配置
cat > ~/.config/fcitx5/config << 'EOF'
[Hotkey]
# Trigger Input Method (Shift+Space for better macOS compatibility)
TriggerKeys=
# Enumerate when press trigger key repeatedly
EnumerateWithTriggerKeys=True
# Temporally switch between first and current Input Method
AltTriggerKeys=
# Enumerate Input Method Forward
EnumerateForwardKeys=
# Enumerate Input Method Backward
EnumerateBackwardKeys=
# Skip first input method while enumerating
EnumerateSkipFirst=False

[Hotkey/TriggerKeys]
0=Control+space
1=Shift+space

[Behavior]
# Active By Default
ActiveByDefault=False
# Share Input State
ShareInputState=No
EOF

info "✓ fcitx5 配置完成"

# ============================================
# 4. 设置环境变量
# ============================================
info "步骤 4/5: 设置环境变量..."

cat >> ~/.bashrc << 'EOF'

# VibeSurf 环境变量
export IN_DOCKER=true
export DISPLAY=:99
export RESOLUTION=1440x900x24
export VIBESURF_WORKSPACE=/data/vibesurf_workspace
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export DBUS_SESSION_BUS_ADDRESS=unix:path=/var/run/dbus/session_bus_socket
EOF

# 立即生效
export IN_DOCKER=true
export DISPLAY=:99
export RESOLUTION=1440x900x24
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export DBUS_SESSION_BUS_ADDRESS=unix:path=/var/run/dbus/session_bus_socket

info "✓ 环境变量设置完成"

# ============================================
# 5. 创建启动脚本
# ============================================
info "步骤 5/5: 创建启动脚本..."

cat > /usr/local/bin/start-vibesurf-gui << 'SCRIPT'
#!/bin/bash
#
# 启动 VibeSurf GUI 环境（Xvfb + x11vnc + noVNC）
#

set -e

# 默认配置
export DISPLAY=${DISPLAY:-:99}
export RESOLUTION=${RESOLUTION:-1440x900x24}
export VNC_PASSWORD=${VNC_PASSWORD:-vibesurf}
export VNC_PORT=${VNC_PORT:-5901}
export NOVNC_PORT=${NOVNC_PORT:-6080}

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 清理函数
cleanup() {
    warn "正在清理..."
    pkill -9 Xvfb 2>/dev/null || true
    pkill -9 x11vnc 2>/dev/null || true
    pkill -f novnc_proxy 2>/dev/null || true
    pkill -9 fcitx5 2>/dev/null || true
}

# 捕获退出信号
trap cleanup EXIT

info "========================================"
info "启动 VibeSurf GUI 环境"
info "========================================"

# 1. 清理旧进程
info "[1/6] 清理旧进程..."
cleanup
sleep 1

# 2. 启动 D-Bus
info "[2/6] 启动 D-Bus..."
mkdir -p /var/run/dbus
rm -f /var/run/dbus/pid
dbus-daemon --session --nofork --nopidfile --address=unix:path=/var/run/dbus/session_bus_socket &
sleep 1

# 3. 启动 Xvfb
info "[3/6] 启动 Xvfb (分辨率: $RESOLUTION)..."
Xvfb $DISPLAY -screen 0 $RESOLUTION -ac +extension GLX +render -noreset &
sleep 2

# 验证 Xvfb
if ! xdpyinfo -display $DISPLAY >/dev/null 2>&1; then
    echo "错误: Xvfb 启动失败"
    exit 1
fi
info "✓ Xvfb 启动成功"

# 4. 启动 fcitx5
info "[4/6] 启动 fcitx5 中文输入法..."
fcitx5 --replace &
sleep 2

# 5. 设置 VNC 密码并启动 x11vnc
info "[5/6] 启动 x11vnc (端口: $VNC_PORT)..."
mkdir -p ~/.vnc
echo "$VNC_PASSWORD" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

x11vnc -display $DISPLAY \
    -forever \
    -shared \
    -noprimary \
    -rfbauth ~/.vnc/passwd \
    -rfbport $VNC_PORT &

sleep 2

# 验证端口
if ! netstat -tlnp 2>/dev/null | grep -q ":$VNC_PORT"; then
    echo "错误: x11vnc 启动失败，端口 $VNC_PORT 未监听"
    exit 1
fi
info "✓ x11vnc 启动成功"

# 6. 启动 noVNC
info "[6/6] 启动 noVNC (端口: $NOVNC_PORT)..."
cd /opt/novnc
nohup ./utils/novnc_proxy \
    --vnc localhost:$VNC_PORT \
    --listen 0.0.0.0:$NOVNC_PORT \
    --web /opt/novnc \
    >/var/log/novnc.log 2>&1 &

sleep 1

# 获取 IP
IP=$(hostname -I | awk '{print $1}')

info ""
info "========================================"
info "✓ VibeSurf GUI 环境启动成功！"
info "========================================"
info ""
info "访问地址:"
info "  - noVNC (Web): http://$IP:$NOVNC_PORT/vnc.html"
info "  - VNC 客户端: $IP:$VNC_PORT"
info ""
info "默认密码:"
info "  VNC 密码: $VNC_PASSWORD"
info ""
info "环境变量:"
info "  DISPLAY=$DISPLAY"
info "  RESOLUTION=$RESOLUTION"
info ""
info "现在可以启动 vibesurf:"
info "  export DISPLAY=$DISPLAY"
info "  vibesurf"
info ""
info "按 Ctrl+C 停止所有服务"
info "========================================"

# 保持运行
wait
SCRIPT

chmod +x /usr/local/bin/start-vibesurf-gui

# 同时复制到项目目录
mkdir -p /opt/vibesurf/scripts
cp /usr/local/bin/start-vibesurf-gui /opt/vibesurf/scripts/

info "✓ 启动脚本已创建: /usr/local/bin/start-vibesurf-gui"

# ============================================
# 安装完成
# ============================================
info ""
info "========================================"
info "✓ VibeSurf 云端环境安装完成！"
info "========================================"
info ""
info "使用方法:"
info ""
info "1. 启动 GUI 环境:"
info "   start-vibesurf-gui"
info ""
info "2. 在另一个终端启动 vibesurf:"
info "   export DISPLAY=:99"
info "   vibesurf"
info ""
info "自定义密码:"
info "   VNC_PASSWORD=yourpassword start-vibesurf-gui"
info ""
info "自定义分辨率:"
info "   RESOLUTION=1920x1080x24 start-vibesurf-gui"
info "========================================"
