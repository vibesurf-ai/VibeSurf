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
    DetailPrint "Installing UV package manager..."
    
    ; Install UV using the official PowerShell one-liner with better error handling
    nsExec::ExecToLog 'powershell -ExecutionPolicy ByPass -NoProfile -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Pop $0
    
    ${If} $0 != 0
        MessageBox MB_OK|MB_ICONSTOP "UV installation failed.$\r$\nPlease ensure internet connection and try again."
        Abort
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
    FileWrite $0 "        # Method 1: Try direct python execution with virtual environment$\r$\n"
    FileWrite $0 "        if os.path.exists(venv_python):$\r$\n"
    FileWrite $0 "            print('Using virtual environment python...')$\r$\n"
    FileWrite $0 "            try:$\r$\n"
    FileWrite $0 "                result = subprocess.run([venv_python, '-m', 'vibesurf'], cwd=install_dir)$\r$\n"
    FileWrite $0 "                if result.returncode == 0:$\r$\n"
    FileWrite $0 "                    return$\r$\n"
    FileWrite $0 "                else:$\r$\n"
    FileWrite $0 "                    print(f'Virtual env python returned: {result.returncode}')$\r$\n"
    FileWrite $0 "            except Exception as e:$\r$\n"
    FileWrite $0 "                print(f'Virtual env python failed: {e}')$\r$\n"
    FileWrite $0 "        else:$\r$\n"
    FileWrite $0 "            print('Virtual environment python not found, checking installation...')$\r$\n"
    FileWrite $0 "            # List contents of .venv directory for debugging$\r$\n"
    FileWrite $0 "            if os.path.exists(venv_dir):$\r$\n"
    FileWrite $0 "                try:$\r$\n"
    FileWrite $0 "                    contents = os.listdir(venv_dir)$\r$\n"
    FileWrite $0 "                    print(f'Contents of .venv: {contents}')$\r$\n"
    FileWrite $0 "                    scripts_dir = os.path.join(venv_dir, 'Scripts')$\r$\n"
    FileWrite $0 "                    if os.path.exists(scripts_dir):$\r$\n"
    FileWrite $0 "                        scripts_contents = os.listdir(scripts_dir)$\r$\n"
    FileWrite $0 "                        print(f'Contents of Scripts: {scripts_contents}')$\r$\n"
    FileWrite $0 "                except Exception as e:$\r$\n"
    FileWrite $0 "                    print(f'Error listing venv contents: {e}')$\r$\n"
    FileWrite $0 "        $\r$\n"
    FileWrite $0 "        # Method 2: Try direct activation + vibesurf command$\r$\n"
    FileWrite $0 "        print('Trying direct vibesurf command in venv...')$\r$\n"
    FileWrite $0 "        if os.path.exists(venv_dir):$\r$\n"
    FileWrite $0 "            try:$\r$\n"
    FileWrite $0 "                # Add venv to path and try direct vibesurf command$\r$\n"
    FileWrite $0 "                venv_scripts = os.path.join(venv_dir, 'Scripts')$\r$\n"
    FileWrite $0 "                env = os.environ.copy()$\r$\n"
    FileWrite $0 "                env['PATH'] = venv_scripts + os.pathsep + env['PATH']$\r$\n"
    FileWrite $0 "                result = subprocess.run(['vibesurf'], env=env, cwd=install_dir)$\r$\n"
    FileWrite $0 "                if result.returncode == 0:$\r$\n"
    FileWrite $0 "                    return$\r$\n"
    FileWrite $0 "                else:$\r$\n"
    FileWrite $0 "                    print(f'Direct vibesurf command returned: {result.returncode}')$\r$\n"
    FileWrite $0 "            except Exception as e:$\r$\n"
    FileWrite $0 "                print(f'Direct vibesurf failed: {e}')$\r$\n"
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
    nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && uv pip install vibesurf pyinstaller setuptools wheel"'
    Pop $6
    FileWrite $3 "VibeSurf and PyInstaller installation exit code: $6$\r$\n"
    
    ; Download VibeSurf Chrome Extension
    DetailPrint "Downloading VibeSurf Chrome Extension..."
    FileWrite $3 "Downloading Chrome Extension$\r$\n"
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "& { try { Write-Host \"Downloading extension...\"; Invoke-WebRequest -Uri \"https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/vibesurf-extension.zip\" -OutFile \"$INSTDIR\\vibesurf-extension.zip\" -UseBasicParsing; Write-Host \"Extension downloaded!\" } catch { Write-Host \"Extension download failed: $_\" } }"'
    Pop $7
    FileWrite $3 "Extension download exit code: $7$\r$\n"
    
    ${If} $6 == 0
        DetailPrint "Creating VibeSurf.exe (this may take 60 seconds)..."
        DetailPrint "Using uv run to ensure proper virtual environment..."
        
        ; Check if icon was created successfully and use it
        DetailPrint "Building EXE with custom icon..."
        ; Use uv run to ensure proper virtual environment activation and PATH with icon
        nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && uv run pyinstaller --onefile --console --name "VibeSurf" --icon "$INSTDIR\\logo.png" --distpath "$INSTDIR" --workpath "$INSTDIR\build" --specpath "$INSTDIR" "$INSTDIR\vibesurf_launcher.py""'
        Pop $1
        FileWrite $3 "PyInstaller compilation with icon exit code: $1$\r$\n"
        
        ; If uv run fails, try direct python call as fallback
        ${If} $1 != 0
            DetailPrint "uv run failed, trying direct python call..."
            FileWrite $3 "uv run PyInstaller failed, trying direct python call$\r$\n"
            ${If} ${FileExists} "$INSTDIR\logo.png"
                nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && "$INSTDIR\.venv\Scripts\python.exe" -m PyInstaller --onefile --console --name "VibeSurf" --icon "$INSTDIR\\logo.png" --distpath "$INSTDIR" --workpath "$INSTDIR\build" --specpath "$INSTDIR" "$INSTDIR\vibesurf_launcher.py""'
            ${Else}
                nsExec::ExecToLog 'cmd /c "cd /d "$INSTDIR" && "$INSTDIR\.venv\Scripts\python.exe" -m PyInstaller --onefile --console --name "VibeSurf" --distpath "$INSTDIR" --workpath "$INSTDIR\build" --specpath "$INSTDIR" "$INSTDIR\vibesurf_launcher.py""'
            ${EndIf}
            Pop $1
            FileWrite $3 "Direct python PyInstaller exit code: $1$\r$\n"
        ${EndIf}
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
            ; Clean up build artifacts but keep logo files for shortcuts
            RMDir /r "$INSTDIR\build"
            Delete "$INSTDIR\VibeSurf.spec"
            Delete "$INSTDIR\vibesurf_launcher.py"
            StrCpy $R9 "exe"
        ${Else}
            DetailPrint "FAILED: VibeSurf.exe not found after compilation!"
            FileWrite $3 "EXE Creation: FAILED - File not found$\r$\n"
            StrCpy $R9 "bat"
        ${EndIf}
    ${Else}
        DetailPrint "PyInstaller compilation failed, using batch launcher"
        FileWrite $3 "PyInstaller compilation: FAILED (exit code $1)$\r$\n"
        FileWrite $3 "Using batch launcher as fallback$\r$\n"
        StrCpy $R9 "bat"
    ${EndIf}
    
    FileClose $3
    DetailPrint "Diagnostics saved to: $INSTDIR\installer_log.txt"
    
    ; Always create bat launcher (either as primary or fallback)
    ${If} $R9 == "bat"
        DetailPrint "EXE creation failed or skipped, creating batch launcher..."
    ${Else}
        DetailPrint "Creating additional batch launcher..."
    ${EndIf}
    
    DetailPrint "Creating batch launcher as fallback..."
    FileOpen $2 "$INSTDIR\VibeSurf.bat" w
    FileWrite $2 "@echo off$\r$\n"
    FileWrite $2 "title VibeSurf - AI Browser Assistant$\r$\n"
    FileWrite $2 "cd /d $\"$INSTDIR$\"$\r$\n"
    FileWrite $2 "echo VibeSurf - AI Browser Assistant$\r$\n"
    FileWrite $2 "echo ========================================$\r$\n"
    FileWrite $2 "echo Starting VibeSurf...$\r$\n"
    FileWrite $2 "echo Trying virtual environment python...$\r$\n"
    FileWrite $2 "if exist $\".venv\\Scripts\\python.exe$\" ($\r$\n"
    FileWrite $2 "    .venv\\Scripts\\python.exe -m vibesurf$\r$\n"
    FileWrite $2 "    if errorlevel 1 ($\r$\n"
    FileWrite $2 "        echo Virtual env failed, trying uv run...$\r$\n"
    FileWrite $2 "        uv run vibesurf$\r$\n"
    FileWrite $2 "        if errorlevel 1 ($\r$\n"
    FileWrite $2 "            echo uv run failed, trying system python...$\r$\n"
    FileWrite $2 "            python -m vibesurf$\r$\n"
    FileWrite $2 "        )$\r$\n"
    FileWrite $2 "    )$\r$\n"
    FileWrite $2 ") else ($\r$\n"
    FileWrite $2 "    echo Virtual environment not found, trying uv run...$\r$\n"
    FileWrite $2 "    uv run vibesurf$\r$\n"
    FileWrite $2 "    if errorlevel 1 ($\r$\n"
    FileWrite $2 "        echo uv run failed, trying system python...$\r$\n"
    FileWrite $2 "        python -m vibesurf$\r$\n"
    FileWrite $2 "    )$\r$\n"
    FileWrite $2 ")$\r$\n"
    FileWrite $2 "pause$\r$\n"
    FileClose $2
    
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
