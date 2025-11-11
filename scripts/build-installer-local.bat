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
echo [STEP 1/3] Setting up build environment...

if not exist "..\dist" mkdir "..\dist"
echo [SUCCESS] Build directory ready
echo.
echo [INFO] Using online UV download approach (no bundling needed)
echo.

:: Copy LICENSE file for NSIS to dist
echo [STEP 2/3] Preparing build files...

if exist "..\LICENSE" (
    copy "..\LICENSE" "..\dist\LICENSE" >nul 2>&1
    echo [SUCCESS] LICENSE file copied to dist/
) else (
    echo [WARNING] LICENSE file not found, creating dummy file in dist/
    echo VibeSurf License > "..\dist\LICENSE"
)
echo.

:: Build installer with NSIS (output to dist)
echo [STEP 3/3] Building installer with NSIS...
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
echo [VERIFICATION] Verifying installer...

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
    echo Build artifacts in dist/ directory:
    echo  • LICENSE - license file for installer
    echo  • VibeSurf-Installer.exe - installer with online UV download
    echo.
    echo ⚠️  NOTE: This installer downloads UV online during installation
    echo     - Requires internet connection during installation
    echo     - UV will be downloaded from GitHub releases automatically
    echo     - More reliable than bundling approach
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