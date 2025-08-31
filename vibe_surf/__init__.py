from dotenv import load_dotenv
import os

try:
    from ._version import version as __version__
except ImportError:
    # Fallback version if _version.py doesn't exist (development mode)
    __version__ = "0.0.0+dev"

project_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

load_dotenv(os.path.join(project_dir, ".env"))