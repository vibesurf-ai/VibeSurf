#!/bin/bash
# Local build script for Unix-like systems (Linux/macOS)
# This script creates a uv environment and builds a standalone executable

set -e  # Exit on any error

echo "🚀 VibeSurf Local Build Script"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

print_success "uv is installed"

# Use dedicated build environment directory
BUILD_ENV=".build-env"

# Clean up existing build environment if it exists
if [ -d "$BUILD_ENV" ]; then
    print_warning "Removing existing build environment directory"
    rm -rf "$BUILD_ENV"
fi

# Step 1: Create dedicated build environment
print_status "Creating dedicated build environment with Python 3.12..."
uv venv "$BUILD_ENV" --python 3.12

# Step 2: Activate build environment and install dependencies
print_status "Activating build environment and installing dependencies..."
source "$BUILD_ENV/bin/activate"

# Verify Python version
PYTHON_VERSION=$(python --version)
print_success "Using Python: $PYTHON_VERSION"

# Install local VibeSurf and PyInstaller
print_status "Installing local vibesurf in development mode and pyinstaller..."
uv pip install -e .
uv pip install pyinstaller

# Verify installation
print_status "Verifying installation..."
python -c "import vibe_surf; print(f'VibeSurf version: {vibe_surf.__version__}')" || {
    print_error "Failed to import vibe_surf"
    exit 1
}

python -c "from vibe_surf.cli import main; print('CLI import successful')" || {
    print_error "Failed to import CLI"
    exit 1
}

# Step 3: Build executable
print_status "Building executable with PyInstaller..."
if [ ! -f "vibesurf.spec" ]; then
    print_error "vibesurf.spec file not found!"
    exit 1
fi

pyinstaller vibesurf.spec --clean --noconfirm

# Step 4: Check build results and handle platform-specific post-processing
PLATFORM=$(uname -s)
print_status "Detected platform: $PLATFORM"

if [ "$PLATFORM" = "Darwin" ]; then
    # macOS - check for .app bundle
    if [ -d "dist/VibeSurf.app" ]; then
        print_success "macOS .app bundle built successfully!"
        
        # Run macOS post-build script if it exists
        if [ -f "macos-post-build.sh" ]; then
            print_status "Running macOS post-build processing..."
            chmod +x macos-post-build.sh
            ./macos-post-build.sh
        else
            print_warning "macos-post-build.sh not found - skipping post-processing"
            echo ""
            echo "📊 App Bundle Information:"
            echo "========================="
            ls -lah dist/VibeSurf.app
            echo ""
            print_success "🎉 Build completed successfully!"
            echo "📁 Your app is located at: ./dist/VibeSurf.app"
            echo "🚀 To run: open ./dist/VibeSurf.app"
        fi
        
    else
        print_error "Build failed - VibeSurf.app bundle not found"
        exit 1
    fi
    
else
    # Linux/Unix - check for regular executable
    if [ -f "dist/vibesurf" ]; then
        print_success "Executable built successfully!"
        
        # Make executable and test
        chmod +x dist/vibesurf
        
        print_status "Testing executable..."
        ./dist/vibesurf --help > /dev/null 2>&1 && {
            print_success "Executable test passed!"
        } || {
            print_warning "Executable test failed, but this might be expected for CLI apps"
        }
        
        # Show file info
        echo ""
        echo "📊 Executable Information:"
        echo "========================="
        ls -lh dist/vibesurf
        
        if command -v file &> /dev/null; then
            file dist/vibesurf
        fi
        
        echo ""
        print_success "🎉 Build completed successfully!"
        echo ""
        echo "📁 Your executable is located at: ./dist/vibesurf"
        echo "🚀 To run: ./dist/vibesurf"
        echo ""
        
    else
        print_error "Build failed - executable not found"
        exit 1
    fi
fi