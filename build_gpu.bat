@echo off
REM 動画背景除去ツール - Windows exe ビルドスクリプト (GPU版)
REM
REM 特徴:
REM   - NVIDIA GPU (CUDA) を優先使用
REM   - GPUがない環境ではCPUにフォールバック
REM   - サイズ: 約1.5〜2GB
REM
REM 前提条件:
REM   - Python 3.10以上がインストールされていること
REM   - ffmpeg.exeがffmpegフォルダに配置されていること
REM   - RVMモデル(rvm_mobilenetv3.torchscript)がmodelsフォルダに配置されていること
REM
REM 使用方法:
REM   build_gpu.bat

echo ========================================
echo 動画背景除去ツール - ビルドスクリプト (GPU版)
echo ========================================
echo.

REM 仮想環境の作成（存在しない場合）
if not exist "venv_gpu" (
    echo 仮想環境を作成中...
    python -m venv venv_gpu
)

REM 仮想環境をアクティブ化
call venv_gpu\Scripts\activate.bat

REM 依存パッケージのインストール
echo 依存パッケージをインストール中...
pip install --upgrade pip

REM PyTorch (CUDA 11.8版) をインストール
echo PyTorch (CUDA版) をインストール中...
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

REM その他の依存パッケージ
pip install -r requirements.txt
pip install pyinstaller

REM モデルファイルの確認
if not exist "models\rvm_mobilenetv3.torchscript" (
    echo.
    echo [警告] モデルファイルが見つかりません。
    echo 以下のURLからダウンロードして models フォルダに配置してください:
    echo https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.torchscript
    echo.
    pause
    exit /b 1
)

REM ffmpegの確認
if not exist "ffmpeg\ffmpeg.exe" (
    echo.
    echo [警告] ffmpeg.exeが見つかりません。
    echo ffmpeg.exeをダウンロードして ffmpeg フォルダに配置してください。
    echo https://ffmpeg.org/download.html
    echo.
    pause
    exit /b 1
)

REM 既存のビルドをクリーンアップ
if exist "dist\BackgroundRemover_GPU" rmdir /s /q "dist\BackgroundRemover_GPU"
if exist "build" rmdir /s /q "build"

REM PyInstallerでビルド
echo.
echo アプリケーションをビルド中...
pyinstaller ^
    --name "BackgroundRemover_GPU" ^
    --onedir ^
    --windowed ^
    --add-data "models;models" ^
    --add-data "ffmpeg;ffmpeg" ^
    --hidden-import "torch" ^
    --hidden-import "torchvision" ^
    --hidden-import "cv2" ^
    --hidden-import "PIL" ^
    --hidden-import "numpy" ^
    --collect-all "torch" ^
    --collect-all "torchvision" ^
    src\main.py

echo.
echo ========================================
echo ビルド完了! (GPU版)
echo 出力先: dist\BackgroundRemover_GPU\
echo.
echo このフォルダをZIP等で配布してください。
echo GPUがない環境でもCPUで動作します（低速）。
echo ========================================
echo.

pause
