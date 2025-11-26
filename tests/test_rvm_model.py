# -*- coding: utf-8 -*-
"""rvm_model.py のテスト"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import torch

from src.rvm_model import RVMModel, download_model, MODEL_URLS, DEFAULT_MODEL_DIR


class TestRVMModel:
    """RVMModelクラスのテスト"""

    def test_init_default_values(self):
        """デフォルト値で初期化されること"""
        model = RVMModel()

        assert model.model_type == "mobilenetv3"
        assert model.model is None
        assert model.rec is None
        assert model.downsample_ratio == 0.25

    def test_init_custom_model_type(self):
        """カスタムモデルタイプを指定できること"""
        model = RVMModel(model_type="resnet50")

        assert model.model_type == "resnet50"
        assert "resnet50" in str(model.model_path)

    def test_init_custom_model_path(self):
        """カスタムモデルパスを指定できること"""
        custom_path = "/custom/path/model.pth"
        model = RVMModel(model_path=custom_path)

        assert str(model.model_path) == custom_path

    def test_init_custom_device(self):
        """カスタムデバイスを指定できること"""
        device = torch.device("cpu")
        model = RVMModel(device=device)

        assert model.device == device

    def test_is_loaded_false_initially(self):
        """初期状態ではロードされていないこと"""
        model = RVMModel()

        assert model.is_loaded() is False

    def test_load_raises_file_not_found(self):
        """モデルファイルがない場合FileNotFoundErrorを発生すること"""
        model = RVMModel(model_path="/nonexistent/path/model.pth")

        with pytest.raises(FileNotFoundError) as exc_info:
            model.load()

        assert "モデルファイルが見つかりません" in str(exc_info.value)

    def test_reset_state(self):
        """状態をリセットできること"""
        model = RVMModel()
        model.rec = (torch.zeros(1), torch.zeros(1))

        model.reset_state()

        assert model.rec is None

    def test_set_downsample_ratio_valid(self):
        """有効なダウンサンプル比率を設定できること"""
        model = RVMModel()

        model.set_downsample_ratio(0.5)
        assert model.downsample_ratio == 0.5

        model.set_downsample_ratio(1.0)
        assert model.downsample_ratio == 1.0

    def test_set_downsample_ratio_clamp_low(self):
        """ダウンサンプル比率が下限でクランプされること"""
        model = RVMModel()

        model.set_downsample_ratio(0.05)
        assert model.downsample_ratio == 0.1

    def test_set_downsample_ratio_clamp_high(self):
        """ダウンサンプル比率が上限でクランプされること"""
        model = RVMModel()

        model.set_downsample_ratio(1.5)
        assert model.downsample_ratio == 1.0

    def test_process_frame_without_load(self):
        """ロードせずにprocess_frameを呼ぶとRuntimeErrorを発生すること"""
        model = RVMModel()

        with pytest.raises(RuntimeError) as exc_info:
            frame = torch.rand(3, 480, 640)
            model.process_frame(frame)

        assert "ロードされていません" in str(exc_info.value)


class TestRVMModelWithMock:
    """モックを使用したRVMModelのテスト"""

    @patch("torch.jit.load")
    def test_load_success(self, mock_jit_load):
        """モデルが正常にロードされること"""
        # モックモデルを設定
        mock_model = MagicMock()
        mock_jit_load.return_value = mock_model

        with tempfile.NamedTemporaryFile(suffix=".pth", delete=False) as f:
            model_path = f.name

        try:
            model = RVMModel(model_path=model_path)
            model.load()

            assert model.is_loaded() is True
            mock_model.eval.assert_called_once()
        finally:
            os.unlink(model_path)

    @patch("torch.jit.load")
    def test_process_frame_first_call(self, mock_jit_load):
        """最初のフレーム処理で正しく推論すること"""
        # モックモデルを設定
        mock_model = MagicMock()
        mock_fgr = torch.rand(1, 3, 480, 640)
        mock_pha = torch.rand(1, 1, 480, 640)
        mock_rec = (torch.rand(1, 16, 120, 160), torch.rand(1, 20, 60, 80))
        mock_model.return_value = (mock_fgr, mock_pha, *mock_rec)
        mock_jit_load.return_value = mock_model

        with tempfile.NamedTemporaryFile(suffix=".pth", delete=False) as f:
            model_path = f.name

        try:
            model = RVMModel(model_path=model_path, device=torch.device("cpu"))
            model.load()

            frame = torch.rand(3, 480, 640)
            fgr, alpha = model.process_frame(frame)

            # 出力形状を確認
            assert fgr.shape == (3, 480, 640)
            assert alpha.shape == (1, 480, 640)

            # recurrent状態が更新されていること
            assert model.rec is not None
        finally:
            os.unlink(model_path)


class TestDownloadModel:
    """download_model関数のテスト"""

    def test_invalid_model_type(self):
        """不正なモデルタイプでValueErrorを発生すること"""
        with pytest.raises(ValueError) as exc_info:
            download_model("invalid_type")

        assert "不明なモデルタイプ" in str(exc_info.value)

    def test_model_urls_exist(self):
        """モデルURLが定義されていること"""
        assert "mobilenetv3" in MODEL_URLS
        assert "resnet50" in MODEL_URLS

    @patch("torch.hub.download_url_to_file")
    def test_download_to_custom_directory(self, mock_download):
        """カスタムディレクトリにダウンロードできること"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = download_model("mobilenetv3", save_dir=temp_dir)

            assert temp_dir in result
            assert "mobilenetv3" in result
            mock_download.assert_called_once()

    def test_skip_download_if_exists(self):
        """既にモデルが存在する場合はダウンロードをスキップすること"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # ダミーファイルを作成
            model_path = Path(temp_dir) / "rvm_mobilenetv3.torchscript"
            model_path.touch()

            with patch("torch.hub.download_url_to_file") as mock_download:
                result = download_model("mobilenetv3", save_dir=temp_dir)

                assert result == str(model_path)
                mock_download.assert_not_called()


class TestModelURLs:
    """MODEL_URLS定数のテスト"""

    def test_urls_are_valid_format(self):
        """URLが有効な形式であること"""
        for model_type, url in MODEL_URLS.items():
            assert url.startswith("https://")
            assert ".torchscript" in url
            assert model_type in url
