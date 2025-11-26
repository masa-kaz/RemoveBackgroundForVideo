#!/bin/bash
# 動画背景除去ツール - macOS (Apple Silicon) ビルドスクリプト
#
# 特徴:
#   - Apple Silicon (M1/M2) のMPSを使用して高速処理
#   - .app バンドル形式で出力
#   - サイズ: 約500MB〜1GB
#
# 前提条件:
#   - Python 3.10以上がインストールされていること
#   - ffmpegがインストールされていること (brew install ffmpeg)
#   - RVMモデル(rvm_mobilenetv3.torchscript)がmodelsフォルダに配置されていること
#
# 使用方法:
#   chmod +x build_mac.sh
#   ./build_mac.sh

set -e

echo "========================================"
echo "動画背景除去ツール - ビルドスクリプト (macOS)"
echo "========================================"
echo

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# 仮想環境の作成（存在しない場合）
if [ ! -d "venv_mac" ]; then
    echo "仮想環境を作成中..."
    python3 -m venv venv_mac
fi

# 仮想環境をアクティブ化
source venv_mac/bin/activate

# 依存パッケージのインストール
echo "依存パッケージをインストール中..."
pip install --upgrade pip

# PyTorch (Apple Silicon版) をインストール
echo "PyTorch (Apple Silicon版) をインストール中..."
pip install torch torchvision

# その他の依存パッケージ
pip install -r requirements.txt
pip install pyinstaller

# モデルファイルの確認
if [ ! -f "models/rvm_mobilenetv3.torchscript" ]; then
    echo
    echo "[警告] モデルファイルが見つかりません。"
    echo "以下のURLからダウンロードして models フォルダに配置してください:"
    echo "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.torchscript"
    echo
    exit 1
fi

# ffmpegの確認
if ! command -v ffmpeg &> /dev/null; then
    echo
    echo "[警告] ffmpegが見つかりません。"
    echo "以下のコマンドでインストールしてください:"
    echo "  brew install ffmpeg"
    echo
    exit 1
fi

# ffmpegのパスを取得
FFMPEG_PATH=$(which ffmpeg)
FFMPEG_DIR=$(dirname "$FFMPEG_PATH")

# 既存のビルドをクリーンアップ
rm -rf dist/BackgroundRemover_Mac.app
rm -rf dist/BackgroundRemover_Mac
rm -rf build

# PyInstallerでビルド
echo
echo "アプリケーションをビルド中..."
pyinstaller \
    --name "BackgroundRemover_Mac" \
    --onedir \
    --windowed \
    --add-data "models:models" \
    --add-binary "${FFMPEG_PATH}:ffmpeg" \
    --hidden-import "torch" \
    --hidden-import "torchvision" \
    --hidden-import "cv2" \
    --hidden-import "PIL" \
    --hidden-import "numpy" \
    --collect-all "torch" \
    --collect-all "torchvision" \
    --osx-bundle-identifier "com.internal.backgroundremover" \
    src/main.py

# .app バンドルに変換
echo
echo ".app バンドルを作成中..."
if [ -d "dist/BackgroundRemover_Mac" ]; then
    # PyInstallerが生成したフォルダを.appバンドル形式に整形
    mkdir -p "dist/BackgroundRemover_Mac.app/Contents/MacOS"
    mkdir -p "dist/BackgroundRemover_Mac.app/Contents/Resources"

    # 実行ファイルとリソースをコピー
    cp -R dist/BackgroundRemover_Mac/* "dist/BackgroundRemover_Mac.app/Contents/MacOS/"

    # Info.plistを作成
    cat > "dist/BackgroundRemover_Mac.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>BackgroundRemover</string>
    <key>CFBundleDisplayName</key>
    <string>動画背景除去ツール</string>
    <key>CFBundleIdentifier</key>
    <string>com.internal.backgroundremover</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>BackgroundRemover_Mac</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
    </array>
</dict>
</plist>
EOF

    # 元のフォルダを削除
    rm -rf "dist/BackgroundRemover_Mac"
fi

echo
echo "========================================"
echo "ビルド完了! (macOS版)"
echo "出力先: dist/BackgroundRemover_Mac.app"
echo
echo "使用方法:"
echo "  1. dist/BackgroundRemover_Mac.app をダブルクリック"
echo "  2. または: open dist/BackgroundRemover_Mac.app"
echo
echo "配布方法:"
echo "  dist/BackgroundRemover_Mac.app をZIP圧縮して配布"
echo "========================================"
echo

# 仮想環境を非アクティブ化
deactivate
