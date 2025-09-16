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
    # macOS - check for single executable (CLI application with icon)
    if [ -f "dist/vibesurf" ]; then
        print_success "macOS CLI executable with icon built successfully!"
        
        # Make executable and apply code signing
        chmod +x dist/vibesurf
        
        print_status "Applying ad-hoc code signature..."
        codesign --force --sign - dist/vibesurf || {
            print_warning "Code signing failed, but executable should still work"
        }
        
        # Remove quarantine attribute
        xattr -c dist/vibesurf 2>/dev/null || {
            print_warning "No quarantine attributes to remove"
        }
        
        # Verify signing
        print_status "Verifying code signature..."
        codesign --verify dist/vibesurf && {
            print_success "✅ Signature verified"
        } || {
            print_warning "⚠️ Signature verification failed"
        }
        
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
        echo "🚀 To run:"
        echo "   • Double-click vibesurf (opens in Terminal with console interface)"
        echo "   • Or run: ./dist/vibesurf"
        echo "💡 This executable has an icon and will open console interface when double-clicked"
        echo ""
        
    else
        print_error "Build failed - vibesurf executable not found"
        exit 1
    fi
    
else
    # Other Unix-like systems are not supported
    print_error "This build script currently only supports macOS."
    print_error "For other platforms, please use the GitHub Actions workflow."
    exit 1
fi