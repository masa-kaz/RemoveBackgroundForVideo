# -*- coding: utf-8 -*-
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
    pattern = rf'^{name}\s*=\s*\{{'
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return {}

    start = match.start()
    # 対応する閉じ括弧を探す
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
create_checkerboard_image = None

try:
    from main import (
        BackgroundRemoverApp,
        CircularProgress,
        CustomDialog,
        Toast,
        create_checkerboard_image,
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


# =============================================================================
# 2. フォントサイズテスト
# =============================================================================
class TestFonts:
    """フォントサイズが仕様通りか確認（アクセシビリティ対応・大きめ）"""

    def test_title_font_size(self):
        """タイトルが28pxであること"""
        assert FONT_SIZES["title"] == 28

    def test_subtitle_font_size(self):
        """サブタイトルが16pxであること"""
        assert FONT_SIZES["subtitle"] == 16

    def test_button_font_size(self):
        """ボタンテキストが20pxであること"""
        assert FONT_SIZES["button"] == 20

    def test_filename_font_size(self):
        """ファイル名が18pxであること"""
        assert FONT_SIZES["filename"] == 18

    def test_video_info_font_size(self):
        """動画情報が16pxであること"""
        assert FONT_SIZES["video_info"] == 16

    def test_hint_font_size(self):
        """補助テキストが15pxであること"""
        assert FONT_SIZES["hint"] == 15

    def test_progress_percent_font_size(self):
        """円形プログレス%が32pxであること"""
        assert FONT_SIZES["progress_percent"] == 32

    def test_frame_count_font_size(self):
        """フレーム数が16pxであること"""
        assert FONT_SIZES["frame_count"] == 16

    def test_footer_font_size(self):
        """フッターが14pxであること"""
        assert FONT_SIZES["footer"] == 14

    def test_dialog_title_font_size(self):
        """ダイアログタイトルが20pxであること"""
        assert FONT_SIZES["dialog_title"] == 20

    def test_dialog_body_font_size(self):
        """ダイアログ本文が16pxであること"""
        assert FONT_SIZES["dialog_body"] == 16

    def test_dialog_button_font_size(self):
        """ダイアログボタンが18pxであること"""
        assert FONT_SIZES["dialog_button"] == 18

    def test_toast_font_size(self):
        """トーストが16pxであること"""
        assert FONT_SIZES["toast"] == 16


# =============================================================================
# 3. ウィンドウサイズテスト
# =============================================================================
class TestWindowSize:
    """ウィンドウサイズが仕様通りか確認"""

    def test_initial_size(self):
        """初期サイズが600x750であること"""
        assert SIZES["window_initial"] == (600, 750)

    def test_minimum_size(self):
        """最小サイズが520x650であること"""
        assert SIZES["window_min"] == (520, 650)

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
# 10. 市松模様テスト
# =============================================================================
@pytest.mark.skipif(not _HAS_GUI_CLASSES, reason="GUI classes not available (no tkinter)")
class TestCheckerboard:
    """市松模様が正しく生成されるか確認"""

    def test_create_checkerboard_image_exists(self):
        """create_checkerboard_image関数が存在すること"""
        assert create_checkerboard_image is not None

    def test_create_checkerboard_image_size(self):
        """指定サイズで市松模様画像が生成されること"""
        width, height = 100, 100
        img = create_checkerboard_image(width, height)
        assert img.size == (width, height)

    def test_create_checkerboard_image_mode(self):
        """市松模様画像がRGBAモードであること"""
        img = create_checkerboard_image(100, 100)
        assert img.mode == "RGBA"


# =============================================================================
# 11. CircularProgressテスト
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
