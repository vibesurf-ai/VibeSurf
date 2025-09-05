# VibeSurf Executable Build Guide

This guide explains how to build standalone executable files for VibeSurf that can run without requiring Python installation.

## 🎯 Overview

VibeSurf can be packaged into standalone executables for:
- **Windows**: `vibesurf-windows-x64.exe`
- **macOS Intel**: `vibesurf-macos-intel-x64` (compatible with Apple Silicon via Rosetta 2)
- **macOS Apple Silicon**: `vibesurf-macos-apple-silicon` (native arm64 performance)
- **Linux**: `vibesurf-linux-x64`

## 🔧 Local Build Instructions

### Prerequisites

1. **Install uv** (Python package manager):
   ```bash
   # On macOS and Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # On Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/your-repo/VibeSurf.git
   cd VibeSurf
   ```

### Building on Linux/macOS

1. **Run the build script**:
   ```bash
   chmod +x build-local.sh
   ./build-local.sh
   ```

2. **Find your executable**:
   - Location: `./dist/vibesurf`
   - Run with: `./dist/vibesurf`

**Note**:
- The script creates a dedicated `.build-env` directory for building, preserving your existing `.venv`
- Uses your current local code (`-e .`), not the PyPI published version

### Building on Windows

1. **Run the build script**:
   ```cmd
   build-local.bat
   ```

2. **Find your executable**:
   - Location: `.\dist\vibesurf.exe`
   - Run with: `.\dist\vibesurf.exe`

**Note**:
- The script creates a dedicated `.build-env` directory for building, preserving your existing `.venv`
- Uses your current local code (`-e .`), not the PyPI published version

## 🧪 Testing the Executable

### Basic Test
```bash
# Linux/macOS
./dist/vibesurf --help

# Windows
.\dist\vibesurf.exe --help
```

### Full Test
```bash
# Linux/macOS
./dist/vibesurf

# Windows
.\dist\vibesurf.exe
```

The executable should:
1. Display the VibeSurf logo
2. Show version information
3. Detect browsers automatically
4. Configure ports and start the backend

## 📦 What's Included

The executable contains:
- **Complete Python runtime** (Python 3.12)
- **All VibeSurf dependencies** (FastAPI, uvicorn, browser-use, etc.)
- **Chrome extension files** (bundled within the executable)
- **Backend API and database components**
- **VibeSurf logo as executable icon** (from `vibe_surf/chrome_extension/icons/logo.png`)

## 🔍 Build Process Details

### Environment Setup

**Local Building:**
- Creates isolated `uv` build environment (`.build-env`) with Python 3.12
- Preserves existing development environment (`.venv`)
- Installs local VibeSurf in development mode (`-e .`) for latest code
- Adds PyInstaller for building

**GitHub Actions Building:**
- Uses matrix strategy with native OS runners (Windows, macOS, Linux)
- Each runner builds the executable for its native platform
- Installs current repository code (`-e .`) at release time
- Ensures executables match the exact released code version

### PyInstaller Configuration
- **Entry point**: `vibe_surf/cli.py`
- **Data files**: Chrome extension, backend templates
- **Hidden imports**: All dynamic imports declared
- **Exclusions**: Removes unnecessary packages (matplotlib, tkinter)
- **Compression**: Uses UPX for smaller file size
- **Icon**: VibeSurf logo embedded as executable icon

### Output
- **File size**: ~100-200MB (varies by platform)
- **Startup time**: 2-5 seconds (first run)
- **Dependencies**: None (fully self-contained)

## 🚀 Distribution

### Manual Distribution
1. Build the executable for your target platform
2. Copy the `dist/vibesurf*` file to target machines
3. Users can run directly without any installation

### GitHub Releases (Automated)
The repository includes GitHub Actions workflows that automatically:
1. **Multi-platform building**: Uses GitHub runners for each target platform
   - `windows-latest` → `vibesurf-windows-x64.exe`
   - `macos-13` (Intel) → `vibesurf-macos-intel-x64`
   - `macos-14` (Apple Silicon) → `vibesurf-macos-apple-silicon`
   - `ubuntu-latest` → `vibesurf-linux-x64`
2. **Current code**: Builds from the repository code at release time (`-e .`)
3. **Upload binaries**: Automatically uploads all platform executables to GitHub Releases
4. **User downloads**: Platform-specific executables ready for distribution

**macOS Compatibility:**
- **Intel build**: Works on Intel Macs natively, Apple Silicon Macs via Rosetta 2
- **Apple Silicon build**: Native arm64 performance on Apple Silicon Macs
- **Recommendation**: Use Apple Silicon build for M1/M2/M3 Macs for best performance

**Why different OS runners?**
PyInstaller creates native executables and requires the target operating system to build properly. Cross-compilation is not supported.

## 🐛 Troubleshooting

### Build Issues

**"uv not found"**
- Install uv following the prerequisites

**"vibesurf.spec not found"**
- Ensure you're in the project root directory

**"Import errors during build"**
- Check that all dependencies are correctly installed
- Verify the `hiddenimports` list in `vibesurf.spec`

### Runtime Issues

**"Extension not found"**
- The executable includes bundled extensions
- Check the console output for path information

**"Port already in use"**
- VibeSurf automatically finds available ports
- Check for other running instances

**"Browser not detected"**
- The executable includes the same browser detection as the regular installation
- Manually specify browser path if needed

## 📊 Performance Comparison

| Aspect | Regular Install | Executable |
|--------|----------------|------------|
| Installation | Requires Python + pip/uv | Download & run |
| Startup Time | ~1 second | ~3 seconds |
| File Size | ~50MB (dependencies) | ~150MB (self-contained) |
| Updates | `uv pip install -U` | Download new executable |
| Portability | Requires Python | Fully portable |

## 🔄 Updates

To update the executable:
1. Download the latest release executable, or
2. Rebuild locally with the latest code

The executable version matches the PyPI package version.