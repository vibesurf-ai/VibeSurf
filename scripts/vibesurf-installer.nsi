; VibeSurf Lightweight Installer
; NSIS Script for creating a professional Windows installer

!define APP_NAME "VibeSurf"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "VibeSurf Team"
!define APP_URL "https://github.com/vibesurf-ai/VibeSurf"
!define APP_DESCRIPTION "AI Browser Assistant"

; Include required libraries
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

; Installer properties
Name "${APP_NAME}"
OutFile "..\dist\VibeSurf-Installer.exe"
InstallDir "$LOCALAPPDATA\${APP_NAME}"
InstallDirRegKey HKCU "Software\${APP_NAME}" ""
RequestExecutionLevel user

; Installer UI Configuration
!define MUI_ABORTWARNING
; Use default NSIS icons for installer UI
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Finish page configuration
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchVibeSurf
!define MUI_FINISHPAGE_SHOWREADME
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Create Desktop Shortcut"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION CreateDesktopShortcut

; Installer pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "../LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Language
!insertmacro MUI_LANGUAGE "English"

; Installer sections
Section "Main Application" SecMain
    SectionIn RO ; Read-only section
    
    SetOutPath "$INSTDIR"
    
    ; Create installation directory
    CreateDirectory "$INSTDIR"
    CreateDirectory "$INSTDIR\uv"
    
    ; Copy application icon (PNG for general use)
    File /oname=$INSTDIR\logo.png "..\vibe_surf\chrome_extension\icons\logo.png"
    
    DetailPrint "Installing VibeSurf AI Browser Assistant..."
    DetailPrint "Checking UV package manager..."
    
    ; Check if UV is already installed
    nsExec::ExecToLog 'uv --version'
    Pop $0
    
    ${If} $0 == 0
        DetailPrint "UV is already installed, skipping installation."
    ${Else}
        DetailPrint "UV not found, installing UV package manager..."
        ; Install UV using the official PowerShell one-liner with better error handling
        nsExec::ExecToLog 'powershell -ExecutionPolicy ByPass -NoProfile -c "irm https://astral.sh/uv/install.ps1 | iex"'
        Pop $0
        
        ${If} $0 != 0
            MessageBox MB_OK|MB_ICONSTOP "UV installation failed.$\r$\nPlease ensure internet connection and try again."
            Abort
        ${EndIf}
        DetailPrint "UV installation completed successfully."
    ${EndIf}
    
    ; Create and setup virtual environment using detected UV path
    DetailPrint "Creating Python virtual environment..."
    ; Use cmd /c to ensure proper command execution
    nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && uv venv .venv --python 3.12"'
    Pop $3
    ${If} $3 != 0
        DetailPrint "Trying with system Python..."
        nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && uv venv .venv"'
        Pop $3
        ${If} $3 != 0
            MessageBox MB_OK|MB_ICONSTOP "Failed to create virtual environment. Please check your Python installation."
            Abort
        ${EndIf}
    ${EndIf}
    
    ; Create Python launcher script (robust startup methods)
    DetailPrint "Creating VibeSurf launcher..."
    FileOpen $0 "$INSTDIR\vibesurf_launcher.py" w
    FileWrite $0 "# -*- coding: utf-8 -*-$\r$\n"
    FileWrite $0 "import os$\r$\n"
    FileWrite $0 "import sys$\r$\n"
    FileWrite $0 "import subprocess$\r$\n"
    FileWrite $0 "import zipfile$\r$\n"
    FileWrite $0 "import shutil$\r$\n"
    FileWrite $0 "import json$\r$\n"
    FileWrite $0 "import urllib.request$\r$\n"
    FileWrite $0 "import urllib.error$\r$\n"
    FileWrite $0 "$\r$\n"
    FileWrite $0 "def check_latest_vibesurf_version():$\r$\n"
    FileWrite $0 "    try:$\r$\n"
    FileWrite $0 "        with urllib.request.urlopen('https://pypi.org/pypi/vibesurf/json', timeout=3) as response:$\r$\n"
    FileWrite $0 "            data = json.loads(response.read().decode('utf-8'))$\r$\n"
    FileWrite $0 "            return data['info']['version']$\r$\n"
    FileWrite $0 "    except Exception as e:$\r$\n"
    FileWrite $0 "        print(f'Failed to check latest version: {e}')$\r$\n"
    FileWrite $0 "        return None$\r$\n"
    FileWrite $0 "$\r$\n"
    FileWrite $0 "def get_vibesurf_version(venv_python):$\r$\n"
    FileWrite $0 "    try:$\r$\n"
    FileWrite $0 "        result = subprocess.run([venv_python, '-c', 'import vibe_surf; print(vibe_surf.__version__)'], $\r$\n"
    FileWrite $0 "                                capture_output=True, text=True, timeout=10)$\r$\n"
    FileWrite $0 "        if result.returncode == 0:$\r$\n"
    FileWrite $0 "            return result.stdout.strip()$\r$\n"
    FileWrite $0 "    except Exception as e:$\r$\n"
    FileWrite $0 "        print(f'Failed to get local version: {e}')$\r$\n"
    FileWrite $0 "    return None$\r$\n"
    FileWrite $0 "$\r$\n"
    FileWrite $0 "def download_extension(install_dir):$\r$\n"
    FileWrite $0 "    extension_zip = os.path.join(install_dir, 'vibesurf-extension.zip')$\r$\n"
    FileWrite $0 "    extension_dir = os.path.join(install_dir, 'chrome_extension')$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    try:$\r$\n"
    FileWrite $0 "        print('Downloading latest Chrome Extension...')$\r$\n"
    FileWrite $0 "        urllib.request.urlretrieve('https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/vibesurf-extension.zip', extension_zip)$\r$\n"
    FileWrite $0 "        print('Extension downloaded successfully!')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Extract extension$\r$\n"
    FileWrite $0 "        if os.path.exists(extension_dir):$\r$\n"
    FileWrite $0 "            shutil.rmtree(extension_dir)$\r$\n"
    FileWrite $0 "            print(f'Removed existing extension directory: {extension_dir}')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        with zipfile.ZipFile(extension_zip, 'r') as zip_ref:$\r$\n"
    FileWrite $0 "            zip_ref.extractall(extension_dir)$\r$\n"
    FileWrite $0 "        print(f'Extension extracted to: {extension_dir}')$\r$\n"
    FileWrite $0 "        return True$\r$\n"
    FileWrite $0 "    except Exception as e:$\r$\n"
    FileWrite $0 "        print(f'Failed to download/extract extension: {e}')$\r$\n"
    FileWrite $0 "        return False$\r$\n"
    FileWrite $0 "$\r$\n"
    FileWrite $0 "def main():$\r$\n"
    FileWrite $0 "    print('VibeSurf - AI Browser Assistant')$\r$\n"
    FileWrite $0 "    print('=' * 40)$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    # Use hardcoded installation directory (PyInstaller runs from temp dir)$\r$\n"
    FileWrite $0 "    install_dir = r'$INSTDIR'  # Real installation path$\r$\n"
    FileWrite $0 "    os.chdir(install_dir)$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    # Define paths$\r$\n"
    FileWrite $0 "    venv_python = os.path.join(install_dir, '.venv', 'Scripts', 'python.exe')$\r$\n"
    FileWrite $0 "    venv_dir = os.path.join(install_dir, '.venv')$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    try:$\r$\n"
    FileWrite $0 "        print('Starting VibeSurf...')$\r$\n"
    FileWrite $0 "        print(f'Install directory: {install_dir}')$\r$\n"
    FileWrite $0 "        print(f'Virtual env path: {venv_python}')$\r$\n"
    FileWrite $0 "        print(f'Virtual env exists: {os.path.exists(venv_dir)}')$\r$\n"
    FileWrite $0 "        print(f'Python exe exists: {os.path.exists(venv_python)}')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Set up environment to use virtual environment$\r$\n"
    FileWrite $0 "        venv_scripts = os.path.join(venv_dir, 'Scripts')$\r$\n"
    FileWrite $0 "        env = os.environ.copy()$\r$\n"
    FileWrite $0 "        env['PATH'] = venv_scripts + os.pathsep + env.get('PATH', '')$\r$\n"
    FileWrite $0 "        env['VIRTUAL_ENV'] = venv_dir$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Check version and decide if update is needed$\r$\n"
    FileWrite $0 "        print('Checking VibeSurf version...')$\r$\n"
    FileWrite $0 "        current_version = get_vibesurf_version(venv_python)$\r$\n"
    FileWrite $0 "        latest_version = check_latest_vibesurf_version()$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        print(f'Current version: {current_version}')$\r$\n"
    FileWrite $0 "        print(f'Latest version: {latest_version}')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        need_update = False$\r$\n"
    FileWrite $0 "        if current_version and latest_version:$\r$\n"
    FileWrite $0 "            if current_version != latest_version:$\r$\n"
    FileWrite $0 "                need_update = True$\r$\n"
    FileWrite $0 "                print(f'Version mismatch detected. Update needed from {current_version} to {latest_version}')$\r$\n"
    FileWrite $0 "            else:$\r$\n"
    FileWrite $0 "                print('VibeSurf is up to date!')$\r$\n"
    FileWrite $0 "        elif not current_version:$\r$\n"
    FileWrite $0 "            need_update = True$\r$\n"
    FileWrite $0 "            print('VibeSurf not found locally, will install...')$\r$\n"
    FileWrite $0 "        else:$\r$\n"
    FileWrite $0 "            print('Unable to check latest version, skipping update check.')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Check if chrome_extension folder exists, force update if missing$\r$\n"
    FileWrite $0 "        extension_dir = os.path.join(install_dir, 'chrome_extension')$\r$\n"
    FileWrite $0 "        if not os.path.exists(extension_dir):$\r$\n"
    FileWrite $0 "            need_update = True$\r$\n"
    FileWrite $0 "            print('Chrome extension folder missing, forcing update and download...')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Perform update if needed$\r$\n"
    FileWrite $0 "        if need_update:$\r$\n"
    FileWrite $0 "            print('Updating VibeSurf and Chrome Extension...')$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Download and extract Chrome Extension$\r$\n"
    FileWrite $0 "            download_extension(install_dir)$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Upgrade VibeSurf package$\r$\n"
    FileWrite $0 "            print('Upgrading VibeSurf package...')$\r$\n"
    FileWrite $0 "            print('VIRTUAL_ENV environment variable:', env.get('VIRTUAL_ENV', 'Not set'))$\r$\n"
    FileWrite $0 "            venv_in_path = '.venv\\\\Scripts' in env.get('PATH', '')$\r$\n"
    FileWrite $0 "            print('PATH includes venv scripts:', venv_in_path)$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Try UV with explicit virtual environment targeting first$\r$\n"
    FileWrite $0 "            venv_python_path = os.path.join(venv_dir, 'Scripts', 'python.exe')$\r$\n"
    FileWrite $0 "            upgrade_cmd = ['uv', 'pip', 'install', 'vibesurf', '-U', '--python', venv_python_path]$\r$\n"
    FileWrite $0 "            try:$\r$\n"
    FileWrite $0 "                print(f'Running upgrade command with explicit python: {upgrade_cmd}')$\r$\n"
    FileWrite $0 "                upgrade_result = subprocess.run(upgrade_cmd, cwd=install_dir, capture_output=True, text=True, env=env)$\r$\n"
    FileWrite $0 "                if upgrade_result.returncode == 0:$\r$\n"
    FileWrite $0 "                    print('VibeSurf upgraded successfully with explicit python targeting!')$\r$\n"
    FileWrite $0 "                    print(f'Upgrade stdout: {upgrade_result.stdout}')$\r$\n"
    FileWrite $0 "                else:$\r$\n"
    FileWrite $0 "                    print(f'Explicit python upgrade failed (exit code {upgrade_result.returncode})')$\r$\n"
    FileWrite $0 "                    print(f'Upgrade stderr: {upgrade_result.stderr}')$\r$\n"
    FileWrite $0 "                    $\r$\n"
    FileWrite $0 "                    # Fallback: try UV without explicit python but with environment$\r$\n"
    FileWrite $0 "                    print('Trying UV upgrade with environment variables only...')$\r$\n"
    FileWrite $0 "                    upgrade_cmd_fallback = ['uv', 'pip', 'install', 'vibesurf', '-U']$\r$\n"
    FileWrite $0 "                    print(f'Running fallback command: {upgrade_cmd_fallback}')$\r$\n"
    FileWrite $0 "                    upgrade_result = subprocess.run(upgrade_cmd_fallback, cwd=install_dir, capture_output=True, text=True, env=env)$\r$\n"
    FileWrite $0 "                    if upgrade_result.returncode == 0:$\r$\n"
    FileWrite $0 "                        print('VibeSurf upgraded successfully with environment variables!')$\r$\n"
    FileWrite $0 "                        print(f'Upgrade stdout: {upgrade_result.stdout}')$\r$\n"
    FileWrite $0 "                    else:$\r$\n"
    FileWrite $0 "                        print(f'Environment variable upgrade also failed (exit code {upgrade_result.returncode})')$\r$\n"
    FileWrite $0 "                        print(f'Upgrade stderr: {upgrade_result.stderr}')$\r$\n"
    FileWrite $0 "            except Exception as e:$\r$\n"
    FileWrite $0 "                pip_cmd = os.path.join(venv_scripts, 'pip.exe')$\r$\n"
    FileWrite $0 "                if os.path.exists(pip_cmd):$\r$\n"
    FileWrite $0 "                    upgrade_cmd = [pip_cmd, 'install', 'vibesurf', '-U']$\r$\n"
    FileWrite $0 "                    print(f'Running pip upgrade command: {upgrade_cmd}')$\r$\n"
    FileWrite $0 "                    upgrade_result = subprocess.run(upgrade_cmd, cwd=install_dir, capture_output=True, text=True, env=env)$\r$\n"
    FileWrite $0 "                    if upgrade_result.returncode == 0:$\r$\n"
    FileWrite $0 "                        print('VibeSurf upgraded successfully!')$\r$\n"
    FileWrite $0 "                    else:$\r$\n"
    FileWrite $0 "                        print(f'Upgrade warning (exit code {upgrade_result.returncode}): {upgrade_result.stderr}')$\r$\n"
    FileWrite $0 "        else:$\r$\n"
    FileWrite $0 "            # No update needed, check if extension exists locally$\r$\n"
    FileWrite $0 "            extension_zip = os.path.join(install_dir, 'vibesurf-extension.zip')$\r$\n"
    FileWrite $0 "            extension_dir = os.path.join(install_dir, 'chrome_extension')$\r$\n"
    FileWrite $0 "            if os.path.exists(extension_zip) and not os.path.exists(extension_dir):$\r$\n"
    FileWrite $0 "                print('Extracting existing Chrome Extension...')$\r$\n"
    FileWrite $0 "                try:$\r$\n"
    FileWrite $0 "                    with zipfile.ZipFile(extension_zip, 'r') as zip_ref:$\r$\n"
    FileWrite $0 "                        zip_ref.extractall(extension_dir)$\r$\n"
    FileWrite $0 "                    print(f'Extension extracted to: {extension_dir}')$\r$\n"
    FileWrite $0 "                except Exception as e:$\r$\n"
    FileWrite $0 "                    print(f'Failed to extract extension: {e}')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Start VibeSurf$\r$\n"
    FileWrite $0 "        print('Starting VibeSurf with virtual environment...')$\r$\n"
    FileWrite $0 "        try:$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Use vibesurf command directly (not python -m vibesurf)$\r$\n"
    FileWrite $0 "            vibesurf_cmd = os.path.join(venv_scripts, 'vibesurf.exe')$\r$\n"
    FileWrite $0 "            if os.path.exists(vibesurf_cmd):$\r$\n"
    FileWrite $0 "                cmd = [vibesurf_cmd]$\r$\n"
    FileWrite $0 "            else:$\r$\n"
    FileWrite $0 "                # Fallback to vibesurf command in PATH$\r$\n"
    FileWrite $0 "                cmd = ['vibesurf']$\r$\n"
    FileWrite $0 "            print(f'Running command: {cmd}')$\r$\n"
    FileWrite $0 "            result = subprocess.run(cmd, env=env, cwd=install_dir)$\r$\n"
    FileWrite $0 "            print(f'Command completed with exit code: {result.returncode}')$\r$\n"
    FileWrite $0 "            if result.returncode == 0:$\r$\n"
    FileWrite $0 "                return$\r$\n"
    FileWrite $0 "        except Exception as e:$\r$\n"
    FileWrite $0 "            print(f'Direct vibesurf command failed: {e}')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        print('All startup methods failed.')$\r$\n"
    FileWrite $0 "        print('Please check if VibeSurf is properly installed in the virtual environment.')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "    except KeyboardInterrupt:$\r$\n"
    FileWrite $0 "        print('VibeSurf startup cancelled by user')$\r$\n"
    FileWrite $0 "    except Exception as e:$\r$\n"
    FileWrite $0 "        print(f'Unexpected error: {e}')$\r$\n"
    FileWrite $0 "    finally:$\r$\n"
    FileWrite $0 "        input('Press Enter to exit...')$\r$\n"
    FileWrite $0 "$\r$\n"
    FileWrite $0 "if __name__ == '__main__':$\r$\n"
    FileWrite $0 "    main()$\r$\n"
    FileClose $0
    
    ; Try to create exe launcher using PyInstaller with detailed diagnostics
    DetailPrint "============================================"
    DetailPrint "ATTEMPTING TO CREATE EXE LAUNCHER"
    DetailPrint "============================================"
    
    ; Create diagnostics log file
    FileOpen $3 "$INSTDIR\installer_log.txt" w
    FileWrite $3 "VibeSurf Installer Diagnostics$\r$\n"
    FileWrite $3 "==============================$\r$\n"
    FileWrite $3 "Installation Directory: $INSTDIR$\r$\n"
    FileWrite $3 "UV Installation: System-wide via PowerShell installer$\r$\n"
    
    ; Install PyInstaller and required dependencies in virtual environment
    DetailPrint "Installing PyInstaller and dependencies..."
    FileWrite $3 "Installing PyInstaller and dependencies in virtual environment$\r$\n"
    
    ; Install PyInstaller, VibeSurf and common dependencies
    DetailPrint "Installing VibeSurf package..."
    nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && uv pip install vibesurf pyinstaller setuptools wheel pip -U"'
    Pop $6
    FileWrite $3 "VibeSurf and PyInstaller installation exit code: $6$\r$\n"
    
    ; Skip initial extension download - will be handled during startup with version check
    DetailPrint "Chrome Extension will be downloaded during first startup..."
    FileWrite $3 "Extension download deferred to startup with version check$\r$\n"
    StrCpy $7 0
    
    ${If} $6 == 0
        DetailPrint "Creating VibeSurf.exe (this may take 60 seconds)..."
        DetailPrint "Using uv run to ensure proper virtual environment..."
        
        ; Check if icon was created successfully and use it
        DetailPrint "Building EXE with custom icon..."
        ; Use uv run to ensure proper virtual environment activation and PATH with icon
        nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && uv run pyinstaller --onefile --console --name "VibeSurf-launch" --icon "$INSTDIR\\logo.png" --distpath "$INSTDIR" --workpath "$INSTDIR\build" --specpath "$INSTDIR" "$INSTDIR\vibesurf_launcher.py""'
        Pop $1
        FileWrite $3 "PyInstaller compilation with icon exit code: $1$\r$\n"
    ${Else}
        DetailPrint "PyInstaller installation failed, skipping EXE creation"
        FileWrite $3 "PyInstaller installation failed$\r$\n"
        StrCpy $1 1
    ${EndIf}
    
    ${If} $1 == 0
        DetailPrint "Checking if VibeSurf.exe was created..."
        ${If} ${FileExists} "$INSTDIR\VibeSurf-launch.exe"
            DetailPrint "SUCCESS! VibeSurf-launch.exe created successfully!"
            FileWrite $3 "EXE Creation: SUCCESS$\r$\n"
            ; Clean up build artifacts but keep vibesurf_launcher.py and logo files for shortcuts
            RMDir /r "$INSTDIR\build"
            Delete "$INSTDIR\VibeSurf-launch.spec"
            DetailPrint "SUCCESS! VibeSurf-launch.exe created successfully!"
            FileWrite $3 "EXE Creation: SUCCESS$\r$\n"
        ${Else}
            DetailPrint "FAILED: VibeSurf-launch.exe not found after compilation!"
            FileWrite $3 "EXE Creation: FAILED - File not found$\r$\n"
        ${EndIf}
    ${Else}
        DetailPrint "PyInstaller compilation failed, keeping Python launcher script"
        FileWrite $3 "PyInstaller compilation: FAILED (exit code $1)$\r$\n"
        FileWrite $3 "Using Python launcher script as fallback$\r$\n"
    ${EndIf}
    
    FileClose $3
    DetailPrint "Diagnostics saved to: $INSTDIR\installer_log.txt"
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    ; Registry entries
    WriteRegStr HKCU "Software\${APP_NAME}" "" $INSTDIR
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "URLInfoAbout" "${APP_URL}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon" "$INSTDIR\logo.png"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1
    
SectionEnd

Section "Desktop Shortcut (Optional)" SecDesktop
    ${If} ${FileExists} "$INSTDIR\VibeSurf-launch.exe"
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\VibeSurf-launch.exe" "" "$INSTDIR\VibeSurf-launch.exe" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
    ${Else}
        ; Fallback to Python launcher script
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\.venv\Scripts\python.exe" "vibesurf_launcher.py" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "$INSTDIR" "${APP_DESCRIPTION}"
    ${EndIf}
SectionEnd

Section "Start Menu Shortcut" SecStartMenu
    SectionIn RO
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    ${If} ${FileExists} "$INSTDIR\VibeSurf-launch.exe"
        CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\VibeSurf-launch.exe" "" "$INSTDIR\VibeSurf-launch.exe" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
    ${Else}
        ; Fallback to Python launcher script
        CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\.venv\Scripts\python.exe" "vibesurf_launcher.py" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "$INSTDIR" "${APP_DESCRIPTION}"
    ${EndIf}
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

; Section descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Main VibeSurf application and runtime components"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Create a desktop shortcut for easy access"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Add VibeSurf to the Start Menu"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; Uninstaller section
Section "Uninstall"
    ; Remove registry entries
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKCU "Software\${APP_NAME}"
    
    ; Remove shortcuts
    Delete "$DESKTOP\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    
    ; Remove installation directory
    RMDir /r "$INSTDIR"
    
SectionEnd

; Installer functions
Function .onInit
    ; Check for existing installation
    ReadRegStr $R0 HKCU "Software\${APP_NAME}" ""
    ${If} $R0 != ""
        MessageBox MB_YESNO|MB_ICONQUESTION "${APP_NAME} is already installed at $R0. Do you want to overwrite it?" IDYES +2
        Abort
        StrCpy $INSTDIR $R0
    ${EndIf}
FunctionEnd

; Function to launch VibeSurf after installation
Function LaunchVibeSurf
    ${If} ${FileExists} "$INSTDIR\VibeSurf-launch.exe"
        ExecShell "open" "$INSTDIR\VibeSurf-launch.exe"
    ${Else}
        ; Fallback to Python launcher script
        ExecShell "open" "$INSTDIR\.venv\Scripts\python.exe" "vibesurf_launcher.py" SW_SHOWNORMAL
    ${EndIf}
FunctionEnd

; Function to create desktop shortcut
Function CreateDesktopShortcut
    ${If} ${FileExists} "$INSTDIR\VibeSurf-launch.exe"
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\VibeSurf-launch.exe" "" "$INSTDIR\VibeSurf-launch.exe" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
    ${Else}
        ; Fallback to Python launcher script
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\.venv\Scripts\python.exe" "vibesurf_launcher.py" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "$INSTDIR" "${APP_DESCRIPTION}"
    ${EndIf}
FunctionEnd

; Remove the old onInstSuccess function since we now use finish page options
; Function .onInstSuccess
; FunctionEnd
