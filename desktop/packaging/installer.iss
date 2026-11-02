#define AppVersion "0.4.0"
[Setup]
AppId={{10A7BA23-45B4-4BD5-B966-5EC0226FAC01}
AppName=ERT Studio
AppVersion={#AppVersion}
AppPublisher=ERT Studio contributors
DefaultDirName={localappdata}\Programs\ERT Studio
DefaultGroupName=ERT Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installer
OutputBaseFilename=ERTStudio-0.4.0-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ERTStudio.exe
SetupLogging=yes
[Files]
Source: "..\..\dist\ERTStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Icons]
Name: "{group}\ERT Studio"; Filename: "{app}\ERTStudio.exe"
Name: "{autodesktop}\ERT Studio"; Filename: "{app}\ERTStudio.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\ERTStudio.exe"; Description: "Launch ERT Studio"; Flags: nowait postinstall skipifsilent
