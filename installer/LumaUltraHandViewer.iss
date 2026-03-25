#ifndef AppName
  #define AppName "Luma Ultra Hand Viewer"
#endif

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#ifndef AppPublisher
  #define AppPublisher "Michon"
#endif

#ifndef AppUrl
  #define AppUrl "https://github.com/your-account/luma-ultra"
#endif

#ifndef SourceDir
  #define SourceDir "..\release\LumaUltraHandViewer"
#endif

#ifndef OutputDir
  #define OutputDir "..\installer-output"
#endif

[Setup]
AppId={{0F68D0DA-4D2A-4EA7-A5A2-DF7A0D730337}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}
DefaultDirName={autopf}\Luma Ultra Hand Viewer
DefaultGroupName=Luma Ultra Hand Viewer
UninstallDisplayIcon={app}\LumaUltraHandViewer.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
OutputDir={#OutputDir}
OutputBaseFilename=LumaUltraHandViewer-Setup-{#AppVersion}
VersionInfoVersion={#AppVersion}
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Luma Ultra Hand Viewer"; Filename: "{app}\LumaUltraHandViewer.exe"
Name: "{autodesktop}\Luma Ultra Hand Viewer"; Filename: "{app}\LumaUltraHandViewer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LumaUltraHandViewer.exe"; Description: "Launch Luma Ultra Hand Viewer"; Flags: nowait postinstall skipifsilent
