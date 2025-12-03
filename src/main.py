"""動画背景除去ツール - GUI (CustomTkinter版)

UI仕様書: .claude/workspace/task.md
"""

import atexit
import contextlib
import os
import signal
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk
import cv2
from PIL import Image, ImageDraw


# tkinterdnd2のインポート（ドラッグ＆ドロップ対応）
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DRAG_AND_DROP_AVAILABLE = True
except ImportError:
    DRAG_AND_DROP_AVAILABLE = False

from rvm_model import RVMModel, download_model
from utils import (
    SUPPORTED_INPUT_EXTENSIONS,
    DeviceInfo,
    format_time,
    get_device_info,
    is_supported_video,
)
from video_processor import (
    OutputParams,
    ProcessingCancelled,
    VideoProcessor,
    _get_subprocess_args,
    calculate_optimal_params,
    get_video_info,
)


# =============================================================================
# カラーテーマ（META AI LABO準拠）
# =============================================================================
COLORS = {
    "primary": "#8BC34A",  # 葉っぱの黄緑（ブランドカラー）
    "primary_dark": "#689F38",  # 葉っぱの濃い緑
    "primary_hover": "#7CB342",  # ホバー時
    "secondary": "#263238",  # フィルム枠のダークネイビー
    "success": "#4CAF50",  # 成功
    "warning": "#FF9800",  # 警告
    "danger": "#F44336",  # エラー
    "danger_hover": "#FFEBEE",  # 危険ボタンホバー時
    "disabled": "#BDBDBD",  # 無効状態
    "bg": "#FAFAFA",  # 明るい背景
    "card": "#FFFFFF",  # カード背景
    "border": "#E0E0E0",  # ボーダー
    "text": "#263238",  # メインテキスト
    "text_secondary": "#616161",  # サブテキスト
    "drop_zone": "#F5F5F5",  # ドロップゾーン
    "drop_zone_hover": "#E8F5E9",  # ドロップゾーンホバー
    "toast_bg": "#263238",  # トースト背景
    "toast_text": "#FFFFFF",  # トーストテキスト
}

# =============================================================================
# フォントサイズ（アクセシビリティ対応・大きめ）
# =============================================================================
FONT_SIZES = {
    "title": 32,
    "subtitle": 18,
    "button": 24,
    "filename": 22,
    "video_info": 18,
    "hint": 17,
    "progress_percent": 40,
    "frame_count": 18,
    "footer": 16,
    "dialog_title": 24,
    "dialog_body": 18,
    "dialog_button": 20,
    "toast": 18,
}

# =============================================================================
# サイズ定数
# =============================================================================
SIZES = {
    "window_initial": (700, 850),
    "window_min": (600, 750),
    "content_max_width": 800,
    "thumbnail_max_width": 500,
    "thumbnail_aspect_ratio": 16 / 9,
    "button_height": 60,
    "button_max_width": 500,
    "circular_progress": 140,
    "padding": 24,
    "dialog_width": 420,
    "dialog_button_height": 50,
    "logo_size": 48,
}

# =============================================================================
# タイミング定数（ミリ秒）
# =============================================================================
TIMING_MS = {
    "thumbnail_update_delay": 50,  # サムネイル更新の遅延
    "auto_close_dialog": 3000,  # 完了ダイアログの自動クローズ
    "window_resize_threshold": 10,  # ウィンドウリサイズ検知の閾値(px)
}

# =============================================================================
# 進捗テキストのフォントサイズ調整閾値
# =============================================================================
PROGRESS_TEXT_THRESHOLDS = {
    "short_text_max_length": 14,  # 100%サイズで表示する最大文字数
    "medium_text_max_length": 17,  # 85%サイズで表示する最大文字数
    "long_text_max_length": 20,  # 70%サイズで表示する最大文字数
    # それ以上は60%サイズ
}

# フレーム数表示の短縮形式閾値
FRAME_COUNT_THRESHOLDS = {
    "use_k_suffix": 10000,  # この値以上で "12.3k" 形式に短縮
}


def format_frame_count(current: int, total: int) -> str:
    """フレーム数を適切な形式でフォーマットする

    10000以上の場合は "12.3k / 98.8k f" 形式に短縮

    Args:
        current: 現在のフレーム数
        total: 総フレーム数

    Returns:
        フォーマットされた文字列
    """
    threshold = FRAME_COUNT_THRESHOLDS["use_k_suffix"]

    if total >= threshold:
        # 短縮形式: "12.3k / 98.8k f"
        current_k = current / 1000
        total_k = total / 1000
        return f"{current_k:.1f}k / {total_k:.1f}k f"

    # 通常形式: "1,234 / 5,678 f"
    return f"{current:,} / {total:,} f"


def calculate_frame_font_size(text: str, base_font_size: int = 18) -> int:
    """フレーム数テキストのフォントサイズを動的に計算する

    Args:
        text: 表示するテキスト
        base_font_size: 基本フォントサイズ

    Returns:
        int: フォントサイズ
    """
    text_length = len(text)
    short_max = PROGRESS_TEXT_THRESHOLDS["short_text_max_length"]
    medium_max = PROGRESS_TEXT_THRESHOLDS["medium_text_max_length"]
    long_max = PROGRESS_TEXT_THRESHOLDS["long_text_max_length"]

    if text_length <= short_max:
        return base_font_size
    if text_length <= medium_max:
        return int(base_font_size * 0.85)
    if text_length <= long_max:
        return int(base_font_size * 0.70)
    # long_maxより長い場合は60%サイズ
    return int(base_font_size * 0.60)


# =============================================================================
# 円形プログレスバー描画定数
# =============================================================================
CIRCULAR_PROGRESS_STYLE = {
    "outline_width": 2,  # アウトラインの太さ
}


# =============================================================================
# 多重起動防止
# =============================================================================
class SingleInstanceLock:
    """アプリの多重起動を防止するロッククラス"""

    LOCK_FILE = Path(tempfile.gettempdir()) / "background_remover_video.lock"

    def __init__(self):
        self._lock_acquired = False

    def _is_process_running(self, pid: int) -> bool:
        """指定したPIDのプロセスが動作中か確認"""
        try:
            if sys.platform == "win32":
                # Windows用: ctypesでプロセス存在確認
                import ctypes

                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            else:
                # Unix系: シグナル0で確認
                os.kill(pid, 0)
                return True
        except Exception:
            return False

    def acquire(self) -> bool:
        """ロックを取得。成功したらTrue、既に別インスタンスが動作中ならFalse"""
        # ロックファイルが存在するか確認
        if self.LOCK_FILE.exists():
            try:
                pid = int(self.LOCK_FILE.read_text().strip())
                if self._is_process_running(pid):
                    # 別のインスタンスが動作中
                    return False
                # プロセスは終了しているが、ロックファイルが残っている
                self.LOCK_FILE.unlink()
            except (ValueError, OSError):
                # ロックファイルが壊れている場合は削除
                with contextlib.suppress(OSError):
                    self.LOCK_FILE.unlink()

        # ロックファイルを作成
        try:
            self.LOCK_FILE.write_text(str(os.getpid()))
            self._lock_acquired = True
            return True
        except OSError:
            return False

    def release(self):
        """ロックを解放"""
        if self._lock_acquired:
            with contextlib.suppress(OSError):
                self.LOCK_FILE.unlink()
            self._lock_acquired = False


def _bring_existing_window_to_front():
    """既存のウィンドウを前面に出す"""
    window_title = "動画背景除去ツール by META AI LABO"

    try:
        if sys.platform == "darwin":
            # macOS: AppleScriptでウィンドウをアクティブ化
            script = """
            tell application "System Events"
                set frontmost of every process whose name contains "Python" to true
            end tell
            """
            subprocess.run(["osascript", "-e", script], capture_output=True)
        elif sys.platform == "win32":
            # Windows: ctypesでウィンドウを前面に出す
            import ctypes

            user32 = ctypes.windll.user32

            # ウィンドウを検索
            hwnd = user32.FindWindowW(None, window_title)
            if hwnd:
                # ウィンドウを前面に出す
                SW_RESTORE = 9
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
    except Exception:
        pass  # エラーがあっても静かに終了


# =============================================================================
# 円形プログレスバー
# =============================================================================
class CircularProgress(ctk.CTkFrame):
    """円形プログレスバー（透明背景、白縁黒文字）"""

    def __init__(
        self,
        master,
        size: int = SIZES["circular_progress"],
        line_width: int = 10,
        progress_color: str = COLORS["primary"],
        bg_color: str = COLORS["border"],
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._size = size
        self._line_width = line_width
        self._progress_color = progress_color
        self._bg_color = bg_color
        self._progress = 0.0
        self._percent_text = "0%"
        self._frame_text = ""

        # Canvasを作成（親フレームの背景色に合わせて視覚的に透明に）
        self.canvas = ctk.CTkCanvas(
            self,
            width=size,
            height=size,
            bg=COLORS["card"],  # 親のサムネイルフレームと同じ白背景
            highlightthickness=0,
        )
        self.canvas.pack()

        self._draw_progress()

    def _draw_text_with_outline(
        self, x: int, y: int, text: str, font_size: int, bold: bool = False
    ):
        """白縁付きの黒文字を描画"""
        font_weight = "bold" if bold else "normal"
        font = (ctk.CTkFont().cget("family"), font_size, font_weight)

        # 白い縁取り（8方向にオフセットして描画）
        outline_color = "white"
        outline_width = CIRCULAR_PROGRESS_STYLE["outline_width"]
        for dx in [-outline_width, 0, outline_width]:
            for dy in [-outline_width, 0, outline_width]:
                if dx != 0 or dy != 0:
                    self.canvas.create_text(
                        x + dx,
                        y + dy,
                        text=text,
                        font=font,
                        fill=outline_color,
                        anchor="center",
                    )

        # 黒い本文
        self.canvas.create_text(
            x,
            y,
            text=text,
            font=font,
            fill=COLORS["text"],
            anchor="center",
        )

    def _draw_progress(self):
        """円とテキストを描画"""
        self.canvas.delete("all")

        center = self._size // 2

        # 背景円（トラック）
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

        # パーセンテージテキスト（白縁黒文字）
        self._draw_text_with_outline(
            center,
            center - 10,
            self._percent_text,
            FONT_SIZES["progress_percent"],
            bold=True,
        )

        # フレーム数テキスト（白縁黒文字、動的フォントサイズ）
        if self._frame_text:
            # 円内に収まるようにフォントサイズを動的に調整
            frame_font_size = self._calculate_frame_font_size(self._frame_text)
            self._draw_text_with_outline(
                center,
                center + 25,
                self._frame_text,
                frame_font_size,
                bold=False,
            )

    def _calculate_frame_font_size(self, text: str) -> int:
        """フレーム数テキストのフォントサイズを動的に計算する

        Args:
            text: 表示するテキスト

        Returns:
            int: フォントサイズ
        """
        base_font_size = FONT_SIZES["frame_count"]  # 18
        return calculate_frame_font_size(text, base_font_size)

    def set(self, value: float, current: int = 0, total: int = 0):
        """進捗を設定 (0.0 ~ 1.0)"""
        self._progress = max(0.0, min(1.0, value))
        self._percent_text = f"{int(self._progress * 100)}%"
        if total > 0:
            self._frame_text = format_frame_count(current, total)
        self._draw_progress()

    def get(self) -> float:
        """現在の進捗を取得"""
        return self._progress

    def reset(self):
        """リセット"""
        self._progress = 0.0
        self._percent_text = "0%"
        self._frame_text = ""
        self._draw_progress()


# =============================================================================
# トースト通知
# =============================================================================
class Toast(ctk.CTkFrame):
    """トースト通知"""

    def __init__(self, master, message: str, duration: int = 2000):
        super().__init__(
            master,
            fg_color=COLORS["toast_bg"],
            corner_radius=8,
        )

        self.label = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=FONT_SIZES["toast"]),
            text_color=COLORS["toast_text"],
        )
        self.label.pack(padx=16, pady=10)

        # 画面下部中央に配置
        self.place(relx=0.5, rely=0.9, anchor="center")

        # 指定時間後に自動消去
        self.after(duration, self._fade_out)

    def _fade_out(self):
        """フェードアウト"""
        self.destroy()


# =============================================================================
# カスタムダイアログ
# =============================================================================
class CustomDialog(ctk.CTkToplevel):
    """カスタムダイアログの基底クラス"""

    def __init__(
        self,
        parent,
        title: str,
        icon: str,
        message: str,
        sub_message: str = "",
        width: int = SIZES["dialog_width"],
        height: int = 220,
    ):
        super().__init__(parent)

        # タイトルバー（✕、最小化等）を非表示にする
        self.overrideredirect(True)

        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # 中央に配置
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - width) // 2
        y = parent.winfo_y() + (parent.winfo_height() - height) // 2
        self.geometry(f"+{x}+{y}")

        # ダイアログに枠線を追加（タイトルバーがないため境界を明確に）
        self.configure(border_width=1, border_color=COLORS["border"])

        # メインフレーム
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(expand=True, fill="both", padx=SIZES["padding"], pady=SIZES["padding"])

        # アイコン
        ctk.CTkLabel(
            self.main_frame,
            text=icon,
            font=ctk.CTkFont(size=36),
        ).pack(pady=(0, 8))

        # メッセージ
        ctk.CTkLabel(
            self.main_frame,
            text=message,
            font=ctk.CTkFont(size=FONT_SIZES["dialog_title"], weight="bold"),
            text_color=COLORS["text"],
        ).pack(pady=(0, 4))

        # サブメッセージ
        if sub_message:
            ctk.CTkLabel(
                self.main_frame,
                text=sub_message,
                font=ctk.CTkFont(size=FONT_SIZES["dialog_body"]),
                text_color=COLORS["text_secondary"],
                wraplength=width - 48,
            ).pack(pady=(0, 16))

        # ボタンフレーム
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(fill="x", pady=(8, 0))

        self.result = None

    def add_button(
        self,
        text: str,
        command: Callable,
        primary: bool = False,
        danger: bool = False,
    ):
        """ボタンを追加"""
        if primary:
            fg_color = COLORS["primary"]
            hover_color = COLORS["primary_hover"]
            text_color = "white"
            border_width = 0
            border_color = None
        elif danger:
            fg_color = "transparent"
            hover_color = "#FFEBEE"
            text_color = COLORS["danger"]
            border_width = 1
            border_color = COLORS["danger"]
        else:
            fg_color = "transparent"
            hover_color = COLORS["drop_zone"]
            text_color = COLORS["text"]
            border_width = 1
            border_color = COLORS["border"]

        btn = ctk.CTkButton(
            self.button_frame,
            text=text,
            font=ctk.CTkFont(size=FONT_SIZES["dialog_button"]),
            height=SIZES["dialog_button_height"],
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            border_width=border_width,
            border_color=border_color,
            command=command,
        )
        btn.pack(side="left", expand=True, fill="x", padx=4)
        return btn


# =============================================================================
# メインアプリケーション
# =============================================================================
class BackgroundRemoverApp:
    """動画背景除去アプリケーションのメインクラス"""

    # 画面状態
    STATE_INITIAL = "initial"
    STATE_FILE_SELECTED = "file_selected"
    STATE_PROCESSING = "processing"
    STATE_COMPLETE = "complete"

    def __init__(self, root):
        """アプリケーションを初期化する"""
        self.root = root
        self.root.title("動画背景除去ツール by META AI LABO")
        self.root.geometry(f"{SIZES['window_initial'][0]}x{SIZES['window_initial'][1]}")
        self.root.minsize(SIZES["window_min"][0], SIZES["window_min"][1])
        self.root.resizable(True, True)

        # ライトモード固定
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")

        # 背景色を設定
        try:
            self.root.configure(fg_color=COLORS["bg"])
        except Exception:
            self.root.configure(bg=COLORS["bg"])

        # ウィンドウアイコンを設定（タスクバー用）
        self._set_window_icon()

        # 状態変数
        self.current_state = self.STATE_INITIAL
        self.input_path: str = ""
        self.output_path: str = ""
        self.temp_output_path: str = ""
        self.is_processing: bool = False
        self.file_selected: bool = False
        self.output_params: OutputParams | None = None  # 出力パラメータ（調整情報）

        # デバイス情報を取得
        self.device_info: DeviceInfo = get_device_info()

        # モデル（遅延ロード）
        self.model: RVMModel | None = None
        self.processor: VideoProcessor | None = None

        # 画像を保持
        self.logo_image = None
        self.thumbnail_image = None
        self.processed_thumbnail_image = None
        self.checkerboard_image = None

        # 元のPIL画像を保持（リサイズ用）
        self._original_thumbnail_pil: Image.Image | None = None
        self._original_processed_pil: Image.Image | None = None
        self._last_window_width: int = 0

        # 動画情報
        self.video_duration: float = 0
        self.video_frame_count: int = 0

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

    def _set_window_icon(self) -> None:
        """ウィンドウアイコンを設定（タスクバー用）"""
        asset_path = self._get_asset_path() / "assets"
        try:
            # Windows: .icoファイルを使用
            ico_path = asset_path / "icon.ico"
            if ico_path.exists():
                self.root.iconbitmap(str(ico_path))
                return

            # フォールバック: .pngファイルを使用
            png_path = asset_path / "icon.png"
            if png_path.exists():
                import tkinter as tk

                icon_image = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, icon_image)
                # 参照を保持（ガベージコレクション防止）
                self._icon_image = icon_image
        except Exception:
            pass  # アイコン設定に失敗しても続行

    def _load_logo(self) -> ctk.CTkImage | None:
        """ロゴ画像を読み込む"""
        logo_path = self._get_asset_path() / "assets" / "icon.png"
        try:
            if logo_path.exists():
                img = Image.open(logo_path)
                return ctk.CTkImage(light_image=img, size=(SIZES["logo_size"], SIZES["logo_size"]))
        except Exception:
            pass
        return None

    def _extract_thumbnail(self, video_path: str) -> ctk.CTkImage | None:
        """動画からサムネイルを抽出する"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None

            ret, frame = cap.read()
            cap.release()

            if not ret:
                return None

            # BGRからRGBに変換
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            # 元画像を保持（リサイズ用）
            self._original_thumbnail_pil = img.copy()

            # サムネイルサイズを計算
            width, height = self._calculate_thumbnail_size()

            # アスペクト比を維持してリサイズ
            img = img.resize((width, height), Image.Resampling.LANCZOS)

            return ctk.CTkImage(light_image=img, size=(width, height))

        except Exception:
            return None

    def _calculate_thumbnail_size(self) -> tuple[int, int]:
        """現在のウィンドウ幅に基づいてサムネイルサイズを計算"""
        window_width = self.root.winfo_width()
        # ウィンドウ幅からパディングを引いた幅を使用（最小200px）
        available_width = window_width - SIZES["padding"] * 4  # 左右のパディング分
        width = max(200, available_width)

        # 元画像のアスペクト比を使用（あれば）
        if self._original_thumbnail_pil:
            orig_w, orig_h = self._original_thumbnail_pil.size
            aspect_ratio = orig_w / orig_h
        else:
            aspect_ratio = SIZES["thumbnail_aspect_ratio"]

        height = int(width / aspect_ratio)
        return width, height

    def _on_window_resize(self, event) -> None:
        """ウィンドウリサイズ時のハンドラ"""
        # rootウィンドウのリサイズのみ処理
        if event.widget != self.root:
            return

        # thumbnail_labelが存在しない場合はスキップ
        if not hasattr(self, "thumbnail_label"):
            return

        # 幅が変わった場合のみサムネイルを更新
        new_width = self.root.winfo_width()
        resize_threshold = TIMING_MS["window_resize_threshold"]
        if abs(new_width - self._last_window_width) > resize_threshold:
            self._last_window_width = new_width
            # 少し遅延させてリサイズ完了後に更新
            self.root.after(TIMING_MS["thumbnail_update_delay"], self._update_thumbnail_size)

    def _update_thumbnail_size(self) -> None:
        """ウィンドウサイズに合わせてサムネイルを更新"""
        # 処理中は更新しない
        if self.is_processing:
            return

        # サムネイルラベルが存在しない、または表示されていない場合はスキップ
        if not hasattr(self, "thumbnail_label") or not self.thumbnail_label.winfo_ismapped():
            return

        # 元画像がない場合はスキップ
        if not self._original_thumbnail_pil and not self._original_processed_pil:
            return

        width, height = self._calculate_thumbnail_size()

        # 完了状態で処理済み画像がある場合
        if self.current_state == self.STATE_COMPLETE and self._original_processed_pil:
            img = self._original_processed_pil.resize((width, height), Image.Resampling.LANCZOS)
            checkerboard = self._create_checkerboard(width, height)
            checkerboard.paste(img, (0, 0), img)
            self.processed_thumbnail_image = ctk.CTkImage(
                light_image=checkerboard, size=(width, height)
            )
            self.thumbnail_label.configure(image=self.processed_thumbnail_image)
            # 強制的に再描画
            self.thumbnail_label.update_idletasks()

        # ファイル選択状態で元画像がある場合
        elif self._original_thumbnail_pil:
            img = self._original_thumbnail_pil.resize((width, height), Image.Resampling.LANCZOS)
            self.thumbnail_image = ctk.CTkImage(light_image=img, size=(width, height))
            self.thumbnail_label.configure(image=self.thumbnail_image)
            # 強制的に再描画
            self.thumbnail_label.update_idletasks()

    def _extract_processed_thumbnail(self, video_path: str) -> ctk.CTkImage | None:
        """処理済み動画からサムネイルを抽出（市松模様背景）

        ProRes 4444のアルファチャンネルはOpenCVで読めないため、
        ffmpegでPNGとして抽出する
        """
        try:
            # 一時ファイルにPNGとして抽出（ffmpegでアルファチャンネル対応）
            temp_png = tempfile.mktemp(suffix=".png")

            # ffmpegのパスを取得
            ffmpeg_path = self._get_ffmpeg_path()

            # ffmpegで最初のフレームをPNGとして抽出（アルファチャンネル付き）
            cmd = [
                ffmpeg_path,
                "-i",
                video_path,
                "-vframes",
                "1",
                "-y",
                temp_png,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                **_get_subprocess_args(),
            )

            if result.returncode != 0 or not Path(temp_png).exists():
                # ffmpegが失敗した場合はOpenCVにフォールバック
                return self._extract_processed_thumbnail_fallback(video_path)

            # PNGを読み込み（アルファチャンネル付き）
            img = Image.open(temp_png).convert("RGBA")

            # 一時ファイルを削除
            with contextlib.suppress(Exception):
                os.remove(temp_png)

            # 元画像を保持（リサイズ用）
            self._original_processed_pil = img.copy()

            # サムネイルサイズを計算
            width, height = self._calculate_thumbnail_size()

            # アスペクト比を維持してリサイズ
            img_resized = img.resize((width, height), Image.Resampling.LANCZOS)

            # 市松模様背景を作成
            checkerboard = self._create_checkerboard(width, height)

            # 市松模様の上に処理済み画像を合成
            checkerboard.paste(img_resized, (0, 0), img_resized)

            return ctk.CTkImage(light_image=checkerboard, size=(width, height))

        except Exception:
            return None

    def _extract_processed_thumbnail_fallback(self, video_path: str) -> ctk.CTkImage | None:
        """OpenCVを使ったフォールバック（アルファなし）"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None

            ret, frame = cap.read()
            cap.release()

            if not ret:
                return None

            # BGRからRGBに変換
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb).convert("RGBA")

            # 元画像を保持（リサイズ用）
            self._original_processed_pil = img.copy()

            # サムネイルサイズを計算
            width, height = self._calculate_thumbnail_size()

            # アスペクト比を維持してリサイズ
            img_resized = img.resize((width, height), Image.Resampling.LANCZOS)

            # 市松模様背景を作成
            checkerboard = self._create_checkerboard(width, height)

            # 画像を合成（アルファなしなのでそのまま）
            checkerboard.paste(img_resized, (0, 0))

            return ctk.CTkImage(light_image=checkerboard, size=(width, height))

        except Exception:
            return None

    def _create_checkerboard(self, width: int, height: int, cell_size: int = 10) -> Image.Image:
        """市松模様（チェッカーボード）画像を生成する

        Args:
            width: 画像の幅
            height: 画像の高さ
            cell_size: 1マスのサイズ（ピクセル）

        Returns:
            Image.Image: 市松模様のRGBA画像
        """
        # 白とライトグレーの2色
        color1 = (255, 255, 255, 255)  # 白
        color2 = (204, 204, 204, 255)  # ライトグレー

        checkerboard = Image.new("RGBA", (width, height), color1)
        draw = ImageDraw.Draw(checkerboard)

        for y in range(0, height, cell_size):
            for x in range(0, width, cell_size):
                # 市松模様のパターン
                if (x // cell_size + y // cell_size) % 2 == 1:
                    draw.rectangle([x, y, x + cell_size - 1, y + cell_size - 1], fill=color2)

        return checkerboard

    def _get_ffmpeg_path(self) -> str:
        """ffmpegのパスを取得"""
        if getattr(sys, "frozen", False):
            # PyInstallerでパッケージ化された場合
            base_path = Path(sys._MEIPASS)
            if sys.platform == "win32":
                ffmpeg_path = base_path / "ffmpeg" / "ffmpeg.exe"
            else:
                ffmpeg_path = base_path / "ffmpeg" / "ffmpeg"
            if ffmpeg_path.exists():
                return str(ffmpeg_path)

        # システムのffmpegを使用
        return "ffmpeg"

    def _setup_ui(self) -> None:
        """UIを構築する"""
        # メインフレーム（最大幅制限 + 中央配置）
        self.outer_frame = ctk.CTkFrame(self.root, fg_color=COLORS["bg"])
        self.outer_frame.pack(fill="both", expand=True)

        self.main_frame = ctk.CTkFrame(
            self.outer_frame,
            fg_color=COLORS["bg"],
            width=SIZES["content_max_width"],
        )
        self.main_frame.pack(fill="both", expand=True, padx=SIZES["padding"], pady=SIZES["padding"])

        # ヘッダー部分（ロゴ左配置 + タイトル）
        self._setup_header()

        # コンテンツエリア
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, pady=(16, 0))

        # ドロップゾーン
        self._setup_drop_zone()

        # サムネイル表示エリア（初期は非表示）
        self._setup_thumbnail_area()

        # ボタンエリア
        self._setup_buttons()

        # フッター
        self._setup_footer()

        # 初期状態を設定
        self._update_ui_state()

        # ウィンドウリサイズイベントをバインド
        self.root.bind("<Configure>", self._on_window_resize)

    def _setup_header(self) -> None:
        """ヘッダーを設定"""
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x")

        # ロゴとタイトルの横並びフレーム
        title_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_row.pack(anchor="w")

        # ロゴ
        self.logo_image = self._load_logo()
        if self.logo_image:
            logo_label = ctk.CTkLabel(title_row, image=self.logo_image, text="")
            logo_label.pack(side="left", padx=(0, 12))

        # タイトル部分
        title_text_frame = ctk.CTkFrame(title_row, fg_color="transparent")
        title_text_frame.pack(side="left")

        ctk.CTkLabel(
            title_text_frame,
            text="動画背景除去ツール",
            font=ctk.CTkFont(size=FONT_SIZES["title"], weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_text_frame,
            text="by META AI LABO",
            font=ctk.CTkFont(size=FONT_SIZES["subtitle"]),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w")

    def _setup_drop_zone(self) -> None:
        """ドロップゾーンを設定"""
        self.drop_zone_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color=COLORS["drop_zone"],
            corner_radius=12,
            border_width=2,
            border_color=COLORS["border"],
        )

        # 縦横中央揃え用のコンテナ
        drop_content = ctk.CTkFrame(self.drop_zone_frame, fg_color="transparent")
        drop_content.place(relx=0.5, rely=0.5, anchor="center")

        # アイコン（大きめ）
        self.drop_icon_label = ctk.CTkLabel(
            drop_content,
            text="📁",
            font=ctk.CTkFont(size=64),
        )
        self.drop_icon_label.pack(pady=(0, 16))

        # テキスト（大きめ）
        self.drop_text_label = ctk.CTkLabel(
            drop_content,
            text="動画をドラッグ＆ドロップ\nまたは クリック",
            font=ctk.CTkFont(size=28),
            text_color=COLORS["text_secondary"],
            justify="center",
        )
        self.drop_text_label.pack()

        # 対応形式（大きめ）
        self.drop_hint_label = ctk.CTkLabel(
            drop_content,
            text=".mp4  .mov  .m4v",
            font=ctk.CTkFont(size=20),
            text_color=COLORS["text_secondary"],
        )
        self.drop_hint_label.pack(pady=(12, 0))

        # クリックイベント
        for widget in [
            self.drop_zone_frame,
            drop_content,
            self.drop_icon_label,
            self.drop_text_label,
            self.drop_hint_label,
        ]:
            widget.bind("<Button-1>", lambda e: self._select_input())

        # ドラッグ＆ドロップ
        if DRAG_AND_DROP_AVAILABLE:
            self.drop_zone_frame.drop_target_register(DND_FILES)
            self.drop_zone_frame.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_zone_frame.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.drop_zone_frame.dnd_bind("<<DragLeave>>", self._on_drag_leave)

    def _setup_thumbnail_area(self) -> None:
        """サムネイル表示エリアを設定"""
        self.thumbnail_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color=COLORS["card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )

        # サムネイル画像
        self.thumbnail_label = ctk.CTkLabel(
            self.thumbnail_frame,
            text="",
            image=None,
        )
        self.thumbnail_label.pack(pady=(16, 8))

        # 円形プログレス（サムネイル上にオーバーレイ、初期は非表示）
        self.progress_overlay = ctk.CTkFrame(
            self.thumbnail_frame,
            fg_color="transparent",
        )

        self.circular_progress = CircularProgress(self.progress_overlay)
        self.circular_progress.pack()

        # ファイル名
        self.filename_label = ctk.CTkLabel(
            self.thumbnail_frame,
            text="",
            font=ctk.CTkFont(size=FONT_SIZES["filename"]),
            text_color=COLORS["text"],
        )
        self.filename_label.pack(pady=(8, 4))

        # 動画情報
        self.video_info_label = ctk.CTkLabel(
            self.thumbnail_frame,
            text="",
            font=ctk.CTkFont(size=FONT_SIZES["video_info"]),
            text_color=COLORS["text_secondary"],
        )
        self.video_info_label.pack(pady=(0, 4))

        # 完了メッセージ（初期は非表示）
        self.complete_label = ctk.CTkLabel(
            self.thumbnail_frame,
            text="✅ 完了!",
            font=ctk.CTkFont(size=FONT_SIZES["dialog_title"], weight="bold"),
            text_color=COLORS["success"],
        )

        # サムネイルエリアもクリック可能に（ファイル選択）
        self.thumbnail_frame.bind("<Button-1>", lambda e: self._on_thumbnail_click())
        self.thumbnail_label.bind("<Button-1>", lambda e: self._on_thumbnail_click())

    def _setup_buttons(self) -> None:
        """ボタンを設定"""
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(fill="x", pady=(16, 0))

        # メインボタン（背景を除去する / ファイルを保存）
        self.main_button = ctk.CTkButton(
            self.button_frame,
            text="🚀 背景を除去する",
            font=ctk.CTkFont(size=FONT_SIZES["button"], weight="bold"),
            height=SIZES["button_height"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color="white",
            corner_radius=8,
            command=self._on_main_button_click,
        )
        self.main_button.pack(fill="x", pady=(0, 8))

        # キャンセルボタン（処理中のみ表示）
        self.cancel_button = ctk.CTkButton(
            self.button_frame,
            text="キャンセル",
            font=ctk.CTkFont(size=FONT_SIZES["button"]),
            height=SIZES["button_height"],
            fg_color="transparent",
            hover_color=COLORS["danger_hover"],
            text_color=COLORS["danger"],
            border_width=1,
            border_color=COLORS["danger"],
            corner_radius=8,
            command=self._on_cancel_click,
        )

        # リンク（別の動画を選択 / やり直す）
        self.link_frame = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        self.link_frame.pack(fill="x", pady=(8, 0))

        self.select_another_link = ctk.CTkButton(
            self.link_frame,
            text="別の動画を選択",
            font=ctk.CTkFont(size=FONT_SIZES["video_info"]),
            fg_color="transparent",
            hover_color=COLORS["drop_zone"],
            text_color=COLORS["primary_dark"],
            command=self._select_input,
        )

        self.retry_link = ctk.CTkButton(
            self.link_frame,
            text="やり直す",
            font=ctk.CTkFont(size=FONT_SIZES["video_info"]),
            fg_color="transparent",
            hover_color=COLORS["drop_zone"],
            text_color=COLORS["primary_dark"],
            command=self._on_retry,
        )

        self.process_another_link = ctk.CTkButton(
            self.link_frame,
            text="別の動画を処理",
            font=ctk.CTkFont(size=FONT_SIZES["video_info"]),
            fg_color="transparent",
            hover_color=COLORS["drop_zone"],
            text_color=COLORS["primary_dark"],
            command=self._on_process_another,
        )

    def _setup_footer(self) -> None:
        """フッターを設定"""
        footer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        footer_frame.pack(fill="x", side="bottom", pady=(16, 0))

        device_icon = "⚡" if self.device_info.is_gpu else "💻"
        speed_text = "高速処理" if self.device_info.is_gpu else "標準処理"

        ctk.CTkLabel(
            footer_frame,
            text=f"{device_icon} {self.device_info.name} - {speed_text}",
            font=ctk.CTkFont(size=FONT_SIZES["footer"]),
            text_color=COLORS["success"] if self.device_info.is_gpu else COLORS["warning"],
        ).pack()

    def _update_ui_state(self) -> None:
        """現在の状態に応じてUIを更新（差分更新方式）"""
        state_handlers = {
            self.STATE_INITIAL: self._update_ui_for_initial_state,
            self.STATE_FILE_SELECTED: self._update_ui_for_file_selected_state,
            self.STATE_PROCESSING: self._update_ui_for_processing_state,
            self.STATE_COMPLETE: self._update_ui_for_complete_state,
        }

        handler = state_handlers.get(self.current_state)
        if handler:
            handler()

        # 再描画を確定
        self.root.update_idletasks()

    def _update_ui_for_initial_state(self) -> None:
        """初期状態のUI更新"""
        drop_zone_visible = self.drop_zone_frame.winfo_ismapped()
        thumbnail_visible = self.thumbnail_frame.winfo_ismapped()

        # 初期状態：ドロップゾーン + グレーアウトのボタン
        if thumbnail_visible:
            self.thumbnail_frame.pack_forget()
        if not drop_zone_visible:
            self.drop_zone_frame.pack(fill="both", expand=True)

        # ボタン・リンク類を非表示
        self.main_button.pack_forget()
        self.cancel_button.pack_forget()
        self.link_frame.pack_forget()
        self.select_another_link.pack_forget()
        self.retry_link.pack_forget()
        self.process_another_link.pack_forget()
        self.progress_overlay.place_forget()
        self.complete_label.pack_forget()

        # メインボタンを設定
        self.main_button.configure(
            text="🚀 背景を除去する",
            state="disabled",
            fg_color=COLORS["disabled"],
        )
        self.main_button.pack(fill="x", pady=(16, 0))

    def _update_ui_for_file_selected_state(self) -> None:
        """ファイル選択後のUI更新"""
        drop_zone_visible = self.drop_zone_frame.winfo_ismapped()
        thumbnail_visible = self.thumbnail_frame.winfo_ismapped()

        if drop_zone_visible:
            self.drop_zone_frame.pack_forget()
        if not thumbnail_visible:
            self.thumbnail_frame.pack(fill="both", expand=True)

        # 不要な要素を非表示
        self.cancel_button.pack_forget()
        self.progress_overlay.place_forget()
        self.complete_label.pack_forget()
        self.retry_link.pack_forget()
        self.process_another_link.pack_forget()

        # メインボタンを設定
        self.main_button.pack_forget()
        self.main_button.configure(
            text="🚀 背景を除去する",
            state="normal",
            fg_color=COLORS["primary"],
        )
        self.main_button.pack(fill="x", pady=(0, 8))

        # リンクを設定
        self.link_frame.pack_forget()
        self.select_another_link.pack_forget()
        self.link_frame.pack(fill="x", pady=(8, 0))
        self.select_another_link.pack(side="left", expand=True)

    def _update_ui_for_processing_state(self) -> None:
        """処理中のUI更新"""
        drop_zone_visible = self.drop_zone_frame.winfo_ismapped()
        thumbnail_visible = self.thumbnail_frame.winfo_ismapped()

        if drop_zone_visible:
            self.drop_zone_frame.pack_forget()
        if not thumbnail_visible:
            self.thumbnail_frame.pack(fill="both", expand=True)

        # 不要な要素を非表示
        self.main_button.pack_forget()
        self.link_frame.pack_forget()
        self.select_another_link.pack_forget()
        self.retry_link.pack_forget()
        self.process_another_link.pack_forget()
        self.complete_label.pack_forget()

        # 円形プログレスをサムネイル上にオーバーレイ
        self.progress_overlay.place(relx=0.5, rely=0.35, anchor="center")
        self.cancel_button.pack(fill="x")

    def _update_ui_for_complete_state(self) -> None:
        """処理完了時のUI更新"""
        drop_zone_visible = self.drop_zone_frame.winfo_ismapped()
        thumbnail_visible = self.thumbnail_frame.winfo_ismapped()

        if drop_zone_visible:
            self.drop_zone_frame.pack_forget()
        if not thumbnail_visible:
            self.thumbnail_frame.pack(fill="both", expand=True)

        # 不要な要素を非表示
        self.cancel_button.pack_forget()
        self.progress_overlay.place_forget()
        self.select_another_link.pack_forget()

        # 完了ラベルとボタンを設定
        self.complete_label.pack_forget()
        self.complete_label.pack(pady=(0, 16))
        self.main_button.pack_forget()
        self.main_button.configure(
            text="💾 ファイルを保存",
            state="normal",
            fg_color=COLORS["primary"],
        )
        self.main_button.pack(fill="x", pady=(0, 8))

        # リンクを設定
        self.link_frame.pack_forget()
        self.retry_link.pack_forget()
        self.process_another_link.pack_forget()
        self.link_frame.pack(fill="x", pady=(8, 0))
        self.retry_link.pack(side="left", expand=True)
        self.process_another_link.pack(side="left", expand=True)

    def _on_drop(self, event) -> None:
        """ファイルがドロップされたときの処理"""
        # 処理中は無視
        if self.current_state == self.STATE_PROCESSING:
            self._reset_drop_zone()
            return

        data = event.data
        if data.startswith("{"):
            path = data.strip("{}")
        else:
            path = data.split()[0] if " " in data else data

        self._reset_drop_zone()

        # 既にファイルが選択されている場合はトースト表示
        if self.file_selected:
            self._set_input_file(path, show_toast=True)
        else:
            self._set_input_file(path)

    def _on_drag_enter(self, event) -> None:
        """ドラッグがドロップゾーンに入ったときの処理"""
        self.drop_zone_frame.configure(
            fg_color=COLORS["drop_zone_hover"],
            border_color=COLORS["primary"],
        )

    def _on_drag_leave(self, event) -> None:
        """ドラッグがドロップゾーンから出たときの処理"""
        self._reset_drop_zone()

    def _reset_drop_zone(self) -> None:
        """ドロップゾーンを初期状態に戻す"""
        self.drop_zone_frame.configure(
            fg_color=COLORS["drop_zone"],
            border_color=COLORS["border"],
        )

    def _on_thumbnail_click(self) -> None:
        """サムネイルエリアがクリックされたときの処理"""
        if self.current_state == self.STATE_FILE_SELECTED:
            self._select_input()

    def _select_input(self) -> None:
        """入力ファイルを選択する"""
        # 処理中は無視
        if self.current_state == self.STATE_PROCESSING:
            return

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
            show_toast = self.file_selected
            self._set_input_file(path, show_toast=show_toast)

    def _set_input_file(self, path: str, show_toast: bool = False) -> None:
        """入力ファイルを設定する"""
        if not path:
            return

        if not is_supported_video(path):
            self._show_error_dialog(
                "サポートされていない形式です", f"対応形式: {', '.join(SUPPORTED_INPUT_EXTENSIONS)}"
            )
            return

        self.input_path = path
        self.file_selected = True
        filename = Path(path).name

        # 動画情報を取得
        try:
            info = get_video_info(path)
            self.video_duration = info.duration
            self.video_frame_count = info.frame_count
            duration_text = f"{format_time(info.duration)}の動画"
        except Exception:
            duration_text = ""

        # サムネイルを抽出
        self.thumbnail_image = self._extract_thumbnail(path)
        if self.thumbnail_image:
            self.thumbnail_label.configure(image=self.thumbnail_image)

        # ラベルを更新
        self.filename_label.configure(text=filename)
        self.video_info_label.configure(text=duration_text)

        # 状態を更新
        self.current_state = self.STATE_FILE_SELECTED
        self._update_ui_state()

        # トースト表示
        if show_toast:
            Toast(self.root, "📁 動画を変更しました")

    def _on_main_button_click(self) -> None:
        """メインボタンがクリックされたときの処理"""
        # 処理中は無視
        if self.current_state == self.STATE_PROCESSING:
            return
        if self.current_state == self.STATE_FILE_SELECTED:
            self._start_processing()
        elif self.current_state == self.STATE_COMPLETE:
            self._save_output_file()

    def _on_cancel_click(self) -> None:
        """キャンセルボタンがクリックされたときの処理"""
        # 処理中のみ有効
        if self.current_state != self.STATE_PROCESSING:
            return
        self._show_cancel_confirm_dialog()

    def _on_retry(self) -> None:
        """やり直しリンクがクリックされたときの処理"""
        # 完了状態のみ有効
        if self.current_state != self.STATE_COMPLETE:
            return
        self.current_state = self.STATE_FILE_SELECTED
        self._update_ui_state()

    def _on_process_another(self) -> None:
        """別の動画を処理リンクがクリックされたときの処理"""
        # 完了状態のみ有効
        if self.current_state != self.STATE_COMPLETE:
            return
        self.input_path = ""
        self.file_selected = False
        self.thumbnail_image = None
        self.processed_thumbnail_image = None
        self.current_state = self.STATE_INITIAL
        self._update_ui_state()

    def _start_processing(self) -> None:
        """処理を開始する"""
        if self.is_processing:
            return

        self.is_processing = True
        self.current_state = self.STATE_PROCESSING
        self._update_ui_state()

        # 円形プログレスをリセット
        self.circular_progress.reset()

        # 一時出力先を設定（ProRes 4444形式で出力）
        self.temp_output_path = tempfile.mktemp(suffix=".mov")

        # 動画情報を取得して最適パラメータを計算
        video_info = get_video_info(self.input_path)
        self.output_params = calculate_optimal_params(
            width=video_info.width,
            height=video_info.height,
            fps=video_info.fps,
            duration_sec=video_info.duration,
        )

        # 別スレッドで処理
        thread = threading.Thread(target=self._process_video)
        thread.daemon = True
        thread.start()

    def _process_video(self) -> None:
        """動画を処理する（別スレッドで実行）"""
        try:
            # モデルをロード（初回のみ）
            if self.model is None:
                self._update_progress_text("モデルを読み込み中...")
                self.model = RVMModel()
                try:
                    self.model.load()
                except FileNotFoundError:
                    self._update_progress_text("モデルをダウンロード中...")
                    download_model()
                    self.model.load()

                self.processor = VideoProcessor(self.model)

            # 処理を実行（出力パラメータを渡す）
            self.processor.process(
                input_path=self.input_path,
                output_path=self.temp_output_path,
                output_params=self.output_params,
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
        self.root.after(0, lambda: self.circular_progress.set(progress, current, total))

    def _update_progress_text(self, text: str) -> None:
        """進捗テキストを更新する（現在は未使用）"""
        # CircularProgressにはframe_label属性がないため、このメソッドは使用しない
        # 将来的にはCircularProgressにテキスト更新メソッドを追加する
        pass

    def _on_complete(self) -> None:
        """処理完了時の処理"""

        def complete():
            self.is_processing = False

            # 処理済みサムネイルを取得（市松模様背景）
            self.processed_thumbnail_image = self._extract_processed_thumbnail(
                self.temp_output_path
            )
            if self.processed_thumbnail_image:
                self.thumbnail_label.configure(image=self.processed_thumbnail_image)

            self.current_state = self.STATE_COMPLETE
            self._update_ui_state()

        self.root.after(0, complete)

    def _on_cancelled(self) -> None:
        """キャンセル時の処理"""

        def handle_cancelled():
            self.is_processing = False

            # 一時ファイルを削除
            if self.temp_output_path and Path(self.temp_output_path).exists():
                with contextlib.suppress(Exception):
                    os.remove(self.temp_output_path)

            self.current_state = self.STATE_FILE_SELECTED
            self._update_ui_state()

        self.root.after(0, handle_cancelled)

    def _on_error(self, error_message: str) -> None:
        """エラー発生時の処理"""

        def handle_error():
            self.is_processing = False
            self.current_state = self.STATE_FILE_SELECTED
            self._update_ui_state()
            self._show_error_dialog("エラーが発生しました", error_message)

        self.root.after(0, handle_error)

    def _save_output_file(self) -> None:
        """出力ファイルを保存する"""
        input_name = Path(self.input_path).stem
        default_name = f"{input_name}_nobg.mov"

        save_path = ctk.filedialog.asksaveasfilename(
            title="保存先を選択",
            defaultextension=".mov",
            initialfile=default_name,
            filetypes=[("MOV (ProRes 4444透過)", "*.mov")],
        )

        if save_path:
            try:
                import shutil

                # 一時ファイルを保存先にコピー
                shutil.copy2(self.temp_output_path, save_path)
                self.output_path = save_path

                # 一時ファイルを削除
                if Path(self.temp_output_path).exists():
                    os.remove(self.temp_output_path)

                # 保存完了ダイアログを表示
                self._show_save_complete_dialog(save_path)

            except Exception as e:
                self._show_error_dialog("ファイルの保存に失敗しました", str(e))

    def _show_save_complete_dialog(self, save_path: str) -> None:
        """保存完了ダイアログを表示"""
        # ファイルサイズを取得
        size_mb = os.path.getsize(save_path) / (1024 * 1024)

        # 調整情報を構築
        adjustment_info = ""
        if self.output_params and self.output_params.is_adjusted:
            adjustments = []
            if self.output_params.resolution_adjusted:
                adjustments.append(
                    f"解像度: {self.output_params.original_width}x{self.output_params.original_height} "
                    f"→ {self.output_params.width}x{self.output_params.height}"
                )
            if self.output_params.fps_adjusted:
                adjustments.append(
                    f"フレームレート: {self.output_params.original_fps:.0f}fps "
                    f"→ {self.output_params.fps:.0f}fps"
                )
            if adjustments:
                adjustment_info = "\n\n" + "\n".join(adjustments)

        # ダイアログの高さを調整
        dialog_height = 240 if not adjustment_info else 300

        dialog = CustomDialog(
            self.root,
            title="保存完了",
            icon="✅",
            message="保存しました",
            sub_message=(
                f"保存先: {save_path}\n\nファイルサイズ: {size_mb:.1f} MB{adjustment_info}"
            ),
            height=dialog_height,
        )
        dialog.add_button("閉じる", dialog.destroy, primary=True)

        # 3秒後に自動で閉じる
        def auto_close():
            with contextlib.suppress(Exception):
                dialog.destroy()

        self.root.after(TIMING_MS["auto_close_dialog"], auto_close)

    # =========================================================================
    # ダイアログ
    # =========================================================================
    def _show_gpu_warning(self) -> None:
        """GPU警告ダイアログを表示"""
        dialog = CustomDialog(
            self.root,
            title="警告",
            icon="⚠️",
            message="GPUが検出されませんでした",
            sub_message="処理は可能ですが、非常に時間がかかります（数時間〜）",
            height=240,
        )
        dialog.add_button("了解", dialog.destroy, primary=True)

    def _show_error_dialog(self, title: str, message: str) -> None:
        """エラーダイアログを表示"""
        dialog = CustomDialog(
            self.root,
            title="エラー",
            icon="❌",
            message=title,
            sub_message=message,
        )
        dialog.add_button("閉じる", dialog.destroy, primary=True)

    def _show_cancel_confirm_dialog(self) -> None:
        """キャンセル確認ダイアログを表示（処理を一時停止）"""
        # 処理を一時停止
        if self.processor:
            self.processor.pause()

        dialog = CustomDialog(
            self.root,
            title="確認",
            icon="⚠️",
            message="処理をキャンセルしますか？",
            sub_message="進行中の処理は破棄されます",
        )

        def on_continue():
            dialog.destroy()
            # 処理を再開
            if self.processor:
                self.processor.resume()

        def on_cancel():
            dialog.destroy()
            if self.processor:
                self.processor.cancel()

        dialog.add_button("続ける", on_continue, primary=True)
        dialog.add_button("キャンセル", on_cancel, danger=True)


# =============================================================================
# メイン
# =============================================================================
def main():
    """アプリケーションのエントリーポイント"""
    # 多重起動チェック
    lock = SingleInstanceLock()
    if not lock.acquire():
        _bring_existing_window_to_front()
        sys.exit(0)

    # 終了時にロックを解放
    atexit.register(lock.release)

    # シグナルハンドラを設定（Ctrl+Cなどで終了時もロック解放）
    def signal_handler(signum, frame):
        lock.release()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if DRAG_AND_DROP_AVAILABLE:
        root = TkinterDnD.Tk()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")
    else:
        root = ctk.CTk()

    BackgroundRemoverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
