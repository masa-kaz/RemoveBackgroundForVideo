# -*- coding: utf-8 -*-
"""動画背景除去ツール - GUI (CustomTkinter版)"""

import math
import subprocess
import sys
import threading
import tempfile
from pathlib import Path

import cv2
import customtkinter as ctk
from PIL import Image, ImageTk

# tkinterdnd2のインポート（ドラッグ＆ドロップ対応）
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except ImportError:
    HAS_DND = False

from rvm_model import RVMModel, download_model
from video_processor import VideoProcessor, get_video_info, ProcessingCancelled
from utils import (
    get_device_info,
    get_output_path,
    is_supported_video,
    format_time,
    SUPPORTED_INPUT_EXTENSIONS,
    DeviceInfo,
)


# カラーテーマ
COLORS = {
    "primary": "#2563eb",  # 青
    "primary_hover": "#1d4ed8",
    "success": "#16a34a",  # 緑
    "warning": "#ea580c",  # オレンジ
    "danger": "#dc2626",  # 赤
    "bg": "#f8fafc",  # 背景
    "card": "#ffffff",  # カード背景
    "border": "#e2e8f0",  # ボーダー
    "text": "#1e293b",  # テキスト
    "text_secondary": "#64748b",  # セカンダリテキスト
    "drop_zone": "#f1f5f9",  # ドロップゾーン
    "drop_zone_hover": "#dbeafe",  # ドロップゾーンホバー
}


class CircularProgress(ctk.CTkFrame):
    """円形プログレスバー"""

    def __init__(
        self,
        master,
        size: int = 120,
        line_width: int = 8,
        progress_color: str = "#2563eb",
        bg_color: str = "#e2e8f0",
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._size = size
        self._line_width = line_width
        self._progress_color = progress_color
        self._bg_color = bg_color
        self._progress = 0.0

        # Canvasを作成
        self.canvas = ctk.CTkCanvas(
            self,
            width=size,
            height=size,
            bg=self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"]),
            highlightthickness=0,
        )
        self.canvas.pack()

        # 中央のテキスト用ラベル
        self.percent_label = ctk.CTkLabel(
            self,
            text="0%",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"],
        )
        self.percent_label.place(relx=0.5, rely=0.5, anchor="center")

        self._draw_progress()

    def _draw_progress(self):
        """円を描画"""
        self.canvas.delete("all")

        # 背景円
        padding = self._line_width
        self.canvas.create_arc(
            padding,
            padding,
            self._size - padding,
            self._size - padding,
            start=90,
            extent=-360,
            style="arc",
            outline=self._bg_color,
            width=self._line_width,
        )

        # プログレス円
        if self._progress > 0:
            extent = -360 * self._progress
            self.canvas.create_arc(
                padding,
                padding,
                self._size - padding,
                self._size - padding,
                start=90,
                extent=extent,
                style="arc",
                outline=self._progress_color,
                width=self._line_width,
            )

    def set(self, value: float):
        """進捗を設定 (0.0 ~ 1.0)"""
        self._progress = max(0.0, min(1.0, value))
        self.percent_label.configure(text=f"{int(self._progress * 100)}%")
        self._draw_progress()

    def get(self) -> float:
        """現在の進捗を取得"""
        return self._progress


class CTkDnDFrame(ctk.CTkFrame):
    """ドラッグ＆ドロップ対応のCTkFrame"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._drop_callback = None
        self._drag_enter_callback = None
        self._drag_leave_callback = None

    def configure_dnd(self, on_drop=None, on_drag_enter=None, on_drag_leave=None):
        """ドラッグ＆ドロップのコールバックを設定"""
        self._drop_callback = on_drop
        self._drag_enter_callback = on_drag_enter
        self._drag_leave_callback = on_drag_leave

        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._handle_drop)
            self.dnd_bind("<<DragEnter>>", self._handle_drag_enter)
            self.dnd_bind("<<DragLeave>>", self._handle_drag_leave)

    def _handle_drop(self, event):
        if self._drop_callback:
            self._drop_callback(event)

    def _handle_drag_enter(self, event):
        if self._drag_enter_callback:
            self._drag_enter_callback(event)

    def _handle_drag_leave(self, event):
        if self._drag_leave_callback:
            self._drag_leave_callback(event)


class BackgroundRemoverApp:
    """動画背景除去アプリケーションのメインクラス"""

    def __init__(self, root):
        """アプリケーションを初期化する

        Args:
            root: CustomTkinterのルートウィンドウ
        """
        self.root = root
        self.root.title("動画背景除去ツール by META AI LABO")
        self.root.geometry("520x580")
        self.root.minsize(450, 500)
        self.root.resizable(True, True)

        # ライトモード固定
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # 背景色を設定（TkinterDnD.Tk()の場合は通常のTkオプションを使用）
        try:
            self.root.configure(fg_color=COLORS["bg"])
        except Exception:
            self.root.configure(bg=COLORS["bg"])

        # 状態変数
        self.input_path: str = ""
        self.output_path: str = ""
        self.temp_output_path: str = ""  # 一時出力先
        self.is_processing: bool = False
        self.file_selected: bool = False

        # デバイス情報を取得
        self.device_info: DeviceInfo = get_device_info()

        # モデル（遅延ロード）
        self.model: RVMModel | None = None
        self.processor: VideoProcessor | None = None

        # ロゴ画像を保持
        self.logo_image = None
        # サムネイル画像を保持
        self.thumbnail_image = None

        # UIを構築
        self._setup_ui()

        # GPUなしの場合は警告を表示
        if self.device_info.warning:
            self.root.after(100, self._show_gpu_warning)

    def _get_asset_path(self) -> Path:
        """アセットのベースパスを取得"""
        if getattr(sys, "frozen", False):
            return Path(sys._MEIPASS)
        return Path(__file__).parent.parent

    def _load_logo(self) -> ctk.CTkImage | None:
        """ロゴ画像を読み込む"""
        logo_path = self._get_asset_path() / "assets" / "icon.png"
        try:
            if logo_path.exists():
                img = Image.open(logo_path)
                return ctk.CTkImage(light_image=img, size=(80, 80))
        except Exception:
            pass
        return None

    def _extract_thumbnail(self, video_path: str, size: tuple = (160, 90)) -> ctk.CTkImage | None:
        """動画からサムネイルを抽出する"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None

            # 最初のフレームを取得
            ret, frame = cap.read()
            cap.release()

            if not ret:
                return None

            # BGRからRGBに変換
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # PILイメージに変換
            img = Image.fromarray(frame_rgb)

            # アスペクト比を維持してリサイズ
            img.thumbnail((size[0] * 2, size[1] * 2), Image.Resampling.LANCZOS)

            # CTkImageとして返す
            return ctk.CTkImage(light_image=img, size=size)

        except Exception:
            return None

    def _setup_ui(self) -> None:
        """UIを構築する"""
        # メインフレーム
        main_frame = ctk.CTkFrame(self.root, fg_color=COLORS["bg"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # ヘッダー部分（ロゴ＋タイトル）
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        # ロゴ
        self.logo_image = self._load_logo()
        if self.logo_image:
            logo_label = ctk.CTkLabel(header_frame, image=self.logo_image, text="")
            logo_label.pack(pady=(0, 8))

        # タイトル
        title_label = ctk.CTkLabel(
            header_frame,
            text="動画背景除去ツール",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"],
        )
        title_label.pack()

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="by META AI LABO",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
        )
        subtitle_label.pack()

        # ドロップゾーン（カード風）
        self.drop_card = CTkDnDFrame(
            main_frame,
            fg_color=COLORS["drop_zone"],
            corner_radius=12,
            border_width=2,
            border_color=COLORS["border"],
        )
        self.drop_card.pack(fill="x", pady=10, ipady=25)

        # ドロップゾーン内のコンテンツ
        self.drop_content = ctk.CTkFrame(self.drop_card, fg_color="transparent")
        self.drop_content.pack(expand=True, fill="both", padx=20, pady=10)

        # ファイルアイコン（初期表示）
        self.drop_icon_label = ctk.CTkLabel(
            self.drop_content,
            text="📁",
            font=ctk.CTkFont(size=36),
        )
        self.drop_icon_label.pack(pady=(5, 5))

        # サムネイル表示用ラベル（初期は非表示）
        self.thumbnail_label = ctk.CTkLabel(
            self.drop_content,
            text="",
            image=None,
        )

        self.drop_text_label = ctk.CTkLabel(
            self.drop_content,
            text="動画ファイルをドラッグ＆ドロップ\nまたはクリックして選択",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"],
            justify="center",
        )
        self.drop_text_label.pack()

        self.drop_hint_label = ctk.CTkLabel(
            self.drop_content,
            text=".mp4  .mov  .m4v",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        )
        self.drop_hint_label.pack(pady=(5, 0))

        # ドロップゾーンをクリック可能に
        self.drop_card.bind("<Button-1>", lambda e: self._select_input())
        for widget in [self.drop_content, self.drop_icon_label, self.drop_text_label, self.drop_hint_label, self.thumbnail_label]:
            widget.bind("<Button-1>", lambda e: self._select_input())

        # ドラッグ＆ドロップの設定
        self.drop_card.configure_dnd(
            on_drop=self._on_drop,
            on_drag_enter=self._on_drag_enter,
            on_drag_leave=self._on_drag_leave,
        )

        # ファイル情報フレーム（初期は非表示）
        self.file_info_frame = ctk.CTkFrame(
            main_frame, fg_color=COLORS["card"], corner_radius=10
        )

        # 出力先フレーム（ファイル情報内）
        self.output_frame = ctk.CTkFrame(self.file_info_frame, fg_color="transparent")

        # 動画情報ラベル
        self.video_info_label = ctk.CTkLabel(
            self.file_info_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
        )

        # 出力先ラベルとボタン
        output_label = ctk.CTkLabel(
            self.output_frame,
            text="出力:",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
        )
        output_label.pack(side="left")

        self.output_name_label = ctk.CTkLabel(
            self.output_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
        )
        self.output_name_label.pack(side="left", padx=(5, 10))

        change_btn = ctk.CTkButton(
            self.output_frame,
            text="変更",
            width=50,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=COLORS["primary"],
            hover_color=COLORS["drop_zone_hover"],
            command=self._select_output,
        )
        change_btn.pack(side="left")

        # プログレスフレーム（円形プログレス）
        self.progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", pady=10)

        # 円形プログレス
        self.circular_progress = CircularProgress(
            self.progress_frame,
            size=120,
            line_width=8,
            progress_color=COLORS["primary"],
            bg_color=COLORS["border"],
        )
        self.circular_progress.pack(pady=(10, 5))

        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
        )
        self.progress_label.pack(fill="x")

        # プログレスフレームを初期は非表示
        self.progress_frame.pack_forget()

        # ボタンフレーム
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=15)

        # メインボタン
        self.process_button = ctk.CTkButton(
            button_frame,
            text="🚀 背景を除去",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45,
            corner_radius=8,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            command=self._start_processing,
            state="disabled",
        )
        self.process_button.pack(fill="x", pady=(0, 8))

        # キャンセルボタン
        self.cancel_button = ctk.CTkButton(
            button_frame,
            text="キャンセル",
            font=ctk.CTkFont(size=13),
            height=38,
            corner_radius=8,
            fg_color="transparent",
            text_color=COLORS["danger"],
            border_width=1,
            border_color=COLORS["danger"],
            hover_color="#fee2e2",
            command=self._cancel_processing,
            state="disabled",
        )
        self.cancel_button.pack(fill="x")

        # キャンセルボタンは初期非表示
        self.cancel_button.pack_forget()

        # フッター（デバイス情報）
        footer_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        footer_frame.pack(fill="x", side="bottom", pady=(10, 0))

        device_icon = "💻" if not self.device_info.is_gpu else "⚡"
        device_color = COLORS["success"] if self.device_info.is_gpu else COLORS["warning"]
        speed_text = "高速処理" if self.device_info.is_gpu else "標準処理"

        device_label = ctk.CTkLabel(
            footer_frame,
            text=f"{device_icon} {self.device_info.name} - {speed_text}",
            font=ctk.CTkFont(size=11),
            text_color=device_color,
        )
        device_label.pack()

    def _on_drop(self, event) -> None:
        """ファイルがドロップされたときの処理"""
        data = event.data

        if data.startswith("{"):
            path = data.strip("{}")
        else:
            path = data.split()[0] if " " in data else data

        self._reset_drop_zone()
        self._set_input_file(path)

    def _on_drag_enter(self, event) -> None:
        """ドラッグがドロップゾーンに入ったときの処理"""
        self.drop_card.configure(
            fg_color=COLORS["drop_zone_hover"],
            border_color=COLORS["primary"],
        )
        self.drop_text_label.configure(text_color=COLORS["primary"])

    def _on_drag_leave(self, event) -> None:
        """ドラッグがドロップゾーンから出たときの処理"""
        self._reset_drop_zone()

    def _reset_drop_zone(self) -> None:
        """ドロップゾーンを初期状態に戻す"""
        if self.file_selected:
            self.drop_card.configure(
                fg_color="#f0fdf4",  # 緑がかった背景
                border_color=COLORS["success"],
            )
        else:
            self.drop_card.configure(
                fg_color=COLORS["drop_zone"],
                border_color=COLORS["border"],
            )
            self.drop_text_label.configure(text_color=COLORS["text_secondary"])

    def _set_input_file(self, path: str) -> None:
        """入力ファイルを設定する"""
        if not path:
            return

        if not is_supported_video(path):
            self._show_error(
                "サポートされていない形式です。\n"
                f"対応形式: {', '.join(SUPPORTED_INPUT_EXTENSIONS)}"
            )
            return

        self.input_path = path
        self.file_selected = True
        filename = Path(path).name

        # 出力パスを自動設定
        self.output_path = get_output_path(path)
        output_name = Path(self.output_path).name

        # サムネイルを抽出して表示
        self.thumbnail_image = self._extract_thumbnail(path, size=(160, 90))
        if self.thumbnail_image:
            self.drop_icon_label.pack_forget()
            self.thumbnail_label.configure(image=self.thumbnail_image)
            self.thumbnail_label.pack(pady=(5, 5))
        else:
            # サムネイル抽出失敗時はアイコンを更新
            self.drop_icon_label.configure(text="✅")

        # ドロップゾーンを更新
        self.drop_text_label.configure(
            text=filename,
            text_color=COLORS["success"],
        )
        self.drop_hint_label.configure(text="別のファイルをドロップして変更")
        self.drop_card.configure(
            fg_color="#f0fdf4",
            border_color=COLORS["success"],
        )

        # 動画情報を取得して表示
        try:
            info = get_video_info(path)
            info_text = (
                f"📹 {info.width}x{info.height} | {info.fps:.1f}fps | "
                f"{format_time(info.duration)} ({info.frame_count}フレーム)"
            )
            self.video_info_label.configure(text=info_text)
        except ValueError as e:
            self.video_info_label.configure(text=str(e))

        # 出力名を設定
        self.output_name_label.configure(text=output_name)

        # ファイル情報フレームを表示
        self.file_info_frame.pack(fill="x", pady=10, padx=5)
        self.video_info_label.pack(fill="x", padx=15, pady=(10, 5))
        self.output_frame.pack(fill="x", padx=15, pady=(0, 10))

        # 処理ボタンを有効化
        self.process_button.configure(state="normal")

    def _select_input(self) -> None:
        """入力ファイルを選択する"""
        filetypes = [
            ("動画ファイル", "*.mp4 *.mov *.m4v"),
            ("MP4", "*.mp4"),
            ("MOV", "*.mov"),
            ("すべてのファイル", "*.*"),
        ]

        path = ctk.filedialog.askopenfilename(
            title="入力動画を選択",
            filetypes=filetypes,
        )

        if path:
            self._set_input_file(path)

    def _select_output(self) -> None:
        """出力先を選択する"""
        if not self.input_path:
            self._show_warning("先に入力ファイルを選択してください。")
            return

        default_name = Path(self.output_path).name if self.output_path else "output.mov"

        path = ctk.filedialog.asksaveasfilename(
            title="出力先を選択",
            defaultextension=".mov",
            initialfile=default_name,
            filetypes=[("MOV (ProRes 4444)", "*.mov")],
        )

        if path:
            self.output_path = path
            self.output_name_label.configure(text=Path(path).name)

    def _start_processing(self) -> None:
        """処理を開始する"""
        if self.is_processing:
            return

        if not self.input_path:
            self._show_warning("入力ファイルを選択してください。")
            return

        self.is_processing = True
        self.process_button.configure(state="disabled")

        # キャンセルボタンを表示
        self.cancel_button.pack(fill="x")
        self.cancel_button.configure(state="normal")

        # プログレスフレームを表示
        self.progress_frame.pack(fill="x", pady=10)
        self.circular_progress.set(0)
        self.progress_label.configure(text="モデルを読み込み中...")

        # 一時出力先を設定（処理完了後にユーザーが保存先を選択）
        self.temp_output_path = tempfile.mktemp(suffix=".mov")

        # 別スレッドで処理
        thread = threading.Thread(target=self._process_video)
        thread.daemon = True
        thread.start()

    def _cancel_processing(self) -> None:
        """処理をキャンセルする"""
        if not self.is_processing:
            return

        if self.processor:
            self.processor.cancel()
            self.progress_label.configure(text="キャンセル中...")
            self.cancel_button.configure(state="disabled")

    def _process_video(self) -> None:
        """動画を処理する（別スレッドで実行）"""
        try:
            # モデルをロード（初回のみ）
            if self.model is None:
                self.model = RVMModel()
                try:
                    self.model.load()
                except FileNotFoundError:
                    self._update_progress_text("モデルをダウンロード中...")
                    download_model()
                    self.model.load()

                self.processor = VideoProcessor(self.model)

            # 処理を実行（一時ファイルに出力）
            self._update_progress_text("処理中...")
            self.processor.process(
                input_path=self.input_path,
                output_path=self.temp_output_path,
                progress_callback=self._on_progress,
            )

            # 完了
            self._on_complete()

        except ProcessingCancelled:
            self._on_cancelled()

        except Exception as e:
            self._on_error(str(e))

    def _on_progress(self, current: int, total: int) -> None:
        """進捗を更新する"""
        progress = current / total
        self.root.after(0, lambda: self._update_progress(progress, current, total))

    def _update_progress(self, progress: float, current: int, total: int) -> None:
        """進捗UIを更新する"""
        self.circular_progress.set(progress)
        self.progress_label.configure(text=f"{current}/{total} フレーム")

    def _update_progress_text(self, text: str) -> None:
        """進捗テキストを更新する"""
        self.root.after(0, lambda: self.progress_label.configure(text=text))

    def _on_complete(self) -> None:
        """処理完了時の処理"""

        def complete():
            self.is_processing = False
            self.process_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            self.cancel_button.pack_forget()
            self.circular_progress.set(1.0)
            self.progress_label.configure(text="✅ 完了!")

            # 完了ダイアログ
            dialog = ctk.CTkToplevel(self.root)
            dialog.title("完了")
            dialog.geometry("400x220")
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()

            # 中央に配置
            dialog.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - 220) // 2
            dialog.geometry(f"+{x}+{y}")

            frame = ctk.CTkFrame(dialog, fg_color="transparent")
            frame.pack(expand=True, fill="both", padx=20, pady=20)

            ctk.CTkLabel(
                frame,
                text="✅",
                font=ctk.CTkFont(size=36),
            ).pack()

            ctk.CTkLabel(
                frame,
                text="背景除去が完了しました",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(pady=(5, 5))

            ctk.CTkLabel(
                frame,
                text="保存先を選択してください",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text_secondary"],
            ).pack(pady=(0, 10))

            btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
            btn_frame.pack(fill="x")

            ctk.CTkButton(
                btn_frame,
                text="📁 保存先を選択",
                command=lambda: self._save_output_file(dialog),
                fg_color=COLORS["primary"],
                height=38,
            ).pack(fill="x", pady=(0, 8))

            ctk.CTkButton(
                btn_frame,
                text="キャンセル（保存しない）",
                command=lambda: self._cancel_save(dialog),
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                border_width=1,
                border_color=COLORS["border"],
                height=32,
            ).pack(fill="x")

        self.root.after(0, complete)

    def _save_output_file(self, dialog) -> None:
        """出力ファイルを保存する"""
        import shutil

        # デフォルトのファイル名を取得
        input_name = Path(self.input_path).stem
        default_name = f"{input_name}_nobg.mov"

        # 保存先を選択
        save_path = ctk.filedialog.asksaveasfilename(
            title="保存先を選択",
            defaultextension=".mov",
            initialfile=default_name,
            filetypes=[("MOV (ProRes 4444)", "*.mov")],
        )

        if save_path:
            try:
                # 一時ファイルから保存先にコピー
                shutil.move(self.temp_output_path, save_path)
                self.output_path = save_path
                dialog.destroy()

                # 保存完了通知
                self._show_save_complete_dialog(save_path)
            except Exception as e:
                self._show_error(f"ファイルの保存に失敗しました:\n{str(e)}")

    def _cancel_save(self, dialog) -> None:
        """保存をキャンセルする"""
        import os

        # 一時ファイルを削除
        if self.temp_output_path and Path(self.temp_output_path).exists():
            try:
                os.remove(self.temp_output_path)
            except Exception:
                pass

        dialog.destroy()
        self._show_info("保存がキャンセルされました。\n処理結果は破棄されました。")

    def _show_save_complete_dialog(self, save_path: str) -> None:
        """保存完了ダイアログを表示"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("保存完了")
        dialog.geometry("380x180")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 中央に配置
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 380) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 180) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        ctk.CTkLabel(
            frame,
            text="💾",
            font=ctk.CTkFont(size=36),
        ).pack()

        ctk.CTkLabel(
            frame,
            text="ファイルを保存しました",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(5, 5))

        # ファイル名を表示
        filename = Path(save_path).name
        ctk.CTkLabel(
            frame,
            text=filename,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 10))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame,
            text="フォルダを開く",
            command=lambda: self._open_folder_and_close(save_path, dialog),
            fg_color=COLORS["primary"],
        ).pack(side="left", expand=True, padx=(0, 5))

        ctk.CTkButton(
            btn_frame,
            text="閉じる",
            command=dialog.destroy,
            fg_color="transparent",
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["border"],
        ).pack(side="left", expand=True, padx=(5, 0))

    def _open_folder_and_close(self, file_path: str, dialog) -> None:
        """フォルダを開いてダイアログを閉じる"""
        dialog.destroy()
        folder = Path(file_path).parent
        if sys.platform == "darwin":
            subprocess.run(["open", str(folder)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    def _open_output_folder(self, dialog=None) -> None:
        """出力フォルダを開く"""
        if dialog:
            dialog.destroy()

        folder = Path(self.output_path).parent
        if sys.platform == "darwin":
            subprocess.run(["open", str(folder)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    def _on_error(self, error_message: str) -> None:
        """エラー発生時の処理"""

        def handle_error():
            self.is_processing = False
            self.process_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            self.cancel_button.pack_forget()
            self.circular_progress.set(0)
            self.progress_label.configure(text="❌ エラーが発生しました")
            self._show_error(f"処理中にエラーが発生しました:\n\n{error_message}")

        self.root.after(0, handle_error)

    def _on_cancelled(self) -> None:
        """キャンセル時の処理"""

        def handle_cancelled():
            import os

            self.is_processing = False
            self.process_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            self.cancel_button.pack_forget()
            self.circular_progress.set(0)
            self.progress_label.configure(text="キャンセルされました")

            # 一時ファイルを削除
            if self.temp_output_path and Path(self.temp_output_path).exists():
                try:
                    os.remove(self.temp_output_path)
                except Exception:
                    pass

            self._show_info("処理がキャンセルされました。")

        self.root.after(0, handle_cancelled)

    def _show_gpu_warning(self) -> None:
        """GPU未検出の警告を表示する"""
        self._show_warning(
            f"{self.device_info.warning}\n\n"
            "処理を続行できますが、7分の動画の場合、数時間かかる可能性があります。"
        )

    def _show_error(self, message: str) -> None:
        """エラーダイアログを表示"""
        ctk.CTkMessagebox = None  # CustomTkinterにはMessageboxがないのでTkinterを使用
        from tkinter import messagebox

        messagebox.showerror("エラー", message)

    def _show_warning(self, message: str) -> None:
        """警告ダイアログを表示"""
        from tkinter import messagebox

        messagebox.showwarning("警告", message)

    def _show_info(self, message: str) -> None:
        """情報ダイアログを表示"""
        from tkinter import messagebox

        messagebox.showinfo("情報", message)


class CTkDnDRoot(ctk.CTk):
    """ドラッグ＆ドロップ対応のCTkルートウィンドウ"""

    def __init__(self, *args, **kwargs):
        # TkinterDnDが利用可能な場合はDnD対応のTkを使用
        if HAS_DND:
            # TkinterDnDのTkをベースにする
            super(ctk.CTk, self).__init__(*args, **kwargs)
            TkinterDnD._require(self)
        else:
            super().__init__(*args, **kwargs)


def main():
    """アプリケーションのエントリーポイント"""
    # カスタムルートウィンドウを使用
    if HAS_DND:
        # TkinterDnDとCustomTkinterを組み合わせる
        root = TkinterDnD.Tk()
        # CustomTkinterのスタイルを適用
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
    else:
        root = ctk.CTk()

    app = BackgroundRemoverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
