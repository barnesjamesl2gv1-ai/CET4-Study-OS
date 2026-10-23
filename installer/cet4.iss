#define AppName "CET4 Study OS"
#define AppVersion "0.1.0"
[Setup]
AppId={{B4D89130-7F32-4BE7-85A9-A1E56BCA0841}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\CET4 Study OS
DefaultGroupName={#AppName}
OutputDir=..\artifacts
OutputBaseFilename=CET4-Study-OS-0.1.0-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
UninstallDisplayName={#AppName}

[Files]
Source: "..\dist\CET4StudyOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "licenses\*.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\docs\ACCEPTANCE_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\CET4 Study OS"; Filename: "{app}\CET4StudyOS.exe"
Name: "{autodesktop}\CET4 Study OS"; Filename: "{app}\CET4StudyOS.exe"

[Run]
Filename: "{app}\CET4StudyOS.exe"; Description: "启动 CET4 Study OS"; Flags: nowait postinstall skipifsilent
