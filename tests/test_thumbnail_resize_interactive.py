"""サムネイルリサイズの実際の動作を確認するテスト

ウィンドウサイズを変更して、サムネイル画像が実際に変更されているか検証する
"""

import sys
from pathlib import Path


# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import customtkinter as ctk
from PIL import Image


# tkinterdnd2のインポート
try:
    from tkinterdnd2 import TkinterDnD

    HAS_DND = True
except ImportError:
    HAS_DND = False


class ThumbnailResizeTest:
    """サムネイルリサイズをテストするクラス"""

    def __init__(self, root):
        self.root = root
        self.root.title("サムネイルリサイズテスト")
        self.root.geometry("700x600")
        self.root.minsize(400, 400)

        ctk.set_appearance_mode("light")

        # 状態変数
        self._original_thumbnail_pil = None
        self._last_window_width = 0
        self.is_processing = False
        self.thumbnail_image = None

        # テスト結果
        self.test_results = []
        self.resize_count = 0

        # メインフレーム
        self.main_frame = ctk.CTkFrame(root, fg_color="#FAFAFA")
        self.main_frame.pack(fill="both", expand=True, padx=24, pady=24)

        # サムネイル表示エリア
        self.thumbnail_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color="#FFFFFF",
            corner_radius=12,
        )
        self.thumbnail_frame.pack(fill="both", expand=True)

        # サムネイル画像
        self.thumbnail_label = ctk.CTkLabel(
            self.thumbnail_frame,
            text="",
        )
        self.thumbnail_label.pack(pady=16)

        # デバッグ情報
        self.debug_label = ctk.CTkLabel(
            self.main_frame,
            text="テスト準備中...",
            font=ctk.CTkFont(size=12),
            justify="left",
        )
        self.debug_label.pack(pady=8)

        # 結果表示
        self.result_label = ctk.CTkLabel(
            self.main_frame,
            text="",
            font=ctk.CTkFont(size=14),
            text_color="#4CAF50",
        )
        self.result_label.pack(pady=8)

        # テスト画像を作成
        self._create_test_image()

        # ウィンドウリサイズイベントをバインド
        self.root.bind("<Configure>", self._on_window_resize)

        # 自動テスト開始ボタン
        btn = ctk.CTkButton(
            self.main_frame,
            text="自動リサイズテスト開始",
            command=self._start_auto_test,
        )
        btn.pack(pady=8)

    def _create_test_image(self):
        """テスト用の画像を作成（識別しやすいグラデーション）"""
        width, height = 1920, 1080
        img = Image.new("RGB", (width, height))

        for y in range(height):
            for x in range(width):
                r = int(255 * x / width)
                g = int(255 * y / height)
                b = 128
                img.putpixel((x, y), (r, g, b))

        self._original_thumbnail_pil = img
        self._update_thumbnail_size()
        self._update_debug("テスト画像作成完了")

    def _calculate_thumbnail_size(self) -> tuple[int, int]:
        """現在のウィンドウ幅に基づいてサムネイルサイズを計算"""
        window_width = self.root.winfo_width()
        available_width = window_width - 24 * 4
        width = max(200, available_width)  # 最大制限なし

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
            self.root.after(50, self._update_thumbnail_size)

    def _update_thumbnail_size(self) -> None:
        """ウィンドウサイズに合わせてサムネイルを更新"""
        if self.is_processing:
            return

        if not hasattr(self, "thumbnail_label"):
            self._update_debug("ERROR: thumbnail_label なし")
            return

        if not self._original_thumbnail_pil:
            self._update_debug("ERROR: 元画像なし")
            return

        width, height = self._calculate_thumbnail_size()

        # リサイズ
        img = self._original_thumbnail_pil.resize((width, height), Image.Resampling.LANCZOS)

        # 新しいCTkImageを作成
        self.thumbnail_image = ctk.CTkImage(light_image=img, size=(width, height))

        # ラベルに設定
        self.thumbnail_label.configure(image=self.thumbnail_image)

        # 強制再描画
        self.thumbnail_label.update_idletasks()

        self.resize_count += 1
        self._update_debug(f"リサイズ #{self.resize_count}: {width}x{height}")

        # テスト結果を記録
        self.test_results.append(
            {
                "window_width": self.root.winfo_width(),
                "thumb_size": (width, height),
                "image_id": id(self.thumbnail_image),
            }
        )

    def _update_debug(self, msg: str):
        """デバッグ情報を更新"""
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        thumb_size = self._calculate_thumbnail_size()

        # CTkImageのIDを取得（異なればオブジェクトが変わっている）
        img_id = id(self.thumbnail_image) if self.thumbnail_image else "None"

        info = f"""Window: {window_width}x{window_height}
Thumb計算値: {thumb_size[0]}x{thumb_size[1]}
CTkImage ID: {img_id}
リサイズ回数: {self.resize_count}
最新: {msg}"""
        self.debug_label.configure(text=info)
        print(f"[DEBUG] {msg}")

    def _start_auto_test(self):
        """自動リサイズテストを開始"""
        self.test_results = []
        self.resize_count = 0
        self.result_label.configure(text="テスト中...", text_color="#FF9800")

        # 様々なサイズにリサイズ
        sizes = [
            (600, 500),
            (800, 600),
            (500, 400),
            (1000, 700),
            (700, 600),
        ]

        def run_test(index):
            if index >= len(sizes):
                self._verify_results()
                return

            w, h = sizes[index]
            self.root.geometry(f"{w}x{h}")
            self._update_debug(f"サイズ変更: {w}x{h}")

            # 次のテストを遅延実行
            self.root.after(500, lambda: run_test(index + 1))

        run_test(0)

    def _verify_results(self):
        """テスト結果を検証"""
        print("\n" + "=" * 50)
        print("テスト結果検証")
        print("=" * 50)

        if len(self.test_results) < 2:
            self.result_label.configure(
                text="ERROR: リサイズイベントが発火していません", text_color="#F44336"
            )
            print("ERROR: リサイズイベントが十分に発火していません")
            return

        # 各リサイズでimage_idが変わっているか確認
        image_ids = [r["image_id"] for r in self.test_results]
        unique_ids = set(image_ids)

        print(f"リサイズ回数: {len(self.test_results)}")
        print(f"ユニークなCTkImage ID数: {len(unique_ids)}")

        for i, result in enumerate(self.test_results):
            print(
                f"  #{i + 1}: Window={result['window_width']}px, "
                f"Thumb={result['thumb_size']}, ID={result['image_id']}"
            )

        # サムネイルサイズが変わっているか確認
        thumb_sizes = [r["thumb_size"] for r in self.test_results]
        unique_sizes = set(thumb_sizes)

        if len(unique_sizes) > 1:
            self.result_label.configure(
                text=f"OK: {len(unique_sizes)}種類のサイズにリサイズされました",
                text_color="#4CAF50",
            )
            print(f"\nSUCCESS: {len(unique_sizes)}種類の異なるサイズが確認されました")
        else:
            self.result_label.configure(
                text="ERROR: サムネイルサイズが変わっていません", text_color="#F44336"
            )
            print("\nFAILED: サムネイルサイズが変わっていません")

        # image_idが変わっているか
        if len(unique_ids) > 1:
            print(f"SUCCESS: CTkImageオブジェクトが{len(unique_ids)}回再作成されました")
        else:
            print("WARNING: CTkImageオブジェクトが再作成されていない可能性があります")


def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = ctk.CTk()

    ThumbnailResizeTest(root)
    root.mainloop()


if __name__ == "__main__":
    main()
