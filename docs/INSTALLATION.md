# インストール手順

## クイックスタート（ビルド済みバイナリ）

最も簡単な方法は、ビルド済みのバイナリをダウンロードすることです。

### ダウンロード

[GitHub Releases](https://github.com/masa-kaz/RemoveBackgroundForVideo/releases) から、お使いの環境に合ったファイルをダウンロードしてください：

| ファイル | 対象環境 | 備考 |
|---------|---------|------|
| `BackgroundRemover_Windows_GPU.zip` | Windows + NVIDIA GPU | 高速処理（推奨） |
| `BackgroundRemover_Windows_CPU.zip` | Windows（GPU不要） | 軽量版、処理は低速 |
| `BackgroundRemover_macOS.zip` | macOS (Apple Silicon) | M1/M2 Mac向け |

### インストール手順

1. ZIPファイルを解凍
2. **Windows**: `BackgroundRemover_GPU.exe` または `BackgroundRemover_CPU.exe` を実行
3. **macOS**: `BackgroundRemover_Mac.app` をダブルクリック（初回は右クリック→「開く」）

**注意**: macOSでは初回起動時に「開発元を確認できない」という警告が表示される場合があります。その場合は、右クリック→「開く」を選択してください。

### Windows版の注意事項（パス長制限）

ZIPファイルは **ドライブ直下の短いフォルダ** に解凍してください。

- ✅ 推奨: `C:\RBV` や `D:\app`
- ❌ 非推奨: `C:\Users\ユーザー名\Downloads\RemoveBackgroundForVideo_GPU_Windows`

Windowsのパス長制限（260文字）により、長いパスでは解凍に失敗する場合があります（エラーコード: `0x80010135`）。

---

## 1. 開発環境のセットアップ

### 前提条件

- Python 3.10以上
- ffmpeg（システムにインストール済み、またはプロジェクトの `ffmpeg/` フォルダに配置）
- Git

### 手順

```bash
# リポジトリをクローン
git clone <repository-url>
cd RemoveBackgroundForVideo

# 仮想環境を作成（推奨）
python -m venv venv

# 仮想環境をアクティブ化
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements-dev.txt
```

### PyTorchのインストール（環境別）

#### Windows + NVIDIA GPU
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

#### macOS (Apple Silicon)
```bash
pip install torch torchvision
```

#### CPU専用
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### モデルのダウンロード

RVMモデル（TorchScript形式）を `models/` フォルダにダウンロードしてください：

```bash
# models/ ディレクトリに移動
cd models

# モデルをダウンロード（約15MB）
curl -L -o rvm_mobilenetv3.torchscript https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.torchscript
```

または、ブラウザから直接ダウンロード：
https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.torchscript

**注意**: リポジトリにはモデルファイルが同梱されているため、クローン後すぐに使用できます。

### ffmpegのインストール

#### macOS
```bash
brew install ffmpeg
```

#### Windows
1. https://ffmpeg.org/download.html からダウンロード
2. 解凍して `ffmpeg.exe` を `ffmpeg/` フォルダに配置

または、システムPATHに追加してください。

---

## 2. Windows exe版のビルド

### 前提条件

- Windows 10/11
- Python 3.10以上
- ffmpeg.exe（`ffmpeg/` フォルダに配置）
- RVMモデル（`models/rvm_mobilenetv3.torchscript`）

### GPU版のビルド（推奨）

```batch
build_gpu.bat
```

出力先: `dist/BackgroundRemover_GPU/`

特徴:
- NVIDIA GPUがある環境では高速処理
- GPUがない環境でもCPUで動作（低速）
- サイズ: 約1.5〜2GB

### CPU版のビルド

```batch
build_cpu.bat
```

出力先: `dist/BackgroundRemover_CPU/`

特徴:
- 軽量版
- サイズ: 約300〜500MB
- 処理速度は遅い

---

## 3. macOS版のビルド

### 前提条件

- macOS 11.0以上（Apple Silicon対応）
- Python 3.10以上
- ffmpeg（`brew install ffmpeg`）
- RVMモデル（`models/rvm_mobilenetv3.torchscript`）

### ビルド手順

```bash
chmod +x build_mac.sh
./build_mac.sh
```

出力先: `dist/BackgroundRemover_Mac.app`

特徴:
- Apple Silicon (M1/M2) のMPSを使用して高速処理
- .appバンドル形式で配布可能
- サイズ: 約500MB〜1GB

---

## 4. 配布方法

### Windows exe版の配布

1. ビルド後、`dist/BackgroundRemover_GPU/` または `dist/BackgroundRemover_CPU/` フォルダをZIP圧縮
2. ZIPファイルを配布
3. 受け取った人は解凍して `BackgroundRemover.exe` を実行

### macOS版の配布

1. ビルド後、`dist/BackgroundRemover_Mac.app` をZIP圧縮
2. ZIPファイルを配布
3. 受け取った人は解凍して `.app` を実行

### 配布先の要件

**Windows:**
- Windows 10/11
- GPU版の場合: NVIDIA GPUとドライバー（推奨、なくても動作）
- Visual C++ 再頒布可能パッケージ（通常はインストール済み）

**macOS:**
- macOS 11.0以上
- Apple Silicon (M1/M2) 推奨

---

## 5. 動作確認

### テストの実行

```bash
# 全テスト実行
pytest

# 詳細出力
pytest -v

# カバレッジ付き
pytest --cov=src
```

### アプリの起動確認

```bash
python -m src.main
```

GUIが起動し、デバイス情報（CUDA/MPS/CPU）が表示されれば成功です。
