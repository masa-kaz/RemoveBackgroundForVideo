"""utils.py のテスト"""

import os
import tempfile

import pytest
import torch

from src.utils import (
    SUPPORTED_INPUT_EXTENSIONS,
    DeviceInfo,
    ensure_directory,
    format_time,
    get_device,
    get_device_info,
    get_file_size_mb,
    get_output_path,
    is_supported_video,
)


class TestGetDevice:
    """get_device関数のテスト"""

    def test_returns_torch_device(self):
        """torch.deviceを返すこと"""
        device = get_device()
        assert isinstance(device, torch.device)

    def test_returns_valid_device_type(self):
        """有効なデバイスタイプを返すこと"""
        device = get_device()
        assert device.type in ["cuda", "mps", "cpu"]


class TestGetDeviceInfo:
    """get_device_info関数のテスト"""

    def test_returns_device_info(self):
        """DeviceInfoを返すこと"""
        info = get_device_info()
        assert isinstance(info, DeviceInfo)

    def test_device_info_has_required_fields(self):
        """DeviceInfoが必要なフィールドを持つこと"""
        info = get_device_info()
        assert hasattr(info, "device")
        assert hasattr(info, "name")
        assert hasattr(info, "is_gpu")
        assert hasattr(info, "warning")

    def test_device_info_device_is_torch_device(self):
        """DeviceInfo.deviceがtorch.deviceであること"""
        info = get_device_info()
        assert isinstance(info.device, torch.device)

    def test_device_info_name_is_string(self):
        """DeviceInfo.nameが文字列であること"""
        info = get_device_info()
        assert isinstance(info.name, str)
        assert len(info.name) > 0

    def test_device_info_is_gpu_is_bool(self):
        """DeviceInfo.is_gpuがブール値であること"""
        info = get_device_info()
        assert isinstance(info.is_gpu, bool)

    def test_cpu_device_has_warning(self):
        """CPUデバイスの場合は警告があること"""
        info = get_device_info()
        if info.device.type == "cpu":
            assert info.warning is not None
            assert "GPU" in info.warning

    def test_gpu_device_has_no_warning(self):
        """GPUデバイスの場合は警告がないこと"""
        info = get_device_info()
        if info.is_gpu:
            assert info.warning is None


class TestIsSupportedVideo:
    """is_supported_video関数のテスト"""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("video.mp4", True),
            ("video.MP4", True),
            ("video.mov", True),
            ("video.MOV", True),
            ("video.m4v", True),
            ("video.avi", False),
            ("video.mkv", False),
            ("video.wmv", False),
            ("video.txt", False),
            ("video", False),
        ],
    )
    def test_extension_detection(self, filename: str, expected: bool):
        """拡張子を正しく判定すること"""
        assert is_supported_video(filename) == expected

    def test_full_path(self):
        """フルパスでも正しく判定すること"""
        assert is_supported_video("/path/to/video.mp4") is True
        assert is_supported_video("/path/to/video.avi") is False


class TestGetOutputPath:
    """get_output_path関数のテスト"""

    def test_default_output_in_same_directory(self):
        """デフォルトでは入力と同じディレクトリに出力すること"""
        result = get_output_path("/path/to/input.mp4")
        assert result == "/path/to/input_nobg.mov"

    def test_custom_output_directory(self):
        """カスタム出力ディレクトリを指定できること"""
        result = get_output_path("/path/to/input.mp4", "/output")
        assert result == "/output/input_nobg.mov"

    def test_preserves_original_stem(self):
        """元のファイル名（拡張子なし）を保持すること"""
        result = get_output_path("/path/to/my_video.mov")
        assert "my_video_nobg" in result

    def test_always_outputs_mov(self):
        """常に.mov拡張子で出力すること"""
        for ext in [".mp4", ".mov", ".m4v"]:
            result = get_output_path(f"/path/to/video{ext}")
            assert result.endswith(".mov")


class TestEnsureDirectory:
    """ensure_directory関数のテスト"""

    def test_creates_directory(self):
        """ディレクトリを作成すること"""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = os.path.join(temp_dir, "new_dir", "sub_dir")
            assert not os.path.exists(new_dir)

            ensure_directory(new_dir)

            assert os.path.exists(new_dir)
            assert os.path.isdir(new_dir)

    def test_existing_directory(self):
        """既存のディレクトリでもエラーにならないこと"""
        with tempfile.TemporaryDirectory() as temp_dir:
            ensure_directory(temp_dir)  # エラーが発生しないこと


class TestGetFileSizeMb:
    """get_file_size_mb関数のテスト"""

    def test_returns_size_in_mb(self):
        """ファイルサイズをMB単位で返すこと"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # 1MBのデータを書き込む
            f.write(b"x" * (1024 * 1024))
            f.flush()

            try:
                size = get_file_size_mb(f.name)
                assert abs(size - 1.0) < 0.01  # 約1MB
            finally:
                os.unlink(f.name)


class TestFormatTime:
    """format_time関数のテスト"""

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0, "00:00"),
            (30, "00:30"),
            (60, "01:00"),
            (90, "01:30"),
            (3599, "59:59"),
            (3600, "01:00:00"),
            (3661, "01:01:01"),
            (7200, "02:00:00"),
        ],
    )
    def test_format_time(self, seconds: float, expected: str):
        """時間を正しくフォーマットすること"""
        assert format_time(seconds) == expected

    def test_fractional_seconds(self):
        """小数点以下の秒数を切り捨てること"""
        assert format_time(30.9) == "00:30"


class TestSupportedExtensions:
    """サポート拡張子の定数テスト"""

    def test_contains_required_extensions(self):
        """必須の拡張子が含まれていること"""
        required = {".mp4", ".mov"}
        assert required.issubset(SUPPORTED_INPUT_EXTENSIONS)


class TestGetFileSizeMbEdgeCases:
    """get_file_size_mb関数のエッジケーステスト"""

    def test_nonexistent_file_raises_error(self):
        """存在しないファイルでエラーを発生すること"""
        with pytest.raises(FileNotFoundError):
            get_file_size_mb("/nonexistent/path/file.mp4")

    def test_empty_file_returns_zero(self):
        """空のファイルは0を返すこと"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            size = get_file_size_mb(temp_path)
            assert size == 0.0
        finally:
            os.unlink(temp_path)


class TestEnsureDirectoryEdgeCases:
    """ensure_directory関数のエッジケーステスト"""

    def test_nested_directory_creation(self):
        """深くネストされたディレクトリを作成できること"""
        with tempfile.TemporaryDirectory() as temp_dir:
            deep_path = os.path.join(temp_dir, "a", "b", "c", "d", "e")
            assert not os.path.exists(deep_path)

            ensure_directory(deep_path)

            assert os.path.exists(deep_path)
            assert os.path.isdir(deep_path)

    def test_file_path_instead_of_directory(self):
        """ファイルパスを渡した場合はエラーになること"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name

        try:
            # 既存のファイルと同じパスにディレクトリを作成しようとする
            with pytest.raises((FileExistsError, OSError)):
                ensure_directory(temp_file)
        finally:
            os.unlink(temp_file)


class TestGetOutputPathEdgeCases:
    """get_output_path関数のエッジケーステスト"""

    def test_unicode_filename(self):
        """日本語ファイル名を正しく処理すること"""
        result = get_output_path("/path/to/動画ファイル.mp4")
        assert "動画ファイル_nobg" in result
        assert result.endswith(".mov")

    def test_filename_with_multiple_dots(self):
        """複数のドットを含むファイル名を正しく処理すること"""
        result = get_output_path("/path/to/my.video.file.mp4")
        assert "my.video.file_nobg" in result
        assert result.endswith(".mov")

    def test_filename_with_spaces(self):
        """スペースを含むファイル名を正しく処理すること"""
        result = get_output_path("/path/to/my video file.mp4")
        assert "my video file_nobg" in result
        assert result.endswith(".mov")


class TestIsSupportedVideoEdgeCases:
    """is_supported_video関数のエッジケーステスト"""

    def test_mixed_case_extension(self):
        """大文字小文字混在の拡張子を正しく判定すること"""
        assert is_supported_video("video.Mp4") is True
        assert is_supported_video("video.MoV") is True

    def test_empty_string(self):
        """空文字列はFalseを返すこと"""
        assert is_supported_video("") is False

    def test_filename_without_extension(self):
        """拡張子なしのファイル名"""
        assert is_supported_video("video") is False
        assert is_supported_video("videomp4") is False


class TestFormatTimeEdgeCases:
    """format_time関数のエッジケーステスト"""

    def test_negative_seconds(self):
        """負の秒数を処理すること"""
        # 負の値でも処理できることを確認（実装依存）
        result = format_time(-30)
        # 負の値の処理は実装による
        assert isinstance(result, str)

    def test_very_large_seconds(self):
        """非常に大きな秒数を処理すること"""
        # 100時間
        result = format_time(360000)
        assert "100:00:00" in result or result.startswith("100")
