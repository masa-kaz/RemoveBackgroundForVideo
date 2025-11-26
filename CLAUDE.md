# RemoveBackgroundForVideo

## プロジェクト概要
動画から人物の背景を自動的に除去し、透過動画（MOV ProRes 4444）を出力するデスクトップアプリケーション。

### 技術スタック
- **言語**: Python 3.10+
- **GUI**: Tkinter
- **AI**: RobustVideoMatting (RVM)
- **動画処理**: OpenCV, ffmpeg
- **ディープラーニング**: PyTorch

### 主要機能
- MP4/MOV動画の背景除去
- NVIDIA CUDA / Apple Silicon (MPS) / CPU対応
- 透過MOV出力
- 音声保持（入力動画の音声を出力に自動的に含める）
- キャンセル機能（処理中に中断可能）

---

# プロジェクト開発ルール

## 🔥 作業開始時の必須手順
### プロジェクトコンテキストの把握
**すべての作業開始前に以下を必ず実行すること:**

1. **プロジェクトインデックス確認**
   - `.claude/workspace/project_index/` 以下のすべての `.json` ファイル

2. **現在のタスク確認**
   - `.claude/workspace/task.md` - 進行中のタスクと進捗

3. **関連ファイルの特定**
   - タスクに関連するファイルをインデックスから特定
   - 必要最小限のファイルのみ実際に読み込み

### 作業実行のルール
- インデックス確認なしでの作業開始は禁止
- 詳細な分析が必要な場合のみ実際のファイルを読み込む
- インデックスで概要把握 → 必要に応じて詳細確認の順序を守る

---

## コーディング規約

### 全般
- 文字コード: UTF-8
- インデント: スペース4つ
- 行の長さ: 100文字以内（推奨）

### Python
- 型ヒントを使用する
- docstringはGoogle形式
- クラス・関数には必ずdocstringを記述

```python
def function_name(param1: str, param2: int) -> bool:
    """関数の説明

    Args:
        param1: パラメータ1の説明
        param2: パラメータ2の説明

    Returns:
        戻り値の説明

    Raises:
        ValueError: エラーの条件
    """
```

### ファイル構成
- ソースコード: `src/`
- テストコード: `tests/`
- ドキュメント: `docs/`

### テスト
- pytest使用
- テストファイル名: `test_<対象モジュール>.py`
- テストクラス名: `Test<対象クラス>`
- テスト関数名: `test_<テスト内容>`

---

## トークン効率化
- プロジェクトインデックスを最大限活用
- 不必要なファイル読み込みを避ける
- 作業範囲を明確にしてから実装開始

---

## ドキュメント
詳細なドキュメントは `docs/` フォルダを参照:
- [README](docs/README.md) - プロジェクト概要
- [インストール](docs/INSTALLATION.md) - セットアップ手順
- [使用方法](docs/USAGE.md) - 操作説明
- [アーキテクチャ](docs/ARCHITECTURE.md) - 技術詳細
- [トラブルシューティング](docs/TROUBLESHOOTING.md) - 問題解決
