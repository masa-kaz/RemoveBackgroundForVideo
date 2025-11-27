# -*- coding: utf-8 -*-
"""Windows EXE E2Eテスト

pywinautoを使用してビルドされたEXEファイルの一連の動作をテストする。

テストシナリオ:
1. 起動 - EXEを起動し、ウィンドウが表示されることを確認
2. ファイル選択 - 入力ボタンをクリックしてテスト動画を選択
3. 処理開始 - 処理開始ボタンをクリックして背景除去を実行
4. 出力確認 - 出力ファイルが生成されることを確認
5. 終了 - アプリケーションを終了

実行方法:
    python tests/e2e_windows_exe.py --exe-path "dist/BackgroundRemover_CPU/BackgroundRemover_CPU.exe"
"""

import argparse
import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime


def check_dependencies():
    """必要なライブラリがインストールされているか確認"""
    missing = []
    try:
        import pywinauto
    except ImportError:
        missing.append("pywinauto")
    try:
        import pyautogui
    except ImportError:
        missing.append("pyautogui")
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")

    if missing:
        print(f"ERROR: Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


check_dependencies()

import pyautogui
from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys
from pywinauto.timings import wait_until
from PIL import Image


class E2ETestRunner:
    """E2Eテストランナー"""

    def __init__(self, exe_path: str, test_video_path: str, output_dir: str):
        self.exe_path = Path(exe_path).resolve()
        self.test_video_path = Path(test_video_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.app = None
        self.main_window = None
        self.screenshot_count = 0
        self.test_results = []

        # 出力ファイルパス（入力と同じディレクトリに生成される）
        self.expected_output_path = self.test_video_path.parent / f"{self.test_video_path.stem}_nobg.mov"

    def log(self, message: str):
        """ログ出力（Windows環境でのエンコーディングエラーを回避）"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            print(f"[{timestamp}] {message}")
        except UnicodeEncodeError:
            # Windowsコンソールで日本語が出力できない場合
            safe_message = message.encode('ascii', errors='replace').decode('ascii')
            print(f"[{timestamp}] {safe_message}")

    def take_screenshot(self, name: str) -> Path:
        """スクリーンショットを撮影"""
        self.screenshot_count += 1
        filename = f"{self.screenshot_count:02d}_{name}.png"
        filepath = self.output_dir / filename

        screenshot = pyautogui.screenshot()
        screenshot.save(str(filepath))
        self.log(f"Screenshot saved: {filename}")
        return filepath

    def record_result(self, step: str, success: bool, message: str = ""):
        """テスト結果を記録"""
        status = "PASS" if success else "FAIL"
        self.test_results.append({
            "step": step,
            "success": success,
            "message": message
        })
        self.log(f"[{status}] {step}: {message}")

    def wait_for_window(self, timeout: int = 30) -> bool:
        """ウィンドウが表示されるまで待機"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 動画背景除去ツールのウィンドウを探す
                windows = Desktop(backend="uia").windows()
                for win in windows:
                    title = win.window_text()
                    if "動画背景除去" in title or "BackgroundRemover" in title:
                        self.main_window = win
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def find_button_by_text(self, text: str):
        """テキストでボタンを検索"""
        try:
            # CustomTkinterのボタンはButtonコントロールとして認識される
            buttons = self.main_window.descendants(control_type="Button")
            for btn in buttons:
                if text in btn.window_text():
                    return btn

            # テキストコントロールとしても探す
            texts = self.main_window.descendants(control_type="Text")
            for txt in texts:
                if text in txt.window_text():
                    # クリック可能な親要素を取得
                    return txt
        except Exception as e:
            self.log(f"Button search error: {e}")
        return None

    def click_element(self, element, offset_x: int = 0, offset_y: int = 0):
        """要素をクリック"""
        try:
            rect = element.rectangle()
            x = rect.left + (rect.width() // 2) + offset_x
            y = rect.top + (rect.height() // 2) + offset_y
            pyautogui.click(x, y)
            return True
        except Exception as e:
            self.log(f"Click error: {e}")
            return False

    def step1_launch(self) -> bool:
        """Step 1: アプリケーション起動"""
        self.log("=== Step 1: Launch Application ===")

        if not self.exe_path.exists():
            self.record_result("Step1_Launch", False, f"EXE not found: {self.exe_path}")
            return False

        try:
            # EXEを起動
            self.log(f"Starting: {self.exe_path}")
            subprocess.Popen([str(self.exe_path)], cwd=str(self.exe_path.parent))

            # ウィンドウが表示されるまで待機
            if not self.wait_for_window(timeout=60):
                self.record_result("Step1_Launch", False, "Window not found within 60 seconds")
                return False

            time.sleep(2)  # UIが完全にロードされるまで待機
            self.take_screenshot("01_launched")

            self.record_result("Step1_Launch", True, "Application launched successfully")
            return True

        except Exception as e:
            self.record_result("Step1_Launch", False, str(e))
            return False

    def step2_select_file(self) -> bool:
        """Step 2: ファイル選択"""
        self.log("=== Step 2: Select Input File ===")

        try:
            # 「入力」または「選択」ボタンを探してクリック
            # pywinautoでCustomTkinterのボタンを見つけるのは難しいので
            # pyautoguiで画像検索またはOCRを使う方法もある

            # 方法1: ウィンドウ上部のドロップゾーンをクリック
            # CustomTkinterのウィンドウ構造に依存

            # 方法2: キーボードショートカットを使用（実装されていれば）

            # 方法3: 直接座標でクリック（ウィンドウサイズに依存）
            rect = self.main_window.rectangle()

            # ドロップゾーン（ウィンドウ上部中央）をクリック
            drop_zone_x = rect.left + (rect.width() // 2)
            drop_zone_y = rect.top + 200  # タイトルバーから少し下

            pyautogui.click(drop_zone_x, drop_zone_y)
            time.sleep(1)

            # ファイル選択ダイアログが開くかを確認
            # 開かない場合は「入力」ボタンを探す
            dialog_found = False
            for _ in range(10):
                dialogs = Desktop(backend="uia").windows()
                for dlg in dialogs:
                    title = dlg.window_text().lower()
                    if "open" in title or "開く" in title or "選択" in title:
                        dialog_found = True
                        break
                if dialog_found:
                    break
                time.sleep(0.5)

            if not dialog_found:
                # ドロップゾーンクリックで開かなかった場合、入力ボタンを探す
                self.log("Dialog not found after clicking drop zone, looking for input button...")

                # ウィンドウ下部にあるボタンエリアをクリック
                button_area_y = rect.bottom - 150
                pyautogui.click(drop_zone_x - 100, button_area_y)  # 入力ボタン位置を推定
                time.sleep(1)

            self.take_screenshot("02_file_dialog")

            # ファイルパスを入力
            # ダイアログのファイル名入力欄にパスを入力
            time.sleep(0.5)

            # Windowsのファイルダイアログでパスを入力
            send_keys(str(self.test_video_path), with_spaces=True)
            time.sleep(0.5)
            send_keys("{ENTER}")

            time.sleep(2)  # ファイル読み込み待機
            self.take_screenshot("03_file_selected")

            # GPU警告ダイアログが表示されていれば閉じる
            self.close_gpu_warning_dialog()

            self.record_result("Step2_SelectFile", True, f"Selected: {self.test_video_path.name}")
            return True

        except Exception as e:
            self.take_screenshot("02_error")
            self.record_result("Step2_SelectFile", False, str(e))
            return False

    def ensure_window_focus(self):
        """ウィンドウにフォーカスを確実に当てる"""
        try:
            # ESCキーでメニューを閉じる
            send_keys("{ESC}")
            time.sleep(0.3)

            # ウィンドウをフォアグラウンドに
            self.main_window.set_focus()
            time.sleep(0.3)

            # ウィンドウのタイトルバーをクリックしてアクティブ化
            rect = self.main_window.rectangle()
            title_x = rect.left + (rect.width() // 2)
            title_y = rect.top + 15  # タイトルバー
            pyautogui.click(title_x, title_y)
            time.sleep(0.3)

        except Exception as e:
            self.log(f"ensure_window_focus error: {e}")

    def safe_click(self, x: int, y: int, description: str = ""):
        """ウィンドウ内であることを確認してクリック"""
        rect = self.main_window.rectangle()

        # 座標がウィンドウ内かチェック
        if x < rect.left or x > rect.right or y < rect.top or y > rect.bottom:
            self.log(f"WARNING: Click ({x}, {y}) is outside window bounds!")
            self.log(f"  Window: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")
            # 座標をウィンドウ内にクランプ
            x = max(rect.left + 10, min(x, rect.right - 10))
            y = max(rect.top + 30, min(y, rect.bottom - 10))
            self.log(f"  Clamped to: ({x}, {y})")

        self.log(f"Clicking at ({x}, {y}) - {description}")
        pyautogui.click(x, y)

    def close_gpu_warning_dialog(self):
        """GPU警告ダイアログを閉じる"""
        self.log("=== Checking for GPU warning dialog ===")
        try:
            # ダイアログが表示されるまで少し待機
            time.sleep(1)

            # ウィンドウにフォーカスを当てる
            self.ensure_window_focus()

            # 「了解」ボタンを探す（メインウィンドウ内のダイアログ）
            # CustomTkinterのダイアログはメインウィンドウ内に表示される
            rect = self.main_window.rectangle()

            # ダイアログの「了解」ボタンの位置を推定
            # ウィンドウの中央より少し下（ただしウィンドウ内に収まるように）
            dialog_btn_x = rect.left + (rect.width() // 2)
            # ウィンドウの60%の位置（中央より少し下、かつ必ずウィンドウ内）
            dialog_btn_y = rect.top + int(rect.height() * 0.6)

            self.safe_click(dialog_btn_x, dialog_btn_y, "GPU dialog OK button")
            time.sleep(1)

            self.take_screenshot("03b_gpu_dialog_closed")
            self.log("GPU warning dialog closed (or was not present)")

        except Exception as e:
            self.log(f"GPU dialog close error (may not be present): {e}")

    def dump_window_controls(self):
        """ウィンドウ内のコントロールをダンプ（デバッグ用）"""
        try:
            self.log("=== Window Controls Dump ===")
            controls = self.main_window.descendants()
            for ctrl in controls:
                try:
                    ctrl_type = ctrl.element_info.control_type
                    ctrl_text = ctrl.window_text()
                    rect = ctrl.rectangle()
                    self.log(f"  {ctrl_type}: '{ctrl_text}' at ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
                except Exception:
                    pass
            self.log("=== End Controls Dump ===")
        except Exception as e:
            self.log(f"Controls dump error: {e}")

    def find_process_button(self):
        """処理開始ボタンを複数の方法で検索"""
        # 方法1: ボタンテキストで検索
        button_texts = ["処理開始", "開始", "Start", "Process", "実行"]
        for text in button_texts:
            btn = self.find_button_by_text(text)
            if btn:
                self.log(f"Found button by text: '{text}'")
                return btn

        # 方法2: すべてのボタンを取得してログ出力
        try:
            buttons = self.main_window.descendants(control_type="Button")
            self.log(f"Found {len(buttons)} buttons in window")
            for i, btn in enumerate(buttons):
                text = btn.window_text()
                rect = btn.rectangle()
                self.log(f"  Button {i}: '{text}' at ({rect.left}, {rect.top})")
                # ボタンテキストに処理関連のキーワードが含まれていれば返す
                if any(kw in text for kw in ["処理", "開始", "Start", "実行"]):
                    return btn
        except Exception as e:
            self.log(f"Button search error: {e}")

        return None

    def step3_process(self) -> bool:
        """Step 3: 処理開始"""
        self.log("=== Step 3: Start Processing ===")

        try:
            # ウィンドウにフォーカスを当てる（ESC + set_focus + タイトルバークリック）
            self.ensure_window_focus()

            # デバッグ: ウィンドウコントロールをダンプ
            self.dump_window_controls()

            rect = self.main_window.rectangle()
            self.log(f"Window rect: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
            self.log(f"Window size: {rect.width()}x{rect.height()}")

            # 方法1: ボタンを検索してクリック
            process_btn = self.find_process_button()
            if process_btn:
                self.log("Clicking process button via pywinauto")
                # フォーカスを確実に
                self.ensure_window_focus()
                try:
                    process_btn.click_input()
                    time.sleep(2)
                except Exception as e:
                    self.log(f"pywinauto click failed: {e}, trying coordinate click")
                    self.click_element(process_btn)
                    time.sleep(2)
            else:
                # 方法2: 座標ベースでクリック（フォールバック）
                # ウィンドウの下部にあるボタンエリアを複数回クリック
                self.log("Button not found, trying coordinate-based clicks")

                # フォーカスを確実に
                self.ensure_window_focus()

                # ウィンドウ下部の複数の位置をクリック（safe_clickで安全に）
                button_positions = [
                    (rect.width() // 2, rect.height() - 80, "center-bottom-80"),
                    (rect.width() // 2, rect.height() - 100, "center-bottom-100"),
                    (rect.width() // 2, rect.height() - 60, "center-bottom-60"),
                    (rect.width() // 2 + 50, rect.height() - 80, "right-80"),
                    (rect.width() // 2 - 50, rect.height() - 80, "left-80"),
                ]

                for rel_x, rel_y, desc in button_positions:
                    # 相対座標を絶対座標に変換
                    x = rect.left + rel_x
                    y = rect.top + rel_y
                    self.safe_click(x, y, desc)
                    time.sleep(1)

            self.take_screenshot("04_processing_started")

            # 処理完了まで待機（最大5分に短縮）
            max_wait = 300  # 5分
            start_time = time.time()
            last_screenshot_time = 0

            while time.time() - start_time < max_wait:
                elapsed = int(time.time() - start_time)

                # 30秒ごとにスクリーンショット
                if elapsed - last_screenshot_time >= 30:
                    self.take_screenshot(f"05_processing_{elapsed}s")
                    last_screenshot_time = elapsed

                # 完了ダイアログのチェック
                try:
                    dialogs = Desktop(backend="uia").windows()
                    for dlg in dialogs:
                        title = dlg.window_text()
                        if "完了" in title or "Complete" in title or "Success" in title or "情報" in title:
                            self.take_screenshot("06_completed_dialog")
                            # OKボタンをクリック
                            try:
                                ok_btn = dlg.child_window(title="OK", control_type="Button")
                                ok_btn.click()
                            except Exception:
                                send_keys("{ENTER}")
                            time.sleep(1)
                            self.record_result("Step3_Process", True, f"Processing completed in {elapsed}s")
                            return True
                except Exception as e:
                    self.log(f"Dialog check error: {e}")

                # 出力ファイルの存在チェック
                if self.expected_output_path.exists():
                    file_size = self.expected_output_path.stat().st_size
                    if file_size > 1000:  # 1KB以上なら完了とみなす
                        self.take_screenshot("06_processing_done")
                        self.record_result("Step3_Process", True, f"Output file created: {file_size} bytes")
                        return True

                time.sleep(2)

            self.take_screenshot("06_timeout")
            self.record_result("Step3_Process", False, f"Processing timeout after {max_wait}s")
            return False

        except Exception as e:
            self.take_screenshot("05_error")
            self.record_result("Step3_Process", False, str(e))
            return False

    def step4_verify_output(self) -> bool:
        """Step 4: 出力確認"""
        self.log("=== Step 4: Verify Output ===")

        try:
            if not self.expected_output_path.exists():
                self.record_result("Step4_VerifyOutput", False, f"Output file not found: {self.expected_output_path}")
                return False

            file_size = self.expected_output_path.stat().st_size

            if file_size < 1000:
                self.record_result("Step4_VerifyOutput", False, f"Output file too small: {file_size} bytes")
                return False

            # 出力ファイルをテスト結果ディレクトリにコピー
            import shutil
            output_copy = self.output_dir / self.expected_output_path.name
            shutil.copy2(self.expected_output_path, output_copy)

            self.record_result("Step4_VerifyOutput", True, f"Output file size: {file_size} bytes")
            return True

        except Exception as e:
            self.record_result("Step4_VerifyOutput", False, str(e))
            return False

    def step5_close(self) -> bool:
        """Step 5: アプリケーション終了"""
        self.log("=== Step 5: Close Application ===")

        try:
            self.take_screenshot("07_before_close")

            # ウィンドウを閉じる
            if self.main_window:
                self.main_window.close()

            time.sleep(2)

            # プロセスが終了したか確認
            # pywinautoでプロセスをチェック

            self.record_result("Step5_Close", True, "Application closed")
            return True

        except Exception as e:
            self.record_result("Step5_Close", False, str(e))
            return False

    def cleanup(self):
        """クリーンアップ"""
        # 出力ファイルを削除
        if self.expected_output_path.exists():
            try:
                self.expected_output_path.unlink()
                self.log(f"Cleaned up: {self.expected_output_path}")
            except Exception:
                pass

        # アプリケーションを強制終了
        try:
            if self.app:
                self.app.kill()
        except Exception:
            pass

        # プロセス名で強制終了
        try:
            os.system('taskkill /F /IM BackgroundRemover_CPU.exe 2>nul')
            os.system('taskkill /F /IM BackgroundRemover_GPU.exe 2>nul')
        except Exception:
            pass

    def generate_report(self) -> str:
        """テストレポートを生成"""
        report_lines = [
            "=" * 60,
            "E2E Test Report",
            "=" * 60,
            f"EXE Path: {self.exe_path}",
            f"Test Video: {self.test_video_path}",
            f"Output Dir: {self.output_dir}",
            "-" * 60,
            "Results:",
        ]

        passed = 0
        failed = 0

        for result in self.test_results:
            status = "PASS" if result["success"] else "FAIL"
            report_lines.append(f"  [{status}] {result['step']}: {result['message']}")
            if result["success"]:
                passed += 1
            else:
                failed += 1

        report_lines.extend([
            "-" * 60,
            f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}",
            "=" * 60,
        ])

        report = "\n".join(report_lines)

        # レポートをファイルに保存
        report_path = self.output_dir / "test_report.txt"
        report_path.write_text(report, encoding="utf-8")

        return report

    def run(self) -> bool:
        """テストを実行"""
        self.log("Starting E2E Test")
        self.log(f"EXE: {self.exe_path}")
        self.log(f"Test Video: {self.test_video_path}")

        try:
            # 事前クリーンアップ
            if self.expected_output_path.exists():
                self.expected_output_path.unlink()

            # テスト実行
            if not self.step1_launch():
                return False

            if not self.step2_select_file():
                return False

            if not self.step3_process():
                return False

            if not self.step4_verify_output():
                return False

            self.step5_close()

            return all(r["success"] for r in self.test_results)

        except Exception as e:
            self.log(f"Test failed with exception: {e}")
            self.take_screenshot("error_final")
            return False

        finally:
            report = self.generate_report()
            print("\n" + report)
            self.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Windows EXE E2E Test")
    parser.add_argument(
        "--exe-path",
        required=True,
        help="Path to the EXE file to test"
    )
    parser.add_argument(
        "--test-video",
        default="tests/fixtures/TestVideo.mp4",
        help="Path to test video file"
    )
    parser.add_argument(
        "--output-dir",
        default="test_output/e2e",
        help="Directory to save test artifacts"
    )

    args = parser.parse_args()

    runner = E2ETestRunner(
        exe_path=args.exe_path,
        test_video_path=args.test_video,
        output_dir=args.output_dir
    )

    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
