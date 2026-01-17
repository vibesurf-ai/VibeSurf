FROM python:3.12-slim

# Set platform for multi-arch builds
ARG TARGETPLATFORM
ARG NODE_MAJOR=20
ARG USE_CHINA_MIRROR=false
ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0.dev0

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    IN_DOCKER=true \
    VIBESURF_WORKSPACE=/data/vibesurf_workspace \
    DISPLAY=:99 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-browsers \
    DEBIAN_FRONTEND=noninteractive \
    GTK_IM_MODULE=fcitx \
    QT_IM_MODULE=fcitx \
    XMODIFIERS=@im=fcitx \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/var/run/dbus/session_bus_socket

# Use China mirror for faster builds in China (set USE_CHINA_MIRROR=true)
RUN if [ "$USE_CHINA_MIRROR" = "true" ]; then \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources; \
    fi

# Install system dependencies
RUN apt-get update && \
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
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install noVNC for web-based VNC access
RUN git clone https://github.com/novnc/noVNC.git /opt/novnc \
    && git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify \
    && ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Install Node.js using NodeSource PPA
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install nodejs -y && \
    rm -rf /var/lib/apt/lists/*

# Verify installations
RUN node -v && npm -v && npx -v && ffmpeg -version

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Verify uv installation
RUN uv --version

# Set up working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY vibe_surf ./vibe_surf

# Build frontend
WORKDIR /app/vibe_surf/frontend
RUN npm ci && \
    npm run build && \
    mkdir -p ../backend/frontend && \
    cp -r build/* ../backend/frontend/

# Back to app directory
WORKDIR /app

# Set version for setuptools-scm (since .git is excluded in .dockerignore)
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION}

# Install VibeSurf using uv
RUN uv venv --python 3.12 /opt/venv && \
    . /opt/venv/bin/activate && \
    if [ "$USE_CHINA_MIRROR" = "true" ]; then \
        uv pip install -e . --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple; \
    else \
        uv pip install -e .; \
    fi

# Install playwright
RUN . /opt/venv/bin/activate && \
    if [ "$USE_CHINA_MIRROR" = "true" ]; then \
        uv pip install playwright --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple; \
    else \
        uv pip install playwright; \
    fi

# Activate virtual environment by default
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# Configure fcitx5 for Chinese input
RUN mkdir -p ~/.config/fcitx5 && \
    echo "[Groups/0]\n\
Name=Default\n\
Default Layout=us\n\
DefaultIM=pinyin\n\
\n\
[Groups/0/Items/0]\n\
Name=keyboard-us\n\
Layout=\n\
\n\
[Groups/0/Items/1]\n\
Name=pinyin\n\
Layout=\n\
\n\
[GroupOrder]\n\
0=Default" > ~/.config/fcitx5/profile

# Install playwright browsers (after activating venv)
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH && \
    /opt/venv/bin/python -m playwright install chromium --with-deps

# Set up supervisor configuration
RUN mkdir -p /var/log/supervisor /var/log/vibesurf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose ports
# 9335: VibeSurf backend
# 6080: noVNC (web-based VNC)
# 5901: VNC server
EXPOSE 9335 6080 5901

# Default command
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
