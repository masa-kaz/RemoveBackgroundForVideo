# 動画背景除去ツール

動画から人物の背景を自動的に除去し、透過動画（WebM VP9）を出力するデスクトップアプリケーションです。

## 特徴

- **AI背景除去**: RobustVideoMatting (RVM) を使用した高精度な背景除去
- **時間的一貫性**: 動画に最適化されたモデルにより、フレーム間のチラつきが少ない
- **GPU対応**: NVIDIA CUDA / Apple Silicon (MPS) で高速処理
- **シンプルなGUI**: ファイル選択と開始ボタンだけの簡単操作
- **透過出力**: WebM (VP9) 形式でアルファチャンネル付き出力
- **自動軽量化**: 保存時にVP9形式で自動圧縮（大幅なファイルサイズ削減）
- **音声保持**: 入力動画の音声を出力に自動的に含める
- **キャンセル機能**: 処理中にキャンセルボタンで中断可能

## 対応形式

### 入力
- MP4 (.mp4)
- MOV (.mov) - iPhone撮影動画を含む
- M4V (.m4v)

### 出力
- WebM (VP9 with alpha) - Canva等の各種ツールで利用可能

## クイックスタート

### 開発環境での実行

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# モデルファイルはリポジトリに同梱済み
# models/rvm_mobilenetv3.torchscript

# アプリ起動
python -m src.main
```

### Windows exe版

`dist/BackgroundRemover_GPU/` または `dist/BackgroundRemover_CPU/` フォルダ内の `BackgroundRemover.exe` を実行してください。

### macOS版

`dist/BackgroundRemover_Mac.app` をダブルクリックして実行してください。

## ドキュメント

- [インストール手順](./INSTALLATION.md)
- [使用方法](./USAGE.md)
- [アーキテクチャ](./ARCHITECTURE.md)
- [トラブルシューティング](./TROUBLESHOOTING.md)

## 動作環境

### 推奨環境
- Windows 10/11 + NVIDIA GPU (CUDA対応)
- macOS (Apple Silicon M1/M2)

### 最低環境
- Windows 10/11 または macOS
- Python 3.10以上（開発時）
- ffmpeg

## ライセンス

- 本ツール: 社内利用
- RobustVideoMatting: GPL-3.0
