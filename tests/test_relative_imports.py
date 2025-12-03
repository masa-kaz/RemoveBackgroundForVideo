"""相対インポートを検出するテスト

PyInstallerでビルドする際、srcディレクトリ内のファイルが
相対インポートを使用していると実行時エラーになるため、
このテストで事前にチェックする。
"""

import ast
from pathlib import Path

import pytest


def find_relative_imports(file_path: Path) -> list[tuple[int, str]]:
    """ファイル内の相対インポートを検出する

    Args:
        file_path: チェックするPythonファイルのパス

    Returns:
        (行番号, インポート文)のリスト
    """
    relative_imports = []

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content, filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            dots = "." * node.level
            import_stmt = f"from {dots}{module} import {names}"
            relative_imports.append((node.lineno, import_stmt))

    return relative_imports


def get_src_python_files() -> list[Path]:
    """srcディレクトリ内のすべてのPythonファイルを取得する"""
    # テストファイルの場所からプロジェクトルートを特定
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    src_dir = project_root / "src"

    if not src_dir.exists():
        return []

    return list(src_dir.glob("**/*.py"))


class TestRelativeImports:
    """相対インポートのテストクラス"""

    @pytest.mark.parametrize("py_file", get_src_python_files(), ids=lambda p: p.name)
    def test_no_relative_imports(self, py_file: Path):
        """srcディレクトリ内のファイルに相対インポートがないことを確認する

        PyInstallerでビルドする際、相対インポートは実行時エラーの原因となるため、
        すべてのインポートは絶対インポートである必要がある。
        """
        relative_imports = find_relative_imports(py_file)

        if relative_imports:
            error_msg = f"\n{py_file.name} に相対インポートが見つかりました:\n"
            for lineno, import_stmt in relative_imports:
                error_msg += f"  行 {lineno}: {import_stmt}\n"
            error_msg += "\nPyInstallerでビルドするには絶対インポートに変更してください。"
            error_msg += "\n例: 'from .module import func' → 'from module import func'"
            pytest.fail(error_msg)

    def test_src_directory_exists(self):
        """srcディレクトリが存在することを確認する"""
        test_dir = Path(__file__).parent
        project_root = test_dir.parent
        src_dir = project_root / "src"

        assert src_dir.exists(), f"srcディレクトリが見つかりません: {src_dir}"

    def test_has_python_files(self):
        """srcディレクトリにPythonファイルが存在することを確認する"""
        py_files = get_src_python_files()
        assert len(py_files) > 0, "srcディレクトリにPythonファイルが見つかりません"
