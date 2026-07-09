; ===========================================================================
;  FABOuanes - Installateur Windows avec assistant de configuration DB
;  Genere par l'assistant de production FABOuanes
; ===========================================================================

#define MyAppName      "FABOuanes"
#define MyAppVersion   "1.4.0"
#define MyAppPublisher "FABOuanes"
#define MyAppExeName   "FABOuanes.exe"

[Setup]
AppId={{9C83D15A-8D36-4B64-96C4-FAB0UANES001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://fabouanes.local
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\..\installer_output
OutputBaseFilename=FABOuanes_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
WizardResizable=yes
WizardSizePercent=115,115
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
SetupIconFile=..\..\static\FABOuanes_desktop.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=
InfoBeforeFile=

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Creer une icone sur le bureau"; GroupDescription: "Raccourcis supplementaires :"; Flags: unchecked

[Dirs]
Name: "{localappdata}\{#MyAppName}"
Name: "{localappdata}\{#MyAppName}\backups"
Name: "{localappdata}\{#MyAppName}\backups\local"
Name: "{localappdata}\{#MyAppName}\imports"
Name: "{localappdata}\{#MyAppName}\logs"
Name: "{localappdata}\{#MyAppName}\notes"
Name: "{localappdata}\{#MyAppName}\pdf_reader"
Name: "{localappdata}\{#MyAppName}\reports_generated"
Name: "{localappdata}\{#MyAppName}\webview"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\..\dist\FABOuanes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\Desinstaller {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer FABOuanes"; Flags: nowait postinstall skipifsilent

; ===========================================================================
;  PASCAL SCRIPT — Pages personnalisees
; ===========================================================================
[Code]

const
  DB_POSTGRES_LOCAL   = 0;
  DB_POSTGRES_SERVER  = 1;

var
  // --- Page choix de base de donnees ---
  PageDbChoice: TWizardPage;
  RadioPgLocal: TNewRadioButton;
  RadioPgServer: TNewRadioButton;
  LabelDbTitle: TNewStaticText;
  LabelDbDesc: TNewStaticText;
  PanelPgLocal: TPanel;
  PanelPgServer: TPanel;

  // --- Page configuration PostgreSQL ---
  PagePgConfig: TWizardPage;
  EditPgPort: TNewEdit;
  EditPgUser: TNewEdit;
  EditPgPass: TPasswordEdit;
  EditPgDbName: TNewEdit;
  LabelPgTitle: TNewStaticText;
  LabelPgPort: TNewStaticText;
  LabelPgUser: TNewStaticText;
  LabelPgPass: TNewStaticText;
  LabelPgDbName: TNewStaticText;
  LabelPgInfo: TNewStaticText;
  FormCard: TPanel;

  // --- Page choix de l'IA ---
  PageAiChoice: TWizardPage;
  RadioAiGemini: TNewRadioButton;
  RadioAiOllama: TNewRadioButton;
  RadioAiBoth: TNewRadioButton;
  LabelAiTitle: TNewStaticText;
  LabelAiGeminiDesc: TNewStaticText;
  LabelAiOllamaDesc: TNewStaticText;
  LabelAiBothDesc: TNewStaticText;
  PanelAiGemini: TPanel;
  PanelAiOllama: TPanel;
  PanelAiBoth: TPanel;

procedure PgLocalCardClick(Sender: TObject);
begin
  RadioPgLocal.Checked := True;
end;

procedure PgServerCardClick(Sender: TObject);
begin
  RadioPgServer.Checked := True;
end;

procedure AiGeminiCardClick(Sender: TObject);
begin
  RadioAiGemini.Checked := True;
end;

procedure AiOllamaCardClick(Sender: TObject);
begin
  RadioAiOllama.Checked := True;
end;

procedure AiBothCardClick(Sender: TObject);
begin
  RadioAiBoth.Checked := True;
end;

function GetDbChoice(): Integer;
begin
  if RadioPgServer.Checked then
    Result := DB_POSTGRES_SERVER
  else
    Result := DB_POSTGRES_LOCAL;
end;


// ---- Create the database choice page ----
procedure CreateDbChoicePage();
var
  TopPos: Integer;
begin
  PageDbChoice := CreateCustomPage(
    wpSelectDir,
    'Base de donnees',
    'Choisissez comment FABOuanes doit stocker ses donnees.'
  );

  TopPos := 0;

  LabelDbTitle := TNewStaticText.Create(PageDbChoice);
  LabelDbTitle.Parent := PageDbChoice.Surface;
  LabelDbTitle.Caption := 'Quel mode souhaitez-vous utiliser ?';
  LabelDbTitle.Font.Name := 'Segoe UI';
  LabelDbTitle.Font.Style := [fsBold];
  LabelDbTitle.Font.Size := 10;
  LabelDbTitle.Left := 0;
  LabelDbTitle.Top := TopPos;
  LabelDbTitle.AutoSize := True;
  TopPos := TopPos + 28;

  // --- Card 1: Local Database ---
  PanelPgLocal := TPanel.Create(PageDbChoice);
  PanelPgLocal.Parent := PageDbChoice.Surface;
  PanelPgLocal.Left := 0;
  PanelPgLocal.Top := TopPos;
  PanelPgLocal.Width := PageDbChoice.SurfaceWidth;
  PanelPgLocal.Height := 76;
  PanelPgLocal.Color := clWhite;
  PanelPgLocal.ParentBackground := False;
  PanelPgLocal.BevelOuter := bvNone;
  PanelPgLocal.Cursor := crHand;
  PanelPgLocal.OnClick := @PgLocalCardClick;

  RadioPgLocal := TNewRadioButton.Create(PageDbChoice);
  RadioPgLocal.Parent := PanelPgLocal;
  RadioPgLocal.Caption := 'PostgreSQL — Utilisation sur ce poste uniquement (recommande)';
  RadioPgLocal.Font.Name := 'Segoe UI';
  RadioPgLocal.Font.Style := [fsBold];
  RadioPgLocal.Font.Size := 9;
  RadioPgLocal.Left := 16;
  RadioPgLocal.Top := 14;
  RadioPgLocal.Width := PanelPgLocal.Width - 32;
  RadioPgLocal.Checked := True;
  RadioPgLocal.Cursor := crHand;

  LabelDbDesc := TNewStaticText.Create(PageDbChoice);
  LabelDbDesc.Parent := PanelPgLocal;
  LabelDbDesc.Caption := 'Base fiable et performante avec PostgreSQL installe sur cette machine.' + #13#10 + 'Ideal pour un usage professionnel quotidien sur un seul poste.';
  LabelDbDesc.Font.Name := 'Segoe UI';
  LabelDbDesc.Font.Size := 8;
  LabelDbDesc.Font.Color := clGray;
  LabelDbDesc.Left := 36;
  LabelDbDesc.Top := 36;
  LabelDbDesc.Width := PanelPgLocal.Width - 52;
  LabelDbDesc.WordWrap := True;
  LabelDbDesc.Cursor := crHand;
  LabelDbDesc.OnClick := @PgLocalCardClick;

  TopPos := TopPos + 88;

  // --- Card 2: Server Database ---
  PanelPgServer := TPanel.Create(PageDbChoice);
  PanelPgServer.Parent := PageDbChoice.Surface;
  PanelPgServer.Left := 0;
  PanelPgServer.Top := TopPos;
  PanelPgServer.Width := PageDbChoice.SurfaceWidth;
  PanelPgServer.Height := 76;
  PanelPgServer.Color := clWhite;
  PanelPgServer.ParentBackground := False;
  PanelPgServer.BevelOuter := bvNone;
  PanelPgServer.Cursor := crHand;
  PanelPgServer.OnClick := @PgServerCardClick;

  RadioPgServer := TNewRadioButton.Create(PageDbChoice);
  RadioPgServer.Parent := PanelPgServer;
  RadioPgServer.Caption := 'PostgreSQL Serveur — Ce poste sert les autres machines du reseau';
  RadioPgServer.Font.Name := 'Segoe UI';
  RadioPgServer.Font.Style := [fsBold];
  RadioPgServer.Font.Size := 9;
  RadioPgServer.Left := 16;
  RadioPgServer.Top := 14;
  RadioPgServer.Width := PanelPgServer.Width - 32;
  RadioPgServer.Checked := False;
  RadioPgServer.Cursor := crHand;

  LabelDbDesc := TNewStaticText.Create(PageDbChoice);
  LabelDbDesc.Parent := PanelPgServer;
  LabelDbDesc.Caption := 'Cette machine devient le serveur FABOuanes. Les autres postes' + #13#10 + 'du reseau (PC, telephone) se connectent a celle-ci.';
  LabelDbDesc.Font.Name := 'Segoe UI';
  LabelDbDesc.Font.Size := 8;
  LabelDbDesc.Font.Color := clGray;
  LabelDbDesc.Left := 36;
  LabelDbDesc.Top := 36;
  LabelDbDesc.Width := PanelPgServer.Width - 52;
  LabelDbDesc.WordWrap := True;
  LabelDbDesc.Cursor := crHand;
  LabelDbDesc.OnClick := @PgServerCardClick;
end;


// ---- Create the PostgreSQL configuration page ----
procedure CreatePgConfigPage();
var
  TopPos: Integer;
begin
  PagePgConfig := CreateCustomPage(
    PageDbChoice.ID,
    'Configuration PostgreSQL',
    'Entrez les parametres de votre PostgreSQL local.'
  );

  TopPos := 0;

  LabelPgTitle := TNewStaticText.Create(PagePgConfig);
  LabelPgTitle.Parent := PagePgConfig.Surface;
  LabelPgTitle.Caption := 'Connexion au PostgreSQL de cette machine';
  LabelPgTitle.Font.Name := 'Segoe UI';
  LabelPgTitle.Font.Style := [fsBold];
  LabelPgTitle.Font.Size := 10;
  LabelPgTitle.Left := 0;
  LabelPgTitle.Top := TopPos;
  LabelPgTitle.AutoSize := True;
  TopPos := TopPos + 28;

  // --- Form Container Card ---
  FormCard := TPanel.Create(PagePgConfig);
  FormCard.Parent := PagePgConfig.Surface;
  FormCard.Left := 0;
  FormCard.Top := TopPos;
  FormCard.Width := PagePgConfig.SurfaceWidth;
  FormCard.Height := 150;
  FormCard.Color := clWhite;
  FormCard.ParentBackground := False;
  FormCard.BevelOuter := bvNone;

  // Username
  LabelPgUser := TNewStaticText.Create(PagePgConfig);
  LabelPgUser.Parent := FormCard;
  LabelPgUser.Caption := 'Nom d''utilisateur :';
  LabelPgUser.Font.Name := 'Segoe UI';
  LabelPgUser.Font.Style := [fsBold];
  LabelPgUser.Font.Size := 9;
  LabelPgUser.Left := 16;
  LabelPgUser.Top := 15;
  LabelPgUser.Width := 150;

  EditPgUser := TNewEdit.Create(PagePgConfig);
  EditPgUser.Parent := FormCard;
  EditPgUser.Left := 185;
  EditPgUser.Top := 12;
  EditPgUser.Width := 220;
  EditPgUser.Height := 24;
  EditPgUser.Font.Name := 'Segoe UI';
  EditPgUser.Font.Size := 9;
  EditPgUser.Text := 'postgres';

  // Password
  LabelPgPass := TNewStaticText.Create(PagePgConfig);
  LabelPgPass.Parent := FormCard;
  LabelPgPass.Caption := 'Mot de passe :';
  LabelPgPass.Font.Name := 'Segoe UI';
  LabelPgPass.Font.Style := [fsBold];
  LabelPgPass.Font.Size := 9;
  LabelPgPass.Left := 16;
  LabelPgPass.Top := 49;
  LabelPgPass.Width := 150;

  EditPgPass := TPasswordEdit.Create(PagePgConfig);
  EditPgPass.Parent := FormCard;
  EditPgPass.Left := 185;
  EditPgPass.Top := 46;
  EditPgPass.Width := 220;
  EditPgPass.Height := 24;
  EditPgPass.Font.Name := 'Segoe UI';
  EditPgPass.Font.Size := 9;
  EditPgPass.Text := '';

  // Port
  LabelPgPort := TNewStaticText.Create(PagePgConfig);
  LabelPgPort.Parent := FormCard;
  LabelPgPort.Caption := 'Port PostgreSQL :';
  LabelPgPort.Font.Name := 'Segoe UI';
  LabelPgPort.Font.Style := [fsBold];
  LabelPgPort.Font.Size := 9;
  LabelPgPort.Left := 16;
  LabelPgPort.Top := 83;
  LabelPgPort.Width := 150;

  EditPgPort := TNewEdit.Create(PagePgConfig);
  EditPgPort.Parent := FormCard;
  EditPgPort.Left := 185;
  EditPgPort.Top := 80;
  EditPgPort.Width := 100;
  EditPgPort.Height := 24;
  EditPgPort.Font.Name := 'Segoe UI';
  EditPgPort.Font.Size := 9;
  EditPgPort.Text := '5432';

  // Database Name
  LabelPgDbName := TNewStaticText.Create(PagePgConfig);
  LabelPgDbName.Parent := FormCard;
  LabelPgDbName.Caption := 'Nom de la base :';
  LabelPgDbName.Font.Name := 'Segoe UI';
  LabelPgDbName.Font.Style := [fsBold];
  LabelPgDbName.Font.Size := 9;
  LabelPgDbName.Left := 16;
  LabelPgDbName.Top := 117;
  LabelPgDbName.Width := 150;

  EditPgDbName := TNewEdit.Create(PagePgConfig);
  EditPgDbName.Parent := FormCard;
  EditPgDbName.Left := 185;
  EditPgDbName.Top := 114;
  EditPgDbName.Width := 220;
  EditPgDbName.Height := 24;
  EditPgDbName.Font.Name := 'Segoe UI';
  EditPgDbName.Font.Size := 9;
  EditPgDbName.Text := 'fabouanes';

  TopPos := TopPos + 158;

  // Info text
  LabelPgInfo := TNewStaticText.Create(PagePgConfig);
  LabelPgInfo.Parent := PagePgConfig.Surface;
  LabelPgInfo.Caption :=
    'PostgreSQL doit etre installe sur cette machine.' + #13#10 +
    'Utilisez le mot de passe choisi lors de l''installation de PostgreSQL.' + #13#10 +
    'Si vous n''avez pas encore installe PostgreSQL, annulez l''installation' + #13#10 +
    'et installez-le depuis : https://www.postgresql.org/download/windows/';
  LabelPgInfo.Left := 0;
  LabelPgInfo.Top := TopPos;
  LabelPgInfo.Width := PagePgConfig.SurfaceWidth;
  LabelPgInfo.WordWrap := True;
  LabelPgInfo.Font.Name := 'Segoe UI';
  LabelPgInfo.Font.Size := 8;
  LabelPgInfo.Font.Color := clGray;
end;


// ---- Skip PgConfig page ----
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;


// ---- Validate PostgreSQL fields ----
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = PagePgConfig.ID then
  begin
    if Trim(EditPgPort.Text) = '' then
    begin
      MsgBox('Le port PostgreSQL est obligatoire.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Trim(EditPgUser.Text) = '' then
    begin
      MsgBox('Le nom d''utilisateur PostgreSQL est obligatoire.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Trim(EditPgDbName.Text) = '' then
    begin
      MsgBox('Le nom de la base de donnees est obligatoire.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;


// ---- Generate a random SECRET_KEY ----
function GenerateSecretKey(): String;
var
  I: Integer;
  Hex: String;
  Chars: String;
begin
  Chars := '0123456789abcdef';
  Hex := '';
  for I := 1 to 64 do
    Hex := Hex + Chars[Random(16) + 1];
  Result := Hex;
end;


// ---- Build DATABASE_URL from user input ----
function BuildDatabaseUrl(): String;
begin
  Result := 'postgresql://' + Trim(EditPgUser.Text) + ':' + Trim(EditPgPass.Text)
            + '@127.0.0.1:' + Trim(EditPgPort.Text)
            + '/' + Trim(EditPgDbName.Text);
end;


// ---- Write the .env file ----
procedure WriteEnvFile();
var
  EnvPath: String;
  Lines: TStringList;
  DbUrl: String;
  SecretKey: String;
begin
  EnvPath := ExpandConstant('{localappdata}') + '\' + '{#MyAppName}' + '\.env';
  DbUrl := BuildDatabaseUrl();
  SecretKey := GenerateSecretKey();

  Lines := TStringList.Create;
  try
    Lines.Add('# Configuration generee par l''installateur FABOuanes');
    Lines.Add('# Date : ' + GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':'));
    Lines.Add('');
    Lines.Add('SECRET_KEY=' + SecretKey);
    Lines.Add('SESSION_COOKIE_SECURE=0');
    Lines.Add('');
    Lines.Add('# PostgreSQL');
    Lines.Add('DATABASE_URL=' + DbUrl);
    Lines.Add('');
    if GetDbChoice() = DB_POSTGRES_SERVER then
    begin
      Lines.Add('# Mode serveur : accessible depuis les autres machines du reseau');
      Lines.Add('FAB_HOST=0.0.0.0');
    end
    else
    begin
      Lines.Add('# Mode local : accessible uniquement depuis cette machine');
      Lines.Add('FAB_HOST=127.0.0.1');
    end;
    Lines.Add('FAB_PORT=5000');
    Lines.Add('');
    Lines.Add('WEB_CONCURRENCY=1');
    Lines.Add('DEFAULT_ADMIN_USERNAME=admin');
    Lines.Add('DEFAULT_ADMIN_PASSWORD=');
    Lines.Add('');

    Lines.SaveToFile(EnvPath);
  finally
    Lines.Free;
  end;

  // Also copy to the app install dir so the embedded EXE picks it up
  CopyFile(EnvPath, ExpandConstant('{app}') + '\.env', False);
end;


// ---- Check if PostgreSQL is installed ----
function IsPostgresInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  if RegKeyExists(HKLM, 'SOFTWARE\PostgreSQL\Installations') or
     RegKeyExists(HKLM32, 'SOFTWARE\PostgreSQL\Installations') or
     RegKeyExists(HKCU, 'SOFTWARE\PostgreSQL\Installations') then
  begin
    Result := True;
    Exit;
  end;
  
  Result := Exec('sc.exe', 'querytype= service state= all postgresql-x64-16', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if Result and (ResultCode = 0) then
  begin
    Result := True;
    Exit;
  end;
  
  Result := Exec('sc.exe', 'querytype= service state= all postgresql-x64-15', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if Result and (ResultCode = 0) then
  begin
    Result := True;
    Exit;
  end;

  Result := Exec('sc.exe', 'querytype= service state= all postgresql-x64-14', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if Result and (ResultCode = 0) then
  begin
    Result := True;
    Exit;
  end;
  
  Result := False;
end;


// ---- Automatically download and install PostgreSQL silently ----
function InstallPostgresAutomatically(Password: String): Boolean;
var
  ResultCode: Integer;
  PsCommand: String;
  PgPass: String;
begin
  PgPass := Trim(Password);
  if PgPass = '' then
    PgPass := '0000';

  WizardForm.StatusLabel.Caption := 'Téléchargement de PostgreSQL 16 (environ 300 Mo)...';
  WizardForm.ProgressGauge.Style := npbstMarquee;

  PsCommand := '-NoProfile -ExecutionPolicy Bypass -Command "' +
    'Write-Host ''[FABOuanes] Téléchargement de PostgreSQL 16...''; ' +
    '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ' +
    'try { ' +
    '  Invoke-WebRequest -Uri ''https://get.enterprisedb.com/postgresql/postgresql-16.2-1-windows-x64.exe'' -OutFile ''$env:TEMP\postgresql_installer.exe''; ' +
    '} catch { ' +
    '  Write-Error ''Échec du téléchargement''; ' +
    '  exit 1; ' +
    '} ' +
    'Write-Host ''[FABOuanes] Installation silencieuse de PostgreSQL...''; ' +
    'Start-Process -FilePath ''$env:TEMP\postgresql_installer.exe'' -ArgumentList ''--mode unattended --unattendedmodeui none --superpassword ' + PgPass + ' --serverport 5432'' -Wait; ' +
    'exit 0;' +
    '"';

  Result := Exec('powershell.exe', PsCommand, '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  WizardForm.ProgressGauge.Style := npbstNormal;

  if not Result or (ResultCode <> 0) then
  begin
    MsgBox('Le téléchargement ou l''installation automatique de PostgreSQL a échoué.' + #13#10 +
           'Assurez-vous d''être connecté à Internet et réessayez.', mbError, MB_OK);
    Result := False;
  end
  else
  begin
    Result := True;
  end;
end;


// ---- Run the desktop bootstrap (DB init / migration) ----
function RunDesktopBootstrap(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if not Exec(
    ExpandConstant('{app}\{#MyAppExeName}'),
    '--bootstrap-only --post-install',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) then
  begin
    MsgBox(
      'Impossible de preparer les donnees locales de FABOuanes.' + #13#10 +
      'Verifiez les droits d''ecriture dans le profil Windows' + #13#10 +
      'puis relancez l''installateur.',
      mbCriticalError,
      MB_OK
    );
    Exit;
  end;

  if ResultCode <> 0 then
  begin
    MsgBox(
      'L''initialisation de la base de donnees a echoue.' + #13#10 +
      '' + #13#10 +
      'Verifiez que PostgreSQL est demarre et que les parametres' + #13#10 +
      'de connexion sont corrects.' + #13#10 +
      '' + #13#10 +
      'Vous pouvez modifier le fichier .env dans :' + #13#10 +
      ExpandConstant('{localappdata}') + '\{#MyAppName}',
      mbCriticalError,
      MB_OK
    );
    Exit;
  end;

  Result := True;
end;


// ---- Check if Ollama is installed ----
function IsOllamaInstalled(): Boolean;
var
  OllamaPath: String;
begin
  OllamaPath := ExpandConstant('{localappdata}') + '\Programs\Ollama\ollama.exe';
  if FileExists(OllamaPath) then
  begin
    Result := True;
    Exit;
  end;
  Result := False;
end;


// ---- Automatically download and install Ollama silently ----
function InstallOllamaAutomatically(): Boolean;
var
  ResultCode: Integer;
  PsCommand: String;
begin
  WizardForm.StatusLabel.Caption := 'Téléchargement de Ollama (environ 180 Mo)...';
  WizardForm.ProgressGauge.Style := npbstMarquee;

  PsCommand := '-NoProfile -ExecutionPolicy Bypass -Command "' +
    'Write-Host ''[FABOuanes] Téléchargement de Ollama...''; ' +
    '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ' +
    'try { ' +
    '  Invoke-WebRequest -Uri ''https://ollama.com/download/OllamaSetup.exe'' -OutFile ''$env:TEMP\ollama_installer.exe''; ' +
    '} catch { ' +
    '  Write-Error ''Échec du téléchargement''; ' +
    '  exit 1; ' +
    '} ' +
    'Write-Host ''[FABOuanes] Installation silencieuse de Ollama...''; ' +
    'Start-Process -FilePath ''$env:TEMP\ollama_installer.exe'' -ArgumentList ''/silent'' -Wait; ' +
    'exit 0;' +
    '"';

  Result := Exec('powershell.exe', PsCommand, '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  WizardForm.ProgressGauge.Style := npbstNormal;

  if not Result or (ResultCode <> 0) then
  begin
    MsgBox('Le téléchargement ou l''installation automatique de Ollama a échoué.', mbError, MB_OK);
    Result := False;
  end
  else
  begin
    Result := True;
  end;
end;


// ---- Pull local AI model with visual progress ----
function PullOllamaModel(): Boolean;
var
  ResultCode: Integer;
  PsCommand: String;
begin
  MsgBox('L''installateur va maintenant lancer Ollama et télécharger le modèle d''IA locale (qwen2.5:7b).' + #13#10 +
         'Cette opération peut prendre du temps (taille du modèle : 4.7 Go).' + #13#10 +
         'Une fenêtre PowerShell va s''ouvrir pour afficher la progression.', mbInformation, MB_OK);

  PsCommand := '-NoProfile -ExecutionPolicy Bypass -Command "' +
    'Write-Host ''[FABOuanes] Lancement du service Ollama...''; ' +
    'Start-Process -FilePath ''$env:LOCALAPPDATA\Programs\Ollama\ollama.exe'' -ArgumentList ''serve'' -NoNewWindow; ' +
    'Start-Sleep -Seconds 5; ' +
    'Write-Host ''[FABOuanes] Téléchargement du modèle d''IA (qwen2.5:7b)...''; ' +
    '& ''$env:LOCALAPPDATA\Programs\Ollama\ollama.exe'' pull qwen2.5:7b; ' +
    'exit 0;' +
    '"';

  Result := Exec('powershell.exe', PsCommand, '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  if not Result or (ResultCode <> 0) then
  begin
    MsgBox('Le téléchargement du modèle a échoué. Vous pourrez le relancer plus tard manuellement en tapant "ollama pull qwen2.5:7b" dans un terminal.', mbError, MB_OK);
    Result := False;
  end
  else
  begin
    Result := True;
  end;
end;


// ---- Called at each installation step ----
procedure CurStepChanged(CurStep: TSetupStep);
var
  DbChoiceLabel: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Check and install PostgreSQL if not present
    if not IsPostgresInstalled() then
    begin
      MsgBox('PostgreSQL n''a pas été détecté sur cette machine.' + #13#10 +
             'L''installateur va maintenant le télécharger et l''installer automatiquement.', mbInformation, MB_OK);
      if not InstallPostgresAutomatically(EditPgPass.Text) then
      begin
        RaiseException('L''installation de PostgreSQL a échoué. PostgreSQL est requis pour cette application.');
      end;
    end;

    // Check and install Ollama if local or hybrid mode chosen
    if RadioAiOllama.Checked or RadioAiBoth.Checked then
    begin
      if not IsOllamaInstalled() then
      begin
        MsgBox('Ollama n''a pas été détecté sur cette machine.' + #13#10 +
               'L''installateur va maintenant le télécharger et l''installer automatiquement.', mbInformation, MB_OK);
        if not InstallOllamaAutomatically() then
        begin
          MsgBox('L''installation de Ollama a échoué. Vous pourrez l''installer plus tard depuis https://ollama.com/.', mbError, MB_OK);
        end;
      end;

      // Pull the model if Ollama installed successfully
      if IsOllamaInstalled() then
      begin
        PullOllamaModel();
      end;
    end;

    // Write the .env based on user choices
    WriteEnvFile();

    // Show what was configured
    case GetDbChoice() of
      DB_POSTGRES_LOCAL:  DbChoiceLabel := 'PostgreSQL (poste unique)';
      DB_POSTGRES_SERVER: DbChoiceLabel := 'PostgreSQL serveur reseau';
    end;

    // Bootstrap
    if not RunDesktopBootstrap() then
      RaiseException('Initialisation FABOuanes interrompue.');
  end;
end;


// ---- Create the AI choice page ----
procedure CreateAiChoicePage();
var
  TopPos: Integer;
begin
  PageAiChoice := CreateCustomPage(
    PagePgConfig.ID,
    'Choix de l''Intelligence Artificielle',
    'Choisissez le mode de fonctionnement de l''IA Sabrina.'
  );

  TopPos := 0;

  LabelAiTitle := TNewStaticText.Create(PageAiChoice);
  LabelAiTitle.Parent := PageAiChoice.Surface;
  LabelAiTitle.Caption := 'Quel assistant IA souhaitez-vous configurer ?';
  LabelAiTitle.Font.Name := 'Segoe UI';
  LabelAiTitle.Font.Style := [fsBold];
  LabelAiTitle.Font.Size := 10;
  LabelAiTitle.Left := 0;
  LabelAiTitle.Top := TopPos;
  LabelAiTitle.AutoSize := True;
  TopPos := TopPos + 28;

  // --- Card 1: Gemini ---
  PanelAiGemini := TPanel.Create(PageAiChoice);
  PanelAiGemini.Parent := PageAiChoice.Surface;
  PanelAiGemini.Left := 0;
  PanelAiGemini.Top := TopPos;
  PanelAiGemini.Width := PageAiChoice.SurfaceWidth;
  PanelAiGemini.Height := 54;
  PanelAiGemini.Color := clWhite;
  PanelAiGemini.ParentBackground := False;
  PanelAiGemini.BevelOuter := bvNone;
  PanelAiGemini.Cursor := crHand;
  PanelAiGemini.OnClick := @AiGeminiCardClick;

  RadioAiGemini := TNewRadioButton.Create(PageAiChoice);
  RadioAiGemini.Parent := PanelAiGemini;
  RadioAiGemini.Caption := 'Google Gemini — Cloud en ligne (recommande)';
  RadioAiGemini.Font.Name := 'Segoe UI';
  RadioAiGemini.Font.Style := [fsBold];
  RadioAiGemini.Font.Size := 9;
  RadioAiGemini.Left := 16;
  RadioAiGemini.Top := 10;
  RadioAiGemini.Width := PanelAiGemini.Width - 32;
  RadioAiGemini.Checked := True;
  RadioAiGemini.Cursor := crHand;

  LabelAiGeminiDesc := TNewStaticText.Create(PageAiChoice);
  LabelAiGeminiDesc.Parent := PanelAiGemini;
  LabelAiGeminiDesc.Caption := 'Necessite une connexion Internet et une cle API. Rapide et econome en ressources.';
  LabelAiGeminiDesc.Font.Name := 'Segoe UI';
  LabelAiGeminiDesc.Font.Size := 8;
  LabelAiGeminiDesc.Font.Color := clGray;
  LabelAiGeminiDesc.Left := 36;
  LabelAiGeminiDesc.Top := 28;
  LabelAiGeminiDesc.Width := PanelAiGemini.Width - 52;
  LabelAiGeminiDesc.WordWrap := True;
  LabelAiGeminiDesc.Cursor := crHand;
  LabelAiGeminiDesc.OnClick := @AiGeminiCardClick;

  TopPos := TopPos + 60;

  // --- Card 2: Ollama ---
  PanelAiOllama := TPanel.Create(PageAiChoice);
  PanelAiOllama.Parent := PageAiChoice.Surface;
  PanelAiOllama.Left := 0;
  PanelAiOllama.Top := TopPos;
  PanelAiOllama.Width := PageAiChoice.SurfaceWidth;
  PanelAiOllama.Height := 54;
  PanelAiOllama.Color := clWhite;
  PanelAiOllama.ParentBackground := False;
  PanelAiOllama.BevelOuter := bvNone;
  PanelAiOllama.Cursor := crHand;
  PanelAiOllama.OnClick := @AiOllamaCardClick;

  RadioAiOllama := TNewRadioButton.Create(PageAiChoice);
  RadioAiOllama.Parent := PanelAiOllama;
  RadioAiOllama.Caption := 'Ollama — Assistant 100% local et prive (sans Internet)';
  RadioAiOllama.Font.Name := 'Segoe UI';
  RadioAiOllama.Font.Style := [fsBold];
  RadioAiOllama.Font.Size := 9;
  RadioAiOllama.Left := 16;
  RadioAiOllama.Top := 10;
  RadioAiOllama.Width := PanelAiOllama.Width - 32;
  RadioAiOllama.Checked := False;
  RadioAiOllama.Cursor := crHand;

  LabelAiOllamaDesc := TNewStaticText.Create(PageAiChoice);
  LabelAiOllamaDesc.Parent := PanelAiOllama;
  LabelAiOllamaDesc.Caption := 'Execution locale. Telecharge le modele (qwen2.5:7b, 4.7 Go) lors de l''installation.';
  LabelAiOllamaDesc.Font.Name := 'Segoe UI';
  LabelAiOllamaDesc.Font.Size := 8;
  LabelAiOllamaDesc.Font.Color := clGray;
  LabelAiOllamaDesc.Left := 36;
  LabelAiOllamaDesc.Top := 28;
  LabelAiOllamaDesc.Width := PanelAiOllama.Width - 52;
  LabelAiOllamaDesc.WordWrap := True;
  LabelAiOllamaDesc.Cursor := crHand;
  LabelAiOllamaDesc.OnClick := @AiOllamaCardClick;

  TopPos := TopPos + 60;

  // --- Card 3: Both (Hybrid) ---
  PanelAiBoth := TPanel.Create(PageAiChoice);
  PanelAiBoth.Parent := PageAiChoice.Surface;
  PanelAiBoth.Left := 0;
  PanelAiBoth.Top := TopPos;
  PanelAiBoth.Width := PageAiChoice.SurfaceWidth;
  PanelAiBoth.Height := 54;
  PanelAiBoth.Color := clWhite;
  PanelAiBoth.ParentBackground := False;
  PanelAiBoth.BevelOuter := bvNone;
  PanelAiBoth.Cursor := crHand;
  PanelAiBoth.OnClick := @AiBothCardClick;

  RadioAiBoth := TNewRadioButton.Create(PageAiChoice);
  RadioAiBoth.Parent := PanelAiBoth;
  RadioAiBoth.Caption := 'Les deux — Mode hybride (Cloud + Local)';
  RadioAiBoth.Font.Name := 'Segoe UI';
  RadioAiBoth.Font.Style := [fsBold];
  RadioAiBoth.Font.Size := 9;
  RadioAiBoth.Left := 16;
  RadioAiBoth.Top := 10;
  RadioAiBoth.Width := PanelAiBoth.Width - 32;
  RadioAiBoth.Checked := False;
  RadioAiBoth.Cursor := crHand;

  LabelAiBothDesc := TNewStaticText.Create(PageAiChoice);
  LabelAiBothDesc.Parent := PanelAiBoth;
  LabelAiBothDesc.Caption := 'Installe Ollama localement et permet de basculer librement vers Gemini en ligne.';
  LabelAiBothDesc.Font.Name := 'Segoe UI';
  LabelAiBothDesc.Font.Size := 8;

  LabelAiBothDesc.Left := 36;
  LabelAiBothDesc.Top := 28;
  LabelAiBothDesc.Width := PanelAiBoth.Width - 52;
  LabelAiBothDesc.WordWrap := True;
  LabelAiBothDesc.Cursor := crHand;
  LabelAiBothDesc.OnClick := @AiBothCardClick;
end;


// ---- Initialize custom pages ----
procedure InitializeWizard();
begin
  // Appliquer la police système Segoe UI moderne par défaut sur tout le Wizard
  WizardForm.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel1.Font.Name := 'Segoe UI';
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.PageNameLabel.Font.Name := 'Segoe UI';
  WizardForm.PageNameLabel.Font.Style := [fsBold];
  WizardForm.PageDescriptionLabel.Font.Name := 'Segoe UI';

  CreateDbChoicePage();
  CreatePgConfigPage();
  CreateAiChoicePage();
end;
