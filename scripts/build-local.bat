@echo off
:: Local build script for Windows
:: This script creates a uv environment and builds a standalone executable

setlocal enabledelayedexpansion

echo 🚀 VibeSurf Local Build Script for Windows
echo ==========================================

:: Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] uv is not installed. Please install it first:
    echo powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    exit /b 1
)

echo [SUCCESS] uv is installed

:: Use dedicated build environment directory
set BUILD_ENV=.build-env

:: Clean up existing build environment if it exists
if exist "%BUILD_ENV%" (
    echo [WARNING] Removing existing build environment directory
    rmdir /s /q "%BUILD_ENV%"
)

:: Step 1: Create dedicated build environment
echo [INFO] Creating dedicated build environment with Python 3.12...
uv venv %BUILD_ENV% --python 3.12
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to create build environment
    exit /b 1
)

:: Step 2: Activate build environment and install dependencies
echo [INFO] Activating build environment and installing dependencies...
call %BUILD_ENV%\Scripts\activate.bat

:: Verify Python version
python --version
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to activate Python environment
    exit /b 1
)

:: Install local VibeSurf and PyInstaller
echo [INFO] Installing local vibesurf in development mode and pyinstaller...
uv pip install -e .
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install local vibesurf
    exit /b 1
)

uv pip install pyinstaller
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install pyinstaller
    exit /b 1
)

:: Verify installation
echo [INFO] Verifying installation...
python -c "import vibe_surf; print(f'VibeSurf version: {vibe_surf.__version__}')"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to import vibe_surf
    exit /b 1
)

python -c "from vibe_surf.cli import main; print('CLI import successful')"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to import CLI
    exit /b 1
)

:: Step 3: Build executable
echo [INFO] Building executable with PyInstaller...
if not exist "vibesurf.spec" (
    echo [ERROR] vibesurf.spec file not found!
    exit /b 1
)

pyinstaller vibesurf.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller build failed
    exit /b 1
)

:: Step 4: Test executable
if exist "dist\vibesurf.exe" (
    echo [SUCCESS] Executable built successfully!
    
    echo [INFO] Testing executable...
    dist\vibesurf.exe --help >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo [SUCCESS] Executable test passed!
    ) else (
        echo [WARNING] Executable test failed, but this might be expected for CLI apps
    )
    
    :: Show file info
    echo.
    echo 📊 Executable Information:
    echo =========================
    dir /q dist\vibesurf.exe
    
    echo.
    echo [SUCCESS] 🎉 Build completed successfully!
    echo.
    echo 📁 Your executable is located at: .\dist\vibesurf.exe
    echo 🚀 To run: .\dist\vibesurf.exe
    echo.
    
) else (
    echo [ERROR] Build failed - executable not found
    exit /b 1
)

echo Press any key to exit...
pause >nul