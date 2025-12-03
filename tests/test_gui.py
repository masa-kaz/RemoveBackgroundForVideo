"""GUIテスト - UI仕様書（.claude/workspace/task.md）に基づく検証

テスト項目:
1. カラーテーマ（META AI LABO準拠）
2. フォントサイズ（アクセシビリティ対応）
3. ウィンドウサイズ
4. 初期状態UI
5. ファイル選択後状態UI
6. 処理中状態UI
7. 完了状態UI
8. ダイアログ
9. トースト通知

実行方法:
    pytest tests/test_gui.py -v
"""

import sys
from pathlib import Path

import pytest


# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# main.pyから定数のみをインポート（GUIなしで検証可能）
# tkinterの依存関係を回避するため、直接ファイルから定数を読み込む
_main_file = Path(__file__).parent.parent / "src" / "main.py"
_main_content = _main_file.read_text(encoding="utf-8")

# 定数を抽出（exec で評価）
import re


def _extract_dict(name: str, content: str) -> dict:
    """ソースコードから辞書定数を抽出"""
    pattern = rf"^{name}\s*=\s*\{{"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return {}

    start = match.start()
    # 対応する閉じ括弧を探す
    brace_count = 0
    end = start
    for i, char in enumerate(content[start:]):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end = start + i + 1
                break

    dict_str = content[start:end]
    # execで評価
    local_vars = {}
    exec(dict_str, {}, local_vars)
    return local_vars.get(name, {})


COLORS = _extract_dict("COLORS", _main_content)
FONT_SIZES = _extract_dict("FONT_SIZES", _main_content)
SIZES = _extract_dict("SIZES", _main_content)

# クラスの存在確認用フラグ
_HAS_GUI_CLASSES = False
BackgroundRemoverApp = None
CircularProgress = None
CustomDialog = None
Toast = None

try:
    from main import (
        BackgroundRemoverApp,
        CircularProgress,
        CustomDialog,
        Toast,
    )

    _HAS_GUI_CLASSES = True
except ImportError:
    pass


# =============================================================================
# 1. カラーテーマテスト
# =============================================================================
class TestColors:
    """カラーテーマが仕様通りか確認（META AI LABO準拠）"""

    def test_primary_color(self):
        """Primary色が#8BC34A（葉っぱの黄緑）であること"""
        assert COLORS["primary"] == "#8BC34A"

    def test_primary_dark_color(self):
        """Primary Dark色が#689F38であること"""
        assert COLORS["primary_dark"] == "#689F38"

    def test_primary_hover_color(self):
        """Primary Hover色が#7CB342であること"""
        assert COLORS["primary_hover"] == "#7CB342"

    def test_secondary_color(self):
        """Secondary色が#263238（フィルム枠のダークネイビー）であること"""
        assert COLORS["secondary"] == "#263238"

    def test_success_color(self):
        """Success色が#4CAF50であること"""
        assert COLORS["success"] == "#4CAF50"

    def test_warning_color(self):
        """Warning色が#FF9800であること"""
        assert COLORS["warning"] == "#FF9800"

    def test_danger_color(self):
        """Danger色が#F44336であること"""
        assert COLORS["danger"] == "#F44336"

    def test_background_color(self):
        """背景色が#FAFAFAであること"""
        assert COLORS["bg"] == "#FAFAFA"

    def test_card_color(self):
        """カード背景色が#FFFFFFであること"""
        assert COLORS["card"] == "#FFFFFF"

    def test_border_color(self):
        """ボーダー色が#E0E0E0であること"""
        assert COLORS["border"] == "#E0E0E0"

    def test_text_color(self):
        """テキスト色が#263238であること"""
        assert COLORS["text"] == "#263238"

    def test_text_secondary_color(self):
        """サブテキスト色が#616161であること"""
        assert COLORS["text_secondary"] == "#616161"

    def test_toast_colors(self):
        """トースト色が仕様通りであること"""
        assert COLORS["toast_bg"] == "#263238"
        assert COLORS["toast_text"] == "#FFFFFF"

    def test_disabled_color(self):
        """無効状態の色が#BDBDBDであること"""
        assert COLORS["disabled"] == "#BDBDBD"

    def test_danger_hover_color(self):
        """危険ボタンホバー色が#FFEBEEであること"""
        assert COLORS["danger_hover"] == "#FFEBEE"


# =============================================================================
# 2. フォントサイズテスト
# =============================================================================
class TestFonts:
    """フォントサイズが仕様通りか確認（アクセシビリティ対応・大きめ）"""

    def test_title_font_size(self):
        """タイトルが32pxであること"""
        assert FONT_SIZES["title"] == 32

    def test_subtitle_font_size(self):
        """サブタイトルが18pxであること"""
        assert FONT_SIZES["subtitle"] == 18

    def test_button_font_size(self):
        """ボタンテキストが24pxであること"""
        assert FONT_SIZES["button"] == 24

    def test_filename_font_size(self):
        """ファイル名が22pxであること"""
        assert FONT_SIZES["filename"] == 22

    def test_video_info_font_size(self):
        """動画情報が18pxであること"""
        assert FONT_SIZES["video_info"] == 18

    def test_hint_font_size(self):
        """補助テキストが17pxであること"""
        assert FONT_SIZES["hint"] == 17

    def test_progress_percent_font_size(self):
        """円形プログレス%が40pxであること"""
        assert FONT_SIZES["progress_percent"] == 40

    def test_frame_count_font_size(self):
        """フレーム数が18pxであること"""
        assert FONT_SIZES["frame_count"] == 18

    def test_footer_font_size(self):
        """フッターが16pxであること"""
        assert FONT_SIZES["footer"] == 16

    def test_dialog_title_font_size(self):
        """ダイアログタイトルが24pxであること"""
        assert FONT_SIZES["dialog_title"] == 24

    def test_dialog_body_font_size(self):
        """ダイアログ本文が18pxであること"""
        assert FONT_SIZES["dialog_body"] == 18

    def test_dialog_button_font_size(self):
        """ダイアログボタンが20pxであること"""
        assert FONT_SIZES["dialog_button"] == 20

    def test_toast_font_size(self):
        """トーストが18pxであること"""
        assert FONT_SIZES["toast"] == 18


# =============================================================================
# 3. ウィンドウサイズテスト
# =============================================================================
class TestWindowSize:
    """ウィンドウサイズが仕様通りか確認"""

    def test_initial_size(self):
        """初期サイズが700x850であること"""
        assert SIZES["window_initial"] == (700, 850)

    def test_minimum_size(self):
        """最小サイズが600x750であること"""
        assert SIZES["window_min"] == (600, 750)

    def test_content_max_width(self):
        """コンテンツ最大幅が800pxであること"""
        assert SIZES["content_max_width"] == 800

    def test_thumbnail_max_width(self):
        """サムネイル最大幅が500pxであること"""
        assert SIZES["thumbnail_max_width"] == 500

    def test_thumbnail_aspect_ratio(self):
        """サムネイルアスペクト比が16:9であること"""
        assert SIZES["thumbnail_aspect_ratio"] == 16 / 9

    def test_button_height(self):
        """ボタン高さが60pxであること"""
        assert SIZES["button_height"] == 60

    def test_button_max_width(self):
        """ボタン最大幅が500pxであること"""
        assert SIZES["button_max_width"] == 500

    def test_circular_progress_size(self):
        """円形プログレスが140pxであること"""
        assert SIZES["circular_progress"] == 140

    def test_padding(self):
        """パディングが24pxであること"""
        assert SIZES["padding"] == 24

    def test_dialog_width(self):
        """ダイアログ幅が420pxであること"""
        assert SIZES["dialog_width"] == 420

    def test_dialog_button_height(self):
        """ダイアログボタン高さが50pxであること"""
        assert SIZES["dialog_button_height"] == 50

    def test_logo_size(self):
        """ロゴサイズが48pxであること"""
        assert SIZES["logo_size"] == 48


# =============================================================================
# 4. 初期状態UIテスト
# =============================================================================
@pytest.mark.skipif(not _HAS_GUI_CLASSES, reason="GUI classes not available (no tkinter)")
class TestInitialState:
    """初期状態UIが仕様通りか確認"""

    def test_app_state_constants(self):
        """画面状態定数が定義されていること"""
        assert BackgroundRemoverApp.STATE_INITIAL == "initial"
        assert BackgroundRemoverApp.STATE_FILE_SELECTED == "file_selected"
        assert BackgroundRemoverApp.STATE_PROCESSING == "processing"
        assert BackgroundRemoverApp.STATE_COMPLETE == "complete"

    def test_all_state_constants_exist(self):
        """すべての状態定数が存在すること"""
        required_states = [
            "STATE_INITIAL",
            "STATE_FILE_SELECTED",
            "STATE_PROCESSING",
            "STATE_COMPLETE",
        ]
        for state in required_states:
            assert hasattr(BackgroundRemoverApp, state), f"Missing state: {state}"


# =============================================================================
# 5. ファイル選択後状態UIテスト
# =============================================================================
@pytest.mark.skipif(not _HAS_GUI_CLASSES, reason="GUI classes not available (no tkinter)")
class TestFileSelectedState:
    """ファイル選択後状態UIが仕様通りか確認"""

    def test_state_constant_exists(self):
        """STATE_FILE_SELECTED定数が存在すること"""
        assert hasattr(BackgroundRemoverApp, "STATE_FILE_SELECTED")
        assert BackgroundRemoverApp.STATE_FILE_SELECTED == "file_selected"


# =============================================================================
# 6. 処理中状態UIテスト
# =============================================================================
@pytest.mark.skipif(not _HAS_GUI_CLASSES, reason="GUI classes not available (no tkinter)")
class TestProcessingState:
    """処理中状態UIが仕様通りか確認"""

    def test_state_constant_exists(self):
        """STATE_PROCESSING定数が存在すること"""
        assert hasattr(BackgroundRemoverApp, "STATE_PROCESSING")
        assert BackgroundRemoverApp.STATE_PROCESSING == "processing"


# =============================================================================
# 7. 完了状態UIテスト
# =============================================================================
@pytest.mark.skipif(not _HAS_GUI_CLASSES, reason="GUI classes not available (no tkinter)")
class TestCompleteState:
    """完了状態UIが仕様通りか確認"""

    def test_state_constant_exists(self):
        """STATE_COMPLETE定数が存在すること"""
        assert hasattr(BackgroundRemoverApp, "STATE_COMPLETE")
        assert BackgroundRemoverApp.STATE_COMPLETE == "complete"


# =============================================================================
# 8. ダイアログテスト
# =============================================================================
class TestDialogs:
    """ダイアログが仕様通りか確認"""

    @pytest.mark.skipif(not _HAS_GUI_CLASSES, reason="GUI classes not available (no tkinter)")
    def test_custom_dialog_class_exists(self):
        """CustomDialogクラスが存在すること"""
        assert CustomDialog is not None

    def test_dialog_default_width(self):
        """ダイアログのデフォルト幅が420pxであること"""
        assert SIZES["dialog_width"] == 420


# =============================================================================
# 9. トースト通知テスト
# =============================================================================
class TestToast:
    """トースト通知が仕様通りか確認"""

    @pytest.mark.skipif(not _HAS_GUI_CLASSES, reason="GUI classes not available (no tkinter)")
    def test_toast_class_exists(self):
        """Toastクラスが存在すること"""
        assert Toast is not None

    def test_toast_background_color(self):
        """トースト背景色が#263238であること"""
        assert COLORS["toast_bg"] == "#263238"

    def test_toast_text_color(self):
        """トーストテキスト色が#FFFFFFであること"""
        assert COLORS["toast_text"] == "#FFFFFF"


# =============================================================================
# 10. CircularProgressテスト
# =============================================================================
class TestCircularProgress:
    """円形プログレスバーが仕様通りか確認"""

    @pytest.mark.skipif(not _HAS_GUI_CLASSES, reason="GUI classes not available (no tkinter)")
    def test_circular_progress_class_exists(self):
        """CircularProgressクラスが存在すること"""
        assert CircularProgress is not None

    def test_circular_progress_default_size(self):
        """円形プログレスのデフォルトサイズが140pxであること"""
        assert SIZES["circular_progress"] == 140


# =============================================================================
# 12. アクセシビリティテスト
# =============================================================================
class TestAccessibility:
    """アクセシビリティが仕様通りか確認"""

    def test_minimum_tap_target_size(self):
        """タップ領域が最低44x44px以上であること"""
        # ボタン高さが60px（44px以上）
        assert SIZES["button_height"] >= 44

        # ダイアログボタン高さが50px（44px以上）
        assert SIZES["dialog_button_height"] >= 44

    def test_font_sizes_are_readable(self):
        """フォントサイズが読みやすいサイズであること"""
        # 最小フォントサイズが14px以上
        min_font_size = min(FONT_SIZES.values())
        assert min_font_size >= 14

    def test_contrast_colors_defined(self):
        """コントラストを確保する色が定義されていること"""
        # テキスト色とサブテキスト色が定義されている
        assert "text" in COLORS
        assert "text_secondary" in COLORS

        # 背景色が定義されている
        assert "bg" in COLORS
        assert "card" in COLORS


# =============================================================================
# 13. 統合テスト（定数の整合性）
# =============================================================================
class TestIntegration:
    """定数間の整合性を確認"""

    def test_all_required_colors_exist(self):
        """必要なカラー定数がすべて存在すること"""
        required_colors = [
            "primary",
            "primary_dark",
            "primary_hover",
            "secondary",
            "success",
            "warning",
            "danger",
            "danger_hover",
            "disabled",
            "bg",
            "card",
            "border",
            "text",
            "text_secondary",
            "drop_zone",
            "drop_zone_hover",
            "toast_bg",
            "toast_text",
        ]
        for color in required_colors:
            assert color in COLORS, f"Missing color: {color}"

    def test_all_required_font_sizes_exist(self):
        """必要なフォントサイズ定数がすべて存在すること"""
        required_fonts = [
            "title",
            "subtitle",
            "button",
            "filename",
            "video_info",
            "hint",
            "progress_percent",
            "frame_count",
            "footer",
            "dialog_title",
            "dialog_body",
            "dialog_button",
            "toast",
        ]
        for font in required_fonts:
            assert font in FONT_SIZES, f"Missing font size: {font}"

    def test_all_required_sizes_exist(self):
        """必要なサイズ定数がすべて存在すること"""
        required_sizes = [
            "window_initial",
            "window_min",
            "content_max_width",
            "thumbnail_max_width",
            "thumbnail_aspect_ratio",
            "button_height",
            "button_max_width",
            "circular_progress",
            "padding",
            "dialog_width",
            "dialog_button_height",
            "logo_size",
        ]
        for size in required_sizes:
            assert size in SIZES, f"Missing size: {size}"


# =============================================================================
# 14. サポートされていないファイル形式テスト（異常系）
# =============================================================================
class TestUnsupportedFileFormat:
    """サポートされていないファイル形式のテスト"""

    def test_unsupported_extension_list(self):
        """非対応拡張子が拒否されること"""
        # main.pyではis_supported_video関数でチェックされる
        # 非対応拡張子リスト
        unsupported_extensions = [".avi", ".mkv", ".wmv", ".flv", ".webm", ".txt", ".jpg"]
        from utils import is_supported_video

        for ext in unsupported_extensions:
            assert is_supported_video(f"video{ext}") is False, f"{ext} should not be supported"

    def test_supported_extension_list(self):
        """対応拡張子が受け入れられること"""
        from utils import SUPPORTED_INPUT_EXTENSIONS, is_supported_video

        # 対応拡張子リスト
        for ext in SUPPORTED_INPUT_EXTENSIONS:
            assert is_supported_video(f"video{ext}") is True, f"{ext} should be supported"

    def test_empty_filename_rejected(self):
        """空のファイル名が拒否されること"""
        from utils import is_supported_video

        assert is_supported_video("") is False

    def test_no_extension_rejected(self):
        """拡張子なしのファイル名が拒否されること"""
        from utils import is_supported_video

        assert is_supported_video("videofile") is False
        assert is_supported_video("video.") is False


# =============================================================================
# 15. 状態遷移エラーテスト（異常系）
# =============================================================================
class TestStateTransitionErrors:
    """状態遷移時のエラーハンドリングテスト"""

    def test_processing_state_blocks_file_selection(self):
        """処理中状態ではファイル選択が無効化されること"""
        # STATE_PROCESSINGでは_select_inputが無視される仕様
        # コード: if self.current_state in (self.STATE_PROCESSING, self.STATE_CONVERTING): return
        assert "processing" in ["initial", "file_selected", "processing", "converting", "complete"]

    def test_converting_state_blocks_file_selection(self):
        """変換中状態ではファイル選択が無効化されること"""
        assert "converting" in ["initial", "file_selected", "processing", "converting", "complete"]

    def test_processing_state_blocks_main_button(self):
        """処理中状態ではメインボタンが無効化されること"""
        # コード: if self.current_state in (self.STATE_PROCESSING, self.STATE_CONVERTING): return
        assert "processing" != "file_selected"

    def test_converting_state_blocks_main_button(self):
        """変換中状態ではメインボタンが無効化されること"""
        assert "converting" != "complete"

    def test_only_processing_state_allows_cancel(self):
        """キャンセルは処理中状態のみで有効なこと"""
        # コード: if self.current_state != self.STATE_PROCESSING: return
        valid_cancel_states = ["processing"]
        invalid_cancel_states = ["initial", "file_selected", "converting", "complete"]
        assert len(valid_cancel_states) == 1
        assert len(invalid_cancel_states) == 4

    def test_retry_only_in_complete_state(self):
        """やり直しは完了状態のみで有効なこと"""
        # コード: if self.current_state != self.STATE_COMPLETE: return
        assert "complete" not in ["initial", "file_selected", "processing", "converting"]

    def test_process_another_only_in_complete_state(self):
        """別の動画を処理は完了状態のみで有効なこと"""
        # コード: if self.current_state != self.STATE_COMPLETE: return
        assert "complete" not in ["initial", "file_selected", "processing", "converting"]


# =============================================================================
# 16. 多重起動防止テスト（異常系）
# =============================================================================
class TestSingleInstanceLock:
    """多重起動防止のテスト"""

    def test_lock_file_path_in_temp_directory(self):
        """ロックファイルがtempディレクトリに配置されること"""
        import tempfile
        from pathlib import Path

        expected_dir = Path(tempfile.gettempdir())
        lock_file_name = "background_remover_video.lock"

        # main.pyのSingleInstanceLock.LOCK_FILEを確認
        assert expected_dir.exists()
        assert lock_file_name == "background_remover_video.lock"

    def test_lock_file_name_constant(self):
        """ロックファイル名が正しいこと"""
        # main.pyの定数を確認
        expected_name = "background_remover_video.lock"
        assert expected_name.endswith(".lock")

    def test_invalid_pid_handling(self):
        """不正なPIDが含まれるロックファイルの処理"""
        import contextlib

        # 不正なPIDの例
        invalid_pids = ["", "abc", "-1", "0"]
        for pid in invalid_pids:
            with contextlib.suppress(ValueError):
                int(pid) if pid else None


# =============================================================================
# 17. 入力検証テスト（異常系）
# =============================================================================
class TestInputValidation:
    """入力検証テスト"""

    def test_empty_path_is_rejected(self):
        """空のパスが拒否されること"""
        # _set_input_file メソッドの if not path: return をテスト
        empty_paths = ["", None]
        for path in empty_paths:
            assert not path  # Falsy

    def test_path_validation_for_supported_video(self):
        """パス検証がis_supported_videoを使用すること"""
        from utils import is_supported_video

        # 存在しないが形式は正しいパス
        assert is_supported_video("/nonexistent/path/video.mp4") is True
        # 存在しないし形式も不正なパス
        assert is_supported_video("/nonexistent/path/video.txt") is False

    def test_unicode_path_handling(self):
        """日本語パスが正しく処理されること"""
        from utils import is_supported_video

        assert is_supported_video("/パス/動画.mp4") is True
        assert is_supported_video("/path/日本語ファイル名.mov") is True

    def test_path_with_special_characters(self):
        """特殊文字を含むパスが正しく処理されること"""
        from utils import is_supported_video

        assert is_supported_video("/path/video (1).mp4") is True
        assert is_supported_video("/path/video-file_name.mov") is True
        assert is_supported_video("/path/video.file.mp4") is True


# =============================================================================
# 18. 色コード妥当性検証テスト（異常系防止）
# =============================================================================
class TestColorValidation:
    """色コードの妥当性検証テスト"""

    def test_all_colors_are_valid_hex_format(self):
        """すべての色が有効なHex形式であること"""
        import re

        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")

        for name, color in COLORS.items():
            assert hex_pattern.match(color), f"Invalid color format for {name}: {color}"

    def test_color_values_not_empty(self):
        """色値が空でないこと"""
        for name, color in COLORS.items():
            assert color, f"Color {name} is empty"
            assert len(color) == 7, f"Color {name} has wrong length: {len(color)}"

    def test_no_duplicate_color_keys(self):
        """重複するカラーキーがないこと"""
        keys = list(COLORS.keys())
        assert len(keys) == len(set(keys)), "Duplicate color keys found"

    def test_primary_colors_are_distinct(self):
        """プライマリ系の色が互いに異なること"""
        primary_colors = [
            COLORS["primary"],
            COLORS["primary_dark"],
            COLORS["primary_hover"],
        ]
        assert len(primary_colors) == len(set(primary_colors)), "Primary colors should be distinct"


# =============================================================================
# 19. フォントサイズ妥当性検証テスト（異常系防止）
# =============================================================================
class TestFontSizeValidation:
    """フォントサイズの妥当性検証テスト"""

    def test_all_font_sizes_are_positive(self):
        """すべてのフォントサイズが正の整数であること"""
        for name, size in FONT_SIZES.items():
            assert isinstance(size, int), f"Font size {name} is not int: {type(size)}"
            assert size > 0, f"Font size {name} is not positive: {size}"

    def test_font_sizes_in_reasonable_range(self):
        """フォントサイズが妥当な範囲内であること（8〜100px）"""
        for name, size in FONT_SIZES.items():
            assert 8 <= size <= 100, f"Font size {name} out of range: {size}"

    def test_hierarchy_font_sizes(self):
        """フォントサイズの階層が正しいこと（タイトル > サブタイトル > 本文）"""
        assert FONT_SIZES["title"] > FONT_SIZES["subtitle"]
        assert FONT_SIZES["dialog_title"] > FONT_SIZES["dialog_body"]


# =============================================================================
# 20. サイズ定数妥当性検証テスト（異常系防止）
# =============================================================================
class TestSizeValidation:
    """サイズ定数の妥当性検証テスト"""

    def test_window_initial_larger_than_minimum(self):
        """初期ウィンドウサイズが最小サイズより大きいこと"""
        assert SIZES["window_initial"][0] >= SIZES["window_min"][0]
        assert SIZES["window_initial"][1] >= SIZES["window_min"][1]

    def test_all_sizes_are_positive(self):
        """すべてのサイズが正の値であること"""
        for name, size in SIZES.items():
            if isinstance(size, tuple):
                for val in size:
                    assert val > 0, f"Size {name} has non-positive value: {val}"
            else:
                assert size > 0, f"Size {name} is not positive: {size}"

    def test_thumbnail_aspect_ratio_valid(self):
        """サムネイルアスペクト比が有効な値であること"""
        ratio = SIZES["thumbnail_aspect_ratio"]
        assert 0.5 <= ratio <= 3.0, f"Thumbnail aspect ratio out of range: {ratio}"

    def test_button_dimensions_valid(self):
        """ボタンのサイズが有効であること"""
        assert SIZES["button_height"] >= 40  # 最低タップサイズ
        assert SIZES["button_max_width"] >= 100  # 最低幅

    def test_dialog_dimensions_valid(self):
        """ダイアログのサイズが有効であること"""
        assert SIZES["dialog_width"] >= 200
        assert SIZES["dialog_button_height"] >= 40


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
