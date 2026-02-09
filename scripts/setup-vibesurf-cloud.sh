#!/bin/bash
#
# VibeSurf Cloud Environment Setup Script
# Installs all dependencies required to run VibeSurf on cloud servers (Ubuntu VM, K8s containers, etc.)
#

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored messages
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "Please run this script as root"
    exit 1
fi

# ============================================
# 1. Install system dependencies
# ============================================
info "Step 1/5: Installing system dependencies..."

apt-get update

apt-get install -y --no-install-recommends \
    # Basic utilities
    wget \
    curl \
    git \
    unzip \
    vim \
    netcat-traditional \
    gnupg \
    ca-certificates \
    # Browser dependencies
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
    # Chinese fonts
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    # Input method framework and Chinese input
    fcitx5 \
    fcitx5-chinese-addons \
    fcitx5-frontend-gtk3 \
    fcitx5-frontend-gtk2 \
    fcitx5-frontend-qt5 \
    fcitx5-config-qt \
    fcitx5-module-xorg \
    im-config \
    # VNC dependencies
    dbus \
    xauth \
    x11vnc \
    tigervnc-tools \
    # Process management
    supervisor \
    net-tools \
    procps \
    # Python numpy dependencies
    python3-numpy \
    # FFmpeg for video processing
    ffmpeg

apt-get clean
rm -rf /var/lib/apt/lists/*

info "✓ System dependencies installed"

# ============================================
# 2. Install noVNC
# ============================================
info "Step 2/5: Installing noVNC..."

if [ -d "/opt/novnc" ]; then
    warn "noVNC already exists, skipping installation"
else
    git clone https://github.com/novnc/noVNC.git /opt/novnc
    git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify
    ln -sf /opt/novnc/vnc.html /opt/novnc/index.html
    info "✓ noVNC installed"
fi

# ============================================
# 3. Configure fcitx5 Chinese input method
# ============================================
info "Step 3/5: Configuring fcitx5 Chinese input method..."

mkdir -p ~/.config/fcitx5

# Create fcitx5 profile config
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

# Create fcitx5 config
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

info "✓ fcitx5 configured"

# ============================================
# 4. Set environment variables
# ============================================
info "Step 4/5: Setting environment variables..."

cat >> ~/.bashrc << 'EOF'

# VibeSurf environment variables
export IN_DOCKER=true
export DISPLAY=:99
export RESOLUTION=1440x900x24
export VIBESURF_WORKSPACE=/data/vibesurf_workspace
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export DBUS_SESSION_BUS_ADDRESS=unix:path=/var/run/dbus/session_bus_socket
EOF

# Apply immediately
export IN_DOCKER=true
export DISPLAY=:99
export RESOLUTION=1440x900x24
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export DBUS_SESSION_BUS_ADDRESS=unix:path=/var/run/dbus/session_bus_socket

info "✓ Environment variables set"

# ============================================
# 5. Create startup script
# ============================================
info "Step 5/6: Creating startup script..."

cat > /usr/local/bin/start-vibesurf-gui << 'SCRIPT'
#!/bin/bash
#
# Start VibeSurf GUI environment (Xvfb + x11vnc + noVNC)
#

set -e

# Default configuration
export DISPLAY=${DISPLAY:-:99}
export RESOLUTION=${RESOLUTION:-1440x900x24}
export VNC_PASSWORD=${VNC_PASSWORD:-vibesurf}
export VNC_PORT=${VNC_PORT:-5901}
export NOVNC_PORT=${NOVNC_PORT:-6080}

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Cleanup function
cleanup() {
    warn "Cleaning up..."
    pkill -9 Xvfb 2>/dev/null || true
    pkill -9 x11vnc 2>/dev/null || true
    pkill -f novnc_proxy 2>/dev/null || true
    pkill -9 fcitx5 2>/dev/null || true
}

# Trap exit signal
trap cleanup EXIT

info "========================================"
info "Starting VibeSurf GUI environment"
info "========================================"

# 1. Cleanup old processes
info "[1/6] Cleaning up old processes..."
cleanup
sleep 1

# 2. Start D-Bus
info "[2/6] Starting D-Bus..."
mkdir -p /var/run/dbus
rm -f /var/run/dbus/pid
dbus-daemon --session --nofork --nopidfile --address=unix:path=/var/run/dbus/session_bus_socket &
sleep 1

# 3. Start Xvfb
info "[3/6] Starting Xvfb (resolution: $RESOLUTION)..."
Xvfb $DISPLAY -screen 0 $RESOLUTION -ac +extension GLX +render -noreset &
sleep 2

# Verify Xvfb
if ! xdpyinfo -display $DISPLAY >/dev/null 2>&1; then
    echo "Error: Xvfb failed to start"
    exit 1
fi
info "✓ Xvfb started successfully"

# 4. Start fcitx5
info "[4/6] Starting fcitx5 Chinese input method..."
fcitx5 --replace &
sleep 2

# 5. Set VNC password and start x11vnc
info "[5/6] Starting x11vnc (port: $VNC_PORT)..."
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

# Verify port
if ! netstat -tlnp 2>/dev/null | grep -q ":$VNC_PORT"; then
    echo "Error: x11vnc failed to start, port $VNC_PORT not listening"
    exit 1
fi
info "✓ x11vnc started successfully"

# 6. Start noVNC
info "[6/6] Starting noVNC (port: $NOVNC_PORT)..."
cd /opt/novnc
nohup ./utils/novnc_proxy \
    --vnc localhost:$VNC_PORT \
    --listen 0.0.0.0:$NOVNC_PORT \
    --web /opt/novnc \
    >/var/log/novnc.log 2>&1 &

sleep 1

# Get IP
IP=$(hostname -I | awk '{print $1}')

info ""
info "========================================"
info "✓ VibeSurf GUI environment started!"
info "========================================"
info ""
info "Access URLs:"
info "  - noVNC (Web): http://$IP:$NOVNC_PORT/vnc.html"
info "  - VNC Client: $IP:$VNC_PORT"
info ""
info "Default password:"
info "  VNC Password: $VNC_PASSWORD"
info ""
info "Environment variables:"
info "  DISPLAY=$DISPLAY"
info "  RESOLUTION=$RESOLUTION"
info ""
info "Now you can start vibesurf:"
info "  export DISPLAY=$DISPLAY"
info "  vibesurf"
info ""
info "Press Ctrl+C to stop all services"
info "========================================"

# Keep running
wait
SCRIPT

chmod +x /usr/local/bin/start-vibesurf-gui

# Also copy to project directory
mkdir -p /opt/vibesurf/scripts
cp /usr/local/bin/start-vibesurf-gui /opt/vibesurf/scripts/

info "✓ Startup script created: /usr/local/bin/start-vibesurf-gui"

# ============================================
# 6. Install Playwright browsers
# ============================================
info "Step 6/6: Installing Playwright browsers..."

# Check if python and pip are available
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    warn "Python not found, skipping Playwright installation"
    PYTHON=""
fi

if [ -n "$PYTHON" ]; then
    # Check if playwright is installed
    if $PYTHON -c "import playwright" 2>/dev/null; then
        info "Installing Playwright Chromium browser..."
        $PYTHON -m playwright install chromium --with-deps || warn "Playwright install failed, you may need to install manually"
    else
        warn "Playwright Python package not found, skipping browser installation"
    fi
fi

info "✓ Playwright setup complete"

# ============================================
# Installation complete
# ============================================
info ""
info "========================================"
info "✓ VibeSurf cloud environment installed!"
info "========================================"
info ""
info "Usage:"
info ""
info "1. Start GUI environment (runs in foreground):"
info "   start-vibesurf-gui"
info ""
info "2. Or start everything in background:"
info "   nohup start-vibesurf-gui > /var/log/vibesurf-gui.log 2>&1 &"
info ""
info "3. Then start vibesurf with browser auto-detection:"
info "   export DISPLAY=:99"
info "   export BROWSER_EXECUTION_PATH=\$(find /ms-browsers/chromium-*/chrome-linux*/chrome ~/.cache/ms-playwright/*/chrome-linux/chrome 2>/dev/null | head -1)"
info "   vibesurf --no_select_browser --host 0.0.0.0"
info ""
info "Custom password:"
info "   VNC_PASSWORD=yourpassword start-vibesurf-gui"
info ""
info "Custom resolution:"
info "   RESOLUTION=1920x1080x24 start-vibesurf-gui"
info "========================================"
