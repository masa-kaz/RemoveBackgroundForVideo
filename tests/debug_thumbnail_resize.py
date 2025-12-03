"""サムネイルリサイズのデバッグスクリプト

実際にGUIを起動してリサイズイベントを確認する
"""

import sys
from pathlib import Path


# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import customtkinter as ctk
from PIL import Image


# tkinterdnd2のインポート（ドラッグ＆ドロップ対応）
try:
    from tkinterdnd2 import TkinterDnD

    HAS_DND = True
except ImportError:
    HAS_DND = False


# 簡易テスト用アプリ
class DebugApp:
    def __init__(self, root):
        self.root = root
        self.root.title("サムネイルリサイズデバッグ")
        self.root.geometry("700x850")
        self.root.minsize(600, 750)

        ctk.set_appearance_mode("light")

        # 状態変数
        self._original_thumbnail_pil = None
        self._last_window_width = 0
        self.is_processing = False

        # メインフレーム
        self.main_frame = ctk.CTkFrame(root, fg_color="#FAFAFA")
        self.main_frame.pack(fill="both", expand=True, padx=24, pady=24)

        # サムネイル表示エリア
        self.thumbnail_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color="#FFFFFF",
            corner_radius=12,
            border_width=1,
            border_color="#E0E0E0",
        )
        self.thumbnail_frame.pack(fill="both", expand=True, pady=(16, 0))

        # サムネイル画像
        self.thumbnail_label = ctk.CTkLabel(
            self.thumbnail_frame,
            text="サムネイルがここに表示されます",
        )
        self.thumbnail_label.pack(pady=16)

        # デバッグ情報
        self.debug_label = ctk.CTkLabel(
            self.thumbnail_frame,
            text="デバッグ情報:",
            font=ctk.CTkFont(size=14),
        )
        self.debug_label.pack(pady=8)

        # テスト画像を作成
        self._create_test_image()

        # ウィンドウリサイズイベントをバインド
        self.root.bind("<Configure>", self._on_window_resize)

        # ボタン
        btn = ctk.CTkButton(
            self.main_frame,
            text="サムネイルをリセット",
            command=self._create_test_image,
        )
        btn.pack(pady=16)

    def _create_test_image(self):
        """テスト用の画像を作成"""
        # 1920x1080のテスト画像を作成（グラデーション）
        width, height = 1920, 1080
        img = Image.new("RGB", (width, height))

        for y in range(height):
            for x in range(width):
                r = int(255 * x / width)
                g = int(255 * y / height)
                b = 128
                img.putpixel((x, y), (r, g, b))

        self._original_thumbnail_pil = img

        # 初期表示
        self._update_thumbnail_size()
        self._update_debug_info("テスト画像を作成しました")

    def _calculate_thumbnail_size(self) -> tuple[int, int]:
        """現在のウィンドウ幅に基づいてサムネイルサイズを計算"""
        window_width = self.root.winfo_width()
        available_width = window_width - 24 * 4  # パディング分
        width = min(500, max(200, available_width))

        if self._original_thumbnail_pil:
            orig_w, orig_h = self._original_thumbnail_pil.size
            aspect_ratio = orig_w / orig_h
        else:
            aspect_ratio = 16 / 9

        height = int(width / aspect_ratio)
        return width, height

    def _on_window_resize(self, event) -> None:
        """ウィンドウリサイズ時のハンドラ"""
        if event.widget != self.root:
            return

        if not hasattr(self, "thumbnail_label"):
            return

        new_width = self.root.winfo_width()
        if abs(new_width - self._last_window_width) > 10:
            self._last_window_width = new_width
            self._update_debug_info(f"リサイズ検出: {new_width}px")
            self.root.after(50, self._update_thumbnail_size)

    def _update_thumbnail_size(self) -> None:
        """ウィンドウサイズに合わせてサムネイルを更新"""
        if self.is_processing:
            return

        if not hasattr(self, "thumbnail_label"):
            self._update_debug_info("ERROR: thumbnail_label なし")
            return

        if not self.thumbnail_label.winfo_ismapped():
            self._update_debug_info("ERROR: thumbnail_label 未マップ")
            return

        if not self._original_thumbnail_pil:
            self._update_debug_info("ERROR: 元画像なし")
            return

        width, height = self._calculate_thumbnail_size()
        self._update_debug_info(f"サムネイル更新: {width}x{height}")

        img = self._original_thumbnail_pil.resize((width, height), Image.Resampling.LANCZOS)
        self.thumbnail_image = ctk.CTkImage(light_image=img, size=(width, height))
        self.thumbnail_label.configure(image=self.thumbnail_image)

    def _update_debug_info(self, msg: str):
        """デバッグ情報を更新"""
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        thumb_size = self._calculate_thumbnail_size()
        info = (
            f"Window: {window_width}x{window_height}, Thumb: {thumb_size[0]}x{thumb_size[1]}\n{msg}"
        )
        self.debug_label.configure(text=info)
        print(f"[DEBUG] {msg} | Window: {window_width}x{window_height}")


def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = ctk.CTk()

    DebugApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
