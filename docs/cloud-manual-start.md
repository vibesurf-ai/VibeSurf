# VibeSurf Cloud Deployment Guide

## Quick Start

Run the setup script on your cloud server (Ubuntu/Debian):

```bash
curl -fsSL https://raw.githubusercontent.com/vibesurf-ai/VibeSurf/main/scripts/setup-vibesurf-cloud.sh | sudo bash
```

Or download and run manually:

```bash
wget https://raw.githubusercontent.com/vibesurf-ai/VibeSurf/main/scripts/setup-vibesurf-cloud.sh
sudo bash setup-vibesurf-cloud.sh
```

## Start VibeSurf

### Option 1: Foreground (for debugging)

```bash
start-vibesurf-gui
```

Then in another terminal:
```bash
export DISPLAY=:99
export BROWSER_EXECUTION_PATH=$(find ~/.cache/ms-playwright/*/chrome-linux/chrome 2>/dev/null | head -1)
vibesurf --no_select_browser --host 0.0.0.0
```

### Option 2: Background (recommended for servers)

```bash
# Start GUI environment in background
nohup start-vibesurf-gui > /var/log/vibesurf-gui.log 2>&1 &

# Wait for Xvfb to be ready
sleep 5

# Start vibesurf
export DISPLAY=:99
export BROWSER_EXECUTION_PATH=$(find ~/.cache/ms-playwright/*/chrome-linux/chrome 2>/dev/null | head -1)
nohup vibesurf --no_select_browser --host 0.0.0.0 > /var/log/vibesurf.log 2>&1 &
```

## Access VibeSurf

- **Web VNC (noVNC)**: http://your-server-ip:6080/vnc.html
  - Default password: `vibesurf`
- **VNC Client**: your-server-ip:5901
- **VibeSurf API**: http://your-server-ip:9335

## Customization

```bash
# Custom VNC password
VNC_PASSWORD=yourpassword start-vibesurf-gui

# Custom resolution
RESOLUTION=1920x1080x24 start-vibesurf-gui

# Custom ports
VNC_PORT=5902 NOVNC_PORT=6081 start-vibesurf-gui
```

## Troubleshooting

### Xvfb not starting
```bash
# Check if Xvfb is running
ps aux | grep Xvfb
xdpyinfo -display :99

# If failed, try different display
Xvfb :100 -screen 0 1440x900x24 -ac +extension GLX +render -noreset &
export DISPLAY=:100
```

### Browser not found
```bash
# Install Playwright browsers manually
python3 -m playwright install chromium --with-deps

# Or find existing browser
find /ms-browsers ~/.cache/ms-playwright -name "chrome" 2>/dev/null | head -1
```

### Port already in use
```bash
# Kill existing processes
pkill -9 Xvfb
pkill -9 x11vnc
pkill -f novnc_proxy
```
