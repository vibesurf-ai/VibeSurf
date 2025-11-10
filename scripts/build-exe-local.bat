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

:: Check if build environment already exists
if exist "%BUILD_ENV%" (
    echo [INFO] Found existing build environment, reusing it...
) else (
    :: Step 1: Create dedicated build environment
    echo [INFO] Creating dedicated build environment with Python 3.12...
    uv venv %BUILD_ENV% --python 3.12
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create build environment
        exit /b 1
    )
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

:: Install dependencies for version extraction and build
echo [INFO] Installing dependencies for version extraction and build...
uv pip install setuptools-scm[toml]
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install setuptools-scm
    exit /b 1
)

:: Step 2.1: Update Extension Version
echo [INFO] Updating Extension Version...
for /f "tokens=*" %%i in ('python -m setuptools_scm') do set VERSION=%%i
echo Version from setuptools-scm: %VERSION%

:: Extract Chrome-compatible version (only numbers and dots)
:: Remove everything after + and any non-numeric/non-dot characters
for /f "tokens=1 delims=+" %%a in ("%VERSION%") do set TEMP_VERSION=%%a
:: Use PowerShell to clean version - only keep digits and dots
for /f "usebackq tokens=*" %%b in (`powershell -Command "('%TEMP_VERSION%' -replace '[^0-9.]', '')"`) do set CLEAN_VERSION=%%b
echo Clean version for extension: %CLEAN_VERSION%

:: Update manifest.json version
cd vibe_surf\chrome_extension
python -c "import json; import sys; version = sys.argv[1]; manifest = json.load(open('manifest.json', 'r')); manifest['version'] = version; json.dump(manifest, open('manifest.json', 'w'), indent=2); print(f'Updated manifest.json version to {version}')" "%CLEAN_VERSION%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to update manifest.json
    exit /b 1
)

:: Create version.js file
echo // Extension version - auto-generated during build > scripts\version.js
echo window.VIBESURF_EXTENSION_VERSION = '%CLEAN_VERSION%'; >> scripts\version.js
echo console.log('[VibeSurf] Extension version:', '%CLEAN_VERSION%'); >> scripts\version.js

echo [SUCCESS] Extension version files updated
echo manifest.json version:
findstr "version" manifest.json
echo version.js content:
type scripts\version.js

cd ..\..

:: Step 2.2: Build frontend
cd vibe_surf\frontend

:: Check if frontend is already built
if exist "..\backend\frontend\index.html" (
    echo [INFO] Frontend already built, skipping build step...
) else (
    echo [INFO] Building frontend...
    
    :: Check if package.json exists
    if not exist "package.json" (
        echo [ERROR] Frontend package.json not found!
        exit /b 1
    )

    :: Install frontend dependencies and build
    call npm ci
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install frontend dependencies
        exit /b 1
    )

    call npm run build
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to build frontend
        exit /b 1
    )

    :: Copy build folder to backend directory as frontend
    if not exist "..\backend\frontend" mkdir "..\backend\frontend"
    xcopy /E /I /Y build\* ..\backend\frontend\
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to copy frontend build
        exit /b 1
    )

    echo [SUCCESS] Frontend build completed
    dir ..\backend\frontend\
)

cd ..\..

:: Step 2.3: Install local VibeSurf and PyInstaller
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