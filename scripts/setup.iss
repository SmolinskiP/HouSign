#define AppName "HouSign"
#define AppVersion "0.9.1"
#define AppPublisher "HouSign"
#define AppExeName "HouSign.exe"

[Setup]
AppId={{8B6952E7-4B0C-4E76-882A-219C5182C5E1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=HouSign-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\HouSign\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

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
    '    "deactivation_sound_enabled": true' + #13#10 +
    '  },' + #13#10 +
    '  "gui": {' + #13#10 +
    '    "window_maximized": true' + #13#10 +
    '  }' + #13#10 +
    '}' + #13#10;
end;

procedure InitializeWizard;
var
  InfoText: TNewStaticText;
begin
  ConfigPage :=
    CreateInputQueryPage(
      wpSelectTasks,
      'Home Assistant Setup',
      'Provide your Home Assistant connection details',
      'Enter the Home Assistant URL and a Long-Lived Access Token. ' +
      'You can leave them blank and configure everything later from the app settings window.'
    );

  ConfigPage.Add('Home Assistant URL', False);
  ConfigPage.Add('Long-Lived Access Token', False);

  ConfigPage.Values[0] := 'http://homeassistant.local:8123/';
  ConfigPage.Values[1] := '';

  InfoText := TNewStaticText.Create(ConfigPage);
  InfoText.Parent := ConfigPage.Surface;
  InfoText.Left := 0;
  InfoText.Top := 110;
  InfoText.Width := ConfigPage.SurfaceWidth;
  InfoText.Height := 90;
  InfoText.AutoSize := False;
  InfoText.WordWrap := True;
  InfoText.Caption :=
    'How to create the token:' + #13#10 +
    '1. Open Home Assistant and go to your user profile.' + #13#10 +
    '2. Scroll to Long-Lived Access Tokens.' + #13#10 +
    '3. Create a new token for HouSign and paste it here.' + #13#10 +
    '4. If you skip this step now, you can edit settings.json or use the Settings screen later.';
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
