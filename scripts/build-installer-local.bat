@echo off
:: Local Installer Builder for VibeSurf
:: Builds NSI installer locally for testing

title VibeSurf Installer Builder
echo.
echo  ██╗   ██╗██╗██████╗ ███████╗███████╗██╗   ██╗██████╗ ███████╗
echo  ██║   ██║██║██╔══██╗██╔════╝██╔════╝██║   ██║██╔══██╗██╔════╝
echo  ██║   ██║██║██████╔╝█████╗  ███████╗██║   ██║██████╔╝█████╗  
echo  ╚██╗ ██╔╝██║██╔══██╗██╔══╝  ╚════██║██║   ██║██╔══██╗██╔══╝  
echo   ╚████╔╝ ██║██████╔╝███████╗███████║╚██████╔╝██║  ██║██║     
echo    ╚═══╝  ╚═╝╚═════╝ ╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     
echo.
echo  🔧 Local Installer Builder
echo  =============================
echo.

setlocal enabledelayedexpansion

:: Check if NSIS is installed
set "NSIS_PATH=C:\Program Files (x86)\NSIS\makensis.exe"
if not exist "%NSIS_PATH%" (
    echo [ERROR] NSIS is not installed!
    echo.
    echo Please install NSIS from: https://nsis.sourceforge.io/Download
    echo Or install via Chocolatey: choco install nsis
    echo.
    pause
    exit /b 1
)

echo [INFO] Found NSIS at: %NSIS_PATH%
echo.

:: Create and setup dist directory
echo [STEP 1/5] Setting up build environment...

if not exist "..\dist" mkdir "..\dist"
echo [SUCCESS] Build directory ready
echo.

:: Download uv.exe for bundling to dist
echo [STEP 2/5] Downloading uv.exe for bundling...

if exist "..\dist\uv.exe" (
    echo [INFO] uv.exe already exists in dist/, skipping download
    goto :uv_ready
)

echo [INFO] Downloading latest uv release for Windows...

:: Use PowerShell to download uv to dist directory
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { " ^
    "  $ProgressPreference = 'SilentlyContinue'; " ^
    "  Write-Host '[INFO] Getting latest uv release info...'; " ^
    "  $response = Invoke-WebRequest -Uri 'https://api.github.com/repos/astral-sh/uv/releases/latest' -UseBasicParsing; " ^
    "  $json = $response.Content | ConvertFrom-Json; " ^
    "  $asset = $json.assets | Where-Object { $_.name -like '*x86_64-pc-windows-msvc.zip' } | Select-Object -First 1; " ^
    "  if ($asset) { " ^
    "    $downloadUrl = $asset.browser_download_url; " ^
    "    Write-Host '[INFO] Downloading:' $downloadUrl; " ^
    "    Invoke-WebRequest -Uri $downloadUrl -OutFile '..\dist\uv.zip' -UseBasicParsing; " ^
    "    Write-Host '[INFO] Extracting uv.exe...'; " ^
    "    Add-Type -AssemblyName System.IO.Compression.FileSystem; " ^
    "    [System.IO.Compression.ZipFile]::ExtractToDirectory('..\dist\uv.zip', '..\dist'); " ^
    "    $extractedDir = Get-ChildItem -Path '..\dist' -Directory | Where-Object { $_.Name -like '*uv*' } | Select-Object -First 1; " ^
    "    if ($extractedDir) { " ^
    "      Move-Item -Path (Join-Path $extractedDir.FullName 'uv.exe') -Destination '..\dist\uv.exe' -Force; " ^
    "      Remove-Item -Path $extractedDir.FullName -Recurse -Force; " ^
    "    } " ^
    "    Remove-Item -Path '..\dist\uv.zip' -Force; " ^
    "    Write-Host '[SUCCESS] uv.exe downloaded to dist/'; " ^
    "  } else { " ^
    "    Write-Error 'Could not find uv Windows release'; " ^
    "    exit 1; " ^
    "  } " ^
    "} catch { " ^
    "  Write-Error ('Download failed: ' + $_.Exception.Message); " ^
    "  exit 1; " ^
    "}"

if %errorlevel% neq 0 (
    echo [ERROR] Failed to download uv.exe
    pause
    exit /b 1
)

:uv_ready
echo [SUCCESS] uv.exe is ready in dist/
echo.

:: Copy LICENSE file for NSIS to dist
echo [STEP 3/5] Preparing build files...

if exist "..\LICENSE" (
    copy "..\LICENSE" "..\dist\LICENSE" >nul 2>&1
    echo [SUCCESS] LICENSE file copied to dist/
) else (
    echo [WARNING] LICENSE file not found, creating dummy file in dist/
    echo VibeSurf License > "..\dist\LICENSE"
)
echo.

:: Build installer with NSIS (output to dist)
echo [STEP 4/5] Building installer with NSIS...
echo [INFO] Using NSIS to compile installer...

"%NSIS_PATH%" vibesurf-installer.nsi

if %errorlevel% neq 0 (
    echo [ERROR] NSIS compilation failed!
    echo.
    echo Check the NSIS script for errors:
    echo - Ensure all required files exist
    echo - Check NSIS script syntax
    echo - Verify NSIS installation
    echo.
    pause
    exit /b 1
)

:: Move installer to dist directory
if exist "VibeSurf-Installer.exe" (
    move "VibeSurf-Installer.exe" "..\dist\VibeSurf-Installer.exe" >nul 2>&1
    echo [SUCCESS] Installer moved to dist/
)

:: Verify installer was created
echo [STEP 5/5] Verifying installer...

if exist "..\dist\VibeSurf-Installer.exe" (
    echo [SUCCESS] Installer created successfully!
    echo.
    echo 📁 Output: dist\VibeSurf-Installer.exe
    
    :: Show file info
    for %%i in ("..\dist\VibeSurf-Installer.exe") do (
        echo    Size: %%~zi bytes
        echo    Date: %%~ti
    )
    
    echo.
    echo 📁 Build artifacts in dist/:
    dir "..\dist" /B
    echo.
    
    echo ============================================
    echo  🎉 Local Installer Build Complete!
    echo ============================================
    echo.
    echo The installer is ready for testing:
    echo  • File: %~dp0..\dist\VibeSurf-Installer.exe
    echo.
    echo To test the installer:
    echo  1. Double-click dist\VibeSurf-Installer.exe
    echo  2. Follow the installation wizard
    echo  3. Test VibeSurf functionality
    echo  4. Uninstall via Control Panel if needed
    echo.
    echo All build artifacts are in dist/ directory:
    echo  • uv.exe - bundled package manager
    echo  • LICENSE - license file for installer
    echo  • VibeSurf-Installer.exe - final installer
    echo.
) else (
    echo [ERROR] Installer was not created!
    echo.
    echo Possible issues:
    echo - NSIS compilation errors
    echo - Missing required files
    echo - Insufficient permissions
    echo.
)

:: No cleanup needed - everything is in dist/

echo Press any key to exit...
pause >nul

endlocal