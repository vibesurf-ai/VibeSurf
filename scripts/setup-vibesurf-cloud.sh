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

# Detect package manager
if command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
elif command -v yum &> /dev/null; then
    PKG_MANAGER="yum"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
else
    error "No supported package manager found (apt, yum, or dnf)"
    exit 1
fi

info "Detected package manager: $PKG_MANAGER"

# ============================================
# 1. Install system dependencies
# ============================================
info "Step 1/8: Installing system dependencies..."

install_packages() {
    case $PKG_MANAGER in
        apt)
            apt-get update
            apt-get install -y --no-install-recommends \
                wget curl git unzip vim netcat-traditional gnupg ca-certificates \
                xvfb libxss1 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
                libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libxcomposite1 \
                libxdamage1 libxfixes3 libxrandr2 xdg-utils \
                fonts-liberation fonts-dejavu fonts-dejavu-core fonts-dejavu-extra fontconfig \
                fonts-noto-cjk fonts-noto-cjk-extra fonts-wqy-microhei fonts-wqy-zenhei \
                fcitx5 fcitx5-chinese-addons fcitx5-frontend-gtk3 fcitx5-frontend-gtk2 \
                fcitx5-frontend-qt5 fcitx5-config-qt fcitx5-module-xorg im-config \
                dbus xauth x11vnc tigervnc-tools \
                supervisor net-tools procps \
                python3-numpy \
                ffmpeg
            apt-get clean
            rm -rf /var/lib/apt/lists/*
            ;;
        yum|dnf)
            $PKG_MANAGER update -y
            $PKG_MANAGER install -y epel-release
            $PKG_MANAGER update -y
            # Use group install syntax (compatible with both yum and dnf)
            $PKG_MANAGER group install -y "Development Tools" 2>/dev/null || $PKG_MANAGER groupinstall -y "Development Tools"

            # Install base packages (common for both CentOS 7 and 8+)
            $PKG_MANAGER install -y \
                wget curl git unzip vim nmap-ncat gnupg ca-certificates \
                xorg-x11-server-Xvfb libXScrnSaver nss nspr \
                atk at-spi2-atk cups-libs dbus-libs libdrm mesa-libgbm \
                gtk3 libXcomposite libXdamage libXfixes libXrandr xdg-utils \
                liberation-fonts dejavu-sans-fonts dejavu-sans-mono-fonts \
                dejavu-serif-fonts fontconfig \
                cjkuni-uming-fonts wqy-microhei-fonts wqy-zenhei-fonts \
                dbus xauth x11vnc tigervnc-server \
                net-tools procps-ng \
                python3 python3-pip \
                ffmpeg || warn "Some packages failed to install"

            # Try to install fcitx5 (CentOS 8+/RHEL 8+), fallback to fcitx (CentOS 7)
            if ! $PKG_MANAGER install -y fcitx5 fcitx5-gtk2 fcitx5-gtk3 fcitx5-qt 2>/dev/null; then
                warn "fcitx5 not available, trying fcitx..."
                $PKG_MANAGER install -y fcitx fcitx-configtool || warn "fcitx installation failed"
            fi

            # Install supervisor via pip if not available in repos
            if ! $PKG_MANAGER install -y supervisor 2>/dev/null; then
                warn "supervisor not in repos, installing via pip3..."
                pip3 install supervisor
            fi

            # Clean up
            $PKG_MANAGER clean all
            ;;
    esac
}

install_packages

info "✓ System dependencies installed"

# ============================================
# 2. Install noVNC
# ============================================
info "Step 2/8: Installing noVNC..."

if [ -d "/opt/novnc" ]; then
    warn "noVNC already exists, skipping installation"
else
    git clone https://github.com/novnc/noVNC.git /opt/novnc
    git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify
    ln -sf /opt/novnc/vnc.html /opt/novnc/index.html
    info "✓ noVNC installed"
fi

# ============================================
# 3. Configure fcitx5/fcitx Chinese input method
# ============================================
info "Step 3/8: Configuring Chinese input method..."

# Detect which input method is installed (fcitx5 for newer systems, fcitx for older)
if command -v fcitx5 &> /dev/null; then
    IM_CMD="fcitx5"
    IM_CONFIG_DIR="~/.config/fcitx5"
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
TriggerKeys=
EnumerateWithTriggerKeys=True
AltTriggerKeys=
EnumerateForwardKeys=
EnumerateBackwardKeys=
EnumerateSkipFirst=False

[Hotkey/TriggerKeys]
0=Control+space
1=Shift+space

[Behavior]
ActiveByDefault=False
ShareInputState=No
EOF
    info "✓ fcitx5 configured"
else
    # Fallback to fcitx (CentOS 7, older systems)
    mkdir -p ~/.config/fcitx
    IM_CMD="fcitx"

    # Create fcitx profile config
    cat > ~/.config/fcitx/profile << 'EOF'
[Profile]
IMName=pinyin
EOF

    info "✓ fcitx configured (legacy mode)"
fi

# ============================================
# 4. Set environment variables
# ============================================
info "Step 4/8: Setting environment variables..."

# Detect input method for environment variables
if command -v fcitx5 &> /dev/null; then
    IM_MODULE="fcitx"
    IM_MODIFIER="@im=fcitx"
else
    IM_MODULE="fcitx"
    IM_MODIFIER="@im=fcitx"
fi

cat >> ~/.bashrc << EOF

# VibeSurf environment variables
export IN_DOCKER=true
export DISPLAY=:99
export RESOLUTION=1440x900x24
export VIBESURF_WORKSPACE=/data/vibesurf_workspace
export GTK_IM_MODULE=$IM_MODULE
export QT_IM_MODULE=$IM_MODULE
export XMODIFIERS=$IM_MODIFIER
export DBUS_SESSION_BUS_ADDRESS=unix:path=/var/run/dbus/session_bus_socket
EOF

# Apply immediately
export IN_DOCKER=true
export DISPLAY=:99
export RESOLUTION=1440x900x24
export GTK_IM_MODULE=$IM_MODULE
export QT_IM_MODULE=$IM_MODULE
export XMODIFIERS=$IM_MODIFIER
export DBUS_SESSION_BUS_ADDRESS=unix:path=/var/run/dbus/session_bus_socket

info "✓ Environment variables set"

# ============================================
# 5. Create startup script
# ============================================
info "Step 5/8: Creating startup script..."

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
    # Skip cleanup if running in background (nohup) to prevent killing services
    # when the parent shell exits
    if [ -n "$VIBESURF_NO_CLEANUP" ]; then
        return
    fi
    warn "Cleaning up..."
    pkill -9 Xvfb 2>/dev/null || true
    pkill -9 x11vnc 2>/dev/null || true
    pkill -f novnc_proxy 2>/dev/null || true
    pkill -9 fcitx5 2>/dev/null || true
    pkill -9 fcitx 2>/dev/null || true
}

# Trap exit signal (only in foreground/interactive mode)
if [ -z "$VIBESURF_NO_CLEANUP" ]; then
    trap cleanup EXIT
fi

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

# 4. Start fcitx/fcitx5 (auto-detect)
if command -v fcitx5 &> /dev/null; then
    info "[4/6] Starting fcitx5 Chinese input method..."
    fcitx5 --replace &
elif command -v fcitx &> /dev/null; then
    info "[4/6] Starting fcitx Chinese input method..."
    fcitx &
else
    warn "No Chinese input method found (fcitx5/fcitx), skipping..."
fi
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
    -rfbport $VNC_PORT \
    -repeat &

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
# 6. Install uv and VibeSurf
# ============================================
info "Step 6/8: Installing uv..."

if command -v uv &> /dev/null; then
    info "uv already installed, skipping"
else
    # Install uv using the official installer
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source the environment to make uv available
    export PATH="$HOME/.cargo/bin:$PATH"
    info "✓ uv installed"
fi

info "Step 7/8: Installing VibeSurf..."

if command -v uv &> /dev/null; then
    uv tool install vibesurf
    info "✓ VibeSurf installed"
else
    warn "uv not found in PATH, skipping VibeSurf installation"
fi

# ============================================
# 8. Install Playwright browsers
# ============================================
info "Step 8/8: Installing Playwright browsers..."

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
info "   VIBESURF_NO_CLEANUP=1 nohup start-vibesurf-gui > /var/log/vibesurf-gui.log 2>&1 &"
info ""
info "3. Then start vibesurf:"
info '   export DISPLAY=:99'
info '   export BROWSER_EXECUTION_PATH=$(find ~/.cache/ms-playwright/*/chrome-linux/chrome 2>/dev/null | head -1)'
info '   vibesurf --no_select_browser --host 0.0.0.0'
info ""
info "Custom password:"
info "   VNC_PASSWORD=yourpassword start-vibesurf-gui"
info ""
info "Custom resolution:"
info "   RESOLUTION=1920x1080x24 start-vibesurf-gui"
info ""
info "Upgrade VibeSurf:"
info "   uv tool upgrade vibesurf"
info "========================================"
