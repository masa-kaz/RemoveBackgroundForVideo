# -*- coding: utf-8 -*-
"""ビルドスクリプトの検証テスト

ビルドスクリプトが正しい設定になっているかを検証する。
"""

import re
from pathlib import Path

import pytest

from src.rvm_model import MODEL_URLS


# プロジェクトルートとビルドスクリプトのパス
PROJECT_ROOT = Path(__file__).parent.parent
BUILD_MAC_SH = PROJECT_ROOT / "build_mac.sh"
BUILD_GPU_BAT = PROJECT_ROOT / "build_gpu.bat"
BUILD_CPU_BAT = PROJECT_ROOT / "build_cpu.bat"

# 期待されるモデルファイル名
EXPECTED_MODEL_FILENAME = "rvm_mobilenetv3.torchscript"


class TestBuildScriptsExist:
    """ビルドスクリプトファイルの存在確認"""

    def test_build_mac_sh_exists(self):
        """build_mac.shが存在すること"""
        assert BUILD_MAC_SH.exists(), f"ファイルが見つかりません: {BUILD_MAC_SH}"

    def test_build_gpu_bat_exists(self):
        """build_gpu.batが存在すること"""
        assert BUILD_GPU_BAT.exists(), f"ファイルが見つかりません: {BUILD_GPU_BAT}"

    def test_build_cpu_bat_exists(self):
        """build_cpu.batが存在すること"""
        assert BUILD_CPU_BAT.exists(), f"ファイルが見つかりません: {BUILD_CPU_BAT}"


class TestBuildMacSh:
    """build_mac.sh の検証"""

    @pytest.fixture
    def script_content(self):
        """スクリプト内容を読み込む"""
        return BUILD_MAC_SH.read_text(encoding="utf-8")

    def test_checks_correct_model_filename(self, script_content):
        """正しいモデルファイル名をチェックしていること"""
        assert EXPECTED_MODEL_FILENAME in script_content, (
            f"build_mac.shで {EXPECTED_MODEL_FILENAME} がチェックされていません"
        )

    def test_model_url_matches_rvm_model(self, script_content):
        """ダウンロードURLがrvm_model.pyと一致すること"""
        expected_url = MODEL_URLS["mobilenetv3"]
        assert expected_url in script_content, (
            f"build_mac.shのダウンロードURLがrvm_model.pyと一致しません\n"
            f"期待: {expected_url}"
        )

    def test_includes_models_in_bundle(self, script_content):
        """modelsフォルダがバンドルに含まれること"""
        assert '--add-data "models:models"' in script_content, (
            "build_mac.shでmodelsフォルダがバンドルに含まれていません"
        )

    def test_checks_ffmpeg(self, script_content):
        """ffmpegのチェックが含まれること"""
        assert "ffmpeg" in script_content.lower(), (
            "build_mac.shでffmpegのチェックが含まれていません"
        )


class TestBuildGpuBat:
    """build_gpu.bat の検証"""

    @pytest.fixture
    def script_content(self):
        """スクリプト内容を読み込む"""
        return BUILD_GPU_BAT.read_text(encoding="utf-8")

    def test_checks_correct_model_filename(self, script_content):
        """正しいモデルファイル名をチェックしていること"""
        assert EXPECTED_MODEL_FILENAME in script_content, (
            f"build_gpu.batで {EXPECTED_MODEL_FILENAME} がチェックされていません"
        )

    def test_model_url_matches_rvm_model(self, script_content):
        """ダウンロードURLがrvm_model.pyと一致すること"""
        expected_url = MODEL_URLS["mobilenetv3"]
        assert expected_url in script_content, (
            f"build_gpu.batのダウンロードURLがrvm_model.pyと一致しません\n"
            f"期待: {expected_url}"
        )

    def test_includes_models_in_bundle(self, script_content):
        """modelsフォルダがバンドルに含まれること"""
        assert '--add-data "models;models"' in script_content, (
            "build_gpu.batでmodelsフォルダがバンドルに含まれていません"
        )

    def test_includes_ffmpeg_in_bundle(self, script_content):
        """ffmpegフォルダがバンドルに含まれること"""
        assert '--add-data "ffmpeg;ffmpeg"' in script_content, (
            "build_gpu.batでffmpegフォルダがバンドルに含まれていません"
        )

    def test_checks_ffmpeg_exe(self, script_content):
        """ffmpeg.exeのチェックが含まれること"""
        assert "ffmpeg.exe" in script_content, (
            "build_gpu.batでffmpeg.exeのチェックが含まれていません"
        )

    def test_uses_cuda_pytorch(self, script_content):
        """CUDA版PyTorchをインストールすること"""
        assert "cu118" in script_content or "cuda" in script_content.lower(), (
            "build_gpu.batでCUDA版PyTorchがインストールされていません"
        )


class TestBuildCpuBat:
    """build_cpu.bat の検証"""

    @pytest.fixture
    def script_content(self):
        """スクリプト内容を読み込む"""
        return BUILD_CPU_BAT.read_text(encoding="utf-8")

    def test_checks_correct_model_filename(self, script_content):
        """正しいモデルファイル名をチェックしていること"""
        assert EXPECTED_MODEL_FILENAME in script_content, (
            f"build_cpu.batで {EXPECTED_MODEL_FILENAME} がチェックされていません"
        )

    def test_model_url_matches_rvm_model(self, script_content):
        """ダウンロードURLがrvm_model.pyと一致すること"""
        expected_url = MODEL_URLS["mobilenetv3"]
        assert expected_url in script_content, (
            f"build_cpu.batのダウンロードURLがrvm_model.pyと一致しません\n"
            f"期待: {expected_url}"
        )

    def test_includes_models_in_bundle(self, script_content):
        """modelsフォルダがバンドルに含まれること"""
        assert '--add-data "models;models"' in script_content, (
            "build_cpu.batでmodelsフォルダがバンドルに含まれていません"
        )

    def test_includes_ffmpeg_in_bundle(self, script_content):
        """ffmpegフォルダがバンドルに含まれること"""
        assert '--add-data "ffmpeg;ffmpeg"' in script_content, (
            "build_cpu.batでffmpegフォルダがバンドルに含まれていません"
        )

    def test_checks_ffmpeg_exe(self, script_content):
        """ffmpeg.exeのチェックが含まれること"""
        assert "ffmpeg.exe" in script_content, (
            "build_cpu.batでffmpeg.exeのチェックが含まれていません"
        )

    def test_uses_cpu_pytorch(self, script_content):
        """CPU版PyTorchをインストールすること"""
        assert "whl/cpu" in script_content, (
            "build_cpu.batでCPU版PyTorchがインストールされていません"
        )


class TestModelFileConsistency:
    """モデルファイル設定の一貫性検証"""

    def test_model_file_exists(self):
        """モデルファイルが存在すること"""
        model_path = PROJECT_ROOT / "models" / EXPECTED_MODEL_FILENAME
        assert model_path.exists(), (
            f"モデルファイルが見つかりません: {model_path}\n"
            f"ダウンロード: {MODEL_URLS['mobilenetv3']}"
        )

    def test_all_scripts_use_same_model_filename(self):
        """全ビルドスクリプトが同じモデルファイル名を使用すること"""
        scripts = [BUILD_MAC_SH, BUILD_GPU_BAT, BUILD_CPU_BAT]

        for script_path in scripts:
            content = script_path.read_text(encoding="utf-8")
            assert EXPECTED_MODEL_FILENAME in content, (
                f"{script_path.name}で {EXPECTED_MODEL_FILENAME} が使用されていません"
            )

    def test_rvm_model_default_path_matches(self):
        """rvm_model.pyのデフォルトパスがビルドスクリプトと一致すること"""
        from src.rvm_model import RVMModel

        model = RVMModel()
        expected_path = PROJECT_ROOT / "models" / EXPECTED_MODEL_FILENAME

        assert model.model_path == expected_path, (
            f"rvm_model.pyのデフォルトパスがビルドスクリプトと一致しません\n"
            f"RVMModel: {model.model_path}\n"
            f"期待: {expected_path}"
        )
