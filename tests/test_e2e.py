# -*- coding: utf-8 -*-
"""E2E (End-to-End) テスト

実際の動画ファイルを使用した統合テスト。
テスト動画: tests/fixtures/TestVideo.mov, TestVideo.mp4
出力先: tests/fixtures/output/ (gitignore対象)

処理結果はモジュールスコープのフィクスチャで共有し、
MP4/MOVそれぞれ1回のみ処理を実行する。
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest

from src.rvm_model import RVMModel
from src.video_processor import VideoProcessor, get_video_info, find_ffmpeg
from src.utils import get_device_info, is_supported_video


# テスト用動画のパス
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_VIDEO_MOV = FIXTURES_DIR / "TestVideo.mov"
TEST_VIDEO_MP4 = FIXTURES_DIR / "TestVideo.mp4"

# E2Eテスト出力先ディレクトリ（gitignore対象）
OUTPUT_DIR = FIXTURES_DIR / "output"

# 出力ファイル名
OUTPUT_MP4_NOBG = "TestVideo_mp4_nobg.mov"
OUTPUT_MOV_NOBG = "TestVideo_mov_nobg.mov"


def ensure_output_dir() -> Path:
    """出力ディレクトリを作成し、パスを返す"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def get_output_path(name: str) -> Path:
    """出力ファイルのパスを取得（既存ファイルは上書き）"""
    ensure_output_dir()
    return OUTPUT_DIR / name


# =============================================================================
# モジュールスコープのフィクスチャ（処理結果を共有）
# =============================================================================

@pytest.fixture(scope="module")
def rvm_model():
    """RVMモデルのフィクスチャ（モジュールスコープで共有）"""
    model_path = Path(__file__).parent.parent / "models" / "rvm_mobilenetv3.torchscript"
    if not model_path.exists():
        pytest.skip("RVMモデルがインストールされていません")

    model = RVMModel()
    model.load()
    return model


@pytest.fixture(scope="module")
def processed_mp4_output(rvm_model) -> Path:
    """MP4動画の処理結果（モジュールスコープで共有）

    1回だけ処理を実行し、結果を複数のテストで共有する。
    """
    if not TEST_VIDEO_MP4.exists():
        pytest.skip("テスト動画が見つかりません")

    output_path = get_output_path(OUTPUT_MP4_NOBG)

    processor = VideoProcessor(rvm_model)
    processor.process(
        input_path=str(TEST_VIDEO_MP4),
        output_path=str(output_path),
    )

    return output_path


@pytest.fixture(scope="module")
def processed_mov_output(rvm_model) -> Path:
    """MOV動画の処理結果（モジュールスコープで共有）

    1回だけ処理を実行し、結果を複数のテストで共有する。
    """
    if not TEST_VIDEO_MOV.exists():
        pytest.skip("テスト動画が見つかりません")

    output_path = get_output_path(OUTPUT_MOV_NOBG)

    processor = VideoProcessor(rvm_model)
    processor.process(
        input_path=str(TEST_VIDEO_MOV),
        output_path=str(output_path),
    )

    return output_path


# =============================================================================
# 基本テスト（フィクスチャ不要）
# =============================================================================

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


# =============================================================================
# フル処理E2Eテスト（フィクスチャを使用）
# =============================================================================

@pytest.mark.slow
class TestFullProcessingE2E:
    """フル処理のE2Eテスト（時間がかかる）"""

    def test_process_mp4_video(self, processed_mp4_output):
        """MP4動画を処理できること"""
        # 出力ファイルが生成されていること
        assert processed_mp4_output.exists()
        assert processed_mp4_output.stat().st_size > 0

    def test_process_mov_video(self, processed_mov_output):
        """MOV動画を処理できること"""
        # 出力ファイルが生成されていること
        assert processed_mov_output.exists()
        assert processed_mov_output.stat().st_size > 0

    def test_progress_callback_called(self, rvm_model):
        """進捗コールバックが呼び出されること"""
        if not TEST_VIDEO_MP4.exists():
            pytest.skip("テスト動画が見つかりません")

        processor = VideoProcessor(rvm_model)

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        # このテストは進捗コールバックの動作確認のため、
        # 別途処理を実行する（出力は既存ファイルを上書き）
        output_path = get_output_path(OUTPUT_MP4_NOBG)

        processor.process(
            input_path=str(TEST_VIDEO_MP4),
            output_path=str(output_path),
            progress_callback=on_progress,
        )

        # 進捗コールバックが呼び出されていること
        assert len(progress_calls) > 0

        # 最後のコールバックでcurrentとtotalが一致すること
        last_call = progress_calls[-1]
        assert last_call[0] == last_call[1]


# =============================================================================
# 出力ファイル検証テスト（フィクスチャを使用）
# =============================================================================

def _get_video_codec_info(video_path: str) -> dict:
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

    return json.loads(result.stdout)


@pytest.mark.slow
class TestOutputValidation:
    """出力ファイルの検証テスト（フィクスチャで共有された出力を使用）"""

    def test_output_is_prores_4444(self, processed_mp4_output):
        """出力がProRes 4444形式であること"""
        # コーデック情報を取得
        info = _get_video_codec_info(str(processed_mp4_output))

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

    def test_output_has_alpha_channel(self, processed_mp4_output):
        """出力がアルファチャンネルを持つこと"""
        # コーデック情報を取得
        info = _get_video_codec_info(str(processed_mp4_output))

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

    def test_output_dimensions_match_input(self, processed_mp4_output):
        """出力の解像度が入力と一致すること"""
        # 入力動画の情報を取得
        input_info = get_video_info(str(TEST_VIDEO_MP4))

        # 出力動画の情報を取得
        output_info = get_video_info(str(processed_mp4_output))

        # 解像度が一致すること
        assert output_info.width == input_info.width, \
            f"幅が一致しません: 入力={input_info.width}, 出力={output_info.width}"
        assert output_info.height == input_info.height, \
            f"高さが一致しません: 入力={input_info.height}, 出力={output_info.height}"

    def test_output_fps_matches_input(self, processed_mp4_output):
        """出力のFPSが入力と一致すること"""
        # 入力動画の情報を取得
        input_info = get_video_info(str(TEST_VIDEO_MP4))

        # 出力動画の情報を取得
        output_info = get_video_info(str(processed_mp4_output))

        # FPSが一致すること（小数点以下の誤差を許容）
        assert abs(output_info.fps - input_info.fps) < 0.1, \
            f"FPSが一致しません: 入力={input_info.fps}, 出力={output_info.fps}"

    def test_output_frame_count_matches_input(self, processed_mp4_output):
        """出力のフレーム数が入力とほぼ一致すること"""
        # 入力動画の情報を取得
        input_info = get_video_info(str(TEST_VIDEO_MP4))

        # 出力動画の情報を取得
        output_info = get_video_info(str(processed_mp4_output))

        # フレーム数がほぼ一致すること（1フレームの誤差を許容）
        # OpenCVとffmpegの間でフレームカウントに微小な差が生じることがある
        frame_diff = abs(output_info.frame_count - input_info.frame_count)
        assert frame_diff <= 1, \
            f"フレーム数の差が大きすぎます: 入力={input_info.frame_count}, 出力={output_info.frame_count}, 差={frame_diff}"

    def test_mov_output_is_prores_4444(self, processed_mov_output):
        """MOV出力がProRes 4444形式であること"""
        # コーデック情報を取得
        info = _get_video_codec_info(str(processed_mov_output))

        # 動画ストリームを探す
        video_stream = None
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        assert video_stream is not None, "動画ストリームが見つかりません"

        # ProRes 4444であることを確認
        codec_name = video_stream.get("codec_name", "")
        assert codec_name == "prores", f"コーデックがProResではありません: {codec_name}"

        profile = video_stream.get("profile", "")
        assert "4444" in profile, f"ProRes 4444ではありません: {profile}"
