"""
Common utilities and configurations for VibeSurf.
"""
import os
import platform
from dotenv import load_dotenv

project_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

load_dotenv(os.path.join(project_dir, ".env"))


def get_workspace_dir():
    """
    Get the workspace directory for VibeSurf.
    
    Returns:
        str: The absolute path to the workspace directory.
    """
    env_workspace_dir = os.getenv("VIBESURF_WORKSPACE", "")
    if not env_workspace_dir or not env_workspace_dir.strip():
        # Set default workspace directory based on OS
        if platform.system() == "Windows":
            default_workspace = os.path.join(os.environ.get("APPDATA", ""), "VibeSurf")
        elif platform.system() == "Darwin":  # macOS
            default_workspace = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "VibeSurf")
        else:  # Linux and others
            default_workspace = os.path.join(os.path.expanduser("~"), ".vibesurf")
        workspace_dir = default_workspace
    else:
        workspace_dir = env_workspace_dir

    workspace_dir = os.path.abspath(workspace_dir)
    os.makedirs(workspace_dir, exist_ok=True)
    return workspace_dir
