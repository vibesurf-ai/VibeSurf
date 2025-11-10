#!/bin/bash
# Local wheel build script for Unix/Linux/macOS
# This script builds Python wheel packages locally

set -e  # Exit on any error

echo "🚀 VibeSurf Local Wheel Build Script for Unix/Linux/macOS"
echo "========================================================"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "[ERROR] uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "[SUCCESS] uv is installed"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "[ERROR] npm is not installed. Please install Node.js first"
    exit 1
fi

echo "[SUCCESS] npm is installed"

# Use dedicated build environment directory
BUILD_ENV=".build-env"

# Clean up dist directory
if [ -d "dist" ]; then
    echo "[WARNING] Removing existing dist directory"
    rm -rf "dist"
fi

# Step 1: Create or reuse dedicated build environment
if [ -d "$BUILD_ENV" ]; then
    echo "[INFO] Reusing existing build environment..."
else
    echo "[INFO] Creating dedicated build environment with Python 3.12..."
    uv venv "$BUILD_ENV" --python 3.12
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create build environment"
        exit 1
    fi
fi

# Step 2: Activate build environment
echo "[INFO] Activating build environment..."
source "$BUILD_ENV/bin/activate"

# Verify Python version
python --version
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate Python environment"
    exit 1
fi

# Step 3: Build frontend
echo "[INFO] Checking frontend build..."
cd vibe_surf/frontend

# Check if package.json exists
if [ ! -f "package.json" ]; then
    echo "[ERROR] Frontend package.json not found!"
    exit 1
fi

# Check if build directory exists
if [ -d "build" ]; then
    echo "[INFO] Frontend build already exists, skipping build process..."
else
    echo "[INFO] Building frontend..."
    # Install frontend dependencies and build
    npm ci
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install frontend dependencies"
        exit 1
    fi

    npm run build
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to build frontend"
        exit 1
    fi
fi

# Copy build folder to backend directory as frontend
mkdir -p "../backend/frontend"
cp -r build/* "../backend/frontend/"
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to copy frontend build"
    exit 1
fi

echo "[SUCCESS] Frontend build completed"
ls -la "../backend/frontend/"

cd "../.."

# Step 4: Install build dependencies and update extension version
echo "[INFO] Installing build dependencies..."
uv pip install --upgrade pip
uv pip install setuptools-scm[toml]
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install build dependencies"
    exit 1
fi

# Step 4.1: Update Extension Version
echo "[INFO] Updating Extension Version..."
VERSION=$(python -m setuptools_scm)
echo "Version from setuptools-scm: $VERSION"

# Extract Chrome-compatible version (only numbers and dots)
# Remove everything after + and any non-numeric/non-dot characters
TEMP_VERSION=$(echo $VERSION | sed 's/+.*//')
CLEAN_VERSION=$(echo $TEMP_VERSION | sed 's/[^0-9.]//g')
echo "Clean version for extension: $CLEAN_VERSION"

# Update manifest.json version
cd vibe_surf/chrome_extension
python -c "import json; import sys; version = sys.argv[1]; manifest = json.load(open('manifest.json', 'r')); manifest['version'] = version; json.dump(manifest, open('manifest.json', 'w'), indent=2); print(f'Updated manifest.json version to {version}')" "$CLEAN_VERSION"
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to update manifest.json"
    exit 1
fi

# Create version.js file
echo "// Extension version - auto-generated during build" > scripts/version.js
echo "window.VIBESURF_EXTENSION_VERSION = '$CLEAN_VERSION';" >> scripts/version.js
echo "console.log('[VibeSurf] Extension version:', '$CLEAN_VERSION');" >> scripts/version.js

echo "[SUCCESS] Extension version files updated"
echo "manifest.json version:"
grep -A1 -B1 '"version"' manifest.json
echo "version.js content:"
cat scripts/version.js

cd "../.."

# Step 5: Build wheel with uv
echo "[INFO] Building wheel with uv..."
uv build --wheel
if [ $? -ne 0 ]; then
    echo "[ERROR] Wheel build failed"
    exit 1
fi

# Step 6: Check built package
echo "[INFO] Checking built package..."
uv pip install twine
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install twine"
    exit 1
fi

twine check dist/*
if [ $? -ne 0 ]; then
    echo "[ERROR] Package check failed"
    exit 1
fi

# Show package contents
echo ""
echo "📊 Built packages:"
echo "=================="
ls -la dist/

# Step 7: Verify installation
echo "[INFO] Verifying package installation..."
for wheel_file in dist/*.whl; do
    if [ -f "$wheel_file" ]; then
        echo "[INFO] Installing and testing wheel: $wheel_file"
        uv pip install "$wheel_file"
        if [ $? -ne 0 ]; then
            echo "[ERROR] Failed to install wheel"
            exit 1
        fi
        
        python -c "import vibe_surf; print(f'Installed version: {vibe_surf.__version__}')"
        if [ $? -ne 0 ]; then
            echo "[ERROR] Failed to import vibe_surf from installed wheel"
            exit 1
        fi
        break
    fi
done

# Step 8: Package Chrome Extension
echo "[INFO] Packaging Chrome Extension..."
cd vibe_surf/chrome_extension

# Create extension zip file
zip -r ../../dist/vibesurf-extension.zip . -x "*.git*" "*.DS_Store*" "node_modules/*"
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to package Chrome extension"
    exit 1
fi

echo "[SUCCESS] Extension packaged successfully"
ls -la ../../dist/vibesurf-extension.zip

cd "../.."

echo ""
echo "[SUCCESS] 🎉 Build completed successfully!"
echo ""
echo "📁 Your packages are located in: ./dist/"
echo "  - Wheel packages: ./dist/*.whl"
echo "  - Chrome extension: ./dist/vibesurf-extension.zip"
echo ""
echo "🚀 To install wheel: pip install dist/*.whl"
echo "🚀 To install extension: Load unpacked from Chrome extensions page"
echo ""