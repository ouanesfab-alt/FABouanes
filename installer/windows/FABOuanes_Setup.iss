; ===========================================================================
;  FABOuanes - Installateur Windows avec assistant de configuration DB
;  Genere par l'assistant de production FABOuanes
; ===========================================================================

#define MyAppName      "FABOuanes"
#define MyAppVersion   "1.3.0"
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
  LabelDbTitle.Font.Style := [fsBold];
  LabelDbTitle.Font.Size := 10;
  LabelDbTitle.Left := 0;
  LabelDbTitle.Top := TopPos;
  LabelDbTitle.AutoSize := True;
  TopPos := TopPos + 32;

  // --- Option 1: PostgreSQL local (this machine only) ---
  RadioPgLocal := TNewRadioButton.Create(PageDbChoice);
  RadioPgLocal.Parent := PageDbChoice.Surface;
  RadioPgLocal.Caption := 'PostgreSQL — Utilisation sur ce poste uniquement (recommande)';
  RadioPgLocal.Font.Style := [fsBold];
  RadioPgLocal.Left := 8;
  RadioPgLocal.Top := TopPos;
  RadioPgLocal.Width := PageDbChoice.SurfaceWidth - 16;
  RadioPgLocal.Checked := True;
  TopPos := TopPos + 22;

  LabelDbDesc := TNewStaticText.Create(PageDbChoice);
  LabelDbDesc.Parent := PageDbChoice.Surface;
  LabelDbDesc.Caption :=
    '     Base fiable et performante avec PostgreSQL installe sur cette machine.' + #13#10 +
    '     Ideal pour un usage professionnel quotidien sur un seul poste.';
  LabelDbDesc.Left := 8;
  LabelDbDesc.Top := TopPos;
  LabelDbDesc.AutoSize := True;
  LabelDbDesc.Font.Color := clGray;
  TopPos := TopPos + 42;

  // --- Option 2: PostgreSQL serveur (this machine = server for others) ---
  RadioPgServer := TNewRadioButton.Create(PageDbChoice);
  RadioPgServer.Parent := PageDbChoice.Surface;
  RadioPgServer.Caption := 'PostgreSQL Serveur — Ce poste sert les autres machines du reseau';
  RadioPgServer.Font.Style := [fsBold];
  RadioPgServer.Left := 8;
  RadioPgServer.Top := TopPos;
  RadioPgServer.Width := PageDbChoice.SurfaceWidth - 16;
  RadioPgServer.Checked := False;
  TopPos := TopPos + 22;

  LabelDbDesc := TNewStaticText.Create(PageDbChoice);
  LabelDbDesc.Parent := PageDbChoice.Surface;
  LabelDbDesc.Caption :=
    '     Cette machine devient le serveur FABOuanes. Les autres postes' + #13#10 +
    '     du reseau (PC, telephone) se connectent a celle-ci.';
  LabelDbDesc.Left := 8;
  LabelDbDesc.Top := TopPos;
  LabelDbDesc.AutoSize := True;
  LabelDbDesc.Font.Color := clGray;
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
  LabelPgTitle.Font.Style := [fsBold];
  LabelPgTitle.Font.Size := 10;
  LabelPgTitle.Left := 0;
  LabelPgTitle.Top := TopPos;
  LabelPgTitle.AutoSize := True;
  TopPos := TopPos + 32;

  // Port
  LabelPgPort := TNewStaticText.Create(PagePgConfig);
  LabelPgPort.Parent := PagePgConfig.Surface;
  LabelPgPort.Caption := 'Port PostgreSQL :';
  LabelPgPort.Left := 0;
  LabelPgPort.Top := TopPos;
  TopPos := TopPos + 18;

  EditPgPort := TNewEdit.Create(PagePgConfig);
  EditPgPort.Parent := PagePgConfig.Surface;
  EditPgPort.Left := 0;
  EditPgPort.Top := TopPos;
  EditPgPort.Width := 100;
  EditPgPort.Text := '5432';
  TopPos := TopPos + 30;

  // User
  LabelPgUser := TNewStaticText.Create(PagePgConfig);
  LabelPgUser.Parent := PagePgConfig.Surface;
  LabelPgUser.Caption := 'Nom d''utilisateur PostgreSQL :';
  LabelPgUser.Left := 0;
  LabelPgUser.Top := TopPos;
  TopPos := TopPos + 18;

  EditPgUser := TNewEdit.Create(PagePgConfig);
  EditPgUser.Parent := PagePgConfig.Surface;
  EditPgUser.Left := 0;
  EditPgUser.Top := TopPos;
  EditPgUser.Width := 300;
  EditPgUser.Text := 'postgres';
  TopPos := TopPos + 30;

  // Password
  LabelPgPass := TNewStaticText.Create(PagePgConfig);
  LabelPgPass.Parent := PagePgConfig.Surface;
  LabelPgPass.Caption := 'Mot de passe PostgreSQL :';
  LabelPgPass.Left := 0;
  LabelPgPass.Top := TopPos;
  TopPos := TopPos + 18;

  EditPgPass := TPasswordEdit.Create(PagePgConfig);
  EditPgPass.Parent := PagePgConfig.Surface;
  EditPgPass.Left := 0;
  EditPgPass.Top := TopPos;
  EditPgPass.Width := 300;
  EditPgPass.Text := '';
  TopPos := TopPos + 30;

  // Database name
  LabelPgDbName := TNewStaticText.Create(PagePgConfig);
  LabelPgDbName.Parent := PagePgConfig.Surface;
  LabelPgDbName.Caption := 'Nom de la base de donnees :';
  LabelPgDbName.Left := 0;
  LabelPgDbName.Top := TopPos;
  TopPos := TopPos + 18;

  EditPgDbName := TNewEdit.Create(PagePgConfig);
  EditPgDbName.Parent := PagePgConfig.Surface;
  EditPgDbName.Left := 0;
  EditPgDbName.Top := TopPos;
  EditPgDbName.Width := 300;
  EditPgDbName.Text := 'fabouanes';
  TopPos := TopPos + 36;

  // Info text
  LabelPgInfo := TNewStaticText.Create(PagePgConfig);
  LabelPgInfo.Parent := PagePgConfig.Surface;
  LabelPgInfo.Caption :=
    'PostgreSQL doit etre installe sur cette machine.' + #13#10 +
    'Utilisez le mot de passe choisi lors de l''installation de PostgreSQL.' + #13#10 +
    '' + #13#10 +
    'Si vous n''avez pas encore installe PostgreSQL, annulez l''installation' + #13#10 +
    'et installez-le depuis : https://www.postgresql.org/download/windows/';
  LabelPgInfo.Left := 0;
  LabelPgInfo.Top := TopPos;
  LabelPgInfo.AutoSize := True;
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


// ---- Initialize custom pages ----
procedure InitializeWizard();
begin
  CreateDbChoicePage();
  CreatePgConfigPage();
end;
