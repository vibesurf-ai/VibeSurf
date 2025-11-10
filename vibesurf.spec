# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import platform
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

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
    (str(vibe_surf_path / 'langflow'), 'vibe_surf/langflow'),
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

# Hidden imports - automatically collect ALL dependencies to avoid manual maintenance
hiddenimports = []

def get_all_installed_packages():
    """Get all packages installed in current environment"""
    import pkg_resources
    installed_packages = []
    
    # Skip known problematic packages that cause issues
    skip_packages = {
        'pip', 'setuptools', 'wheel', 'pyinstaller',
        'matplotlib', 'tkinter', 'jupyter', 'ipython',
        'pytest', 'coverage', 'flake8', 'black', 'mypy',
        'PIL'  # Use Pillow instead
    }
    
    try:
        for distribution in pkg_resources.working_set:
            pkg_name = distribution.project_name.lower()
            if pkg_name not in skip_packages:
                installed_packages.append(distribution.project_name)
    except Exception as e:
        print(f"Warning: Could not enumerate all packages: {e}")
    
    return sorted(list(set(installed_packages)))

# Automatically discover all installed packages
print("Auto-discovering all environment dependencies...")
packages_to_collect = get_all_installed_packages()
print(f"Found {len(packages_to_collect)} installed packages to collect")

# Collect all dependencies automatically with robust error handling
print("Collecting dependencies with full automation...")
for package in packages_to_collect:
    try:
        # collect_all returns (hiddenimports, datas, binaries)
        pkg_hidden, pkg_datas, pkg_binaries = collect_all(package)
        
        # Enhanced filtering to ensure only valid module names are added
        valid_imports = []
        for item in pkg_hidden:
            if isinstance(item, str):
                # Skip file paths (contains path separators and .py extension)
                if ('\\' in item or '/' in item) and item.endswith('.py'):
                    continue
                # Skip items with invalid characters for module names
                if not all(c.isalnum() or c in '._-' for c in item):
                    continue
                # Only add valid Python module names
                if item and not item.startswith('/') and not item.startswith('\\'):
                    valid_imports.append(item)
                    hiddenimports.append(item)
            elif isinstance(item, (tuple, list)) and len(item) > 0 and isinstance(item[0], str):
                # Handle tuples - use first element as module name
                module_name = item[0]
                if ('\\' in module_name or '/' in module_name) and module_name.endswith('.py'):
                    continue
                if not all(c.isalnum() or c in '._-' for c in module_name):
                    continue
                if module_name and not module_name.startswith('/') and not module_name.startswith('\\'):
                    valid_imports.append(module_name)
                    hiddenimports.append(module_name)
        
        # Add data files safely
        if pkg_datas:
            datas.extend(pkg_datas)
        
        print(f"  {package} ({len(valid_imports)} modules)")
        
    except ImportError:
        continue
    except Exception as e:
        print(f"  ! Skipping {package}: {str(e)[:50]}")
        continue

# Add explicit hidden imports for modules that are dynamically imported
# These are often missed by automatic collection
explicit_hidden_imports = [
    # passlib bcrypt handlers - dynamically imported by CryptContext
    'passlib.handlers.bcrypt',
    'passlib.handlers.argon2',
    'passlib.handlers.pbkdf2',
    'passlib.handlers.scrypt',
    'passlib.handlers.sha2_crypt',
    # bcrypt C extensions
    'bcrypt._bcrypt',
    # Other commonly missed dynamic imports
    'multiprocessing.pool',
    'multiprocessing.dummy',
]

# Add explicit imports and remove duplicates
hiddenimports.extend(explicit_hidden_imports)
hiddenimports = list(set(hiddenimports))  # Remove duplicates

print(f"Total dependencies collected: {len(hiddenimports)} modules")
print(f"Added {len(explicit_hidden_imports)} explicit hidden imports for dynamic modules")
print("Automatic dependency collection complete!")

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