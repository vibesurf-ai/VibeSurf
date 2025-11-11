; VibeSurf Lightweight Installer
; NSIS Script for creating a professional Windows installer

!define APP_NAME "VibeSurf"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "VibeSurf Team"
!define APP_URL "https://github.com/yourusername/VibeSurf"
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
    
    ; Copy bundled uv.exe if it exists (check in dist directory)
    IfFileExists "..\dist\uv.exe" 0 +3
        DetailPrint "Installing bundled uv package manager..."
        File /oname=$INSTDIR\uv\uv.exe "..\dist\uv.exe"
        Goto UVReady
    
    ; Download uv if not bundled
    DetailPrint "Downloading uv package manager from GitHub..."
    
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "& { \
        try { \
            $$ProgressPreference = \"SilentlyContinue\"; \
            $$ErrorActionPreference = \"Stop\"; \
            Write-Host \"[INFO] Starting UV download process...\"; \
            \
            Write-Host \"[INFO] Fetching latest UV release info...\"; \
            $$response = Invoke-WebRequest -Uri \"https://api.github.com/repos/astral-sh/uv/releases/latest\" -UseBasicParsing -TimeoutSec 30; \
            Write-Host \"[INFO] API response received, size: \" + $$response.Content.Length + \" bytes\"; \
            \
            $$json = $$response.Content | ConvertFrom-Json; \
            $$asset = $$json.assets | Where-Object { $$_.name -like \"*x86_64-pc-windows-msvc.zip\" } | Select-Object -First 1; \
            \
            if ($$asset) { \
                $$downloadUrl = $$asset.browser_download_url; \
                $$zipPath = \"$INSTDIR\\uv\\uv.zip\"; \
                Write-Host \"[INFO] Downloading from: $$downloadUrl\"; \
                Write-Host \"[INFO] Download target: $$zipPath\"; \
                \
                Invoke-WebRequest -Uri $$downloadUrl -OutFile $$zipPath -UseBasicParsing -TimeoutSec 120; \
                \
                if (Test-Path $$zipPath) { \
                    Write-Host \"[INFO] Download completed, file size: \" + (Get-Item $$zipPath).Length + \" bytes\"; \
                } else { \
                    throw \"Downloaded file not found\"; \
                } \
                \
                Write-Host \"[INFO] Extracting UV archive...\"; \
                Add-Type -AssemblyName System.IO.Compression.FileSystem; \
                [System.IO.Compression.ZipFile]::ExtractToDirectory($$zipPath, \"$INSTDIR\\uv\\temp\"); \
                \
                Write-Host \"[INFO] Looking for uv.exe in extracted files...\"; \
                $$uvExe = Get-ChildItem -Path \"$INSTDIR\\uv\\temp\" -Recurse -Name \"uv.exe\" | Select-Object -First 1; \
                if ($$uvExe) { \
                    $$sourcePath = Join-Path \"$INSTDIR\\uv\\temp\" $$uvExe; \
                    $$destPath = \"$INSTDIR\\uv\\uv.exe\"; \
                    Write-Host \"[INFO] Moving uv.exe from $$sourcePath to $$destPath\"; \
                    Move-Item -Path $$sourcePath -Destination $$destPath -Force; \
                } else { \
                    throw \"uv.exe not found in extracted archive\"; \
                } \
                \
                Write-Host \"[INFO] Cleaning up temporary files...\"; \
                Remove-Item -Path \"$INSTDIR\\uv\\temp\" -Recurse -Force -ErrorAction SilentlyContinue; \
                Remove-Item -Path $$zipPath -Force -ErrorAction SilentlyContinue; \
                \
                if (Test-Path \"$INSTDIR\\uv\\uv.exe\") { \
                    Write-Host \"[SUCCESS] UV installation completed successfully\"; \
                    exit 0; \
                } else { \
                    throw \"Final verification failed: uv.exe not found at expected location\"; \
                } \
            } else { \
                throw \"Could not find Windows x64 UV release in API response\"; \
            } \
        } catch { \
            Write-Error \"[ERROR] UV download failed: $$($_.Exception.Message)\"; \
            Write-Error \"[ERROR] Stack trace: $$($_.ScriptStackTrace)\"; \
            exit 1; \
        } \
    }"'
    
    Pop $0 ; Get return value
    ${If} $0 != 0
        MessageBox MB_OK|MB_ICONSTOP "Failed to download UV package manager.$\r$\n$\r$\nPossible causes:$\r$\n- No internet connection$\r$\n- GitHub API unreachable$\r$\n- Firewall blocking downloads$\r$\n- PowerShell execution restricted$\r$\n$\r$\nPlease check your network settings and try again."
        Abort
    ${EndIf}
    
    UVReady:
    DetailPrint "Verifying uv installation..."
    IfFileExists "$INSTDIR\uv\uv.exe" UVExists UVMissing
    
    UVMissing:
        MessageBox MB_OK|MB_ICONSTOP "UV package manager not found at $INSTDIR\uv\uv.exe.$\r$\n$\r$\nThis could be due to:$\r$\n- Network connection issues during download$\r$\n- Firewall blocking the download$\r$\n- PowerShell execution policy restrictions$\r$\n$\r$\nPlease check your internet connection and try again."
        Abort
    
    UVExists:
    DetailPrint "UV found successfully. Installing VibeSurf application..."
    
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