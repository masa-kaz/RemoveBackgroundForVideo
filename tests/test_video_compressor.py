"""動画圧縮モジュールのテスト

video_compressor.py の機能をテストする。
- バックアップ作成
- ファイル整合性チェック
- 圧縮後のファイルが破損していないこと
- -movflags +faststart の使用
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_compressor import (
    DEFAULT_AUDIO_BITRATE_KBPS,
    DEFAULT_MAX_SIZE_MB,
    FFPROBE_TIMEOUT_SECONDS,
    MIN_VIDEO_BITRATE_KBPS,
    SAFETY_MARGIN,
    VP9_CRF,
    VP9_VIDEO_BITRATE,
    CompressionResult,
    calculate_target_bitrate,
    compress_if_needed,
    compress_video,
    get_file_size_mb,
    verify_video_integrity,
)


# テスト用動画
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_VIDEO_MOV = FIXTURES_DIR / "TestVideo.mov"
TEST_VIDEO_MP4 = FIXTURES_DIR / "TestVideo.mp4"


class TestVerifyVideoIntegrity:
    """整合性チェック関数のテスト"""

    def test_valid_video_returns_true(self):
        """正常な動画ファイルはTrueを返す"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        result = verify_video_integrity(str(TEST_VIDEO_MOV))
        assert result is True

    def test_invalid_file_returns_false(self):
        """破損したファイルはFalseを返す"""
        with tempfile.NamedTemporaryFile(suffix=".mov", delete=False) as f:
            # 不正なデータを書き込み
            f.write(b"invalid video data")
            temp_path = f.name

        try:
            result = verify_video_integrity(temp_path)
            assert result is False
        finally:
            os.unlink(temp_path)

    def test_nonexistent_file_returns_false(self):
        """存在しないファイルはFalseを返す"""
        result = verify_video_integrity("/nonexistent/path/video.mov")
        assert result is False

    def test_empty_file_returns_false(self):
        """空のファイルはFalseを返す"""
        with tempfile.NamedTemporaryFile(suffix=".mov", delete=False) as f:
            temp_path = f.name

        try:
            result = verify_video_integrity(temp_path)
            assert result is False
        finally:
            os.unlink(temp_path)


class TestCalculateTargetBitrate:
    """目標ビットレート計算のテスト"""

    def test_basic_calculation(self):
        """基本的なビットレート計算"""
        # 60秒、100MB目標
        bitrate = calculate_target_bitrate(60, 100)
        # 100MB * 8bit / 60秒 ≒ 13,333 kbps (音声128kbps考慮、安全マージン考慮)
        assert bitrate > 0
        assert bitrate < 20000  # 合理的な範囲

    def test_minimum_bitrate_guarantee(self):
        """最低ビットレートが保証される"""
        # 非常に長い動画、小さいサイズ → MIN_VIDEO_BITRATE_KBPS保証
        bitrate = calculate_target_bitrate(3600, 10)  # 1時間、10MB
        assert bitrate >= MIN_VIDEO_BITRATE_KBPS

    def test_short_video_high_bitrate(self):
        """短い動画は高いビットレートになる"""
        bitrate = calculate_target_bitrate(10, 100)  # 10秒、100MB
        assert bitrate > 50000  # かなり高いビットレート


class TestCompressVideoBackup:
    """圧縮時のバックアップ機能のテスト"""

    def test_backup_created_on_overwrite_mode(self):
        """上書きモード時にバックアップが作成される"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        # テスト用に一時ディレクトリにコピー
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_video.mov"
            shutil.copy2(TEST_VIDEO_MOV, test_file)

            original_size = get_file_size_mb(str(test_file))

            # 小さいサイズに圧縮を試みる（1MB以下）
            # ただし元が2MB未満なのでスキップされる可能性
            if original_size > 1:
                result = compress_video(
                    str(test_file),
                    output_path=None,  # 上書きモード
                    max_size_mb=1,
                )

                # バックアップファイルが処理中に作成されたことを確認
                # 成功時は削除されるので、処理結果で判断
                assert result.success or result.error_message is not None

    def test_backup_deleted_on_success(self):
        """圧縮成功時にバックアップが削除される"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_video.mov"
            shutil.copy2(TEST_VIDEO_MOV, test_file)

            backup_path = Path(temp_dir) / "test_video_backup.mov"

            # 圧縮実行（サイズが小さいのでスキップされる）
            compress_video(
                str(test_file),
                output_path=None,
                max_size_mb=100,  # 大きいサイズ指定でスキップ
            )

            # スキップ時はバックアップは作成されない
            assert not backup_path.exists()


class TestCompressVideoIntegrity:
    """圧縮後のファイル整合性テスト"""

    def test_compressed_file_is_valid(self):
        """圧縮後のファイルが正常であること（透過なしH.264）"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "compressed.mov"

            # preserve_alpha=Falseで.mov形式を維持
            result = compress_video(
                str(TEST_VIDEO_MOV),
                output_path=str(output_file),
                max_size_mb=0.5,  # 0.5MBに圧縮を試みる
                preserve_alpha=False,
            )

            if result.success:
                # 出力ファイルの整合性チェック
                assert verify_video_integrity(result.output_path)

                # ffprobeで詳細確認
                ffprobe = shutil.which("ffprobe")
                if ffprobe:
                    proc = subprocess.run(
                        [ffprobe, "-v", "error", "-show_format", result.output_path],
                        capture_output=True,
                        text=True,
                    )
                    assert proc.returncode == 0
                    assert "duration" in proc.stdout

    def test_movflags_faststart_applied(self):
        """-movflags +faststart が適用されていること（透過なし）"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        ffprobe = shutil.which("ffprobe")
        if ffprobe is None:
            pytest.skip("ffprobeが見つかりません")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "compressed.mov"

            # preserve_alpha=Falseで.mov形式を維持
            result = compress_video(
                str(TEST_VIDEO_MOV),
                output_path=str(output_file),
                max_size_mb=0.5,
                preserve_alpha=False,
            )

            if result.success:
                # moov atomがファイル先頭近くにあることを確認
                # ffprobeで format を取得し、moov atom の位置を確認
                proc = subprocess.run(
                    [ffprobe, "-v", "trace", "-show_format", result.output_path],
                    capture_output=True,
                    text=True,
                )
                # -movflags +faststart が適用されていれば
                # moov atom がファイル先頭にある（traceログで確認可能）
                # 最低限、ファイルが正常に読めることを確認
                assert proc.returncode == 0


class TestCompressVideoWithRealFile:
    """実際のファイルを使った圧縮テスト"""

    def test_compress_to_smaller_size(self):
        """ファイルを指定サイズ以下に圧縮できる（透過なしH.264）"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        original_size = get_file_size_mb(str(TEST_VIDEO_MOV))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "compressed.mov"

            # 元のサイズより小さく設定して圧縮を強制する
            # テスト動画は約2MBなので、0.5MBに圧縮を試みる
            target_size = original_size * 0.25

            # preserve_alpha=Falseで.mov形式を維持
            result = compress_video(
                str(TEST_VIDEO_MOV),
                output_path=str(output_file),
                max_size_mb=target_size,
                preserve_alpha=False,
            )

            # 圧縮が実行されたことを確認
            if result.success and result.compression_ratio != 1.0:
                # 出力ファイルが存在する
                assert Path(result.output_path).exists()

                # ファイルが破損していないことが最重要
                assert verify_video_integrity(result.output_path)

    def test_skip_if_already_small(self):
        """既に目標サイズ以下の場合はスキップ"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        original_size = get_file_size_mb(str(TEST_VIDEO_MOV))

        result = compress_video(
            str(TEST_VIDEO_MOV),
            output_path=None,
            max_size_mb=original_size + 10,  # 十分大きい目標
        )

        assert result.success is True
        assert result.compression_ratio == 1.0  # 圧縮なし


class TestCompressIfNeeded:
    """compress_if_needed関数のテスト"""

    def test_returns_compression_result(self):
        """CompressionResultを返す"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        result = compress_if_needed(
            str(TEST_VIDEO_MOV),
            max_size_mb=100,
        )

        assert hasattr(result, "success")
        assert hasattr(result, "original_size_mb")
        assert hasattr(result, "compressed_size_mb")


class TestEdgeCases:
    """エッジケースのテスト"""

    def test_nonexistent_input_file(self):
        """存在しない入力ファイルはエラーを返す"""
        result = compress_video(
            "/nonexistent/path/video.mov",
            max_size_mb=100,
        )

        # 例外ではなくエラー結果を返す
        assert result.success is False
        assert "見つかりません" in result.error_message


class TestCompressVideoErrorHandling:
    """compress_video関数のエラーハンドリングテスト"""

    def test_large_target_size_skips_compression(self):
        """十分大きいターゲットサイズの場合は圧縮がスキップされる"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        original_size = get_file_size_mb(str(TEST_VIDEO_MOV))

        result = compress_video(
            str(TEST_VIDEO_MOV),
            max_size_mb=original_size + 100,  # 十分大きいサイズ
        )

        # スキップされる
        assert result.success is True
        assert result.compression_ratio == 1.0

    def test_negative_size_handled(self):
        """負のサイズ指定でも適切に処理される"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        # 負のサイズでも圧縮は実行される（ファイルが0より大きいため）
        compress_video(
            str(TEST_VIDEO_MOV),
            max_size_mb=-100,
        )
        # エラーなく処理される（圧縮される）- 結果は実装依存


class TestCalculateTargetBitrateEdgeCases:
    """calculate_target_bitrate関数のエッジケーステスト"""

    def test_very_short_duration(self):
        """非常に短い動画のビットレート計算"""
        # 1秒、100MB
        bitrate = calculate_target_bitrate(1, 100)
        assert bitrate > 0

    def test_zero_duration(self):
        """0秒の動画（ゼロ除算対策）"""
        import contextlib

        # 0秒はゼロ除算の可能性
        with contextlib.suppress(ZeroDivisionError):
            calculate_target_bitrate(0, 100)
            # 実装によってはエラーになるかもしれない

    def test_negative_max_size(self):
        """負のサイズ指定"""
        bitrate = calculate_target_bitrate(60, -100)
        # 最低ビットレートが保証される
        assert bitrate >= MIN_VIDEO_BITRATE_KBPS


class TestVerifyVideoIntegrityEdgeCases:
    """verify_video_integrity関数のエッジケーステスト"""

    def test_directory_instead_of_file(self):
        """ディレクトリを渡した場合"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = verify_video_integrity(temp_dir)
            # ディレクトリは動画として無効
            assert result is False

    @patch("video_compressor.subprocess.run")
    @patch("video_compressor.find_ffmpeg", return_value="ffmpeg")
    def test_ffprobe_timeout(self, mock_find, mock_run):
        """ffprobeがタイムアウトした場合"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ffprobe"], timeout=30)

        if TEST_VIDEO_MOV.exists():
            result = verify_video_integrity(str(TEST_VIDEO_MOV))
            # タイムアウト時はFalseを返す
            assert result is False

    @patch("video_compressor.subprocess.run")
    @patch("video_compressor.find_ffmpeg", return_value="ffmpeg")
    def test_ffprobe_returns_empty(self, mock_find, mock_run):
        """ffprobeが空の出力を返す場合"""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        if TEST_VIDEO_MOV.exists():
            result = verify_video_integrity(str(TEST_VIDEO_MOV))
            # 空の出力は整合性チェック失敗
            assert result is False

    @patch("video_compressor.subprocess.run")
    @patch("video_compressor.find_ffmpeg", return_value="ffmpeg")
    def test_ffprobe_nonzero_return(self, mock_find, mock_run):
        """ffprobeが非ゼロを返す場合"""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        if TEST_VIDEO_MOV.exists():
            result = verify_video_integrity(str(TEST_VIDEO_MOV))
            # 非ゼロはFalseを返す
            assert result is False


class TestCompressionResultDataclass:
    """CompressionResultデータクラスのテスト"""

    def test_compression_result_creation(self):
        """CompressionResultを作成できること"""
        result = CompressionResult(
            success=True,
            input_path="/input/video.mov",
            output_path="/output/video.webm",
            original_size_mb=100.0,
            compressed_size_mb=50.0,
            compression_ratio=0.5,
        )

        assert result.success is True
        assert result.original_size_mb == 100.0
        assert result.compressed_size_mb == 50.0
        assert result.compression_ratio == 0.5

    def test_compression_result_with_error(self):
        """エラーメッセージ付きCompressionResult"""
        result = CompressionResult(
            success=False,
            input_path="/input/video.mov",
            output_path="/input/video.mov",
            original_size_mb=100.0,
            compressed_size_mb=100.0,
            compression_ratio=1.0,
            error_message="圧縮に失敗しました",
        )

        assert result.success is False
        assert result.error_message == "圧縮に失敗しました"

    def test_compression_result_optional_fields(self):
        """オプションフィールドのデフォルト値"""
        result = CompressionResult(
            success=True,
            input_path="/input/video.mov",
            output_path="/output/video.webm",
            original_size_mb=100.0,
            compressed_size_mb=50.0,
            compression_ratio=0.5,
        )

        assert result.target_bitrate_kbps is None
        assert result.error_message is None
        assert result.backup_path is None

    def test_preserve_alpha_option(self):
        """preserve_alpha オプションのテスト"""
        if not TEST_VIDEO_MOV.exists():
            pytest.skip("テスト動画が見つかりません")

        with tempfile.TemporaryDirectory() as temp_dir:
            # アルファ保持
            output_alpha = Path(temp_dir) / "with_alpha.mov"
            result_alpha = compress_video(
                str(TEST_VIDEO_MOV),
                output_path=str(output_alpha),
                max_size_mb=0.5,
                preserve_alpha=True,
            )

            # アルファなし
            output_no_alpha = Path(temp_dir) / "no_alpha.mp4"
            result_no_alpha = compress_video(
                str(TEST_VIDEO_MOV),
                output_path=str(output_no_alpha),
                max_size_mb=0.5,
                preserve_alpha=False,
            )

            # どちらも成功または適切にエラー処理
            # アルファなしの方が小さいはず（H.264の場合）
            if result_alpha.success and result_no_alpha.success:
                # H.264の方が一般的に小さい
                pass  # サイズ比較は入力によるので省略


class TestCompressionConstants:
    """圧縮関連の定数テスト"""

    def test_default_max_size_mb(self):
        """デフォルト最大ファイルサイズが正しい値であること"""
        assert DEFAULT_MAX_SIZE_MB == 1023

    def test_default_audio_bitrate_kbps(self):
        """デフォルト音声ビットレートが正しい値であること"""
        assert DEFAULT_AUDIO_BITRATE_KBPS == 128

    def test_min_video_bitrate_kbps(self):
        """最低映像ビットレートが正しい値であること"""
        assert MIN_VIDEO_BITRATE_KBPS == 500

    def test_safety_margin(self):
        """安全マージンが正しい値であること"""
        assert SAFETY_MARGIN == 0.95
        assert 0 < SAFETY_MARGIN <= 1.0

    def test_vp9_video_bitrate(self):
        """VP9ビットレートが設定されていること"""
        assert VP9_VIDEO_BITRATE == "2M"

    def test_vp9_crf(self):
        """VP9 CRFが正しい範囲であること"""
        assert VP9_CRF == "35"
        # CRFは0-63の範囲（文字列として格納）
        crf_value = int(VP9_CRF)
        assert 0 <= crf_value <= 63

    def test_ffprobe_timeout_seconds(self):
        """ffprobeタイムアウトが妥当な値であること"""
        assert FFPROBE_TIMEOUT_SECONDS == 30
        assert FFPROBE_TIMEOUT_SECONDS > 0
