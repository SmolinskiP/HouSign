#ifndef AppName
  #define AppName "HouSign"
#endif
#ifndef AppVersion
  #define AppVersion "0.9.1"
#endif
#ifndef AppExeName
  #define AppExeName "HouSign.exe"
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "HouSign-Setup"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\HouSign"
#endif
#define AppPublisher "Patryk Smoliński"
#define AppURL "https://github.com/SmolinskiP/HouSign"

[Setup]
AppId={{8B6952E7-4B0C-4E76-882A-219C5182C5E1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile=..\logo.ico
WizardImageFile=assets\wizard_sidebar.bmp
WizardSmallImageFile=assets\wizard_small.bmp
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=..\LICENSE.txt
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "autostart"; Description: "Start HouSign automatically when &Windows starts"; GroupDescription: "Startup:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: "{app}\{#AppExeName}"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
Filename: "{#AppURL}"; Description: "Visit GitHub Repository"; Flags: shellexec skipifsilent postinstall unchecked
Filename: "https://buymeacoffee.com/smolinskip"; Description: "Buy Developer a Coffee"; Flags: shellexec skipifsilent postinstall unchecked

[Code]
var
  ConfigPage: TInputQueryWizardPage;

function JsonEscape(const Value: string): string;
var
  ResultValue: string;
begin
  ResultValue := Value;
  StringChangeEx(ResultValue, '\', '\\', True);
  StringChangeEx(ResultValue, '"', '\"', True);
  Result := ResultValue;
end;

function BuildSettingsJson(): string;
var
  UrlValue: string;
  TokenValue: string;
begin
  UrlValue := JsonEscape(Trim(ConfigPage.Values[0]));
  TokenValue := JsonEscape(Trim(ConfigPage.Values[1]));

  Result :=
    '{' + #13#10 +
    '  "ha": {' + #13#10 +
    '    "url": "' + UrlValue + '",' + #13#10 +
    '    "token": "' + TokenValue + '"' + #13#10 +
    '  },' + #13#10 +
    '  "runtime": {' + #13#10 +
    '    "camera_index": 0,' + #13#10 +
    '    "model_path": "models/hand_landmarker.task",' + #13#10 +
    '    "gestures_config": "gestures.yaml",' + #13#10 +
    '    "bindings_config": "gesture_bindings.json",' + #13#10 +
    '    "print_every": 10,' + #13#10 +
    '    "mirror": true' + #13#10 +
    '  },' + #13#10 +
    '  "recognition": {' + #13#10 +
    '    "listening_mode": "activation_required",' + #13#10 +
    '    "activation_mode": "one_hand",' + #13#10 +
    '    "activation_trigger_id": "right_front_0_11111",' + #13#10 +
    '    "activation_gesture_name": "open_palm",' + #13#10 +
    '    "activation_hold_ms": 600,' + #13#10 +
    '    "session_timeout_ms": 4000,' + #13#10 +
    '    "activation_sound_enabled": true,' + #13#10 +
    '    "deactivation_sound_enabled": true,' + #13#10 +
    '    "gesture_sound_enabled": true,' + #13#10 +
    '    "gesture_hold_ms": 140,' + #13#10 +
    '    "gesture_gap_tolerance_ms": 100' + #13#10 +
    '  },' + #13#10 +
    '  "gui": {' + #13#10 +
    '    "window_maximized": true' + #13#10 +
    '  }' + #13#10 +
    '}' + #13#10;
end;

procedure InitializeWizard;
begin
  ConfigPage :=
    CreateInputQueryPage(
      wpSelectTasks,
      'Home Assistant Setup',
      'Provide your Home Assistant connection details',
      'You can leave these blank and configure them later from the app settings window.' + #13#10 +
      'To get a token: HA Profile → Security → Long-Lived Access Tokens → Create Token.'
    );

  ConfigPage.Add('Home Assistant URL:', False);
  ConfigPage.Add('Long-Lived Access Token:', False);

  ConfigPage.Values[0] := 'http://homeassistant.local:8123/';
  ConfigPage.Values[1] := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsPath: string;
begin
  if CurStep = ssPostInstall then
  begin
    SettingsPath := ExpandConstant('{app}\settings.json');
    SaveStringToFile(SettingsPath, BuildSettingsJson(), False);
  end;
end;
