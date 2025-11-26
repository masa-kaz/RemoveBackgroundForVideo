# -*- coding: utf-8 -*-
"""動画処理ロジック"""

import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision.transforms.functional import to_tensor

from .rvm_model import RVMModel
from .utils import get_output_path, is_supported_video, ensure_directory


class ProcessingCancelled(Exception):
    """処理がキャンセルされた場合の例外"""
    pass


@dataclass
class VideoInfo:
    """動画情報を格納するデータクラス"""
    width: int
    height: int
    fps: float
    frame_count: int
    duration: float  # 秒
    has_audio: bool = False  # 音声の有無


def get_video_info(video_path: str, ffmpeg_path: Optional[str] = None) -> VideoInfo:
    """動画の情報を取得する

    Args:
        video_path: 動画ファイルのパス
        ffmpeg_path: ffmpegのパス（音声確認用、Noneの場合は自動検出）

    Returns:
        VideoInfo: 動画情報

    Raises:
        ValueError: 動画を開けない場合
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"動画を開けません: {video_path}")

    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0

        # 音声の有無を確認
        has_audio = _check_audio_stream(video_path, ffmpeg_path)

        return VideoInfo(
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            duration=duration,
            has_audio=has_audio,
        )
    finally:
        cap.release()


def _check_audio_stream(video_path: str, ffmpeg_path: Optional[str] = None) -> bool:
    """動画に音声ストリームがあるか確認する

    Args:
        video_path: 動画ファイルのパス
        ffmpeg_path: ffmpegのパス

    Returns:
        bool: 音声ストリームがある場合True
    """
    try:
        ffprobe_path = ffmpeg_path.replace("ffmpeg", "ffprobe") if ffmpeg_path else "ffprobe"
        if ffmpeg_path and "ffmpeg.exe" in ffmpeg_path:
            ffprobe_path = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")

        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                video_path,
            ],
            capture_output=True,
            text=True,
        )
        return "audio" in result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        # ffprobeが見つからない場合はTrueを返す（音声があると仮定）
        return True


def find_ffmpeg() -> str:
    """ffmpegの実行可能ファイルを探す

    Returns:
        str: ffmpegのパス

    Raises:
        RuntimeError: ffmpegが見つからない場合
    """
    # 同梱されているffmpegを探す
    app_dir = Path(__file__).parent.parent
    ffmpeg_paths = [
        app_dir / "ffmpeg" / "ffmpeg.exe",  # Windows
        app_dir / "ffmpeg" / "ffmpeg",  # Unix
        "ffmpeg",  # システムPATH
    ]

    for path in ffmpeg_paths:
        path_str = str(path)
        # システムPATHの場合はwhichで確認
        if path_str == "ffmpeg":
            try:
                subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    check=True,
                )
                return "ffmpeg"
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        elif Path(path_str).exists():
            return path_str

    raise RuntimeError(
        "ffmpegが見つかりません。ffmpegをインストールするか、"
        "ffmpegフォルダに配置してください。"
    )


class VideoProcessor:
    """動画の背景除去を行うプロセッサー"""

    def __init__(
        self,
        model: RVMModel,
        ffmpeg_path: Optional[str] = None,
    ):
        """プロセッサーを初期化する

        Args:
            model: RVMModelインスタンス
            ffmpeg_path: ffmpegのパス（Noneの場合は自動検出）
        """
        self.model = model
        self.ffmpeg_path = ffmpeg_path or find_ffmpeg()
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        """処理をキャンセルする"""
        self._cancel_flag.set()

    def reset_cancel(self) -> None:
        """キャンセルフラグをリセットする"""
        self._cancel_flag.clear()

    def is_cancelled(self) -> bool:
        """キャンセルされているかどうかを返す"""
        return self._cancel_flag.is_set()

    def process(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """動画の背景を除去して透過MOVを出力する

        Args:
            input_path: 入力動画のパス
            output_path: 出力ファイルのパス（Noneの場合は自動生成）
            progress_callback: 進捗コールバック関数 (current_frame, total_frames)

        Returns:
            str: 出力ファイルのパス

        Raises:
            ValueError: サポートされていない形式の場合
            RuntimeError: 処理に失敗した場合
            ProcessingCancelled: 処理がキャンセルされた場合
        """
        # キャンセルフラグをリセット
        self.reset_cancel()

        if not is_supported_video(input_path):
            raise ValueError(f"サポートされていない動画形式です: {input_path}")

        if output_path is None:
            output_path = get_output_path(input_path)

        # 出力ディレクトリを確保
        ensure_directory(str(Path(output_path).parent))

        # 動画情報を取得
        video_info = get_video_info(input_path, self.ffmpeg_path)

        # 一時ディレクトリを作成
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # フレームを処理
            self._process_frames(
                input_path=input_path,
                output_dir=temp_path,
                video_info=video_info,
                progress_callback=progress_callback,
            )

            # キャンセル確認
            if self.is_cancelled():
                raise ProcessingCancelled("処理がキャンセルされました")

            # PNGシーケンスからMOV (ProRes 4444) を生成（音声付き）
            self._create_prores_video(
                frames_dir=temp_path,
                input_path=input_path,
                output_path=output_path,
                fps=video_info.fps,
                has_audio=video_info.has_audio,
            )

        return output_path

    def _process_frames(
        self,
        input_path: str,
        output_dir: Path,
        video_info: VideoInfo,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """動画のフレームを処理する

        Args:
            input_path: 入力動画のパス
            output_dir: 出力ディレクトリ
            video_info: 動画情報
            progress_callback: 進捗コールバック

        Raises:
            ProcessingCancelled: 処理がキャンセルされた場合
        """
        # モデルの状態をリセット
        self.model.reset_state()

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise RuntimeError(f"動画を開けません: {input_path}")

        try:
            frame_idx = 0
            while True:
                # キャンセル確認
                if self.is_cancelled():
                    raise ProcessingCancelled("処理がキャンセルされました")

                ret, frame = cap.read()
                if not ret:
                    break

                # BGRからRGBに変換
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # PIL Imageに変換してtensorに
                pil_image = Image.fromarray(frame_rgb)
                tensor = to_tensor(pil_image)

                # 背景除去
                fgr, alpha = self.model.process_frame(tensor)

                # RGBA画像を生成
                rgba = self._create_rgba_image(fgr, alpha)

                # PNGとして保存
                output_frame_path = output_dir / f"frame_{frame_idx:06d}.png"
                rgba.save(str(output_frame_path), "PNG")

                frame_idx += 1

                # 進捗コールバック
                if progress_callback:
                    progress_callback(frame_idx, video_info.frame_count)

        finally:
            cap.release()

    def _create_rgba_image(
        self, fgr: torch.Tensor, alpha: torch.Tensor
    ) -> Image.Image:
        """前景とアルファマスクからRGBA画像を生成する

        Args:
            fgr: 前景画像テンソル (3, H, W)
            alpha: アルファマスク (1, H, W)

        Returns:
            Image.Image: RGBA画像
        """
        # CPUに移動
        fgr = fgr.cpu()
        alpha = alpha.cpu()

        # 値を0-255の範囲にクランプ
        fgr = torch.clamp(fgr, 0, 1)
        alpha = torch.clamp(alpha, 0, 1)

        # numpy配列に変換
        fgr_np = (fgr.permute(1, 2, 0).numpy() * 255).astype(np.uint8)
        alpha_np = (alpha.squeeze(0).numpy() * 255).astype(np.uint8)

        # RGBAに結合
        rgba = np.dstack([fgr_np, alpha_np])

        return Image.fromarray(rgba, mode="RGBA")

    def _create_prores_video(
        self,
        frames_dir: Path,
        input_path: str,
        output_path: str,
        fps: float,
        has_audio: bool = False,
    ) -> None:
        """PNGシーケンスからProRes 4444動画を生成する（音声付き）

        Args:
            frames_dir: フレームが格納されたディレクトリ
            input_path: 入力動画のパス（音声抽出用）
            output_path: 出力ファイルパス
            fps: フレームレート
            has_audio: 音声を含めるかどうか
        """
        input_pattern = str(frames_dir / "frame_%06d.png")

        if has_audio:
            # 音声付きで出力
            cmd = [
                self.ffmpeg_path,
                "-y",  # 上書き確認なし
                "-framerate", str(fps),
                "-i", input_pattern,
                "-i", input_path,  # 元動画から音声を取得
                "-c:v", "prores_ks",
                "-profile:v", "4444",  # ProRes 4444
                "-pix_fmt", "yuva444p10le",  # アルファチャンネル付き
                "-q:v", "10",  # 品質（0-32、低いほど高品質）
                "-c:a", "aac",  # 音声コーデック
                "-b:a", "192k",  # 音声ビットレート
                "-map", "0:v:0",  # 映像は最初の入力から
                "-map", "1:a:0?",  # 音声は2番目の入力から（存在する場合）
                "-shortest",  # 短い方に合わせる
                output_path,
            ]
        else:
            # 音声なしで出力
            cmd = [
                self.ffmpeg_path,
                "-y",  # 上書き確認なし
                "-framerate", str(fps),
                "-i", input_pattern,
                "-c:v", "prores_ks",
                "-profile:v", "4444",  # ProRes 4444
                "-pix_fmt", "yuva444p10le",  # アルファチャンネル付き
                "-q:v", "10",  # 品質（0-32、低いほど高品質）
                output_path,
            ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpegエラー: {result.stderr}"
            )
