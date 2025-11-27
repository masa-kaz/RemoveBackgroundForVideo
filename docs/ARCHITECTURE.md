# アーキテクチャ

## プロジェクト構造

```
RemoveBackgroundForVideo/
├── src/                    # ソースコード
│   ├── __init__.py
│   ├── main.py             # GUIエントリーポイント（CustomTkinter）
│   ├── video_processor.py  # 動画処理ロジック
│   ├── video_compressor.py # WebM変換・圧縮モジュール
│   ├── rvm_model.py        # RVMモデル管理
│   └── utils.py            # ユーティリティ関数
├── tests/                  # テストコード
│   ├── __init__.py
│   ├── test_utils.py
│   ├── test_rvm_model.py
│   ├── test_video_processor.py
│   ├── test_video_compressor.py
│   ├── test_build_scripts.py
│   ├── test_e2e.py
│   └── fixtures/           # テスト用動画ファイル
│       ├── TestVideo.mov
│       └── TestVideo.mp4
├── scripts/                # ユーティリティスクリプト
│   ├── create_manual.py    # 操作マニュアル生成
│   ├── capture_screenshots.py  # スクリーンショット撮影
│   └── compress_video.py   # 動画圧縮CLIツール
├── models/                 # AIモデル格納
│   └── rvm_mobilenetv3.torchscript
├── ffmpeg/                 # ffmpeg実行ファイル
│   └── ffmpeg.exe
├── docs/                   # ドキュメント
│   ├── *.md                # 各種マークダウン
│   ├── 操作マニュアル_動画背景除去ツール.docx  # Word形式マニュアル
│   └── manual_images/      # マニュアル用スクリーンショット
├── assets/                 # アプリアセット
│   └── icon.png            # アプリロゴ
├── .claude/                # Claude Code設定
│   └── workspace/
│       ├── project_index/  # プロジェクトインデックス
│       └── task.md         # UI仕様書
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

状態管理:
- `STATE_IDLE`: 待機中
- `STATE_PROCESSING`: 背景除去処理中
- `STATE_CONVERTING`: WebM変換中
- `STATE_COMPLETE`: 完了

機能:
- CustomTkinterベースのモダンなウィンドウ
- ファイル選択ダイアログ
- 進捗バー表示
- マルチスレッド処理（UIフリーズ防止）
- キャンセルボタンで処理中断可能
- 自動WebM変換（背景除去後）

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
5. video_compressorでWebM (VP9)に変換

### src/video_compressor.py
**役割**: WebM形式への変換と圧縮

主要クラス/関数:
- `CompressionResult`: 圧縮結果を格納するデータクラス
- `compress_video()`: 動画をWebM (VP9)形式に変換
- `compress_if_needed()`: サイズ制限を超える場合のみ圧縮
- `verify_video_integrity()`: 動画ファイルの整合性チェック
- `calculate_target_bitrate()`: 目標ビットレート計算

特徴:
- VP9コーデックで透過（アルファチャンネル）を保持
- 高速エンコード設定（realtime、cpu-used=8）
- 自動バックアップと復元機能
- Canva対応のWebM出力

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
┌───────────────────┐
│ video_compressor  │
│   ┌─────────────┐ │
│   │ VP9 WebM    │ │
│   │ 変換        │ │
│   └─────────────┘ │
└─────────┬─────────┘
          ▼
[出力動画 (WebM with alpha)]
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
| test_video_compressor.py | video_compressor.py | 20 |
| test_build_scripts.py | ビルドスクリプト | 22 |
| test_e2e.py | E2E統合テスト | 14 |
| test_gui.py | GUI（UI仕様準拠） | 34 |

合計: 165テスト

テスト実行:
```bash
# 全テスト
pytest -v

# E2Eテスト除外（高速）
pytest -v --ignore=tests/test_e2e.py

# E2Eテストのみ
pytest tests/test_e2e.py -v
```
