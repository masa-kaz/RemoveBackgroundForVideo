# -*- coding: utf-8 -*-
"""video_processor.py のテスト"""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import cv2
import numpy as np
import pytest
import torch
from PIL import Image

from src.video_processor import (
    VideoProcessor,
    VideoInfo,
    ProcessingCancelled,
    get_video_info,
    find_ffmpeg,
    _check_audio_stream,
)


class TestVideoInfo:
    """VideoInfoデータクラスのテスト"""

    def test_create_video_info(self):
        """VideoInfoを作成できること"""
        info = VideoInfo(
            width=1920,
            height=1080,
            fps=30.0,
            frame_count=900,
            duration=30.0,
        )

        assert info.width == 1920
        assert info.height == 1080
        assert info.fps == 30.0
        assert info.frame_count == 900
        assert info.duration == 30.0
        assert info.has_audio is False  # デフォルト値

    def test_create_video_info_with_audio(self):
        """VideoInfoに音声フラグを設定できること"""
        info = VideoInfo(
            width=1920,
            height=1080,
            fps=30.0,
            frame_count=900,
            duration=30.0,
            has_audio=True,
        )

        assert info.has_audio is True


class TestGetVideoInfo:
    """get_video_info関数のテスト"""

    def test_invalid_path(self):
        """存在しないファイルでValueErrorを発生すること"""
        with pytest.raises(ValueError) as exc_info:
            get_video_info("/nonexistent/path/video.mp4")

        assert "動画を開けません" in str(exc_info.value)

    def test_get_info_from_video(self):
        """動画ファイルから情報を取得できること"""
        # テスト用の短い動画を作成
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            temp_path = f.name

        try:
            # OpenCVで短いテスト動画を作成
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(temp_path, fourcc, 30.0, (640, 480))

            # 10フレーム書き込み
            for _ in range(10):
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                writer.write(frame)

            writer.release()

            # 情報を取得
            info = get_video_info(temp_path)

            assert info.width == 640
            assert info.height == 480
            assert info.fps == 30.0
            assert info.frame_count == 10
            assert abs(info.duration - 10 / 30.0) < 0.1
        finally:
            os.unlink(temp_path)


class TestCheckAudioStream:
    """_check_audio_stream関数のテスト"""

    @patch("subprocess.run")
    def test_audio_stream_exists(self, mock_run):
        """音声ストリームが存在する場合Trueを返すこと"""
        mock_run.return_value = Mock(stdout="audio\n", returncode=0)

        result = _check_audio_stream("/path/to/video.mp4")

        assert result is True

    @patch("subprocess.run")
    def test_audio_stream_not_exists(self, mock_run):
        """音声ストリームが存在しない場合Falseを返すこと"""
        mock_run.return_value = Mock(stdout="", returncode=0)

        result = _check_audio_stream("/path/to/video.mp4")

        assert result is False

    @patch("subprocess.run")
    def test_ffprobe_not_found(self, mock_run):
        """ffprobeが見つからない場合Trueを返すこと（安全側に倒す）"""
        mock_run.side_effect = FileNotFoundError()

        result = _check_audio_stream("/path/to/video.mp4")

        assert result is True


class TestFindFfmpeg:
    """find_ffmpeg関数のテスト"""

    @patch("subprocess.run")
    def test_find_system_ffmpeg(self, mock_run):
        """システムPATHのffmpegを見つけられること"""
        mock_run.return_value = Mock(returncode=0)

        # 同梱ffmpegが存在しない状態をシミュレート
        with patch("pathlib.Path.exists", return_value=False):
            result = find_ffmpeg()

        assert result == "ffmpeg"

    def test_ffmpeg_not_found(self):
        """ffmpegが見つからない場合RuntimeErrorを発生すること"""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(RuntimeError) as exc_info:
                    find_ffmpeg()

                assert "ffmpegが見つかりません" in str(exc_info.value)


class TestVideoProcessor:
    """VideoProcessorクラスのテスト"""

    def test_init(self):
        """VideoProcessorを初期化できること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        assert processor.model == mock_model
        assert processor.ffmpeg_path == "ffmpeg"

    def test_init_custom_ffmpeg_path(self):
        """カスタムffmpegパスを指定できること"""
        mock_model = Mock()
        custom_path = "/custom/ffmpeg"

        processor = VideoProcessor(model=mock_model, ffmpeg_path=custom_path)

        assert processor.ffmpeg_path == custom_path

    def test_process_unsupported_format(self):
        """サポートされていない形式でValueErrorを発生すること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        with pytest.raises(ValueError) as exc_info:
            processor.process("/path/to/video.avi")

        assert "サポートされていない動画形式" in str(exc_info.value)


class TestVideoProcessorCancel:
    """VideoProcessorのキャンセル機能のテスト"""

    def test_cancel_flag_initial_state(self):
        """初期状態ではキャンセルされていないこと"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        assert processor.is_cancelled() is False

    def test_cancel_sets_flag(self):
        """cancelメソッドがフラグを設定すること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        processor.cancel()

        assert processor.is_cancelled() is True

    def test_reset_cancel_clears_flag(self):
        """reset_cancelメソッドがフラグをクリアすること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        processor.cancel()
        assert processor.is_cancelled() is True

        processor.reset_cancel()
        assert processor.is_cancelled() is False

    def test_cancel_raises_exception_during_frame_processing(self):
        """フレーム処理中にキャンセルするとProcessingCancelled例外が発生すること"""
        mock_model = Mock()
        mock_model.process_frame.return_value = (
            torch.rand(3, 100, 100),
            torch.rand(1, 100, 100),
        )

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        # キャンセルフラグを設定
        processor.cancel()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # VideoCapture モックを設定
            with patch("cv2.VideoCapture") as mock_capture_class:
                mock_capture = Mock()
                mock_capture.isOpened.return_value = True

                frame = np.zeros((100, 100, 3), dtype=np.uint8)
                mock_capture.read.side_effect = [
                    (True, frame),
                    (True, frame),
                    (False, None),
                ]
                mock_capture_class.return_value = mock_capture

                video_info = VideoInfo(
                    width=100,
                    height=100,
                    fps=30.0,
                    frame_count=2,
                    duration=2 / 30.0,
                )

                with pytest.raises(ProcessingCancelled) as exc_info:
                    processor._process_frames(
                        input_path="/dummy/path.mp4",
                        output_dir=output_dir,
                        video_info=video_info,
                    )

                assert "キャンセル" in str(exc_info.value)


class TestVideoProcessorCreateRgbaImage:
    """VideoProcessor._create_rgba_image メソッドのテスト"""

    def test_create_rgba_image(self):
        """RGBA画像を正しく生成できること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        # テストデータを作成
        fgr = torch.rand(3, 100, 100)
        alpha = torch.rand(1, 100, 100)

        result = processor._create_rgba_image(fgr, alpha)

        assert isinstance(result, Image.Image)
        assert result.mode == "RGBA"
        assert result.size == (100, 100)

    def test_create_rgba_image_clamps_values(self):
        """値が0-1の範囲にクランプされること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        # 範囲外の値を持つテストデータ
        fgr = torch.tensor([[[1.5, -0.5], [0.5, 0.5]]] * 3)
        alpha = torch.tensor([[[1.2, -0.2], [0.5, 0.5]]])

        result = processor._create_rgba_image(fgr, alpha)

        # 画像が正常に作成されること（エラーが発生しないこと）
        assert isinstance(result, Image.Image)


class TestVideoProcessorWithMock:
    """モックを使用したVideoProcessorの統合テスト"""

    @patch("subprocess.run")
    @patch("cv2.VideoCapture")
    def test_process_frames(self, mock_capture_class, mock_subprocess):
        """フレームを処理できること"""
        # モックモデルを設定
        mock_model = Mock()
        mock_model.process_frame.return_value = (
            torch.rand(3, 480, 640),
            torch.rand(1, 480, 640),
        )

        # VideoCapture モックを設定
        mock_capture = Mock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 3,
        }.get(prop, 0)

        # 3フレーム読み込んで終了
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_capture.read.side_effect = [
            (True, frame),
            (True, frame),
            (True, frame),
            (False, None),
        ]
        mock_capture_class.return_value = mock_capture

        # subprocess モックを設定（stdout を文字列に設定）
        mock_subprocess.return_value = Mock(returncode=0, stderr="", stdout="audio")

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        # 一時ファイルで処理
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.mp4")
            output_path = os.path.join(temp_dir, "output.mov")

            # ダミー入力ファイルを作成
            Path(input_path).touch()

            # 処理を実行（実際の処理をモック）
            with patch.object(processor, "_process_frames") as mock_process:
                with patch.object(processor, "_create_prores_video") as mock_create:
                    result = processor.process(input_path, output_path)

            # 結果を確認
            assert result == output_path

    def test_progress_callback(self):
        """進捗コールバックが呼び出されること"""
        mock_model = Mock()
        mock_model.process_frame.return_value = (
            torch.rand(3, 100, 100),
            torch.rand(1, 100, 100),
        )

        progress_values = []

        def progress_callback(current, total):
            progress_values.append((current, total))

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        # _process_frames を直接テスト
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # VideoCapture モックを設定
            with patch("cv2.VideoCapture") as mock_capture_class:
                mock_capture = Mock()
                mock_capture.isOpened.return_value = True

                frame = np.zeros((100, 100, 3), dtype=np.uint8)
                mock_capture.read.side_effect = [
                    (True, frame),
                    (True, frame),
                    (False, None),
                ]
                mock_capture_class.return_value = mock_capture

                video_info = VideoInfo(
                    width=100,
                    height=100,
                    fps=30.0,
                    frame_count=2,
                    duration=2 / 30.0,
                )

                processor._process_frames(
                    input_path="/dummy/path.mp4",
                    output_dir=output_dir,
                    video_info=video_info,
                    progress_callback=progress_callback,
                )

        # コールバックが呼び出されたことを確認
        assert len(progress_values) == 2
        assert progress_values[0] == (1, 2)
        assert progress_values[1] == (2, 2)
