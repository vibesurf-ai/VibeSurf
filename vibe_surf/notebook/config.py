from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
import os


@dataclass
class NotebookServerConfig:
    """
    Configuration for Jupyter server management.

    This class contains all settings related to Jupyter Lab server
    startup, networking, and runtime behavior.
    """

    # Network settings
    port: int = 8888
    host: str = "127.0.0.1"  # Restrict to localhost for security

    # SSL/TLS settings
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    ssl_options: Optional[Dict[str, Any]] = None

    # Authentication settings
    token: Optional[str] = None
    password: Optional[str] = None

    # Directory settings
    notebook_dir: Optional[str] = None

    # Browser and UI settings
    auto_launch_browser: bool = False
    open_browser: bool = False

    # CORS and security settings
    allow_origin: str = "*"
    allow_origin_pat: str = ""
    disable_check_xsrf: bool = True

    # Server behavior
    allow_remote_access: bool = False

    # Logging and debugging
    log_level: str = "INFO"
    debug: bool = False

    config_file: Optional[str] = None

    # Startup settings
    startup_timeout: int = 60  # seconds to wait for server to be ready (increased for Windows)
    shutdown_timeout: int = 60

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.notebook_dir is None:
            self.notebook_dir = os.getcwd()

        # Ensure notebook directory exists
        Path(self.notebook_dir).mkdir(parents=True, exist_ok=True)
