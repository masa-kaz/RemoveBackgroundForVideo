"""main.py (GUI) のユニットテスト

Tkinterをモックしてヘッドレス環境でも実行可能。
"""

import sys
from unittest.mock import MagicMock


# Tkinterとcustomtkinterをモック（importの前に設定）
mock_tkinter = MagicMock()
mock_tkinter.constants = MagicMock()
mock_tkinter.Tk = MagicMock
sys.modules["tkinter"] = mock_tkinter
sys.modules["tkinter.ttk"] = MagicMock()
sys.modules["tkinter.constants"] = MagicMock()
sys.modules["customtkinter"] = MagicMock()
sys.modules["tkinterdnd2"] = MagicMock()

from src.main import (
    CIRCULAR_PROGRESS_STYLE,
    DRAG_AND_DROP_AVAILABLE,
    FRAME_COUNT_THRESHOLDS,
    PROGRESS_TEXT_THRESHOLDS,
    TIMING_MS,
    calculate_frame_font_size,
    format_frame_count,
)


class TestMainConstants:
    """main.py の定数テスト"""

    def test_timing_ms_thumbnail_update_delay(self):
        """サムネイル更新遅延が正しい値であること"""
        assert TIMING_MS["thumbnail_update_delay"] == 50

    def test_timing_ms_auto_close_dialog(self):
        """自動クローズ時間が正しい値であること"""
        assert TIMING_MS["auto_close_dialog"] == 3000

    def test_timing_ms_window_resize_threshold(self):
        """ウィンドウリサイズ閾値が正しい値であること"""
        assert TIMING_MS["window_resize_threshold"] == 10

    def test_progress_text_thresholds_short(self):
        """短いテキストの閾値が正しい値であること"""
        assert PROGRESS_TEXT_THRESHOLDS["short_text_max_length"] == 14

    def test_progress_text_thresholds_medium(self):
        """中程度テキストの閾値が正しい値であること"""
        assert PROGRESS_TEXT_THRESHOLDS["medium_text_max_length"] == 17

    def test_progress_text_thresholds_long(self):
        """長いテキストの閾値が正しい値であること"""
        assert PROGRESS_TEXT_THRESHOLDS["long_text_max_length"] == 20

    def test_frame_count_thresholds_use_k_suffix(self):
        """k接尾辞使用の閾値が正しい値であること"""
        assert FRAME_COUNT_THRESHOLDS["use_k_suffix"] == 10000

    def test_circular_progress_outline_width(self):
        """アウトライン幅が正しい値であること"""
        assert CIRCULAR_PROGRESS_STYLE["outline_width"] == 2

    def test_drag_and_drop_available_is_bool(self):
        """ドラッグ＆ドロップ可否がブール値であること"""
        assert isinstance(DRAG_AND_DROP_AVAILABLE, bool)


class TestFrameCountFormat:
    """フレーム数フォーマット関数のテスト"""

    def test_format_frame_count_under_threshold(self):
        """10000未満の場合はカンマ区切り形式"""
        result = format_frame_count(1234, 5678)
        assert result == "1,234 / 5,678 f"

    def test_format_frame_count_at_threshold(self):
        """10000の場合はk形式"""
        result = format_frame_count(5000, 10000)
        assert result == "5.0k / 10.0k f"

    def test_format_frame_count_above_threshold(self):
        """10000以上の場合はk形式"""
        result = format_frame_count(12345, 98765)
        assert result == "12.3k / 98.8k f"

    def test_format_frame_count_large_numbers(self):
        """非常に大きなフレーム数の場合"""
        result = format_frame_count(123456, 987654)
        assert result == "123.5k / 987.7k f"

    def test_format_frame_count_zero(self):
        """0の場合"""
        result = format_frame_count(0, 5000)
        assert result == "0 / 5,000 f"

    def test_format_frame_count_boundary(self):
        """境界値9999の場合はカンマ区切り形式"""
        result = format_frame_count(5000, 9999)
        assert result == "5,000 / 9,999 f"


class TestFrameFontSize:
    """フレームフォントサイズ計算のテスト"""

    def test_calculate_frame_font_size_short_text(self):
        """短いテキスト（14文字以下）は基本サイズ"""
        # 13文字
        result = calculate_frame_font_size("1,234 / 5,678", base_font_size=18)
        assert result == 18  # 基本サイズ

    def test_calculate_frame_font_size_medium_text(self):
        """中程度テキスト（15-17文字）は85%サイズ"""
        # 17文字
        result = calculate_frame_font_size("12,345 / 67,890 f", base_font_size=18)
        assert result == int(18 * 0.85)  # 15

    def test_calculate_frame_font_size_long_text(self):
        """長いテキスト（18-20文字）は70%サイズ"""
        # 19文字
        result = calculate_frame_font_size("123,456 / 789,012 f", base_font_size=18)
        assert result == int(18 * 0.70)  # 12

    def test_calculate_frame_font_size_very_long_text(self):
        """非常に長いテキスト（20文字超）は60%サイズ"""
        # 23文字
        result = calculate_frame_font_size("1,234,567 / 9,876,543 f", base_font_size=18)
        assert result == int(18 * 0.60)  # 10

    def test_calculate_frame_font_size_k_format(self):
        """k形式のテキストはコンパクト（14文字以下）"""
        # "12.3k / 98.8k f" は 17文字
        result = calculate_frame_font_size("12.3k / 98.8k f", base_font_size=18)
        assert result == int(18 * 0.85)  # 15

    def test_calculate_frame_font_size_custom_base(self):
        """カスタム基本フォントサイズ"""
        result = calculate_frame_font_size("short text", base_font_size=24)
        assert result == 24
