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
    
    ; Always download UV online using direct GitHub link - simplified approach
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $$ProgressPreference=\"SilentlyContinue\"; $$url=\"https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip\"; $$zip=\"$INSTDIR\\uv\\uv.zip\"; $$temp=\"$INSTDIR\\uv\\temp\"; Write-Host \"[INFO] Downloading UV...\"; (New-Object System.Net.WebClient).DownloadFile($$url, $$zip); Write-Host \"[INFO] Extracting...\"; Add-Type -A System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory($$zip, $$temp); $$exe = Get-ChildItem -Path $$temp -Recurse -Name \"uv.exe\" | Select -First 1; Copy-Item (Join-Path $$temp $$exe) \"$INSTDIR\\uv\\uv.exe\" -Force; Remove-Item $$temp -Recurse -Force; Remove-Item $$zip -Force; Write-Host \"[SUCCESS] UV installed\"; exit 0; } catch { Write-Error \"[ERROR] $$($_.Exception.Message)\"; exit 1; }"'
    
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
    
    nsExec::ExecToLog '"$INSTDIR\uv\uv.exe" pip install vibesurf --upgrade'
    Pop $0
    ${If} $0 != 0
        MessageBox MB_OK|MB_ICONSTOP "Failed to install VibeSurf using UV.$\r$\n$\r$\nError code: $0$\r$\n$\r$\nPossible causes:$\r$\n- Network connectivity issues$\r$\n- PyPI access blocked$\r$\n- Package not found on PyPI$\r$\n$\r$\nPlease check the installation log and try again."
        Abort
    ${EndIf}
    
    ; Create launcher script
    FileOpen $0 "$INSTDIR\launch-vibesurf.bat" w
    FileWrite $0 "@echo off$\r$\n"
    FileWrite $0 "title VibeSurf - AI Browser Assistant$\r$\n"
    FileWrite $0 "cd /d $\"$INSTDIR$\"$\r$\n"
    FileWrite $0 "$\"$INSTDIR\uv\uv.exe$\" run vibesurf$\r$\n"
    FileClose $0
    
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

Section "Desktop Shortcut" SecDesktop
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\launch-vibesurf.bat" "" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
SectionEnd

Section "Start Menu Shortcut" SecStartMenu
    SectionIn RO
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\launch-vibesurf.bat" "" "$INSTDIR\logo.png" 0 SW_SHOWNORMAL "" "${APP_DESCRIPTION}"
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

Function .onInstSuccess
    ExecShell "open" "$INSTDIR\launch-vibesurf.bat"
FunctionEnd