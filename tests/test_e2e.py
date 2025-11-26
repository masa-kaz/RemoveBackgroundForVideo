# -*- coding: utf-8 -*-
"""E2E (End-to-End) テスト

実際の動画ファイルを使用した統合テスト。
テスト動画: tests/fixtures/TestVideo.mov, TestVideo.mp4
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.rvm_model import RVMModel
from src.video_processor import VideoProcessor, get_video_info, find_ffmpeg
from src.utils import get_device_info, is_supported_video


# テスト用動画のパス
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_VIDEO_MOV = FIXTURES_DIR / "TestVideo.mov"
TEST_VIDEO_MP4 = FIXTURES_DIR / "TestVideo.mp4"


class TestFixturesExist:
    """テスト用動画ファイルの存在確認"""

    def test_fixtures_directory_exists(self):
        """fixturesディレクトリが存在すること"""
        assert FIXTURES_DIR.exists()
        assert FIXTURES_DIR.is_dir()

    def test_test_video_mov_exists(self):
        """TestVideo.movが存在すること"""
        assert TEST_VIDEO_MOV.exists(), f"テスト動画が見つかりません: {TEST_VIDEO_MOV}"

    def test_test_video_mp4_exists(self):
        """TestVideo.mp4が存在すること"""
        assert TEST_VIDEO_MP4.exists(), f"テスト動画が見つかりません: {TEST_VIDEO_MP4}"


class TestVideoInfoE2E:
    """動画情報取得のE2Eテスト"""

    def test_get_video_info_mov(self):
        """MOV動画の情報を取得できること"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        info = get_video_info(str(TEST_VIDEO_MOV))

        assert info.width > 0
        assert info.height > 0
        assert info.fps > 0
        assert info.frame_count > 0
        assert info.duration > 0

    def test_get_video_info_mp4(self):
        """MP4動画の情報を取得できること"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        info = get_video_info(str(TEST_VIDEO_MP4))

        assert info.width > 0
        assert info.height > 0
        assert info.fps > 0
        assert info.frame_count > 0
        assert info.duration > 0

    def test_is_supported_video_mov(self):
        """MOVがサポート形式として認識されること"""
        assert is_supported_video(str(TEST_VIDEO_MOV)) is True

    def test_is_supported_video_mp4(self):
        """MP4がサポート形式として認識されること"""
        assert is_supported_video(str(TEST_VIDEO_MP4)) is True


class TestDeviceDetection:
    """デバイス検出のE2Eテスト"""

    def test_device_info_available(self):
        """デバイス情報を取得できること"""
        info = get_device_info()

        assert info.device is not None
        assert info.name is not None
        assert isinstance(info.is_gpu, bool)

    def test_device_is_functional(self):
        """検出されたデバイスが機能すること"""
        import torch

        info = get_device_info()
        device = info.device

        # 簡単なテンソル演算でデバイスが機能することを確認
        tensor = torch.zeros(1, device=device)
        result = tensor + 1

        assert result.item() == 1.0


@pytest.mark.skipif(
    not Path(__file__).parent.parent.joinpath("models", "rvm_mobilenetv3.torchscript").exists(),
    reason="RVMモデルがインストールされていません"
)
class TestModelLoadingE2E:
    """モデル読み込みのE2Eテスト"""

    def test_model_loads_successfully(self):
        """モデルが正常にロードできること"""
        model = RVMModel()
        model.load()

        assert model.is_loaded() is True

    def test_model_inference_works(self):
        """モデル推論が動作すること"""
        import torch

        model = RVMModel()
        model.load()

        # ダミーフレームで推論テスト
        dummy_frame = torch.rand(3, 480, 640)
        fgr, alpha = model.process_frame(dummy_frame)

        assert fgr.shape == (3, 480, 640)
        assert alpha.shape == (1, 480, 640)


@pytest.mark.skipif(
    not Path(__file__).parent.parent.joinpath("models", "rvm_mobilenetv3.torchscript").exists(),
    reason="RVMモデルがインストールされていません"
)
@pytest.mark.slow
class TestFullProcessingE2E:
    """フル処理のE2Eテスト（時間がかかる）"""

    def test_process_mp4_video(self):
        """MP4動画を処理できること"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        model = RVMModel()
        model.load()
        processor = VideoProcessor(model)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.mov")

            # 処理実行
            result = processor.process(
                input_path=str(TEST_VIDEO_MP4),
                output_path=output_path,
            )

            # 出力ファイルが生成されていること
            assert os.path.exists(result)
            assert os.path.getsize(result) > 0

    def test_process_mov_video(self):
        """MOV動画を処理できること"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        model = RVMModel()
        model.load()
        processor = VideoProcessor(model)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.mov")

            # 処理実行
            result = processor.process(
                input_path=str(TEST_VIDEO_MOV),
                output_path=output_path,
            )

            # 出力ファイルが生成されていること
            assert os.path.exists(result)
            assert os.path.getsize(result) > 0

    def test_progress_callback_called(self):
        """進捗コールバックが呼び出されること"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        model = RVMModel()
        model.load()
        processor = VideoProcessor(model)

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.mov")

            processor.process(
                input_path=str(TEST_VIDEO_MP4),
                output_path=output_path,
                progress_callback=on_progress,
            )

            # 進捗コールバックが呼び出されていること
            assert len(progress_calls) > 0

            # 最後のコールバックでcurrentとtotalが一致すること
            last_call = progress_calls[-1]
            assert last_call[0] == last_call[1]


@pytest.mark.skipif(
    not Path(__file__).parent.parent.joinpath("models", "rvm_mobilenetv3.torchscript").exists(),
    reason="RVMモデルがインストールされていません"
)
@pytest.mark.slow
class TestOutputValidation:
    """出力ファイルの検証テスト"""

    def _get_video_codec_info(self, video_path: str) -> dict:
        """ffprobeで動画のコーデック情報を取得"""
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path is None:
            pytest.skip("ffmpegが見つかりません")

        # ffprobeのパスを推測（ffmpegと同じディレクトリ）
        ffmpeg_dir = Path(ffmpeg_path).parent
        ffprobe_path = ffmpeg_dir / "ffprobe"
        if not ffprobe_path.exists():
            ffprobe_path = ffmpeg_dir / "ffprobe.exe"
        if not ffprobe_path.exists():
            # システムPATHから検索
            import shutil
            ffprobe_path = shutil.which("ffprobe")

        if ffprobe_path is None:
            pytest.skip("ffprobeが見つかりません")

        result = subprocess.run(
            [
                str(ffprobe_path),
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                video_path,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.fail(f"ffprobeの実行に失敗: {result.stderr}")

        import json
        return json.loads(result.stdout)

    def test_output_is_prores_4444(self):
        """出力がProRes 4444形式であること"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        model = RVMModel()
        model.load()
        processor = VideoProcessor(model)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.mov")

            processor.process(
                input_path=str(TEST_VIDEO_MP4),
                output_path=output_path,
            )

            # コーデック情報を取得
            info = self._get_video_codec_info(output_path)

            # 動画ストリームを探す
            video_stream = None
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            assert video_stream is not None, "動画ストリームが見つかりません"

            # ProRes 4444 (prores profile 4) であることを確認
            codec_name = video_stream.get("codec_name", "")
            assert codec_name == "prores", f"コーデックがProResではありません: {codec_name}"

            # プロファイルが4444であること（profile=4）
            profile = video_stream.get("profile", "")
            assert "4444" in profile, f"ProRes 4444ではありません: {profile}"

    def test_output_has_alpha_channel(self):
        """出力がアルファチャンネルを持つこと"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        model = RVMModel()
        model.load()
        processor = VideoProcessor(model)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.mov")

            processor.process(
                input_path=str(TEST_VIDEO_MP4),
                output_path=output_path,
            )

            # コーデック情報を取得
            info = self._get_video_codec_info(output_path)

            # 動画ストリームを探す
            video_stream = None
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            assert video_stream is not None, "動画ストリームが見つかりません"

            # ピクセルフォーマットがアルファを含むこと
            pix_fmt = video_stream.get("pix_fmt", "")
            # ProRes 4444のアルファ付きフォーマット
            assert "a" in pix_fmt or "alpha" in pix_fmt.lower(), \
                f"アルファチャンネルがありません: {pix_fmt}"

    def test_output_dimensions_match_input(self):
        """出力の解像度が入力と一致すること"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        model = RVMModel()
        model.load()
        processor = VideoProcessor(model)

        # 入力動画の情報を取得
        input_info = get_video_info(str(TEST_VIDEO_MP4))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.mov")

            processor.process(
                input_path=str(TEST_VIDEO_MP4),
                output_path=output_path,
            )

            # 出力動画の情報を取得
            output_info = get_video_info(output_path)

            # 解像度が一致すること
            assert output_info.width == input_info.width, \
                f"幅が一致しません: 入力={input_info.width}, 出力={output_info.width}"
            assert output_info.height == input_info.height, \
                f"高さが一致しません: 入力={input_info.height}, 出力={output_info.height}"

    def test_output_fps_matches_input(self):
        """出力のFPSが入力と一致すること"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        model = RVMModel()
        model.load()
        processor = VideoProcessor(model)

        # 入力動画の情報を取得
        input_info = get_video_info(str(TEST_VIDEO_MP4))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.mov")

            processor.process(
                input_path=str(TEST_VIDEO_MP4),
                output_path=output_path,
            )

            # 出力動画の情報を取得
            output_info = get_video_info(output_path)

            # FPSが一致すること（小数点以下の誤差を許容）
            assert abs(output_info.fps - input_info.fps) < 0.1, \
                f"FPSが一致しません: 入力={input_info.fps}, 出力={output_info.fps}"

    def test_output_frame_count_matches_input(self):
        """出力のフレーム数が入力とほぼ一致すること"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        model = RVMModel()
        model.load()
        processor = VideoProcessor(model)

        # 入力動画の情報を取得
        input_info = get_video_info(str(TEST_VIDEO_MP4))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.mov")

            processor.process(
                input_path=str(TEST_VIDEO_MP4),
                output_path=output_path,
            )

            # 出力動画の情報を取得
            output_info = get_video_info(output_path)

            # フレーム数がほぼ一致すること（1フレームの誤差を許容）
            # OpenCVとffmpegの間でフレームカウントに微小な差が生じることがある
            frame_diff = abs(output_info.frame_count - input_info.frame_count)
            assert frame_diff <= 1, \
                f"フレーム数の差が大きすぎます: 入力={input_info.frame_count}, 出力={output_info.frame_count}, 差={frame_diff}"
