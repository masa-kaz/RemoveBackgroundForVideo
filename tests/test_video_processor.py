"""video_processor.py のテスト"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest
import torch
from PIL import Image

from src.video_processor import (
    MAX_FILE_SIZE_MB,
    SAFETY_MARGIN,
    OutputParams,
    ProcessingCancelled,
    VideoInfo,
    VideoProcessor,
    _check_audio_stream,
    calculate_optimal_params,
    estimate_prores_size_mb,
    find_ffmpeg,
    get_video_info,
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
        with (
            patch("subprocess.run", side_effect=FileNotFoundError()),
            patch("pathlib.Path.exists", return_value=False),
            pytest.raises(RuntimeError) as exc_info,
        ):
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


class TestVideoProcessorPauseResume:
    """VideoProcessorの一時停止/再開機能のテスト"""

    def test_pause_sets_flag(self):
        """pauseメソッドが一時停止フラグを設定すること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        assert processor.is_paused() is False

        processor.pause()

        assert processor.is_paused() is True

    def test_resume_clears_flag(self):
        """resumeメソッドが一時停止フラグをクリアすること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        processor.pause()
        assert processor.is_paused() is True

        processor.resume()

        assert processor.is_paused() is False

    def test_cancel_clears_pause(self):
        """cancelがpause状態を解除すること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        processor.pause()
        assert processor.is_paused() is True

        processor.cancel()

        # キャンセル時はpause状態が解除される
        assert processor.is_paused() is False
        assert processor.is_cancelled() is True


class TestVideoProcessorCreateProresVideo:
    """VideoProcessor._create_prores_video メソッドのテスト"""

    def _create_output_params(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
    ) -> OutputParams:
        """テスト用のOutputParamsを作成するヘルパー"""
        return OutputParams(
            width=width,
            height=height,
            fps=fps,
            original_width=width,
            original_height=height,
            original_fps=fps,
            is_adjusted=False,
        )

    @patch("subprocess.run")
    def test_create_prores_video_without_audio(self, mock_run):
        """音声なしでProRes動画を作成できること"""
        mock_run.return_value = Mock(returncode=0, stderr="")
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        with tempfile.TemporaryDirectory() as temp_dir:
            frames_dir = Path(temp_dir)
            output_path = str(frames_dir / "output.mov")
            output_params = self._create_output_params()

            processor._create_prores_video(
                frames_dir=frames_dir,
                input_path="/dummy/input.mp4",
                output_path=output_path,
                output_params=output_params,
                has_audio=False,
            )

            # ffmpegが呼び出されたことを確認
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]

            # 音声関連のオプションが含まれていないこと
            assert "-map" not in call_args
            assert "-c:a" not in call_args

    @patch("subprocess.run")
    def test_create_prores_video_with_audio(self, mock_run):
        """音声ありでProRes動画を作成できること"""
        mock_run.return_value = Mock(returncode=0, stderr="")
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        with tempfile.TemporaryDirectory() as temp_dir:
            frames_dir = Path(temp_dir)
            output_path = str(frames_dir / "output.mov")
            output_params = self._create_output_params()

            processor._create_prores_video(
                frames_dir=frames_dir,
                input_path="/dummy/input.mp4",
                output_path=output_path,
                output_params=output_params,
                has_audio=True,
            )

            # ffmpegが呼び出されたことを確認
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]

            # 音声関連のオプションが含まれていること
            assert "-c:a" in call_args
            assert "aac" in call_args

    @patch("subprocess.run")
    def test_create_prores_video_ffmpeg_error(self, mock_run):
        """ffmpegエラー時にRuntimeErrorを発生すること"""
        mock_run.return_value = Mock(returncode=1, stderr="Error: Invalid input")
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        with tempfile.TemporaryDirectory() as temp_dir:
            frames_dir = Path(temp_dir)
            output_path = str(frames_dir / "output.mov")
            output_params = self._create_output_params()

            with pytest.raises(RuntimeError) as exc_info:
                processor._create_prores_video(
                    frames_dir=frames_dir,
                    input_path="/dummy/input.mp4",
                    output_path=output_path,
                    output_params=output_params,
                    has_audio=False,
                )

            assert "ffmpegエラー" in str(exc_info.value)
            assert "Invalid input" in str(exc_info.value)


class TestVideoProcessorBuildFfmpegCommand:
    """VideoProcessor._build_ffmpeg_command メソッドのテスト"""

    def _create_output_params(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
        original_width: int | None = None,
        original_height: int | None = None,
        original_fps: float | None = None,
    ) -> OutputParams:
        """テスト用のOutputParamsを作成するヘルパー"""
        return OutputParams(
            width=width,
            height=height,
            fps=fps,
            original_width=original_width or width,
            original_height=original_height or height,
            original_fps=original_fps or fps,
            is_adjusted=(original_width is not None or original_fps is not None),
        )

    def test_build_command_basic_structure(self):
        """基本的なコマンド構造が正しいこと"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        with tempfile.TemporaryDirectory() as temp_dir:
            frames_dir = Path(temp_dir)
            output_params = self._create_output_params()

            cmd = processor._build_ffmpeg_command(
                frames_dir=frames_dir,
                input_path="/dummy/input.mp4",
                output_path="/dummy/output.mov",
                output_params=output_params,
                has_audio=False,
            )

            # 基本要素が含まれていること
            assert cmd[0] == "ffmpeg"
            assert "-y" in cmd
            assert "-c:v" in cmd
            assert "prores_ks" in cmd
            assert "/dummy/output.mov" in cmd

    def test_build_command_with_resolution_scaling(self):
        """解像度スケーリングが適用されること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        with tempfile.TemporaryDirectory() as temp_dir:
            frames_dir = Path(temp_dir)
            # 解像度が調整されたパラメータ
            output_params = self._create_output_params(
                width=960,
                height=540,
                original_width=1920,
                original_height=1080,
            )

            cmd = processor._build_ffmpeg_command(
                frames_dir=frames_dir,
                input_path="/dummy/input.mp4",
                output_path="/dummy/output.mov",
                output_params=output_params,
                has_audio=False,
            )

            # スケールフィルタが含まれていること
            assert "-vf" in cmd
            vf_index = cmd.index("-vf")
            assert "scale=960:540" in cmd[vf_index + 1]

    def test_build_command_without_audio_no_audio_options(self):
        """音声なしの場合、音声オプションが含まれないこと"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        with tempfile.TemporaryDirectory() as temp_dir:
            frames_dir = Path(temp_dir)
            output_params = self._create_output_params()

            cmd = processor._build_ffmpeg_command(
                frames_dir=frames_dir,
                input_path="/dummy/input.mp4",
                output_path="/dummy/output.mov",
                output_params=output_params,
                has_audio=False,
            )

            assert "-c:a" not in cmd
            assert "-map" not in cmd
            assert "-shortest" not in cmd

    def test_build_command_with_audio_has_audio_options(self):
        """音声ありの場合、音声オプションが含まれること"""
        mock_model = Mock()

        with patch("src.video_processor.find_ffmpeg", return_value="ffmpeg"):
            processor = VideoProcessor(model=mock_model)

        with tempfile.TemporaryDirectory() as temp_dir:
            frames_dir = Path(temp_dir)
            output_params = self._create_output_params()

            cmd = processor._build_ffmpeg_command(
                frames_dir=frames_dir,
                input_path="/dummy/input.mp4",
                output_path="/dummy/output.mov",
                output_params=output_params,
                has_audio=True,
            )

            assert "-c:a" in cmd
            assert "aac" in cmd
            assert "-map" in cmd
            assert "-shortest" in cmd


class TestGetVideoInfoEdgeCases:
    """get_video_info関数のエッジケーステスト"""

    def test_fps_zero_handling(self):
        """fps=0の場合のduration計算"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            temp_path = f.name

        try:
            # fps=0の動画をシミュレート（モックで）
            with patch("cv2.VideoCapture") as mock_cap_class:
                mock_cap = Mock()
                mock_cap.isOpened.return_value = True
                mock_cap.get.side_effect = lambda prop: {
                    cv2.CAP_PROP_FRAME_WIDTH: 640,
                    cv2.CAP_PROP_FRAME_HEIGHT: 480,
                    cv2.CAP_PROP_FPS: 0,  # fps = 0
                    cv2.CAP_PROP_FRAME_COUNT: 100,
                }.get(prop, 0)
                mock_cap_class.return_value = mock_cap

                with patch("src.video_processor._check_audio_stream", return_value=False):
                    info = get_video_info(temp_path)

                # fps=0の場合、durationも0になる
                assert info.duration == 0
        finally:
            os.unlink(temp_path)


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
            with (
                patch.object(processor, "_process_frames"),
                patch.object(processor, "_create_prores_video"),
            ):
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


class TestCalculateOptimalParams:
    """calculate_optimal_params関数のテスト

    動画サイズに合わせて動的に段階的に容量が削減されることを確認する。
    """

    # 目標サイズ（安全マージン込み）
    TARGET_SIZE_MB = MAX_FILE_SIZE_MB * SAFETY_MARGIN

    def test_short_video_no_adjustment(self):
        """短い動画は調整不要であること"""
        # 1920x1080, 30fps, 60秒 → 推定約356MB（目標921.6MB以下）
        params = calculate_optimal_params(
            width=1920,
            height=1080,
            fps=30.0,
            duration_sec=60.0,
        )

        # 調整なし
        assert params.is_adjusted is False
        assert params.width == 1920
        assert params.height == 1080
        assert params.fps == 30.0

        # 推定サイズが目標以下であること
        estimated = estimate_prores_size_mb(
            params.width, params.height, params.fps, 60.0
        )
        assert estimated <= self.TARGET_SIZE_MB

    def test_medium_video_fps_reduction_only(self):
        """中程度の動画はfps削減のみで対応すること"""
        # 1920x1080, 60fps, 120秒 → 推定約1424MB → fps削減で対応
        params = calculate_optimal_params(
            width=1920,
            height=1080,
            fps=60.0,
            duration_sec=120.0,
        )

        # fpsのみ調整、解像度は維持
        assert params.is_adjusted is True
        assert params.width == 1920
        assert params.height == 1080
        assert params.fps < 60.0  # fpsが削減されている
        assert params.fps >= 24.0  # 下限24fps

        # 推定サイズが目標以下であること
        estimated = estimate_prores_size_mb(
            params.width, params.height, params.fps, 120.0
        )
        assert estimated <= self.TARGET_SIZE_MB

    def test_long_video_fps_and_resolution_reduction(self):
        """長い動画はfps削減＋解像度削減で対応すること"""
        # 1920x1080, 30fps, 469.83秒 → 推定約2787MB → fps＋解像度削減
        params = calculate_optimal_params(
            width=1920,
            height=1080,
            fps=30.0,
            duration_sec=469.83,
        )

        # 調整あり
        assert params.is_adjusted is True

        # 解像度が削減されていること
        assert params.width < 1920 or params.height < 1080

        # fpsは24fps以上（下限）
        assert params.fps >= 24.0

        # 推定サイズが目標以下であること
        estimated = estimate_prores_size_mb(
            params.width, params.height, params.fps, 469.83
        )
        assert estimated <= self.TARGET_SIZE_MB

    def test_4k_video_adjustment(self):
        """4K動画でも1GB以下に収まること"""
        # 3840x2160, 30fps, 120秒 → 推定約2848MB
        params = calculate_optimal_params(
            width=3840,
            height=2160,
            fps=30.0,
            duration_sec=120.0,
        )

        # 調整あり
        assert params.is_adjusted is True

        # 推定サイズが目標以下であること
        estimated = estimate_prores_size_mb(
            params.width, params.height, params.fps, 120.0
        )
        assert estimated <= self.TARGET_SIZE_MB
        assert estimated <= MAX_FILE_SIZE_MB  # 絶対に1GB以下

    def test_fps_reduction_order(self):
        """fps削減は60→30→24の順で行われること"""
        # 60fpsの動画でfps削減が必要なケース
        # 1920x1080, 60fps, 100秒 → 推定約1187MB
        params = calculate_optimal_params(
            width=1920,
            height=1080,
            fps=60.0,
            duration_sec=100.0,
        )

        # 30fpsに削減されているはず（60→30で約593MB）
        assert params.fps == 30.0
        assert params.width == 1920  # 解像度は維持

    def test_fps_minimum_is_24(self):
        """fpsの下限は24fpsであること"""
        # 非常に長い動画でもfpsは24fps未満にならない
        params = calculate_optimal_params(
            width=1920,
            height=1080,
            fps=60.0,
            duration_sec=1000.0,  # 非常に長い
        )

        # fpsは24fps以上
        assert params.fps >= 24.0

    def test_resolution_is_even_number(self):
        """出力解像度は偶数であること（ffmpegの要件）"""
        params = calculate_optimal_params(
            width=1920,
            height=1080,
            fps=30.0,
            duration_sec=500.0,
        )

        # 幅・高さが偶数であること
        assert params.width % 2 == 0
        assert params.height % 2 == 0

    def test_original_values_preserved(self):
        """元の値が保持されること"""
        params = calculate_optimal_params(
            width=1920,
            height=1080,
            fps=60.0,
            duration_sec=300.0,
        )

        # 元の値が保持されている
        assert params.original_width == 1920
        assert params.original_height == 1080
        assert params.original_fps == 60.0

    def test_always_under_1gb(self):
        """様々なケースで必ず1GB以下になること"""
        test_cases = [
            (1920, 1080, 30.0, 60.0),    # 短い
            (1920, 1080, 30.0, 300.0),   # 中程度
            (1920, 1080, 30.0, 600.0),   # 長い
            (1920, 1080, 60.0, 300.0),   # 高fps
            (3840, 2160, 30.0, 120.0),   # 4K
            (3840, 2160, 60.0, 180.0),   # 4K高fps
            (1280, 720, 30.0, 1800.0),   # HD長時間
        ]

        for width, height, fps, duration in test_cases:
            params = calculate_optimal_params(width, height, fps, duration)
            estimated = estimate_prores_size_mb(
                params.width, params.height, params.fps, duration
            )

            # 目標サイズ以下であること
            assert estimated <= self.TARGET_SIZE_MB, (
                f"Failed for {width}x{height}@{fps}fps, {duration}s: "
                f"estimated={estimated:.1f}MB > target={self.TARGET_SIZE_MB:.1f}MB"
            )

            # 絶対に1GB以下であること
            assert estimated <= MAX_FILE_SIZE_MB, (
                f"Exceeded 1GB for {width}x{height}@{fps}fps, {duration}s: "
                f"estimated={estimated:.1f}MB"
            )


class TestEstimateProresSize:
    """estimate_prores_size_mb関数のテスト"""

    def test_estimate_basic(self):
        """基本的な推定計算が正しいこと"""
        # 1920x1080, 30fps, 60秒
        size = estimate_prores_size_mb(1920, 1080, 30.0, 60.0)

        # 計算: 1920 * 1080 * 0.8 * 30 * 60 / 8 / 1024 / 1024 ≈ 356MB
        assert 350 < size < 360

    def test_estimate_proportional_to_resolution(self):
        """推定サイズは解像度に比例すること"""
        size_1080p = estimate_prores_size_mb(1920, 1080, 30.0, 60.0)
        size_720p = estimate_prores_size_mb(1280, 720, 30.0, 60.0)

        # 720pは1080pの約44%のピクセル数
        ratio = (1280 * 720) / (1920 * 1080)
        assert abs(size_720p / size_1080p - ratio) < 0.01

    def test_estimate_proportional_to_fps(self):
        """推定サイズはfpsに比例すること"""
        size_30fps = estimate_prores_size_mb(1920, 1080, 30.0, 60.0)
        size_60fps = estimate_prores_size_mb(1920, 1080, 60.0, 60.0)

        # 60fpsは30fpsの2倍
        assert abs(size_60fps / size_30fps - 2.0) < 0.01

    def test_estimate_proportional_to_duration(self):
        """推定サイズは長さに比例すること"""
        size_60s = estimate_prores_size_mb(1920, 1080, 30.0, 60.0)
        size_120s = estimate_prores_size_mb(1920, 1080, 30.0, 120.0)

        # 120秒は60秒の2倍
        assert abs(size_120s / size_60s - 2.0) < 0.01
