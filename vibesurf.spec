# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Ensure using current environment's Python
python_path = sys.executable
print(f"Using Python: {python_path}")

block_cipher = None

# Dynamically find vibe_surf installation location
try:
    import vibe_surf
    vibe_surf_path = Path(vibe_surf.__file__).parent
    print(f"VibeSurf package location: {vibe_surf_path}")
    cli_path = vibe_surf_path / 'cli.py'
except ImportError:
    # Fallback to relative path (development environment)
    vibe_surf_path = Path.cwd() / 'vibe_surf'
    cli_path = vibe_surf_path / 'cli.py'
    print(f"Using development path: {vibe_surf_path}")

# Check if CLI file exists
if not cli_path.exists():
    print(f"ERROR: CLI file not found at {cli_path}")
    print("Please ensure vibe_surf is properly installed or run from project directory")
    sys.exit(1)

# Data files collection - include all necessary static files
datas = [
    (str(vibe_surf_path / 'chrome_extension'), 'vibe_surf/chrome_extension'),
    (str(vibe_surf_path / 'backend'), 'vibe_surf/backend'),
]

# Hidden imports - all dynamic imports that PyInstaller might miss
hiddenimports = [
    # Core web framework
    'uvicorn.main',
    'uvicorn.config', 
    'uvicorn.server',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
    'fastapi.applications',
    'fastapi.routing',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    
    # Browser automation
    'browser_use',
    'cdp_use',
    
    # HTTP and networking
    'aiohttp.web',
    'aiohttp.client',
    'websockets.server',
    'websockets.client',
    
    # Database
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.pool',
    'aiosqlite',
    
    # Core dependencies
    'rich.console',
    'rich.panel',
    'rich.prompt',
    'rich.text',
    'pydantic',
    'pydantic.main',
    'pydantic.fields',
    'langgraph',
    'langgraph.graph',
    
    # Image processing
    'scikit-image',
    'skimage.io',
    'skimage.transform',
    
    # JSON and data processing
    'json_repair',
    'uuid7',
    'psutil',
    'aiofiles',
    'anyio',
    'python_socks',
    'python_multipart',
    'python_dotenv',
    'greenlet',
    'getmac',
]

# Analysis configuration
a = Analysis(
    [str(cli_path)],
    pathex=[str(vibe_surf_path.parent)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',  # Large plotting library not needed
        'tkinter',     # GUI library not needed
        'PyQt5',       # GUI library not needed
        'PyQt6',       # GUI library not needed
        'PySide2',     # GUI library not needed
        'PySide6',     # GUI library not needed
        'jupyter',     # Jupyter notebook not needed
        'IPython',     # Interactive Python not needed
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate files to reduce size
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='vibesurf',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress to reduce file size
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(vibe_surf_path / 'chrome_extension' / 'icons' / 'logo.png'),
)