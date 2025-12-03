# RemoveBackgroundForVideo - Justfile
#
# 使用方法:
#   just install    - 開発用依存関係をインストール
#   just lint       - Lintチェック（エラーのみ報告）
#   just format     - 自動フォーマット修正
#   just test       - テスト実行
#   just check      - lint + test（CI用）
#   just clean      - キャッシュファイルを削除

# デフォルト: ヘルプ表示
default:
    @just --list

# 依存関係インストール
install:
    pip install -r requirements-dev.txt

# Lintチェック（修正なし、エラー報告のみ）
lint:
    ruff check src/ tests/
    ruff format --check src/ tests/

# 自動フォーマット修正
format:
    ruff check --fix src/ tests/
    ruff format src/ tests/

# テスト実行
test:
    pytest tests/ -v

# テスト実行（カバレッジ付き）
test-cov:
    pytest tests/ -v --cov=src --cov-report=term-missing

# CIチェック（lint + test）
check: lint test

# キャッシュ削除
clean:
    rm -rf __pycache__ .pytest_cache .ruff_cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# アプリ起動
run:
    cd src && python main.py
