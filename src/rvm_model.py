# -*- coding: utf-8 -*-
"""RobustVideoMatting モデル管理"""

from pathlib import Path
from typing import Optional, Tuple

import torch

from utils import get_device

# モデルのダウンロードURL（TorchScript形式）
MODEL_URLS = {
    "mobilenetv3": "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.torchscript",
    "resnet50": "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50_fp32.torchscript",
}

# デフォルトモデルディレクトリ
DEFAULT_MODEL_DIR = Path(__file__).parent.parent / "models"


class RVMModel:
    """RobustVideoMatting モデルラッパー

    動画の背景除去に特化したディープラーニングモデルを管理する。
    時系列の一貫性を保つため、recurrent状態を内部で管理する。
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_type: str = "mobilenetv3",
        device: Optional[torch.device] = None,
    ):
        """モデルを初期化する

        Args:
            model_path: モデルファイルのパス（Noneの場合は自動検出/ダウンロード）
            model_type: モデルタイプ（"mobilenetv3" or "resnet50"）
            device: 使用するデバイス（Noneの場合は自動検出）
        """
        self.model_type = model_type
        self.device = device or get_device()
        self.model: Optional[nn.Module] = None
        self.rec: Optional[Tuple[torch.Tensor, ...]] = None
        self.downsample_ratio: float = 0.25

        # モデルパスの決定
        if model_path:
            self.model_path = Path(model_path)
        else:
            self.model_path = DEFAULT_MODEL_DIR / f"rvm_{model_type}.torchscript"

    def load(self) -> None:
        """モデルをロードする

        Raises:
            FileNotFoundError: モデルファイルが見つからない場合
        """
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"モデルファイルが見つかりません: {self.model_path}\n"
                f"以下のURLからダウンロードしてください:\n"
                f"{MODEL_URLS.get(self.model_type, 'Unknown model type')}"
            )

        # モデルをロード
        self.model = torch.jit.load(str(self.model_path), map_location=self.device)
        self.model.eval()

        # recurrent状態をリセット
        self.reset_state()

    def reset_state(self) -> None:
        """recurrent状態をリセットする（新しい動画処理時に呼び出す）"""
        self.rec = None

    def is_loaded(self) -> bool:
        """モデルがロードされているかどうかを返す"""
        return self.model is not None

    @torch.no_grad()
    def process_frame(
        self, frame: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """1フレームを処理してアルファマスクを生成する

        Args:
            frame: 入力フレーム (C, H, W) 形式、値は0-1の範囲

        Returns:
            Tuple[torch.Tensor, torch.Tensor]:
                - fgr: 前景画像 (C, H, W)
                - alpha: アルファマスク (1, H, W)

        Raises:
            RuntimeError: モデルがロードされていない場合
        """
        if self.model is None:
            raise RuntimeError("モデルがロードされていません。load()を呼び出してください。")

        # バッチ次元を追加
        src = frame.unsqueeze(0).to(self.device)

        # 推論
        if self.rec is None:
            fgr, pha, *self.rec = self.model(src, downsample_ratio=self.downsample_ratio)
        else:
            fgr, pha, *self.rec = self.model(
                src, *self.rec, downsample_ratio=self.downsample_ratio
            )

        # バッチ次元を削除して返す
        return fgr.squeeze(0), pha.squeeze(0)

    def set_downsample_ratio(self, ratio: float) -> None:
        """ダウンサンプル比率を設定する

        Args:
            ratio: ダウンサンプル比率（0.1〜1.0）
                   小さいほど高速だが精度が下がる
        """
        self.downsample_ratio = max(0.1, min(1.0, ratio))


def download_model(model_type: str = "mobilenetv3", save_dir: Optional[str] = None) -> str:
    """モデルをダウンロードする

    Args:
        model_type: モデルタイプ（"mobilenetv3" or "resnet50"）
        save_dir: 保存先ディレクトリ（Noneの場合はデフォルト）

    Returns:
        str: ダウンロードしたモデルファイルのパス

    Raises:
        ValueError: 不明なモデルタイプの場合
    """
    if model_type not in MODEL_URLS:
        raise ValueError(f"不明なモデルタイプ: {model_type}")

    url = MODEL_URLS[model_type]
    save_directory = Path(save_dir) if save_dir else DEFAULT_MODEL_DIR
    save_directory.mkdir(parents=True, exist_ok=True)

    filename = f"rvm_{model_type}.torchscript"
    save_path = save_directory / filename

    if save_path.exists():
        print(f"モデルは既に存在します: {save_path}")
        return str(save_path)

    print(f"モデルをダウンロード中: {url}")

    # torch.hub.download_url_to_file を使用
    torch.hub.download_url_to_file(url, str(save_path), progress=True)

    print(f"ダウンロード完了: {save_path}")
    return str(save_path)
