"""ユーティリティ関数"""

import os
from dataclasses import dataclass
from pathlib import Path

import torch


# サポートする入力形式
SUPPORTED_INPUT_EXTENSIONS = {".mp4", ".mov", ".m4v"}

# 出力形式
OUTPUT_EXTENSION = ".mov"


@dataclass
class DeviceInfo:
    """デバイス情報を格納するデータクラス"""

    device: torch.device
    name: str
    is_gpu: bool
    warning: str | None = None


def get_device() -> torch.device:
    """利用可能な最適なデバイスを取得する

    Returns:
        torch.device: CUDA > MPS > CPU の優先順位で選択
    """
    device_info = get_device_info()
    return device_info.device


def get_device_info() -> DeviceInfo:
    """利用可能な最適なデバイスの詳細情報を取得する

    Returns:
        DeviceInfo: デバイス情報（デバイス、名前、GPU有無、警告メッセージ）
    """
    # CUDA (NVIDIA GPU) を優先
    try:
        if torch.cuda.is_available():
            device = torch.device("cuda")
            gpu_name = torch.cuda.get_device_name(0)
            return DeviceInfo(
                device=device,
                name=f"NVIDIA GPU ({gpu_name})",
                is_gpu=True,
                warning=None,
            )
    except Exception:
        pass  # CUDAが利用できない場合はフォールバック

    # MPS (Apple Silicon) を次に優先
    try:
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = torch.device("mps")
            return DeviceInfo(
                device=device,
                name="Apple Silicon (MPS)",
                is_gpu=True,
                warning=None,
            )
    except Exception:
        pass  # MPSが利用できない場合はフォールバック

    # CPU フォールバック
    return DeviceInfo(
        device=torch.device("cpu"),
        name="CPU",
        is_gpu=False,
        warning="GPUが検出されませんでした。CPU処理は非常に遅くなります。",
    )


def is_supported_video(file_path: str) -> bool:
    """サポートされている動画形式かどうかを判定する

    Args:
        file_path: ファイルパス

    Returns:
        bool: サポートされている形式の場合True
    """
    ext = Path(file_path).suffix.lower()
    return ext in SUPPORTED_INPUT_EXTENSIONS


def get_output_path(input_path: str, output_dir: str | None = None) -> str:
    """出力ファイルパスを生成する

    Args:
        input_path: 入力ファイルパス
        output_dir: 出力ディレクトリ（Noneの場合は入力と同じディレクトリ）

    Returns:
        str: 出力ファイルパス（_nobg.mov形式）
    """
    input_path = Path(input_path)
    stem = input_path.stem

    if output_dir:
        output_directory = Path(output_dir)
    else:
        output_directory = input_path.parent

    output_filename = f"{stem}_nobg{OUTPUT_EXTENSION}"
    return str(output_directory / output_filename)


def ensure_directory(path: str) -> None:
    """ディレクトリが存在しない場合は作成する

    Args:
        path: ディレクトリパス
    """
    os.makedirs(path, exist_ok=True)


def get_file_size_mb(file_path: str) -> float:
    """ファイルサイズをMB単位で取得する

    Args:
        file_path: ファイルパス

    Returns:
        float: ファイルサイズ（MB）
    """
    return os.path.getsize(file_path) / (1024 * 1024)


def format_time(seconds: float) -> str:
    """秒数を時:分:秒形式にフォーマットする

    Args:
        seconds: 秒数

    Returns:
        str: フォーマットされた時間文字列
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
