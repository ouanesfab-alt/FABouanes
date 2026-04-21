[Setup]
AppId={{9C83D15A-8D36-4B64-96C4-FAB0UANES001}}
AppName=FABOuanes
AppVersion=1.2.2
AppPublisher=FABOuanes
AppPublisherURL=https://fabouanes.local
DefaultDirName={localappdata}\Programs\FABOuanes
DefaultGroupName=FABOuanes
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
UninstallDisplayIcon={app}\FABOuanes.exe

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Creer une icone sur le bureau"; GroupDescription: "Raccourcis supplementaires :"; Flags: unchecked

[Dirs]
Name: "{localappdata}\FABOuanes"
Name: "{localappdata}\FABOuanes\backups"
Name: "{localappdata}\FABOuanes\backups\local"
Name: "{localappdata}\FABOuanes\imports"
Name: "{localappdata}\FABOuanes\logs"
Name: "{localappdata}\FABOuanes\notes"
Name: "{localappdata}\FABOuanes\pdf_reader"
Name: "{localappdata}\FABOuanes\reports_generated"
Name: "{localappdata}\FABOuanes\webview"

[Files]
Source: "..\..\dist\FABOuanes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FABOuanes"; Filename: "{app}\FABOuanes.exe"
Name: "{autodesktop}\FABOuanes"; Filename: "{app}\FABOuanes.exe"; Tasks: desktopicon
Name: "{group}\Desinstaller FABOuanes"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\FABOuanes.exe"; Description: "Lancer FABOuanes desktop"; Flags: nowait postinstall skipifsilent

[Code]
function RunDesktopBootstrap(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if not Exec(
    ExpandConstant('{app}\FABOuanes.exe'),
    '--bootstrap-only --post-install',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) then
  begin
    MsgBox(
      'Impossible de preparer les donnees locales de FABOuanes. Verifie les droits d''ecriture dans le profil Windows puis relance l''installateur.',
      mbCriticalError,
      MB_OK
    );
    Exit;
  end;

  if ResultCode <> 0 then
  begin
    MsgBox(
      'L''initialisation locale de FABOuanes a echoue. La base n''a pas pu etre preparee automatiquement.',
      mbCriticalError,
      MB_OK
    );
    Exit;
  end;

  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not RunDesktopBootstrap() then
      RaiseException('Initialisation FABOuanes interrompue.');
  end;
end;
