@echo off
:: Local wheel build script for Windows
:: This script builds Python wheel packages locally

setlocal enabledelayedexpansion

echo 🚀 VibeSurf Local Wheel Build Script for Windows
echo ===============================================

:: Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] uv is not installed. Please install it first:
    echo powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    exit /b 1
)

echo [SUCCESS] uv is installed

:: Check if npm is installed
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm is not installed. Please install Node.js first
    exit /b 1
)

echo [SUCCESS] npm is installed

:: Use dedicated build environment directory
set BUILD_ENV=.build-env

:: Clean up dist directory
if exist "dist" (
    echo [WARNING] Removing existing dist directory
    rmdir /s /q "dist"
)

:: Step 1: Create or reuse dedicated build environment
if exist "%BUILD_ENV%" (
    echo [INFO] Reusing existing build environment...
) else (
    echo [INFO] Creating dedicated build environment with Python 3.12...
    uv venv %BUILD_ENV% --python 3.12
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to create build environment
        exit /b 1
    )
)

:: Step 2: Activate build environment
echo [INFO] Activating build environment...
call %BUILD_ENV%\Scripts\activate.bat

:: Verify Python version
python --version
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to activate Python environment
    exit /b 1
)

:: Step 3: Build frontend
echo [INFO] Checking frontend build...
cd vibe_surf\frontend

:: Check if package.json exists
if not exist "package.json" (
    echo [ERROR] Frontend package.json not found!
    exit /b 1
)

:: Check if build directory exists
if exist "build" (
    echo [INFO] Frontend build already exists, skipping build process...
) else (
    echo [INFO] Building frontend...
    :: Install frontend dependencies and build
    call npm ci
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to install frontend dependencies
        exit /b 1
    )

    call npm run build
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to build frontend
        exit /b 1
    )
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

cd ..\..

:: Step 4: Install build dependencies and update extension version
echo [INFO] Installing build dependencies...
uv pip install --upgrade pip
uv pip install build setuptools-scm[toml]
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install build dependencies
    exit /b 1
)

:: Step 4.1: Update Extension Version
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

:: Step 5: Build wheel with uv
echo [INFO] Building wheel with uv...
uv build --wheel
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Wheel build failed
    exit /b 1
)

:: Step 6: Check built package
echo [INFO] Checking built package...
uv pip install twine
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install twine
    exit /b 1
)

twine check dist/*
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Package check failed
    exit /b 1
)

:: Show package contents
echo.
echo 📊 Built packages:
echo ==================
dir dist\

:: Step 7: Verify installation
echo [INFO] Verifying package installation...
for %%f in (dist\*.whl) do (
    echo [INFO] Installing and testing wheel: %%f
    uv pip install "%%f"
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to install wheel
        exit /b 1
    )
    
    python -c "import vibe_surf; print(f'Installed version: {vibe_surf.__version__}')"
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to import vibe_surf from installed wheel
        exit /b 1
    )
    goto :wheel_found
)

:wheel_found

:: Step 8: Package Chrome Extension
echo [INFO] Packaging Chrome Extension...
cd vibe_surf\chrome_extension

:: Create extension zip using PowerShell
powershell -Command "Compress-Archive -Path '.\*' -DestinationPath '..\..\dist\vibesurf-extension.zip' -Force"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to package Chrome extension
    exit /b 1
)

echo [SUCCESS] Extension packaged successfully
dir ..\..\dist\vibesurf-extension.zip

cd ..\..

echo.
echo [SUCCESS] 🎉 Build completed successfully!
echo.
echo 📁 Your packages are located in: .\dist\
echo   - Wheel packages: .\dist\*.whl
echo   - Chrome extension: .\dist\vibesurf-extension.zip
echo.
echo 🚀 To install wheel: pip install dist\*.whl
echo 🚀 To install extension: Load unpacked from Chrome extensions page
echo.

echo Press any key to exit...
pause >nul