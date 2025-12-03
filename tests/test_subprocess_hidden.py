"""subprocess ウィンドウ非表示機能のテスト

Windowsでsubprocessを実行する際にコンソールウィンドウを
非表示にするための_get_subprocess_args関数をテストする。
"""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.video_processor import _get_subprocess_args


class TestGetSubprocessArgs:
    """_get_subprocess_args関数のテスト"""

    def test_returns_dict(self):
        """戻り値がdict型であること"""
        result = _get_subprocess_args()
        assert isinstance(result, dict)

    def test_non_windows_returns_empty_dict(self):
        """非Windows環境（現在の環境）では空のdictが返されること"""
        if sys.platform != "win32":
            result = _get_subprocess_args()
            assert result == {}

    @patch("src.video_processor.sys.platform", "darwin")
    def test_macos_returns_empty_dict(self):
        """macOS環境では空のdictが返されること"""
        result = _get_subprocess_args()
        assert result == {}

    @patch("src.video_processor.sys.platform", "linux")
    def test_linux_returns_empty_dict(self):
        """Linux環境では空のdictが返されること"""
        result = _get_subprocess_args()
        assert result == {}

    def test_non_windows_args_can_be_unpacked_to_subprocess_run(self):
        """非Windows環境の戻り値がsubprocess.runに展開可能であること"""
        with patch("src.video_processor.sys.platform", "darwin"):
            args = _get_subprocess_args()
            # 空のdictなのでエラーなく展開できる
            assert args == {}


class TestGetSubprocessArgsWindows:
    """Windows環境での_get_subprocess_args関数のテスト（モック使用）

    注意: subprocess.STARTUPINFOなどのWindows専用属性は非Windows環境には
    存在しないため、create=Trueオプションでモックを作成する。
    """

    @pytest.fixture
    def mock_subprocess_windows(self):
        """Windows用subprocess属性をモックするフィクスチャ"""
        mock_startupinfo_class = MagicMock()
        mock_startupinfo_instance = MagicMock()
        mock_startupinfo_instance.dwFlags = 0
        mock_startupinfo_instance.wShowWindow = 0
        mock_startupinfo_class.return_value = mock_startupinfo_instance

        return {
            "STARTUPINFO": mock_startupinfo_class,
            "STARTF_USESHOWWINDOW": 1,
            "SW_HIDE": 0,
            "CREATE_NO_WINDOW": 0x08000000,
            "instance": mock_startupinfo_instance,
        }

    def test_windows_returns_startupinfo(self, mock_subprocess_windows):
        """Windows環境ではstartupinfoが含まれること"""
        with (
            patch("src.video_processor.sys.platform", "win32"),
            patch(
                "src.video_processor.subprocess.STARTUPINFO",
                mock_subprocess_windows["STARTUPINFO"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.STARTF_USESHOWWINDOW",
                mock_subprocess_windows["STARTF_USESHOWWINDOW"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.SW_HIDE",
                mock_subprocess_windows["SW_HIDE"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.CREATE_NO_WINDOW",
                mock_subprocess_windows["CREATE_NO_WINDOW"],
                create=True,
            ),
        ):
            result = _get_subprocess_args()

            assert "startupinfo" in result
            # STARTUPINFOが呼び出されたことを確認
            mock_subprocess_windows["STARTUPINFO"].assert_called_once()

    def test_windows_returns_creationflags(self, mock_subprocess_windows):
        """Windows環境ではcreationflagsが含まれること"""
        with (
            patch("src.video_processor.sys.platform", "win32"),
            patch(
                "src.video_processor.subprocess.STARTUPINFO",
                mock_subprocess_windows["STARTUPINFO"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.STARTF_USESHOWWINDOW",
                mock_subprocess_windows["STARTF_USESHOWWINDOW"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.SW_HIDE",
                mock_subprocess_windows["SW_HIDE"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.CREATE_NO_WINDOW",
                mock_subprocess_windows["CREATE_NO_WINDOW"],
                create=True,
            ),
        ):
            result = _get_subprocess_args()

            assert "creationflags" in result
            assert result["creationflags"] == 0x08000000  # CREATE_NO_WINDOW

    def test_windows_startupinfo_flags_are_set(self, mock_subprocess_windows):
        """Windows環境のstartupinfoに正しいフラグが設定されること"""
        with (
            patch("src.video_processor.sys.platform", "win32"),
            patch(
                "src.video_processor.subprocess.STARTUPINFO",
                mock_subprocess_windows["STARTUPINFO"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.STARTF_USESHOWWINDOW",
                mock_subprocess_windows["STARTF_USESHOWWINDOW"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.SW_HIDE",
                mock_subprocess_windows["SW_HIDE"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.CREATE_NO_WINDOW",
                mock_subprocess_windows["CREATE_NO_WINDOW"],
                create=True,
            ),
        ):
            result = _get_subprocess_args()

            # startupinfoが含まれていること
            assert "startupinfo" in result

            # dwFlagsにSTARTF_USESHOWWINDOW（ビット演算）が設定されていることを確認
            startupinfo = result["startupinfo"]
            # モックのdwFlagsが更新されていること（ビット演算で1が設定される）
            assert startupinfo.dwFlags == 1  # STARTF_USESHOWWINDOW

            # wShowWindowにSW_HIDE（0）が設定されていること
            assert startupinfo.wShowWindow == 0  # SW_HIDE

    def test_windows_multiple_calls_return_new_instances(self, mock_subprocess_windows):
        """Windows環境で複数回呼び出すと新しいインスタンスが返されること"""
        call_count = 0

        def create_new_instance():
            nonlocal call_count
            call_count += 1
            instance = MagicMock()
            instance.dwFlags = 0
            instance.wShowWindow = 0
            instance.call_id = call_count
            return instance

        mock_subprocess_windows["STARTUPINFO"].side_effect = create_new_instance

        with (
            patch("src.video_processor.sys.platform", "win32"),
            patch(
                "src.video_processor.subprocess.STARTUPINFO",
                mock_subprocess_windows["STARTUPINFO"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.STARTF_USESHOWWINDOW",
                mock_subprocess_windows["STARTF_USESHOWWINDOW"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.SW_HIDE",
                mock_subprocess_windows["SW_HIDE"],
                create=True,
            ),
            patch(
                "src.video_processor.subprocess.CREATE_NO_WINDOW",
                mock_subprocess_windows["CREATE_NO_WINDOW"],
                create=True,
            ),
        ):
            result1 = _get_subprocess_args()
            result2 = _get_subprocess_args()

            # 異なるインスタンスであること
            assert result1["startupinfo"] is not result2["startupinfo"]
            assert result1["startupinfo"].call_id == 1
            assert result2["startupinfo"].call_id == 2


class TestGetSubprocessArgsRealWindows:
    """実際のWindows環境でのテスト（Windowsでのみ実行）"""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows専用テスト")
    def test_real_windows_returns_valid_startupinfo(self):
        """実際のWindows環境でSTARTUPINFOが返されること"""
        result = _get_subprocess_args()

        assert "startupinfo" in result
        assert isinstance(result["startupinfo"], subprocess.STARTUPINFO)
        assert result["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
        assert result["startupinfo"].wShowWindow == subprocess.SW_HIDE

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows専用テスト")
    def test_real_windows_returns_valid_creationflags(self):
        """実際のWindows環境でCREATE_NO_WINDOWが返されること"""
        result = _get_subprocess_args()

        assert "creationflags" in result
        assert result["creationflags"] == subprocess.CREATE_NO_WINDOW

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows専用テスト")
    def test_real_windows_subprocess_run_with_args(self):
        """実際のWindows環境でsubprocess.runに引数を渡せること"""
        args = _get_subprocess_args()

        # 実際にコマンドを実行してエラーが出ないことを確認
        result = subprocess.run(
            ["cmd", "/c", "echo", "test"],
            capture_output=True,
            text=True,
            **args,
        )
        assert result.returncode == 0
