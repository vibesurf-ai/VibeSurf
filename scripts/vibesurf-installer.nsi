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
    DetailPrint "Downloading UV package manager from GitHub..."
    
    ; Download UV using simple but robust PowerShell script
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Write-Host [INFO] Downloading UV...; Invoke-WebRequest -Uri https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip -OutFile $INSTDIR\\uv\\uv.zip -UseBasicParsing; Write-Host [INFO] Extracting...; Expand-Archive $INSTDIR\\uv\\uv.zip $INSTDIR\\uv\\temp -Force; Copy-Item $INSTDIR\\uv\\temp\\*\\uv.exe $INSTDIR\\uv\\uv.exe -Force; Remove-Item $INSTDIR\\uv\\temp -Recurse -Force; Remove-Item $INSTDIR\\uv\\uv.zip -Force; Write-Host [SUCCESS] UV installed; } catch { Write-Error [ERROR] UV download failed; exit 1; }"'
    
    Pop $0 ; Get return value
    ${If} $0 != 0
        DetailPrint "UV download failed, showing troubleshooting options..."
        MessageBox MB_YESNO|MB_ICONQUESTION "Failed to download UV package manager from GitHub.$\r$\n$\r$\nThis could be due to:$\r$\n- Network connectivity issues$\r$\n- Corporate firewall blocking GitHub$\r$\n- PowerShell execution policy restrictions$\r$\n$\r$\nDo you want to try alternative download method?" IDNO AbortInstall
        
        ; Try alternative download using curl with direct link
        DetailPrint "Trying alternative download method with curl..."
        nsExec::ExecToLog 'cmd /c "curl --version >nul 2>&1 && ( \
            echo [INFO] Using curl for UV download... && \
            echo [INFO] Downloading from: https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip && \
            curl -L -A "VibeSurf-Installer/1.0" -o "$INSTDIR\uv\uv.zip" "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" && \
            powershell -NoProfile -Command "Add-Type -A System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::ExtractToDirectory('$INSTDIR\uv\uv.zip', '$INSTDIR\uv\temp')" && \
            for /r "$INSTDIR\uv\temp" %%f in (uv.exe) do copy "%%f" "$INSTDIR\uv\uv.exe" && \
            rmdir /s /q "$INSTDIR\uv\temp" && \
            del "$INSTDIR\uv\uv.zip" && \
            echo [SUCCESS] UV installed via curl \
        ) || ( \
            echo [ERROR] curl download also failed \
        )"'
        
        Pop $1
        ${If} $1 != 0
            AbortInstall:
            MessageBox MB_OK|MB_ICONSTOP "Both PowerShell and curl download methods failed.$\r$\n$\r$\nPlease install UV manually from: https://docs.astral.sh/uv/getting-started/installation/$\r$\n$\r$\nThen run: uv pip install vibesurf"
            Abort
        ${EndIf}
    ${EndIf}
    
    ; Verify UV installation
    DetailPrint "Verifying UV installation..."
    ${If} ${FileExists} "$INSTDIR\uv\uv.exe"
        DetailPrint "UV found successfully. Installing VibeSurf application..."
    ${Else}
        MessageBox MB_OK|MB_ICONSTOP "UV package manager installation failed.$\r$\n$\r$\nPlease check your internet connection and try again.$\r$\nAlternatively, install UV manually from: https://docs.astral.sh/uv/"
        Abort
    ${EndIf}
    
    ; Install VibeSurf initially (launcher will handle future updates)
    DetailPrint "Installing VibeSurf package..."
    nsExec::ExecToLog '"$INSTDIR\uv\uv.exe" pip install vibesurf --upgrade'
    Pop $0
    ${If} $0 != 0
        MessageBox MB_YESNO|MB_ICONQUESTION "Failed to install VibeSurf initially.$\r$\n$\r$\nError code: $0$\r$\n$\r$\nThis may be due to network issues. The launcher will attempt to download VibeSurf on first run.$\r$\n$\r$\nContinue with installation?" IDNO AbortInstall2
        DetailPrint "Continuing installation - VibeSurf will be downloaded on first launch"
        Goto SkipInitialInstall
        
        AbortInstall2:
        Abort
    ${Else}
        DetailPrint "VibeSurf installed successfully"
    ${EndIf}
    
    SkipInitialInstall:
    
    ; Create Python launcher script with auto-upgrade
    DetailPrint "Creating VibeSurf launcher with auto-upgrade..."
    FileOpen $0 "$INSTDIR\vibesurf_launcher.py" w
    FileWrite $0 "#!/usr/bin/env python3$\r$\n"
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
    FileWrite $0 "    uv_exe = os.path.join(install_dir, 'uv', 'uv.exe')$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    if not os.path.exists(uv_exe):$\r$\n"
    FileWrite $0 "        print('Error: UV package manager not found')$\r$\n"
    FileWrite $0 "        input('Press Enter to exit...')$\r$\n"
    FileWrite $0 "        return$\r$\n"
    FileWrite $0 "    $\r$\n"
    FileWrite $0 "    try:$\r$\n"
    FileWrite $0 "        print('Checking for VibeSurf updates...')$\r$\n"
    FileWrite $0 "        # Try update with extended timeout and better error handling$\r$\n"
    FileWrite $0 "        try:$\r$\n"
    FileWrite $0 "            result = subprocess.run([uv_exe, 'pip', 'install', 'vibesurf', '--upgrade', '--quiet', '--timeout', '60'], $\r$\n"
    FileWrite $0 "                                   capture_output=True, text=True, timeout=45)$\r$\n"
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
    FileWrite $0 "        subprocess.run([uv_exe, 'run', 'vibesurf'], check=True)$\r$\n"
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
    FileWrite $3 "UV Executable: $INSTDIR\uv\uv.exe$\r$\n"
    
    DetailPrint "Installing PyInstaller via UV..."
    FileWrite $3 "Step 1: Installing PyInstaller$\r$\n"
    
    ; First check UV environment
    DetailPrint "Checking UV environment..."
    nsExec::ExecToLog '"$INSTDIR\uv\uv.exe" --version'
    Pop $5
    FileWrite $3 "UV version check exit code: $5$\r$\n"
    
    ; Try PyInstaller installation with verbose output
    DetailPrint "Attempting PyInstaller installation with detailed logging..."
    nsExec::ExecToLog '"$INSTDIR\uv\uv.exe" pip install pyinstaller'
    Pop $0
    FileWrite $3 "PyInstaller install exit code: $0$\r$\n"
    
    ; Show detailed results to user
    ${If} $0 == 0
        DetailPrint "PyInstaller installed successfully!"
        FileWrite $3 "PyInstaller installation: SUCCESS$\r$\n"
        
        DetailPrint "Checking PyInstaller version..."
        nsExec::ExecToLog 'cd /d "$INSTDIR" && "$INSTDIR\uv\uv.exe" run pyinstaller --version'
        Pop $2
        FileWrite $3 "PyInstaller version check exit code: $2$\r$\n"
        
        ${If} $2 == 0
            DetailPrint "PyInstaller version check passed!"
            FileWrite $3 "PyInstaller version check: SUCCESS$\r$\n"
            
            DetailPrint "Creating VibeSurf.exe (this may take 30-60 seconds)..."
            DetailPrint "Please wait while PyInstaller compiles the executable..."
            nsExec::ExecToLog 'cd /d "$INSTDIR" && "$INSTDIR\uv\uv.exe" run pyinstaller --onefile --console --name "VibeSurf" --distpath "$INSTDIR" --workpath "$INSTDIR\build" --specpath "$INSTDIR" --log-level DEBUG vibesurf_launcher.py'
            Pop $1
            FileWrite $3 "PyInstaller compilation exit code: $1$\r$\n"
            
            DetailPrint "PyInstaller compilation finished with exit code: $1"
            
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
        ${Else}
            DetailPrint "FAILED: PyInstaller version check failed!"
            FileWrite $3 "PyInstaller version check: FAILED$\r$\n"
            MessageBox MB_OK|MB_ICONEXCLAMATION "PyInstaller Environment Error!$\r$\n$\r$\nPyInstaller was installed but cannot run properly.$\r$\nThis usually indicates UV environment issues.$\r$\n$\r$\nUsing batch launcher instead."
            StrCpy $R9 "bat"
        ${EndIf}
    ${Else}
        DetailPrint "FAILED: PyInstaller installation failed after all attempts!"
        FileWrite $3 "PyInstaller installation: FAILED (exit code $0)$\r$\n"
        FileWrite $3 "All installation methods failed$\r$\n"
        FileWrite $3 "Detailed diagnosis:$\r$\n"
        
        ; Try to get more diagnostic info
        DetailPrint "Running additional diagnostics..."
        nsExec::ExecToLog '"$INSTDIR\uv\uv.exe" pip list'
        
        ${If} $0 == 2
            FileWrite $3 "Exit code 2 suggests: Command line argument error or package conflict$\r$\n"
            FileWrite $3 "This often happens when:$\r$\n"
            FileWrite $3 "- UV cache is corrupted$\r$\n"
            FileWrite $3 "- PyInstaller has dependency conflicts$\r$\n"
            FileWrite $3 "- UV environment is isolated and missing system packages$\r$\n"
            MessageBox MB_YESNO|MB_ICONQUESTION "PyInstaller Installation Failed (Exit Code 2)$\r$\n$\r$\nThis usually indicates a UV environment or dependency issue.$\r$\n$\r$\nCommon causes:$\r$\n- UV cache corruption$\r$\n- Package dependency conflicts$\r$\n- Missing system libraries$\r$\n$\r$\nWould you like to try a system Python fallback?"  IDYES TrySystemPython IDNO UseBAT
            
            TrySystemPython:
            DetailPrint "Trying system Python as fallback..."
            FileWrite $3 "Attempting system Python fallback$\r$\n"
            nsExec::ExecToLog 'python -m pip install pyinstaller --quiet'
            Pop $6
            FileWrite $3 "System Python PyInstaller exit code: $6$\r$\n"
            
            ${If} $6 == 0
                DetailPrint "System Python PyInstaller installed! Trying EXE creation..."
                nsExec::ExecToLog 'cd /d "$INSTDIR" && python -m PyInstaller --onefile --console --name "VibeSurf" vibesurf_launcher.py'
                Pop $7
                ${If} $7 == 0
                    ${AndIf} ${FileExists} "$INSTDIR\dist\VibeSurf.exe"
                    DetailPrint "SUCCESS! EXE created with system Python!"
                    FileWrite $3 "System Python EXE creation: SUCCESS$\r$\n"
                    CopyFiles "$INSTDIR\dist\VibeSurf.exe" "$INSTDIR\VibeSurf.exe"
                    RMDir /r "$INSTDIR\dist"
                    RMDir /r "$INSTDIR\build"
                    Delete "$INSTDIR\VibeSurf.spec"
                    Delete "$INSTDIR\vibesurf_launcher.py"
                    MessageBox MB_OK|MB_ICONINFORMATION "Success!$\r$\n$\r$\nVibeSurf.exe was created using system Python.$\r$\n$\r$\nNote: UV PyInstaller failed but system Python worked."
                    StrCpy $R9 "exe"
                    Goto EndDiagnostics
                ${Else}
                    FileWrite $3 "System Python EXE creation also failed$\r$\n"
                ${EndIf}
            ${EndIf}
            
            UseBAT:
            MessageBox MB_OK|MB_ICONINFORMATION "EXE Creation Failed$\r$\n$\r$\nPyInstaller could not be installed in either UV or system Python environment.$\r$\n$\r$\nUsing reliable batch launcher instead.$\r$\nThe batch launcher works just as well and auto-updates!"
        ${Else}
            FileWrite $3 "Exit code $0 suggests other issues$\r$\n"
            MessageBox MB_OK|MB_ICONEXCLAMATION "PyInstaller Installation Failed!$\r$\n$\r$\nFailed with exit code: $0$\r$\n$\r$\nUsing batch launcher instead.$\r$\nCheck installer_log.txt for details."
        ${EndIf}
        
        StrCpy $R9 "bat"
        EndDiagnostics:
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
        FileWrite $2 "$\"$INSTDIR\uv\uv.exe$\" pip install vibesurf --upgrade --quiet$\r$\n"
        FileWrite $2 "if %errorlevel% equ 0 ($\r$\n"
        FileWrite $2 "    echo VibeSurf is up to date!$\r$\n"
        FileWrite $2 ") else ($\r$\n"
        FileWrite $2 "    echo Note: Update check failed, using existing version$\r$\n"
        FileWrite $2 ")$\r$\n"
        FileWrite $2 "echo Updating VibeSurf Chrome Extension...$\r$\n"
        FileWrite $2 "powershell -NoProfile -ExecutionPolicy Bypass -Command $\"& { try { Write-Host 'Downloading extension...'; if (Test-Path '$INSTDIR\\vibesurf-extension') { Remove-Item '$INSTDIR\\vibesurf-extension' -Recurse -Force }; New-Item -Path '$INSTDIR\\vibesurf-extension' -ItemType Directory -Force; Invoke-WebRequest -Uri 'https://github.com/vibesurf-ai/VibeSurf/releases/latest/download/vibesurf-extension.zip' -OutFile '$INSTDIR\\vibesurf-extension.zip' -UseBasicParsing; Expand-Archive '$INSTDIR\\vibesurf-extension.zip' '$INSTDIR\\vibesurf-extension' -Force; Remove-Item '$INSTDIR\\vibesurf-extension.zip' -Force; Write-Host 'Extension updated!' } catch { Write-Host 'Extension update failed, continuing...' } }$\"$\r$\n"
        FileWrite $2 "echo Starting VibeSurf...$\r$\n"
        FileWrite $2 "timeout /t 1 /nobreak >nul$\r$\n"
        FileWrite $2 "$\"$INSTDIR\uv\uv.exe$\" run vibesurf$\r$\n"
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
