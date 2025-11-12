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
    
    ; Copy application icon
    File /oname=$INSTDIR\logo.png "..\vibe_surf\chrome_extension\icons\logo.png"
    
    DetailPrint "Installing VibeSurf AI Browser Assistant..."
    DetailPrint "Installing UV package manager..."
    
    ; Install UV using the official PowerShell one-liner with better error handling
    nsExec::ExecToLog 'powershell -ExecutionPolicy ByPass -NoProfile -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Pop $0
    
    ${If} $0 != 0
        MessageBox MB_OK|MB_ICONSTOP "UV installation failed.$\r$\nPlease ensure internet connection and try again."
        Abort
    ${EndIf}
    
    ; Add UV to PATH for current session (UV installs to %USERPROFILE%\.cargo\bin)
    ReadEnvStr $1 "PATH"
    System::Call 'kernel32::SetEnvironmentVariable(t "PATH", t "%USERPROFILE%\.cargo\bin;$1")'
    
    ; Verify UV installation
    DetailPrint "Verifying UV installation..."
    nsExec::ExecToLog 'uv --version'
    Pop $2
    ${If} $2 != 0
        MessageBox MB_OK|MB_ICONSTOP "UV installation verification failed. Please restart the installer."
        Abort
    ${EndIf}
    
    ; Create and setup virtual environment
    DetailPrint "Creating Python virtual environment..."
    nsExec::ExecToLog 'cd /d "$INSTDIR" && uv venv .venv --python 3.11'
    Pop $3
    ${If} $3 != 0
        DetailPrint "Trying with system Python..."
        nsExec::ExecToLog 'cd /d "$INSTDIR" && uv venv .venv'
        Pop $3
        ${If} $3 != 0
            MessageBox MB_OK|MB_ICONSTOP "Failed to create virtual environment. Please check your Python installation."
            Abort
        ${EndIf}
    ${EndIf}
    
    ; Create Python launcher script with auto-upgrade
    DetailPrint "Creating VibeSurf launcher with auto-upgrade..."
    FileOpen $0 "$INSTDIR\vibesurf_launcher.py" w
    FileWrite $0 "# -*- coding: utf-8 -*-$\r$\n"
    FileWrite $0 "import os$\r$\n"
    FileWrite $0 "import sys$\r$\n"
    FileWrite $0 "import subprocess$\r$\n"
    FileWrite $0 "import time$\r$\n"
    FileWrite $0 "$\r$\n"
    FileWrite $0 "def main():$\r$\n"
    FileWrite $0 "    print('VibeSurf - AI Browser Assistant')$\r$\n"
    FileWrite $0 "    print('=' * 40)$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    install_dir = os.path.dirname(os.path.abspath(__file__))$\r$\n"
    FileWrite $0 "    os.chdir(install_dir)$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    # Check if UV is available in system PATH$\r$\n"
    FileWrite $0 "    try:$\r$\n"
    FileWrite $0 "        subprocess.run(['uv', '--version'], capture_output=True, check=True)$\r$\n"
    FileWrite $0 "    except (subprocess.CalledProcessError, FileNotFoundError):$\r$\n"
    FileWrite $0 "        print('Error: UV package manager not found in system PATH')$\r$\n"
    FileWrite $0 "        print('Please ensure UV is properly installed')$\r$\n"
    FileWrite $0 "        input('Press Enter to exit...')$\r$\n"
    FileWrite $0 "        return$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    try:$\r$\n"
    FileWrite $0 "        print('Checking for VibeSurf updates...')$\r$\n"
    FileWrite $0 "        # Try update with extended timeout and better error handling$\r$\n"
    FileWrite $0 "        try:$\r$\n"
    FileWrite $0 "            # Ensure virtual environment exists$\r$\n"
    FileWrite $0 "            if not os.path.exists('.venv'):$\r$\n"
    FileWrite $0 "                print('Creating virtual environment...')$\r$\n"
    FileWrite $0 "                subprocess.run(['uv', 'venv', '.venv'], check=True)$\r$\n"
    FileWrite $0 "            result = subprocess.run(['uv', 'pip', 'install', 'vibesurf', '--upgrade'], $\r$\n"
    FileWrite $0 "                                   capture_output=True, text=True, timeout=60)$\r$\n"
    FileWrite $0 "            if result.returncode == 0:$\r$\n"
    FileWrite $0 "                print('VibeSurf is up to date!')$\r$\n"
    FileWrite $0 "            else:$\r$\n"
    FileWrite $0 "                print('Update available but download had issues, using existing version')$\r$\n"
    FileWrite $0 "        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):$\r$\n"
    FileWrite $0 "            print('Update check failed or timed out, using existing version')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Download vibesurf-extension.zip$\r$\n"
    FileWrite $0 "        print('Updating VibeSurf Chrome Extension...')$\r$\n"
    FileWrite $0 "        try:$\r$\n"
    FileWrite $0 "            import urllib.request$\r$\n"
    FileWrite $0 "            import zipfile$\r$\n"
    FileWrite $0 "            import shutil$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            extension_url = 'https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/vibesurf-extension.zip'$\r$\n"
    FileWrite $0 "            extension_zip = os.path.join(install_dir, 'vibesurf-extension.zip')$\r$\n"
    FileWrite $0 "            extension_dir = os.path.join(install_dir, 'vibesurf-extension')$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Remove existing extension folder if it exists$\r$\n"
    FileWrite $0 "            if os.path.exists(extension_dir):$\r$\n"
    FileWrite $0 "                print('Removing old extension folder...')$\r$\n"
    FileWrite $0 "                shutil.rmtree(extension_dir)$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Download latest extension$\r$\n"
    FileWrite $0 "            print('Downloading latest extension...')$\r$\n"
    FileWrite $0 "            urllib.request.urlretrieve(extension_url, extension_zip)$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Create extension directory$\r$\n"
    FileWrite $0 "            os.makedirs(extension_dir, exist_ok=True)$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Extract extension to proper directory$\r$\n"
    FileWrite $0 "            print('Extracting extension...')$\r$\n"
    FileWrite $0 "            with zipfile.ZipFile(extension_zip, 'r') as zip_ref:$\r$\n"
    FileWrite $0 "                zip_ref.extractall(extension_dir)$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "            # Clean up zip file$\r$\n"
    FileWrite $0 "            os.remove(extension_zip)$\r$\n"
    FileWrite $0 "            print('Extension updated successfully!')$\r$\n"
    FileWrite $0 "            $\r$\n"
    FileWrite $0 "        except Exception as ext_error:$\r$\n"
    FileWrite $0 "            print(f'Extension update failed: {ext_error}')$\r$\n"
    FileWrite $0 "            print('Continuing with VibeSurf startup...')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        print('Starting VibeSurf...')$\r$\n"
    FileWrite $0 "        time.sleep(1)$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Launch VibeSurf$\r$\n"
    FileWrite $0 "        subprocess.run(['uv', 'run', 'vibesurf'], check=True)$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "    except subprocess.TimeoutExpired:$\r$\n"
    FileWrite $0 "        print('VibeSurf startup timed out, please try again...')$\r$\n"
    FileWrite $0 "        input('Press Enter to exit...')$\r$\n"
    FileWrite $0 "    except KeyboardInterrupt:$\r$\n"
    FileWrite $0 "        print('VibeSurf startup cancelled by user')$\r$\n"
    FileWrite $0 "    except Exception as e:$\r$\n"
    FileWrite $0 "        print(f'Error: {e}')$\r$\n"
    FileWrite $0 "        print('Please check your internet connection and try again.')$\r$\n"
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
    
    ; Install PyInstaller in virtual environment
    DetailPrint "Installing PyInstaller..."
    FileWrite $3 "Installing PyInstaller in virtual environment$\r$\n"
    
    nsExec::ExecToLog 'cd /d "$INSTDIR" && uv pip install pyinstaller'
    Pop $4
    FileWrite $3 "PyInstaller installation exit code: $4$\r$\n"
    
    ${If} $4 == 0
        DetailPrint "Creating VibeSurf.exe (this may take 60 seconds)..."
        ; Use direct PyInstaller call with virtual environment activation
        nsExec::ExecToLog 'cd /d "$INSTDIR" && .venv\Scripts\python.exe -m PyInstaller --onefile --console --name "VibeSurf" --distpath "$INSTDIR" --workpath "$INSTDIR\build" --specpath "$INSTDIR" "$INSTDIR\vibesurf_launcher.py"'
        Pop $1
        FileWrite $3 "PyInstaller compilation exit code: $1$\r$\n"
    ${Else}
        DetailPrint "PyInstaller installation failed, skipping EXE creation"
        FileWrite $3 "PyInstaller installation failed$\r$\n"
        StrCpy $1 1
    ${EndIf}
    
    ${If} $1 == 0
        DetailPrint "Checking if VibeSurf.exe was created..."
        ${If} ${FileExists} "$INSTDIR\VibeSurf.exe"
            DetailPrint "SUCCESS! VibeSurf.exe created successfully!"
            FileWrite $3 "EXE Creation: SUCCESS$\r$\n"
            MessageBox MB_OK|MB_ICONINFORMATION "VibeSurf.exe created successfully!$\r$\n$\r$\nThe executable launcher has been created and is ready to use."
            ; Clean up build artifacts
            RMDir /r "$INSTDIR\build"
            Delete "$INSTDIR\VibeSurf.spec"
            Delete "$INSTDIR\vibesurf_launcher.py"
            StrCpy $R9 "exe"
        ${Else}
            DetailPrint "FAILED: VibeSurf.exe not found after compilation!"
            FileWrite $3 "EXE Creation: FAILED - File not found$\r$\n"
            MessageBox MB_OK|MB_ICONEXCLAMATION "EXE Creation Failed!$\r$\n$\r$\nPyInstaller completed but VibeSurf.exe was not created.$\r$\nUsing batch file launcher instead.$\r$\n$\r$\nCheck installer_log.txt for details."
            StrCpy $R9 "bat"
        ${EndIf}
    ${Else}
        DetailPrint "FAILED: PyInstaller compilation failed with exit code $1"
        FileWrite $3 "PyInstaller compilation: FAILED (exit code $1)$\r$\n"
        FileWrite $3 "Possible causes:$\r$\n"
        FileWrite $3 "- Missing Python dependencies$\r$\n"
        FileWrite $3 "- UV environment isolation issues$\r$\n"
        FileWrite $3 "- Antivirus software blocking compilation$\r$\n"
        FileWrite $3 "- Insufficient system resources$\r$\n"
        MessageBox MB_OK|MB_ICONEXCLAMATION "EXE Creation Failed!$\r$\n$\r$\nPyInstaller failed with exit code: $1$\r$\n$\r$\nPossible causes:$\r$\n- Missing Python dependencies$\r$\n- UV environment isolation$\r$\n- Antivirus blocking compilation$\r$\n$\r$\nUsing batch launcher instead.$\r$\nCheck installer_log.txt for details."
        StrCpy $R9 "bat"
    ${EndIf}
    
    FileClose $3
    DetailPrint "Diagnostics saved to: $INSTDIR\installer_log.txt"
    
    ; Create bat launcher as fallback (with auto-upgrade)
    ${If} $R9 == "bat"
        DetailPrint "Creating batch launcher as fallback..."
        FileOpen $2 "$INSTDIR\VibeSurf.bat" w
        FileWrite $2 "@echo off$\r$\n"
        FileWrite $2 "title VibeSurf - AI Browser Assistant$\r$\n"
        FileWrite $2 "cd /d $\"$INSTDIR$\"$\r$\n"
        FileWrite $2 "echo VibeSurf - AI Browser Assistant$\r$\n"
        FileWrite $2 "echo ========================================$\r$\n"
        FileWrite $2 "echo Checking for updates...$\r$\n"
        FileWrite $2 "if not exist $\".venv$\" ($\r$\n"
        FileWrite $2 "    echo Creating virtual environment...$\r$\n"
        FileWrite $2 "    uv venv .venv$\r$\n"
        FileWrite $2 "    if errorlevel 1 ($\r$\n"
        FileWrite $2 "        echo Error: Virtual environment creation failed$\r$\n"
        FileWrite $2 "        pause$\r$\n"
        FileWrite $2 "        exit /b 1$\r$\n"
        FileWrite $2 "    )$\r$\n"
        FileWrite $2 ")$\r$\n"
        FileWrite $2 "uv pip install vibesurf --upgrade$\r$\n"
        FileWrite $2 ":launch$\r$\n"
        FileWrite $2 "if %errorlevel% equ 0 ($\r$\n"
        FileWrite $2 "    echo VibeSurf is up to date!$\r$\n"
        FileWrite $2 ") else ($\r$\n"
        FileWrite $2 "    echo Note: Update check failed, using existing version$\r$\n"
        FileWrite $2 ")$\r$\n"
        FileWrite $2 "echo Updating VibeSurf Chrome Extension...$\r$\n"
        FileWrite $2 "powershell -NoProfile -ExecutionPolicy Bypass -Command $\"& { try { Write-Host 'Downloading extension...'; if (Test-Path '$INSTDIR\\vibesurf-extension') { Remove-Item '$INSTDIR\\vibesurf-extension' -Recurse -Force }; New-Item -Path '$INSTDIR\\vibesurf-extension' -ItemType Directory -Force; Invoke-WebRequest -Uri 'https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/vibesurf-extension.zip' -OutFile '$INSTDIR\\vibesurf-extension.zip' -UseBasicParsing; Expand-Archive '$INSTDIR\\vibesurf-extension.zip' '$INSTDIR\\vibesurf-extension' -Force; Remove-Item '$INSTDIR\\vibesurf-extension.zip' -Force; Write-Host 'Extension updated!' } catch { Write-Host 'Extension update failed, continuing...' } }$\"$\r$\n"
        FileWrite $2 "echo Starting VibeSurf...$\r$\n"
        FileWrite $2 "timeout /t 1 /nobreak >nul$\r$\n"
        FileWrite $2 "uv run vibesurf$\r$\n"
        FileWrite $2 "pause$\r$\n"
        FileClose $2
    ${EndIf}
    
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
    ${If} ${FileExists} "$INSTDIR\VibeSurf.exe"
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\VibeSurf.exe" "" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
    ${Else}
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\VibeSurf.bat" "" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
    ${EndIf}
SectionEnd

Section "Start Menu Shortcut" SecStartMenu
    SectionIn RO
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    ${If} ${FileExists} "$INSTDIR\VibeSurf.exe"
        CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\VibeSurf.exe" "" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
    ${Else}
        CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\VibeSurf.bat" "" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
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
    ${If} ${FileExists} "$INSTDIR\VibeSurf.exe"
        ExecShell "open" "$INSTDIR\VibeSurf.exe"
    ${ElseIf} ${FileExists} "$INSTDIR\VibeSurf.bat"
        ExecShell "open" "$INSTDIR\VibeSurf.bat"
    ${EndIf}
FunctionEnd

; Function to create desktop shortcut
Function CreateDesktopShortcut
    ${If} ${FileExists} "$INSTDIR\VibeSurf.exe"
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\VibeSurf.exe" "" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
    ${Else}
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\VibeSurf.bat" "" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
    ${EndIf}
FunctionEnd

; Remove the old onInstSuccess function since we now use finish page options
; Function .onInstSuccess
; FunctionEnd
