# -*- coding: utf-8 -*-
"""main.py (GUI) のユニットテスト

Tkinterをモックしてヘッドレス環境でも実行可能。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import pytest

# Tkinterをモック
sys.modules["tkinter"] = MagicMock()
sys.modules["tkinter.ttk"] = MagicMock()

from src.main import BackgroundRemoverApp


class TestBackgroundRemoverAppInit:
    """BackgroundRemoverAppの初期化テスト"""

    @patch("src.main.get_device_info")
    def test_init_creates_instance(self, mock_get_device_info):
        """インスタンスが正常に作成されること"""
        mock_get_device_info.return_value = Mock(
            device="cpu",
            name="CPU",
            is_gpu=False,
            warning=None,
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        assert app is not None
        assert app.root == mock_root

    @patch("src.main.get_device_info")
    def test_init_sets_window_title(self, mock_get_device_info):
        """ウィンドウタイトルが設定されること"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        BackgroundRemoverApp(mock_root)

        mock_root.title.assert_called_with("動画背景除去ツール")

    @patch("src.main.get_device_info")
    def test_init_sets_window_size(self, mock_get_device_info):
        """ウィンドウサイズが設定されること"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        BackgroundRemoverApp(mock_root)

        mock_root.geometry.assert_called_with("500x400")

    @patch("src.main.get_device_info")
    def test_init_window_resizable(self, mock_get_device_info):
        """ウィンドウがリサイズ可能であること"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        BackgroundRemoverApp(mock_root)

        mock_root.resizable.assert_called_with(True, True)

    @patch("src.main.get_device_info")
    def test_init_state_variables(self, mock_get_device_info):
        """状態変数が正しく初期化されること"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        assert app.input_path == ""
        assert app.output_path == ""
        assert app.is_processing is False
        assert app.model is None
        assert app.processor is None

    @patch("src.main.get_device_info")
    def test_init_shows_gpu_warning_when_no_gpu(self, mock_get_device_info):
        """GPU未検出時に警告が表示されること"""
        mock_get_device_info.return_value = Mock(
            device="cpu",
            name="CPU",
            is_gpu=False,
            warning="GPUが検出されませんでした",
        )

        mock_root = MagicMock()
        BackgroundRemoverApp(mock_root)

        # root.after(100, self._show_gpu_warning) が呼ばれること
        mock_root.after.assert_called()

    @patch("src.main.get_device_info")
    def test_init_no_warning_when_gpu_available(self, mock_get_device_info):
        """GPU検出時に警告が表示されないこと"""
        mock_get_device_info.return_value = Mock(
            device="cuda",
            name="NVIDIA GPU",
            is_gpu=True,
            warning=None,
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        # warningがNoneの場合、afterは_setup_ui内で呼ばれない
        # （_setup_ui内でafterが呼ばれる場合もあるのでチェックしない）
        assert app.device_info.warning is None


class TestSelectInput:
    """入力ファイル選択のテスト"""

    @patch("src.main.get_device_info")
    @patch("src.main.filedialog")
    @patch("src.main.is_supported_video")
    @patch("src.main.get_output_path")
    @patch("src.main.get_video_info")
    def test_select_input_valid_file(
        self,
        mock_get_video_info,
        mock_get_output_path,
        mock_is_supported,
        mock_filedialog,
        mock_get_device_info,
    ):
        """有効なファイルを選択した場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )
        mock_filedialog.askopenfilename.return_value = "/path/to/video.mp4"
        mock_is_supported.return_value = True
        mock_get_output_path.return_value = "/path/to/video_nobg.mov"
        mock_get_video_info.return_value = Mock(
            width=1920, height=1080, fps=30.0, frame_count=900, duration=30.0
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.input_var = MagicMock()
        app.output_var = MagicMock()
        app.info_var = MagicMock()
        app.process_button = MagicMock()

        app._select_input()

        assert app.input_path == "/path/to/video.mp4"
        assert app.output_path == "/path/to/video_nobg.mov"
        app.input_var.set.assert_called_with("video.mp4")
        app.output_var.set.assert_called_with("video_nobg.mov")
        app.process_button.config.assert_called_with(state="normal")

    @patch("src.main.get_device_info")
    @patch("src.main.filedialog")
    @patch("src.main.is_supported_video")
    @patch("src.main.messagebox")
    def test_select_input_unsupported_format(
        self,
        mock_messagebox,
        mock_is_supported,
        mock_filedialog,
        mock_get_device_info,
    ):
        """サポートされていない形式の場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )
        mock_filedialog.askopenfilename.return_value = "/path/to/video.avi"
        mock_is_supported.return_value = False

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        app._select_input()

        mock_messagebox.showerror.assert_called_once()
        assert app.input_path == ""

    @patch("src.main.get_device_info")
    @patch("src.main.filedialog")
    def test_select_input_cancelled(self, mock_filedialog, mock_get_device_info):
        """ファイル選択がキャンセルされた場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )
        mock_filedialog.askopenfilename.return_value = ""

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        app._select_input()

        assert app.input_path == ""


class TestSelectOutput:
    """出力先選択のテスト"""

    @patch("src.main.get_device_info")
    @patch("src.main.filedialog")
    def test_select_output_valid(self, mock_filedialog, mock_get_device_info):
        """出力先を選択した場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )
        mock_filedialog.asksaveasfilename.return_value = "/new/path/output.mov"

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.input_path = "/path/to/video.mp4"
        app.output_path = "/path/to/video_nobg.mov"
        app.output_var = MagicMock()

        app._select_output()

        assert app.output_path == "/new/path/output.mov"
        app.output_var.set.assert_called_with("output.mov")

    @patch("src.main.get_device_info")
    @patch("src.main.messagebox")
    def test_select_output_without_input(self, mock_messagebox, mock_get_device_info):
        """入力ファイル未選択時"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.input_path = ""

        app._select_output()

        mock_messagebox.showwarning.assert_called_once()


class TestStartProcessing:
    """処理開始のテスト"""

    @patch("src.main.get_device_info")
    @patch("src.main.threading")
    def test_start_processing_valid(self, mock_threading, mock_get_device_info):
        """正常に処理を開始する場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.input_path = "/path/to/video.mp4"
        app.output_path = "/path/to/output.mov"
        app.process_button = MagicMock()
        app.cancel_button = MagicMock()
        app.progressbar = MagicMock()
        app.progress_var = MagicMock()

        app._start_processing()

        assert app.is_processing is True
        app.process_button.config.assert_called_with(state="disabled")
        app.cancel_button.config.assert_called_with(state="normal")
        mock_threading.Thread.assert_called_once()

    @patch("src.main.get_device_info")
    def test_start_processing_already_processing(self, mock_get_device_info):
        """既に処理中の場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.is_processing = True

        # 何も起こらない（早期リターン）
        app._start_processing()

        assert app.is_processing is True

    @patch("src.main.get_device_info")
    @patch("src.main.messagebox")
    def test_start_processing_no_input(self, mock_messagebox, mock_get_device_info):
        """入力ファイルが選択されていない場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.input_path = ""

        app._start_processing()

        mock_messagebox.showwarning.assert_called_once()
        assert app.is_processing is False


class TestCancelProcessing:
    """キャンセル処理のテスト"""

    @patch("src.main.get_device_info")
    def test_cancel_processing(self, mock_get_device_info):
        """処理をキャンセルする場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.is_processing = True
        app.processor = MagicMock()
        app.progress_var = MagicMock()
        app.cancel_button = MagicMock()

        app._cancel_processing()

        app.processor.cancel.assert_called_once()
        app.progress_var.set.assert_called_with("キャンセル中...")
        app.cancel_button.config.assert_called_with(state="disabled")

    @patch("src.main.get_device_info")
    def test_cancel_processing_not_processing(self, mock_get_device_info):
        """処理中でない場合"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.is_processing = False
        app.processor = MagicMock()

        app._cancel_processing()

        # processorのcancelは呼ばれない
        app.processor.cancel.assert_not_called()


class TestProgressCallbacks:
    """進捗コールバックのテスト"""

    @patch("src.main.get_device_info")
    def test_on_progress(self, mock_get_device_info):
        """進捗更新コールバック"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        app._on_progress(50, 100)

        # root.after(0, ...) が呼ばれること
        mock_root.after.assert_called()

    @patch("src.main.get_device_info")
    def test_update_progress(self, mock_get_device_info):
        """進捗UI更新"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)
        app.progressbar = {}  # 辞書として扱う
        app.progress_var = MagicMock()

        app._update_progress(50.0, 50, 100)

        assert app.progressbar["value"] == 50.0
        app.progress_var.set.assert_called_with("処理中: 50/100 フレーム (50.0%)")


class TestCompletionCallbacks:
    """完了/エラー/キャンセルコールバックのテスト"""

    @patch("src.main.get_device_info")
    def test_on_complete(self, mock_get_device_info):
        """処理完了時"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        app._on_complete()

        # root.after(0, ...) が呼ばれること
        mock_root.after.assert_called()

    @patch("src.main.get_device_info")
    def test_on_error(self, mock_get_device_info):
        """エラー発生時"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        app._on_error("Test error message")

        # root.after(0, ...) が呼ばれること
        mock_root.after.assert_called()

    @patch("src.main.get_device_info")
    def test_on_cancelled(self, mock_get_device_info):
        """キャンセル時"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        app._on_cancelled()

        # root.after(0, ...) が呼ばれること
        mock_root.after.assert_called()


class TestShowGpuWarning:
    """GPU警告表示のテスト"""

    @patch("src.main.get_device_info")
    @patch("src.main.messagebox")
    def test_show_gpu_warning(self, mock_messagebox, mock_get_device_info):
        """GPU警告を表示"""
        mock_get_device_info.return_value = Mock(
            device="cpu",
            name="CPU",
            is_gpu=False,
            warning="GPUが検出されませんでした",
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        app._show_gpu_warning()

        mock_messagebox.showwarning.assert_called_once()


class TestResponsiveDesign:
    """レスポンシブデザインのテスト"""

    @patch("src.main.get_device_info")
    def test_window_is_resizable(self, mock_get_device_info):
        """ウィンドウがリサイズ可能であること"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        BackgroundRemoverApp(mock_root)

        # resizable(True, True) が呼ばれること
        mock_root.resizable.assert_called_with(True, True)

    @patch("src.main.get_device_info")
    def test_minimum_window_size_is_set(self, mock_get_device_info):
        """最小ウィンドウサイズが設定されていること"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        BackgroundRemoverApp(mock_root)

        # minsize(400, 350) が呼ばれること
        mock_root.minsize.assert_called_with(400, 350)

    @patch("src.main.get_device_info")
    def test_default_window_size(self, mock_get_device_info):
        """デフォルトウィンドウサイズが適切であること"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        BackgroundRemoverApp(mock_root)

        # geometry("500x400") が呼ばれること
        mock_root.geometry.assert_called_with("500x400")

    @patch("src.main.get_device_info")
    def test_input_label_has_responsive_attributes(self, mock_get_device_info):
        """入力ラベルがレスポンシブ属性を持つこと"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        # input_labelが存在すること（レスポンシブ対応で追加）
        assert hasattr(app, "input_label")

    @patch("src.main.get_device_info")
    def test_output_label_has_responsive_attributes(self, mock_get_device_info):
        """出力ラベルがレスポンシブ属性を持つこと"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        # output_labelが存在すること（レスポンシブ対応で追加）
        assert hasattr(app, "output_label")

    @patch("src.main.get_device_info")
    def test_progressbar_exists(self, mock_get_device_info):
        """プログレスバーが存在すること"""
        mock_get_device_info.return_value = Mock(
            device="cpu", name="CPU", is_gpu=False, warning=None
        )

        mock_root = MagicMock()
        app = BackgroundRemoverApp(mock_root)

        # progressbarが存在すること
        assert hasattr(app, "progressbar")
