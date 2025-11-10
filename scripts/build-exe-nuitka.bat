@echo off
:: Nuitka build script - Much faster alternative to PyInstaller
:: Nuitka compiles to native code and is generally 3-5x faster to build

setlocal enabledelayedexpansion

echo 🚀 VibeSurf Nuitka Build Script (Fast Alternative)
echo ================================================

:: Check if nuitka is installed
python -c "import nuitka" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing nuitka...
    uv pip install nuitka
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install nuitka
        exit /b 1
    )
)

echo [SUCCESS] Nuitka is available

:: Build with Nuitka (much faster)
echo [INFO] Building with Nuitka (faster compilation)...

python -m nuitka ^
    --onefile ^
    --output-dir=dist ^
    --output-filename=vibesurf-nuitka.exe ^
    --enable-plugin=anti-bloat ^
    --assume-yes-for-downloads ^
    --follow-imports ^
    --include-data-dir=vibe_surf/chrome_extension=vibe_surf/chrome_extension ^
    --include-data-dir=vibe_surf/backend=vibe_surf/backend ^
    --include-data-dir=vibe_surf/langflow=vibe_surf/langflow ^
    --include-module=passlib.handlers.bcrypt ^
    --include-module=bcrypt._bcrypt ^
    --include-module=aiosqlite ^
    --include-module=uvicorn ^
    --include-module=fastapi ^
    --windows-console-mode=force ^
    --windows-icon-from-png=vibe_surf/chrome_extension/icons/logo.png ^
    vibe_surf/cli.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Nuitka build failed
    exit /b 1
)

echo [SUCCESS] 🎉 Nuitka build completed!
echo 📁 Executable: .\dist\vibesurf-nuitka.exe

pause