# アーキテクチャ

## プロジェクト構造

```
RemoveBackgroundForVideo/
├── src/                    # ソースコード
│   ├── __init__.py
│   ├── main.py             # GUIエントリーポイント
│   ├── video_processor.py  # 動画処理ロジック
│   ├── rvm_model.py        # RVMモデル管理
│   └── utils.py            # ユーティリティ関数
├── tests/                  # テストコード
│   ├── __init__.py
│   ├── test_utils.py
│   ├── test_rvm_model.py
│   ├── test_video_processor.py
│   ├── test_build_scripts.py
│   ├── test_e2e.py
│   └── fixtures/           # テスト用動画ファイル
│       ├── TestVideo.mov
│       └── TestVideo.mp4
├── models/                 # AIモデル格納
│   └── rvm_mobilenetv3.torchscript
├── ffmpeg/                 # ffmpeg実行ファイル
│   └── ffmpeg.exe
├── docs/                   # ドキュメント
├── .claude/                # Claude Code設定
│   └── workspace/
│       ├── project_index/  # プロジェクトインデックス
│       └── task.md         # タスク管理
├── requirements.txt        # 本番依存パッケージ
├── requirements-dev.txt    # 開発依存パッケージ
├── pytest.ini              # pytest設定
├── build_gpu.bat           # Windows GPU版ビルド
├── build_cpu.bat           # Windows CPU版ビルド
├── build_mac.sh            # macOS版ビルド
├── .gitignore
└── CLAUDE.md               # Claude Code指示書
```

---

## モジュール構成

### src/main.py
**役割**: GUIアプリケーションのエントリーポイント

主要クラス:
- `BackgroundRemoverApp`: メインアプリケーションクラス

機能:
- Tkinterベースのシンプルなウィンドウ
- ファイル選択ダイアログ
- 進捗バー表示
- マルチスレッド処理（UIフリーズ防止）
- キャンセルボタンで処理中断可能

### src/video_processor.py
**役割**: 動画の読み込み・処理・出力

主要クラス/関数:
- `VideoProcessor`: 動画処理のメインクラス
- `VideoInfo`: 動画情報を格納するデータクラス（音声有無を含む）
- `ProcessingCancelled`: キャンセル時の例外クラス
- `get_video_info()`: 動画のメタ情報を取得
- `find_ffmpeg()`: ffmpegの実行ファイルを検索
- `_check_audio_stream()`: 動画に音声があるか確認

処理フロー:
1. 動画を読み込み（OpenCV）
2. フレームごとにRVMで背景除去（キャンセル確認付き）
3. RGBA画像としてPNG連番出力
4. ffmpegでProRes 4444に変換（音声があれば自動的に含める）

### src/rvm_model.py
**役割**: RobustVideoMattingモデルの管理

主要クラス/関数:
- `RVMModel`: モデルのロード・推論を担当
- `download_model()`: モデルのダウンロード

特徴:
- TorchScript形式のモデルを使用
- recurrent状態を保持して時間的一貫性を実現
- ダウンサンプル比率の調整が可能

### src/utils.py
**役割**: 共通ユーティリティ関数

主要クラス/関数:
- `DeviceInfo`: デバイス情報を格納
- `get_device()`: 最適なデバイスを取得
- `get_device_info()`: デバイスの詳細情報を取得
- `is_supported_video()`: サポート形式の判定
- `get_output_path()`: 出力パスの生成
- `format_time()`: 時間フォーマット

---

## 処理フロー

```
[入力動画 (MP4/MOV)]
        │
        ▼
┌───────────────────┐
│   VideoProcessor  │
│   ┌─────────────┐ │
│   │ OpenCV読込  │ │
│   └──────┬──────┘ │
│          ▼        │
│   ┌─────────────┐ │
│   │ フレーム    │ │
│   │ 抽出        │ │
│   └──────┬──────┘ │
└──────────┼────────┘
           ▼
┌───────────────────┐
│     RVMModel      │
│   ┌─────────────┐ │
│   │ 推論        │ │
│   │ (GPU/CPU)   │ │
│   └──────┬──────┘ │
│          ▼        │
│   ┌─────────────┐ │
│   │ マスク生成  │ │
│   └──────┬──────┘ │
└──────────┼────────┘
           ▼
┌───────────────────┐
│ RGBA画像生成      │
│ (前景 + アルファ) │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│   PNG連番出力     │
│   (一時ファイル)  │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│     ffmpeg        │
│   ┌─────────────┐ │
│   │ ProRes 4444 │ │
│   │ エンコード  │ │
│   └─────────────┘ │
└─────────┬─────────┘
          ▼
[出力動画 (MOV with alpha)]
```

---

## デバイス選択ロジック

```python
# 優先順位
1. CUDA (NVIDIA GPU)  # 最高速
2. MPS (Apple Silicon) # 高速
3. CPU                 # 低速（フォールバック）
```

---

## 依存関係

### 本番環境
- `torch`: ディープラーニングフレームワーク
- `torchvision`: 画像処理ユーティリティ
- `opencv-python`: 動画読み込み
- `numpy`: 数値計算
- `Pillow`: 画像処理

### 開発環境（追加）
- `pytest`: テストフレームワーク
- `pytest-cov`: カバレッジ計測
- `pyinstaller`: exe化

### 外部ツール
- `ffmpeg`: 動画エンコード（ProRes出力に必須）

---

## テスト構成

| ファイル | テスト対象 | テスト数 |
|---------|-----------|---------|
| test_utils.py | utils.py | 37 |
| test_rvm_model.py | rvm_model.py | 18 |
| test_video_processor.py | video_processor.py | 20 |
| test_build_scripts.py | ビルドスクリプト | 22 |
| test_e2e.py | E2E統合テスト | 14 |

合計: 111テスト

テスト実行:
```bash
# 全テスト
pytest -v

# E2Eテスト除外（高速）
pytest -v --ignore=tests/test_e2e.py

# E2Eテストのみ
pytest tests/test_e2e.py -v
```
