FROM python:3.12-slim

# Set platform for multi-arch builds
ARG TARGETPLATFORM
ARG NODE_MAJOR=20

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    IN_DOCKER=true \
    VIBESURF_WORKSPACE=/data/vibesurf_workspace \
    DISPLAY=:99 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-browsers \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
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
    libgconf-2-4 \
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
    && rm -rf /var/lib/apt/lists/*

# Install noVNC for web-based VNC access
RUN git clone https://github.com/novnc/noVNC.git /opt/novnc \
    && git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify \
    && ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Install Node.js using NodeSource PPA
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install nodejs -y \
    && rm -rf /var/lib/apt/lists/*

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

# Install VibeSurf using uv
RUN uv venv --python 3.12 /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install -e .

# Activate virtual environment by default
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# Install playwright browsers
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH && \
    playwright install chromium --with-deps

# Set up supervisor configuration
RUN mkdir -p /var/log/supervisor /var/log/vibesurf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose ports
# 9335: VibeSurf backend
# 6080: noVNC (web-based VNC)
# 5901: VNC server
EXPOSE 9335 6080 5901

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9335/health || exit 1

# Default command
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
