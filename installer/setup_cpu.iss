; 動画背景除去ツール - CPU版 Inno Setup スクリプト
;
; NVIDIA GPU検出機能付き
; - GPU検出時: 警告を表示してインストール可能
; - GPU未検出時: そのままインストール

#define MyAppName "動画背景除去ツール"
#define MyAppNameEn "BackgroundRemover"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "META AI LABO"
#define MyAppExeName "BackgroundRemover_CPU.exe"
#define MyAppEdition "CPU"

[Setup]
; アプリケーション情報（GPU版と同じAppIdで上書き可能にする）
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} ({#MyAppEdition}版)
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
; 出力設定
OutputDir=..\dist
OutputBaseFilename=BackgroundRemover_CPU_Setup
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
; 上書きインストール（更新）を許可
UsePreviousAppDir=yes
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
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "スタートメニューにショートカットを作成"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; PyInstallerで生成されたファイルをすべてコピー
Source: "..\dist\BackgroundRemover_CPU\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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
var
  GPUDetected: Boolean;
  GPUName: String;
  ExistingVersion: String;

// NVIDIA GPUを検出する関数
function DetectNvidiaGPU(): Boolean;
var
  ResultCode: Integer;
  TempFile: String;
  Lines: TArrayOfString;
  i: Integer;
begin
  Result := False;
  GPUName := '';
  TempFile := ExpandConstant('{tmp}\gpu_check.txt');

  // nvidia-smiコマンドでGPU情報を取得
  if Exec('cmd.exe', '/c nvidia-smi --query-gpu=name --format=csv,noheader > "' + TempFile + '" 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      if LoadStringsFromFile(TempFile, Lines) then
      begin
        for i := 0 to GetArrayLength(Lines) - 1 do
        begin
          if Length(Lines[i]) > 0 then
          begin
            GPUName := Lines[i];
            Result := True;
            Break;
          end;
        end;
      end;
    end;
  end;

  // 一時ファイルを削除
  DeleteFile(TempFile);
end;

// 既存のインストールバージョンを取得
function GetExistingVersion(): String;
var
  UninstallKey: String;
  Version: String;
begin
  Result := '';
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';
  if RegQueryStringValue(HKLM, UninstallKey, 'DisplayVersion', Version) then
    Result := Version
  else if RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', Version) then
    Result := Version;
end;

// インストール前のチェック
function InitializeSetup(): Boolean;
var
  Msg: String;
begin
  Result := False;

  // GPU検出
  GPUDetected := DetectNvidiaGPU();

  // 既存バージョン取得
  ExistingVersion := GetExistingVersion();

  if GPUDetected then
  begin
    // GPU検出時 - 警告を表示
    if ExistingVersion <> '' then
    begin
      // 既存インストールあり
      Msg := '動画背景除去ツール セットアップ (CPU版)' + #13#10 + #13#10 +
             '⚠️ NVIDIA GPU が検出されました' + #13#10 +
             '     ' + GPUName + #13#10 + #13#10 +
             'このPCはGPU版に対応しています。' + #13#10 +
             'より高速なGPU版のご利用をおすすめします。' + #13#10 + #13#10 +
             '既にインストールされています' + #13#10 +
             '     現在のバージョン: ' + ExistingVersion + #13#10 +
             '     新しいバージョン: {#MyAppVersion}' + #13#10 + #13#10 +
             'CPU版をインストールしますか？';
    end
    else
    begin
      // 新規インストール
      Msg := '動画背景除去ツール セットアップ (CPU版)' + #13#10 + #13#10 +
             '⚠️ NVIDIA GPU が検出されました' + #13#10 +
             '     ' + GPUName + #13#10 + #13#10 +
             'このPCはGPU版に対応しています。' + #13#10 +
             'より高速なGPU版のご利用をおすすめします。' + #13#10 + #13#10 +
             'CPU版をインストールしますか？';
    end;

    Result := MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES;
  end
  else
  begin
    // GPU未検出時 - 通常インストール
    if ExistingVersion <> '' then
    begin
      // 既存インストールあり
      if ExistingVersion = '{#MyAppVersion}' then
        Msg := '動画背景除去ツール セットアップ (CPU版)' + #13#10 + #13#10 +
               '✅ CPU版をインストールします' + #13#10 + #13#10 +
               '既に同じバージョン (' + ExistingVersion + ') がインストールされています。' + #13#10 + #13#10 +
               '再インストールしますか？'
      else
        Msg := '動画背景除去ツール セットアップ (CPU版)' + #13#10 + #13#10 +
               '✅ CPU版をインストールします' + #13#10 + #13#10 +
               '⚠️ 既にインストールされています' + #13#10 +
               '     現在のバージョン: ' + ExistingVersion + #13#10 +
               '     新しいバージョン: {#MyAppVersion}' + #13#10 + #13#10 +
               '上書きインストール（更新）しますか？';

      Result := MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES;
    end
    else
    begin
      // 新規インストール
      Msg := '動画背景除去ツール セットアップ (CPU版)' + #13#10 + #13#10 +
             '✅ CPU版をインストールします' + #13#10 + #13#10 +
             '※ 処理速度はGPU版より遅くなります' + #13#10 + #13#10 +
             'インストールを開始しますか？';

      Result := MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES;
    end;
  end;
end;

// アンインストール前の確認
function InitializeUninstall(): Boolean;
begin
  Result := MsgBox('動画背景除去ツールをアンインストールしますか？', mbConfirmation, MB_YESNO) = IDYES;
end;
