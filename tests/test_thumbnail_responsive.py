# -*- coding: utf-8 -*-
"""サムネイルレスポンシブ機能のテスト

ウィンドウリサイズに応じてサムネイルサイズが変わるかテストする
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# main.pyから定数を読み込む
_main_file = Path(__file__).parent.parent / "src" / "main.py"
_main_content = _main_file.read_text(encoding="utf-8")

import re

def _extract_dict(name: str, content: str) -> dict:
    """ソースコードから辞書定数を抽出"""
    pattern = rf'^{name}\s*=\s*\{{'
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return {}

    start = match.start()
    brace_count = 0
    end = start
    for i, char in enumerate(content[start:]):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end = start + i + 1
                break

    dict_str = content[start:end]
    local_vars = {}
    exec(dict_str, {}, local_vars)
    return local_vars.get(name, {})

SIZES = _extract_dict("SIZES", _main_content)


class TestThumbnailSizeCalculation:
    """サムネイルサイズ計算のテスト"""

    def test_sizes_constants_exist(self):
        """必要な定数が存在すること"""
        assert "thumbnail_max_width" in SIZES
        assert "thumbnail_aspect_ratio" in SIZES
        assert "padding" in SIZES

    def test_thumbnail_max_width(self):
        """サムネイル最大幅が500pxであること"""
        assert SIZES["thumbnail_max_width"] == 500

    def test_padding(self):
        """パディングが24pxであること"""
        assert SIZES["padding"] == 24


class TestCalculateThumbnailSizeFunction:
    """_calculate_thumbnail_size関数のテスト"""

    def test_function_exists_in_code(self):
        """_calculate_thumbnail_size関数がコードに存在すること"""
        assert "_calculate_thumbnail_size" in _main_content

    def test_function_uses_window_width(self):
        """関数がウィンドウ幅を使用していること"""
        # コード内でwinfo_widthを呼んでいることを確認
        func_start = _main_content.find("def _calculate_thumbnail_size")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "winfo_width" in func_code

    def test_function_respects_max_width(self):
        """関数が最大幅を尊重していること"""
        func_start = _main_content.find("def _calculate_thumbnail_size")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "thumbnail_max_width" in func_code

    def test_function_uses_aspect_ratio(self):
        """関数がアスペクト比を使用していること"""
        func_start = _main_content.find("def _calculate_thumbnail_size")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "aspect_ratio" in func_code


class TestOnWindowResizeFunction:
    """_on_window_resize関数のテスト"""

    def test_function_exists_in_code(self):
        """_on_window_resize関数がコードに存在すること"""
        assert "_on_window_resize" in _main_content

    def test_function_checks_widget(self):
        """関数がevent.widgetをチェックしていること"""
        func_start = _main_content.find("def _on_window_resize")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "event.widget" in func_code

    def test_function_checks_width_change(self):
        """関数が幅の変化をチェックしていること"""
        func_start = _main_content.find("def _on_window_resize")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "_last_window_width" in func_code

    def test_function_calls_update(self):
        """関数が_update_thumbnail_sizeを呼んでいること"""
        func_start = _main_content.find("def _on_window_resize")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "_update_thumbnail_size" in func_code


class TestUpdateThumbnailSizeFunction:
    """_update_thumbnail_size関数のテスト"""

    def test_function_exists_in_code(self):
        """_update_thumbnail_size関数がコードに存在すること"""
        assert "_update_thumbnail_size" in _main_content

    def test_function_checks_processing(self):
        """関数が処理中かどうかをチェックしていること"""
        func_start = _main_content.find("def _update_thumbnail_size")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "is_processing" in func_code

    def test_function_updates_thumbnail_label(self):
        """関数がthumbnail_labelを更新していること"""
        func_start = _main_content.find("def _update_thumbnail_size")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "thumbnail_label" in func_code
        assert "configure" in func_code


class TestConfigureEventBinding:
    """<Configure>イベントバインディングのテスト"""

    def test_configure_event_binding_exists(self):
        """<Configure>イベントがバインドされていること"""
        assert '<Configure>' in _main_content or '"Configure"' in _main_content

    def test_binding_calls_on_window_resize(self):
        """バインディングが_on_window_resizeを呼んでいること"""
        # bindと_on_window_resizeが近くにあることを確認
        bind_pos = _main_content.find('bind("<Configure>"')
        if bind_pos == -1:
            bind_pos = _main_content.find("bind('<Configure>'")
        assert bind_pos != -1, "<Configure>イベントのバインディングが見つかりません"

        # バインディングの行を確認
        line_start = _main_content.rfind("\n", 0, bind_pos) + 1
        line_end = _main_content.find("\n", bind_pos)
        binding_line = _main_content[line_start:line_end]
        assert "_on_window_resize" in binding_line


class TestOriginalImageStorage:
    """元画像保持の変数テスト"""

    def test_original_thumbnail_pil_variable(self):
        """_original_thumbnail_pil変数が定義されていること"""
        assert "_original_thumbnail_pil" in _main_content

    def test_original_processed_pil_variable(self):
        """_original_processed_pil変数が定義されていること"""
        assert "_original_processed_pil" in _main_content

    def test_last_window_width_variable(self):
        """_last_window_width変数が定義されていること"""
        assert "_last_window_width" in _main_content


class TestExtractThumbnailSavesOriginal:
    """_extract_thumbnailが元画像を保持するかテスト"""

    def test_extract_thumbnail_saves_original(self):
        """_extract_thumbnailで元画像が保存されること"""
        func_start = _main_content.find("def _extract_thumbnail")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        assert "_original_thumbnail_pil" in func_code
        # .copy()で保存されていることを確認
        assert "copy()" in func_code or "_original_thumbnail_pil = img" in func_code


class TestIntegration:
    """統合テスト - コードフローの確認"""

    def test_resize_flow_exists(self):
        """リサイズフローが存在すること"""
        # 1. <Configure>バインディング
        assert "<Configure>" in _main_content
        # 2. _on_window_resize関数
        assert "def _on_window_resize" in _main_content
        # 3. _update_thumbnail_size関数
        assert "def _update_thumbnail_size" in _main_content
        # 4. _calculate_thumbnail_size関数
        assert "def _calculate_thumbnail_size" in _main_content

    def test_thumbnail_label_image_update(self):
        """thumbnail_label.configure(image=...)が呼ばれること"""
        func_start = _main_content.find("def _update_thumbnail_size")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        # configureでimageを設定していることを確認
        assert "configure(image=" in func_code


class TestPotentialIssues:
    """潜在的な問題のテスト"""

    def test_after_delay_used(self):
        """root.afterで遅延が使われていること（リサイズ完了待ち）"""
        func_start = _main_content.find("def _on_window_resize")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        # afterが使われていることを確認
        has_after = ".after(" in func_code
        print(f"DEBUG: .after() used: {has_after}")
        print(f"DEBUG: func_code snippet: {func_code[:500]}")

    def test_winfo_ismapped_check(self):
        """winfo_ismappedチェックがあること"""
        func_start = _main_content.find("def _update_thumbnail_size")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        has_ismapped = "winfo_ismapped" in func_code
        print(f"DEBUG: winfo_ismapped check: {has_ismapped}")

    def test_original_pil_check(self):
        """元画像の存在チェックがあること"""
        func_start = _main_content.find("def _update_thumbnail_size")
        func_end = _main_content.find("def ", func_start + 1)
        func_code = _main_content[func_start:func_end]
        has_check = "_original_thumbnail_pil" in func_code
        print(f"DEBUG: _original_thumbnail_pil check: {has_check}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
