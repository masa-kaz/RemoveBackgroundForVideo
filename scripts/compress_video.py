#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""動画容量削減CLIツール

ProRes 4444形式の動画を指定サイズ以下に圧縮する。

使用例:
    # 1023MB以下に圧縮（デフォルト）
    python scripts/compress_video.py input.mov

    # 500MB以下に圧縮
    python scripts/compress_video.py input.mov --max-size 500

    # 別ファイルに出力
    python scripts/compress_video.py input.mov -o output.mov --max-size 1023

    # 透過なしで圧縮（より小さくなる）
    python scripts/compress_video.py input.mov --no-alpha
"""

import argparse
import sys
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from video_compressor import compress_video, get_file_size_mb, DEFAULT_MAX_SIZE_MB


def main():
    parser = argparse.ArgumentParser(
        description="動画ファイルを指定サイズ以下に圧縮する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 1023MB以下に圧縮（デフォルト、上書き）
  python scripts/compress_video.py input.mov

  # 500MB以下に圧縮
  python scripts/compress_video.py input.mov --max-size 500

  # 別ファイルに出力
  python scripts/compress_video.py input.mov -o output.mov

  # 透過なしで圧縮（H.264、より小さくなる）
  python scripts/compress_video.py input.mov --no-alpha
        """,
    )

    parser.add_argument(
        "input",
        type=str,
        help="入力動画ファイルパス",
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="出力動画ファイルパス（省略時は入力ファイルを上書き）",
    )

    parser.add_argument(
        "--max-size",
        type=int,
        default=DEFAULT_MAX_SIZE_MB,
        help=f"最大ファイルサイズ (MB)、デフォルト: {DEFAULT_MAX_SIZE_MB}MB",
    )

    parser.add_argument(
        "--no-alpha",
        action="store_true",
        help="透過情報を保持しない（H.264でより小さく圧縮）",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="進捗メッセージを表示しない",
    )

    args = parser.parse_args()

    # 入力ファイルの確認
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"エラー: 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not input_path.is_file():
        print(f"エラー: 入力パスはファイルではありません: {input_path}", file=sys.stderr)
        sys.exit(1)

    # 現在のファイルサイズを表示
    current_size = get_file_size_mb(str(input_path))
    if not args.quiet:
        print(f"入力ファイル: {input_path}")
        print(f"現在のサイズ: {current_size:.1f} MB")
        print(f"目標サイズ: {args.max_size} MB以下")

    # 圧縮が必要か確認
    if current_size <= args.max_size:
        if not args.quiet:
            print(f"ファイルは既に {args.max_size} MB以下です。圧縮は不要です。")
        sys.exit(0)

    if not args.quiet:
        print(f"圧縮中...")

    # 圧縮実行
    result = compress_video(
        input_path=str(input_path),
        output_path=args.output,
        max_size_mb=args.max_size,
        preserve_alpha=not args.no_alpha,
    )

    # 結果を表示
    if result.success:
        if not args.quiet:
            print(f"圧縮完了!")
            print(f"出力ファイル: {result.output_path}")
            print(f"圧縮前: {result.original_size_mb:.1f} MB")
            print(f"圧縮後: {result.compressed_size_mb:.1f} MB")
            print(f"圧縮率: {result.compression_ratio * 100:.1f}%")
            if result.target_bitrate_kbps:
                print(f"使用ビットレート: {result.target_bitrate_kbps} kbps")
        sys.exit(0)
    else:
        print(f"エラー: {result.error_message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
