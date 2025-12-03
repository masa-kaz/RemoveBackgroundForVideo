"""動画容量削減モジュール

ProRes 4444形式の動画を指定サイズ以下に圧縮する。
透過情報を保持したまま、ビットレートを調整してファイルサイズを制御する。
"""

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from video_processor import _get_subprocess_args, find_ffmpeg, get_video_info


# ファイルサイズ設定
DEFAULT_MAX_SIZE_MB = 1023

# ビットレート設定
DEFAULT_AUDIO_BITRATE_KBPS = 128
MIN_VIDEO_BITRATE_KBPS = 500  # これ以下だと品質が著しく低下

# 安全マージン（推定サイズからの余裕、5%）
SAFETY_MARGIN = 0.95

# VP9エンコード設定
VP9_VIDEO_BITRATE = "2M"
VP9_CRF = "35"  # 品質設定（0-63、高いほど低品質・小サイズ）

# ffprobe タイムアウト（秒）
FFPROBE_TIMEOUT_SECONDS = 30


@dataclass
class CompressionResult:
    """圧縮結果"""

    success: bool
    input_path: str
    output_path: str
    original_size_mb: float
    compressed_size_mb: float
    compression_ratio: float
    target_bitrate_kbps: int | None = None
    error_message: str | None = None
    backup_path: str | None = None


def get_file_size_mb(file_path: str) -> float:
    """ファイルサイズをMB単位で取得する

    Args:
        file_path: ファイルパス

    Returns:
        ファイルサイズ (MB)
    """
    return os.path.getsize(file_path) / (1024 * 1024)


def calculate_target_bitrate(
    duration_seconds: float,
    max_size_mb: float,
    audio_bitrate_kbps: int = DEFAULT_AUDIO_BITRATE_KBPS,
    safety_margin: float = SAFETY_MARGIN,
) -> int:
    """目標ビットレートを計算する

    Args:
        duration_seconds: 動画の長さ（秒）
        max_size_mb: 最大ファイルサイズ (MB)
        audio_bitrate_kbps: 音声ビットレート (kbps)
        safety_margin: 安全マージン（SAFETY_MARGIN = 5%余裕を持つ）

    Returns:
        目標ビットレート (kbps)
    """
    # 利用可能なビット数を計算
    # max_size_mb * 1024 * 1024 * 8 = 総ビット数
    # 音声分を引いて、動画に使えるビット数を算出
    total_bits = max_size_mb * 1024 * 1024 * 8 * safety_margin
    audio_bits = audio_bitrate_kbps * 1000 * duration_seconds
    video_bits = total_bits - audio_bits

    # ビットレート (kbps) に変換
    video_bitrate_kbps = int(video_bits / duration_seconds / 1000)

    # 最低ビットレートを保証（これ以下だと品質が著しく低下）
    return max(video_bitrate_kbps, MIN_VIDEO_BITRATE_KBPS)


def verify_video_integrity(file_path: str) -> bool:
    """ffprobeで動画ファイルの整合性を確認する

    Args:
        file_path: 動画ファイルパス

    Returns:
        True: 整合性OK, False: 破損またはエラー
    """
    # ffprobeのパスを探す
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path is None:
        return False

    ffmpeg_dir = Path(ffmpeg_path).parent
    ffprobe_path = ffmpeg_dir / "ffprobe"
    if not ffprobe_path.exists():
        ffprobe_path = ffmpeg_dir / "ffprobe.exe"
    if not ffprobe_path.exists():
        ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path is None:
        # ffprobeがない場合はファイル存在とサイズで簡易チェック
        return Path(file_path).exists() and os.path.getsize(file_path) > 0

    try:
        result = subprocess.run(
            [
                str(ffprobe_path),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
            **_get_subprocess_args(),
        )
        # 正常に終了し、durationが取得できれば整合性OK
        return result.returncode == 0 and len(result.stdout.strip()) > 0
    except Exception:
        return False


def compress_video(
    input_path: str,
    output_path: str | None = None,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB,
    preserve_alpha: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
) -> CompressionResult:
    """動画を指定サイズ以下に圧縮する

    Args:
        input_path: 入力動画ファイルパス
        output_path: 出力動画ファイルパス（Noneの場合は入力ファイルを上書き）
        max_size_mb: 最大ファイルサイズ (MB)、デフォルト1023MB
        preserve_alpha: 透過情報を保持するか
        progress_callback: 進捗コールバック (current, total)

    Returns:
        CompressionResult: 圧縮結果
    """
    input_path = str(input_path)
    backup_path = None

    # ファイル存在チェック
    if not Path(input_path).exists():
        return CompressionResult(
            success=False,
            input_path=input_path,
            output_path=input_path,
            original_size_mb=0,
            compressed_size_mb=0,
            compression_ratio=1.0,
            error_message=f"入力ファイルが見つかりません: {input_path}",
        )

    original_size_mb = get_file_size_mb(input_path)

    # 既にサイズ以下の場合はスキップ
    if original_size_mb <= max_size_mb:
        return CompressionResult(
            success=True,
            input_path=input_path,
            output_path=input_path,
            original_size_mb=original_size_mb,
            compressed_size_mb=original_size_mb,
            compression_ratio=1.0,
        )

    # ffmpegを検索
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path is None:
        return CompressionResult(
            success=False,
            input_path=input_path,
            output_path=input_path,
            original_size_mb=original_size_mb,
            compressed_size_mb=original_size_mb,
            compression_ratio=1.0,
            error_message="ffmpegが見つかりません",
        )

    # 動画情報を取得
    video_info = get_video_info(input_path)
    duration_seconds = video_info.duration

    # 目標ビットレートを計算
    target_bitrate_kbps = calculate_target_bitrate(duration_seconds, max_size_mb)

    # 出力パスを決定
    if output_path is None:
        # 上書きモード: バックアップを作成
        input_file = Path(input_path)
        backup_path = str(input_file.parent / f"{input_file.stem}_backup{input_file.suffix}")

        # バックアップを作成
        shutil.copy2(input_path, backup_path)

        # 一時ファイルに出力
        temp_dir = tempfile.gettempdir()
        temp_output = Path(temp_dir) / f"compressed_{Path(input_path).name}"
        final_output = input_path
        should_use_temp_file = True
    else:
        temp_output = Path(output_path)
        final_output = output_path
        should_use_temp_file = False

    # ffmpegコマンドを構築
    if preserve_alpha:
        # VP9 + WebMで透過を保持（効率的な圧縮、Canva対応）
        # 出力ファイル名を.webmに変更
        if should_use_temp_file:
            temp_output = Path(temp_dir) / f"compressed_{Path(input_path).stem}.webm"
        else:
            temp_output = Path(output_path).with_suffix(".webm")
            final_output = str(temp_output)

        # 高速VP9エンコード設定
        cmd = [
            ffmpeg_path,
            "-y",  # 上書き確認なし
            "-i",
            input_path,
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",  # 透過対応
            "-b:v",
            VP9_VIDEO_BITRATE,
            "-crf",
            VP9_CRF,
            "-deadline",
            "realtime",  # 最速モード
            "-cpu-used",
            "8",  # 最大CPU使用（0-8、8が最速）
            "-row-mt",
            "1",  # マルチスレッド有効
            "-c:a",
            "libopus",
            "-b:a",
            f"{DEFAULT_AUDIO_BITRATE_KBPS}k",
            str(temp_output),
        ]
    else:
        # H.264で透過なし（より小さくなる）
        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-b:v",
            f"{target_bitrate_kbps}k",
            "-c:a",
            "aac",
            "-b:a",
            f"{DEFAULT_AUDIO_BITRATE_KBPS}k",
            "-movflags",
            "+faststart",
            str(temp_output),
        ]

    try:
        # ffmpegを実行
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            **_get_subprocess_args(),
        )

        # 完了を待つ
        _, stderr = process.communicate()

        if process.returncode != 0:
            # 失敗時はバックアップから復元
            if backup_path and Path(backup_path).exists():
                shutil.move(backup_path, input_path)
            return CompressionResult(
                success=False,
                input_path=input_path,
                output_path=input_path,
                original_size_mb=original_size_mb,
                compressed_size_mb=original_size_mb,
                compression_ratio=1.0,
                target_bitrate_kbps=target_bitrate_kbps,
                error_message=f"ffmpegエラー: {stderr}",
            )

        # 圧縮後のファイル整合性チェック
        if not verify_video_integrity(str(temp_output)):
            # 整合性チェック失敗: バックアップから復元
            if temp_output.exists():
                temp_output.unlink()
            if backup_path and Path(backup_path).exists():
                shutil.move(backup_path, input_path)
            return CompressionResult(
                success=False,
                input_path=input_path,
                output_path=input_path,
                original_size_mb=original_size_mb,
                compressed_size_mb=original_size_mb,
                compression_ratio=1.0,
                target_bitrate_kbps=target_bitrate_kbps,
                error_message="圧縮後のファイルが破損しています",
            )

        # 圧縮後のサイズを確認
        compressed_size_mb = get_file_size_mb(str(temp_output))

        # 一時ファイルを使用した場合
        # preserve_alphaの場合はWebM形式なので、元のMOVと同じディレクトリに保存
        if should_use_temp_file:
            if preserve_alpha:
                # WebM: 元ファイルと同じディレクトリに.webmとして保存
                final_output = str(Path(input_path).with_suffix(".webm"))
            shutil.move(str(temp_output), final_output)

        # 置き換え後も整合性チェック
        if not verify_video_integrity(final_output):
            # 整合性チェック失敗: バックアップから復元
            if backup_path and Path(backup_path).exists():
                shutil.move(backup_path, final_output)
            return CompressionResult(
                success=False,
                input_path=input_path,
                output_path=input_path,
                original_size_mb=original_size_mb,
                compressed_size_mb=original_size_mb,
                compression_ratio=1.0,
                target_bitrate_kbps=target_bitrate_kbps,
                error_message="ファイル移動後に破損が検出されました",
            )

        # 成功: バックアップを削除
        if backup_path and Path(backup_path).exists():
            Path(backup_path).unlink()

        return CompressionResult(
            success=True,
            input_path=input_path,
            output_path=final_output,
            original_size_mb=original_size_mb,
            compressed_size_mb=compressed_size_mb,
            compression_ratio=compressed_size_mb / original_size_mb,
            target_bitrate_kbps=target_bitrate_kbps,
        )

    except Exception as e:
        # 一時ファイルがあれば削除
        if should_use_temp_file and temp_output.exists():
            temp_output.unlink()

        # バックアップから復元
        if backup_path and Path(backup_path).exists():
            shutil.move(backup_path, input_path)

        return CompressionResult(
            success=False,
            input_path=input_path,
            output_path=input_path,
            original_size_mb=original_size_mb,
            compressed_size_mb=original_size_mb,
            compression_ratio=1.0,
            target_bitrate_kbps=target_bitrate_kbps,
            error_message=str(e),
        )


def compress_if_needed(
    input_path: str,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB,
    preserve_alpha: bool = True,
) -> CompressionResult:
    """ファイルサイズが制限を超えている場合のみ圧縮する

    Args:
        input_path: 入力動画ファイルパス
        max_size_mb: 最大ファイルサイズ (MB)、デフォルト1023MB
        preserve_alpha: 透過情報を保持するか

    Returns:
        CompressionResult: 圧縮結果
    """
    return compress_video(
        input_path=input_path,
        output_path=None,  # 上書き
        max_size_mb=max_size_mb,
        preserve_alpha=preserve_alpha,
    )
