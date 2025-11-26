# -*- coding: utf-8 -*-
"""スクリーンショット撮影スクリプト

アプリの各状態のスクリーンショットを自動撮影してマニュアル用画像を作成する
引数でモードを指定：
  --initial   : 初期画面を撮影
  --selected  : 動画選択後の画面を撮影
  --processing: 処理中画面を撮影
  --done      : 完了画面を撮影
  --capture   : 現在の画面を撮影（ファイル名指定）
"""

import sys
import subprocess
import argparse
from pathlib import Path

# PILのインポート
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# macOS用のスクリーンキャプチャ
try:
    import Quartz
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "manual_images"


def find_app_window():
    """アプリのウィンドウIDを検索"""
    if not HAS_QUARTZ:
        return None

    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    for window in windows:
        name = str(window.get('kCGWindowOwnerName', '')).lower()
        title = str(window.get('kCGWindowName', ''))
        # python, tk, 動画背景除去などのキーワードで検索
        if 'python' in name or '動画背景除去' in title:
            window_id = window.get('kCGWindowNumber')
            if window_id:
                print(f"  ウィンドウ発見: {window.get('kCGWindowOwnerName')} - {title} (ID: {window_id})")
                return window_id
    return None


def capture_window(output_path: Path, window_id=None) -> bool:
    """ウィンドウをキャプチャ"""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        if window_id:
            # 特定のウィンドウをキャプチャ
            result = subprocess.run(
                ['screencapture', '-l', str(window_id), '-o', str(output_path)],
                capture_output=True
            )
        else:
            # ウィンドウIDを探す
            found_id = find_app_window()
            if found_id:
                result = subprocess.run(
                    ['screencapture', '-l', str(found_id), '-o', str(output_path)],
                    capture_output=True
                )
            else:
                # フォールバック：対話モードで選択
                print("  ウィンドウが見つかりません。手動で選択してください...")
                result = subprocess.run(
                    ['screencapture', '-i', '-W', str(output_path)],
                    capture_output=True
                )

        if result.returncode == 0 and output_path.exists():
            print(f"  撮影完了: {output_path}")

            # 画像サイズを調整
            if HAS_PIL:
                img = Image.open(output_path)
                width, height = img.size
                print(f"  元サイズ: {width}x{height}")

                max_width = 600
                if width > max_width:
                    ratio = max_width / width
                    new_size = (max_width, int(height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    img.save(output_path)
                    print(f"  リサイズ: {new_size[0]}x{new_size[1]}")

            return True
        else:
            print(f"  撮影失敗")
            return False

    except Exception as e:
        print(f"  エラー: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="アプリのスクリーンショットを撮影")
    parser.add_argument('--initial', action='store_true', help='初期画面を撮影')
    parser.add_argument('--selected', action='store_true', help='動画選択後の画面を撮影')
    parser.add_argument('--processing', action='store_true', help='処理中画面を撮影')
    parser.add_argument('--done', action='store_true', help='完了画面を撮影')
    parser.add_argument('--capture', type=str, help='指定ファイル名で撮影 (例: 01_initial.png)')
    args = parser.parse_args()

    print("=" * 50)
    print("スクリーンショット撮影")
    print("=" * 50)
    print(f"出力先: {OUTPUT_DIR}")

    if args.initial:
        print("\n[初期画面を撮影]")
        capture_window(OUTPUT_DIR / "01_initial.png")

    elif args.selected:
        print("\n[動画選択後の画面を撮影]")
        capture_window(OUTPUT_DIR / "02_selected.png")

    elif args.processing:
        print("\n[処理中画面を撮影]")
        capture_window(OUTPUT_DIR / "03_processing.png")

    elif args.done:
        print("\n[完了画面を撮影]")
        capture_window(OUTPUT_DIR / "04_done.png")

    elif args.capture:
        print(f"\n[{args.capture}として撮影]")
        capture_window(OUTPUT_DIR / args.capture)

    else:
        print("\n使い方:")
        print("  python scripts/capture_screenshots.py --initial")
        print("  python scripts/capture_screenshots.py --selected")
        print("  python scripts/capture_screenshots.py --processing")
        print("  python scripts/capture_screenshots.py --done")
        print("  python scripts/capture_screenshots.py --capture ファイル名.png")
        print("\n手順:")
        print("  1. アプリを起動: PYTHONPATH=src python src/main.py")
        print("  2. 各状態にしてから上記コマンドで撮影")


if __name__ == "__main__":
    main()
