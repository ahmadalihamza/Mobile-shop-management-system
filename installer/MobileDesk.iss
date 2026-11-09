#define AppVersion "1.6.0"
[Setup]
AppId={{187E601B-A049-4E9C-8C83-16630C96D029}
AppName=Mobile Desk
AppVersion={#AppVersion}
AppPublisher=Mobile Desk
DefaultDirName={localappdata}\Programs\MobileDesk
DefaultGroupName=Mobile Desk
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.18362
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\MobileDesk.exe
SetupIconFile=..\resources\app.ico
LicenseFile=..\LICENSE
InfoAfterFile=after-install.txt
OutputDir=..\dist
OutputBaseFilename=MobileDesk-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.6.0.0

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\MobileDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{app}\_internal\resources\client_seed.zip"
Type: filesandordirs; Name: "{app}\client-migration-report"
Type: files; Name: "{app}\docs\MIGRATION.md"
Type: files; Name: "{app}\docs\EXCEL_FINDINGS.md"
Type: files; Name: "{app}\MobileDesk-1.0.0-Source.zip"
Type: files; Name: "{app}\MobileDesk-1.1.0-Source.zip"
Type: files; Name: "{app}\MobileDesk-1.2.0-Source.zip"
Type: files; Name: "{app}\MobileDesk-1.3.0-Source.zip"
Type: files; Name: "{app}\MobileDesk-1.4.0-Source.zip"
Type: files; Name: "{app}\MobileDesk-1.5.0-Source.zip"

[Icons]
Name: "{group}\Mobile Desk"; Filename: "{app}\MobileDesk.exe"
Name: "{group}\Mobile Desk User Guide"; Filename: "{app}\USER_GUIDE.md"
Name: "{autodesktop}\Mobile Desk"; Filename: "{app}\MobileDesk.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MobileDesk.exe"; Description: "Open Mobile Desk"; Flags: nowait postinstall skipifsilent

; No data-folder or backup delete entries: upgrades/uninstall retain shop records.
