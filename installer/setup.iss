; 動画背景除去ツール - Inno Setup スクリプト
;
; このスクリプトはPyInstallerでビルドされたアプリケーションを
; Windowsインストーラーとしてパッケージ化します。

#define MyAppName "動画背景除去ツール"
#define MyAppNameEn "BackgroundRemover"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "META AI LABO"
#define MyAppExeName "BackgroundRemover_GPU.exe"

[Setup]
; アプリケーション情報
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
; 出力設定
OutputDir=..\dist
OutputBaseFilename=BackgroundRemover_Setup
; インストーラーの圧縮設定
Compression=lzma2/ultra64
SolidCompression=yes
; 管理者権限が必要（Program Filesへのインストールのため）
PrivilegesRequired=admin
; Windows 10以降
MinVersion=10.0
; 64bit専用
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; その他
DisableProgramGroupPage=yes
LicenseFile=
InfoBeforeFile=
InfoAfterFile=
SetupIconFile=
WizardStyle=modern
; 日本語対応
ShowLanguageDialog=no

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked
Name: "startmenuicon"; Description: "スタートメニューにショートカットを作成"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked

[Files]
; PyInstallerで生成されたファイルをすべてコピー
Source: "..\dist\BackgroundRemover_GPU\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; デスクトップショートカット
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; スタートメニューショートカット
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon
; スタートメニューにアンインストーラー
Name: "{autoprograms}\{#MyAppName} をアンインストール"; Filename: "{uninstallexe}"

[Run]
; インストール完了後にアプリを起動するオプション
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; アンインストール時に削除する追加ファイル（ログファイル等）
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
// インストール前のチェック
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

// アンインストール前の確認
function InitializeUninstall(): Boolean;
begin
  Result := MsgBox('動画背景除去ツールをアンインストールしますか？', mbConfirmation, MB_YESNO) = IDYES;
end;
