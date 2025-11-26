#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""相対インポートを検出するLinterスクリプト

PyInstallerでビルドする際、srcディレクトリ内のファイルが
相対インポートを使用していると実行時エラーになるため、
このスクリプトで事前にチェックする。

使用方法:
    python scripts/check_relative_imports.py

終了コード:
    0: 相対インポートなし（OK）
    1: 相対インポートあり（エラー）
"""

import ast
import sys
from pathlib import Path


def find_relative_imports(file_path: Path) -> list[tuple[int, str]]:
    """ファイル内の相対インポートを検出する

    Args:
        file_path: チェックするPythonファイルのパス

    Returns:
        (行番号, インポート文)のリスト
    """
    relative_imports = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))

        for node in ast.walk(tree):
            # from .module import something 形式
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:  # level > 0 は相対インポート
                    module = node.module or ""
                    names = ", ".join(alias.name for alias in node.names)
                    dots = "." * node.level
                    import_stmt = f"from {dots}{module} import {names}"
                    relative_imports.append((node.lineno, import_stmt))

    except SyntaxError as e:
        print(f"  構文エラー: {e}", file=sys.stderr)
    except Exception as e:
        print(f"  エラー: {e}", file=sys.stderr)

    return relative_imports


def check_directory(src_dir: Path) -> dict[Path, list[tuple[int, str]]]:
    """ディレクトリ内のすべてのPythonファイルをチェックする

    Args:
        src_dir: チェックするディレクトリ

    Returns:
        {ファイルパス: [(行番号, インポート文), ...]} の辞書
    """
    results = {}

    for py_file in src_dir.glob("**/*.py"):
        relative_imports = find_relative_imports(py_file)
        if relative_imports:
            results[py_file] = relative_imports

    return results


def main() -> int:
    """メイン関数

    Returns:
        終了コード（0: OK, 1: エラー）
    """
    # プロジェクトルートを特定
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / "src"

    if not src_dir.exists():
        print(f"エラー: srcディレクトリが見つかりません: {src_dir}", file=sys.stderr)
        return 1

    print(f"相対インポートをチェック中: {src_dir}")
    print("=" * 60)

    results = check_directory(src_dir)

    if not results:
        print("✓ 相対インポートは見つかりませんでした")
        return 0

    print("✗ 相対インポートが見つかりました:")
    print()

    for file_path, imports in results.items():
        relative_path = file_path.relative_to(project_root)
        print(f"  {relative_path}:")
        for lineno, import_stmt in imports:
            print(f"    行 {lineno}: {import_stmt}")
        print()

    print("=" * 60)
    print("PyInstallerでビルドするには、これらを絶対インポートに変更してください。")
    print("例: 'from .module import func' → 'from module import func'")

    return 1


if __name__ == "__main__":
    sys.exit(main())
