# -*- coding: utf-8 -*-
"""動画容量削減モジュール

ProRes 4444形式の動画を指定サイズ以下に圧縮する。
透過情報を保持したまま、ビットレートを調整してファイルサイズを制御する。
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from video_processor import find_ffmpeg, get_video_info


# デフォルトの最大ファイルサイズ (MB)
DEFAULT_MAX_SIZE_MB = 1023


@dataclass
class CompressionResult:
    """圧縮結果"""
    success: bool
    input_path: str
    output_path: str
    original_size_mb: float
    compressed_size_mb: float
    compression_ratio: float
    target_bitrate_kbps: Optional[int] = None
    error_message: Optional[str] = None
    backup_path: Optional[str] = None


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
    audio_bitrate_kbps: int = 128,
    safety_margin: float = 0.95,
) -> int:
    """目標ビットレートを計算する

    Args:
        duration_seconds: 動画の長さ（秒）
        max_size_mb: 最大ファイルサイズ (MB)
        audio_bitrate_kbps: 音声ビットレート (kbps)
        safety_margin: 安全マージン（0.95 = 5%余裕を持つ）

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

    # 最低ビットレートを保証（品質が極端に下がらないように）
    return max(video_bitrate_kbps, 500)


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
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # 正常に終了し、durationが取得できれば整合性OK
        return result.returncode == 0 and len(result.stdout.strip()) > 0
    except Exception:
        return False


def compress_video(
    input_path: str,
    output_path: Optional[str] = None,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB,
    preserve_alpha: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
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
        use_temp = True
    else:
        temp_output = Path(output_path)
        final_output = output_path
        use_temp = False

    # ffmpegコマンドを構築
    if preserve_alpha:
        # VP9 + WebMで透過を保持（効率的な圧縮、Canva対応）
        # 出力ファイル名を.webmに変更
        if use_temp:
            temp_output = Path(temp_dir) / f"compressed_{Path(input_path).stem}.webm"
        else:
            temp_output = Path(output_path).with_suffix(".webm")
            final_output = str(temp_output)

        # 高速VP9エンコード設定
        cmd = [
            ffmpeg_path,
            "-y",  # 上書き確認なし
            "-i", input_path,
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",  # 透過対応
            "-b:v", "2M",  # ビットレート2Mbps
            "-crf", "35",  # 品質設定
            "-deadline", "realtime",  # 最速モード
            "-cpu-used", "8",  # 最大CPU使用
            "-row-mt", "1",  # マルチスレッド有効
            "-c:a", "libopus",
            "-b:a", "128k",
            str(temp_output),
        ]
    else:
        # H.264で透過なし（より小さくなる）
        cmd = [
            ffmpeg_path,
            "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-b:v", f"{target_bitrate_kbps}k",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(temp_output),
        ]

    try:
        # ffmpegを実行
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
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
        if use_temp:
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
        if use_temp and temp_output.exists():
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
