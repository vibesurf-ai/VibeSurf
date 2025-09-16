# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import platform
from pathlib import Path

# Ensure using current environment's Python
python_path = sys.executable
print(f"Using Python: {python_path}")

block_cipher = None

# Dynamically find vibe_surf installation location and get version
try:
    import vibe_surf
    vibe_surf_path = Path(vibe_surf.__file__).parent
    app_version = vibe_surf.__version__
    print(f"VibeSurf package location: {vibe_surf_path}")
    print(f"VibeSurf version: {app_version}")
    cli_path = vibe_surf_path / 'cli.py'
except ImportError:
    # Fallback to relative path (development environment)
    vibe_surf_path = Path.cwd() / 'vibe_surf'
    cli_path = vibe_surf_path / 'cli.py'
    
    # Try to get version from _version.py or fallback
    try:
        version_file = vibe_surf_path / '_version.py'
        if version_file.exists():
            version_locals = {}
            exec(version_file.read_text(), version_locals)
            app_version = version_locals.get('version', '0.0.0+dev')
        else:
            app_version = '0.0.0+dev'
    except Exception as e:
        app_version = '0.0.0+dev'
        print(f"WARNING: Could not determine version: {e}")
    
    print(f"Using development path: {vibe_surf_path}")
    print(f"Using fallback version: {app_version}")

# Dynamically find browser_use installation location for prompt templates
try:
    import browser_use
    browser_use_path = Path(browser_use.__file__).parent
    print(f"browser_use package location: {browser_use_path}")
except ImportError:
    print("WARNING: browser_use not found, system prompts may not work in executable")
    browser_use_path = None

# Check if CLI file exists
if not cli_path.exists():
    print(f"ERROR: CLI file not found at {cli_path}")
    print("Please ensure vibe_surf is properly installed or run from project directory")
    sys.exit(1)

# Platform detection and configuration
current_platform = platform.system()
print(f"Building for platform: {current_platform}")

# Configure icon and console mode based on platform
if current_platform == "Windows":
    # Windows can use ICO or PNG, but prefer ICO if available
    ico_file = vibe_surf_path / 'chrome_extension' / 'icons' / 'logo.ico'
    if ico_file.exists():
        icon_file = ico_file
        print(f"Windows detected - using ICO icon")
    else:
        icon_file = vibe_surf_path / 'chrome_extension' / 'icons' / 'logo.png'
        print(f"Windows detected - using PNG icon (ICO not found)")
    console_mode = True
else:  # Other platforms not supported
    print(f"ERROR: Platform {current_platform} is not supported")
    print("VibeSurf currently supports Windows only")
    sys.exit(1)

# Verify icon file exists
if not icon_file.exists():
    print(f"WARNING: Icon file not found at {icon_file}")
    icon_file = None
else:
    print(f"Using icon: {icon_file}")

# Data files collection - include all necessary static files
datas = [
    (str(vibe_surf_path / 'chrome_extension'), 'vibe_surf/chrome_extension'),
    (str(vibe_surf_path / 'backend'), 'vibe_surf/backend'),
]

# Add browser_use prompt template files if available
if browser_use_path:
    browser_use_agent_path = browser_use_path / 'agent'
    # Include the markdown system prompt files
    prompt_files = [
        'system_prompt.md',
        'system_prompt_no_thinking.md',
        'system_prompt_flash.md'
    ]
    for prompt_file in prompt_files:
        prompt_file_path = browser_use_agent_path / prompt_file
        if prompt_file_path.exists():
            datas.append((str(prompt_file_path), f'browser_use/agent'))
            print(f"Added browser_use prompt file: {prompt_file}")
        else:
            print(f"WARNING: browser_use prompt file not found: {prompt_file_path}")
    
    # Include JavaScript files for DOM operations
    browser_use_dom_path = browser_use_path / 'dom'
    if browser_use_dom_path.exists():
        datas.append((str(browser_use_dom_path), 'browser_use/dom'))
        print(f"Added browser_use DOM directory: {browser_use_dom_path}")

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

# Create executable - use onefile mode for all platforms (CLI apps work better this way)
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
    console=console_mode,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file) if icon_file else None,  # Set icon for all platforms
)
print(f"Using onefile mode for {current_platform} (CLI application)")
print(f"Console mode: {console_mode}")
print(f"Executable icon: {icon_file}")