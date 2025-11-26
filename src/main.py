# -*- coding: utf-8 -*-
"""動画背景除去ツール - GUI"""

import sys
import threading
from pathlib import Path
from tkinter import Tk, Label, Button, Frame, StringVar, filedialog, messagebox
from tkinter.ttk import Progressbar, Style

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


class BackgroundRemoverApp:
    """動画背景除去アプリケーションのメインクラス"""

    def __init__(self, root: Tk):
        """アプリケーションを初期化する

        Args:
            root: Tkinterのルートウィンドウ
        """
        self.root = root
        self.root.title("動画背景除去ツール")
        self.root.geometry("500x400")
        self.root.minsize(400, 350)  # 最小サイズを設定
        self.root.resizable(True, True)  # リサイズ可能

        # 状態変数
        self.input_path: str = ""
        self.output_path: str = ""
        self.is_processing: bool = False

        # デバイス情報を取得
        self.device_info: DeviceInfo = get_device_info()

        # モデル（遅延ロード）
        self.model: RVMModel | None = None
        self.processor: VideoProcessor | None = None

        # UIを構築
        self._setup_ui()

        # GPUなしの場合は警告を表示
        if self.device_info.warning:
            self.root.after(100, self._show_gpu_warning)

    def _setup_ui(self) -> None:
        """UIを構築する"""
        # スタイル設定
        style = Style()
        style.configure("TProgressbar", thickness=20)

        # メインフレーム（リサイズに追従）
        main_frame = Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        # タイトル
        title_label = Label(
            main_frame,
            text="動画背景除去ツール",
            font=("Helvetica", 16, "bold"),
        )
        title_label.pack(pady=(0, 10))

        # デバイス情報
        device_text = f"使用デバイス: {self.device_info.name}"
        device_color = "green" if self.device_info.is_gpu else "orange"
        device_label = Label(main_frame, text=device_text, fg=device_color)
        device_label.pack(pady=(0, 15))

        # ドロップゾーン（ファイルをドラッグ＆ドロップできるエリア）
        self.drop_frame = Frame(
            main_frame,
            relief="groove",
            borderwidth=2,
            bg="#f0f0f0",
        )
        self.drop_frame.pack(fill="x", pady=10, ipady=20)

        self.drop_label = Label(
            self.drop_frame,
            text="ここに動画ファイルをドラッグ＆ドロップ\n(.mp4, .mov, .m4v)",
            bg="#f0f0f0",
            fg="#666666",
            font=("Helvetica", 10),
        )
        self.drop_label.pack(expand=True)

        # ドラッグ＆ドロップが利用可能な場合は有効化
        if HAS_DND:
            self._setup_drag_and_drop()

        # 入力ファイル選択（リサイズに追従）
        input_frame = Frame(main_frame)
        input_frame.pack(fill="x", pady=5)

        Label(input_frame, text="入力ファイル:", anchor="w").pack(side="left")
        self.input_var = StringVar(value="選択されていません")
        self.input_label = Label(input_frame, textvariable=self.input_var, anchor="w")
        self.input_label.pack(side="left", fill="x", expand=True, padx=5)
        Button(input_frame, text="選択", command=self._select_input).pack(side="right")

        # 出力先選択（リサイズに追従）
        output_frame = Frame(main_frame)
        output_frame.pack(fill="x", pady=5)

        Label(output_frame, text="出力先:", anchor="w").pack(side="left")
        self.output_var = StringVar(value="自動生成")
        self.output_label = Label(output_frame, textvariable=self.output_var, anchor="w")
        self.output_label.pack(side="left", fill="x", expand=True, padx=5)
        Button(output_frame, text="変更", command=self._select_output).pack(side="right")

        # 動画情報
        info_frame = Frame(main_frame)
        info_frame.pack(fill="x", pady=15)
        self.info_var = StringVar(value="")
        Label(info_frame, textvariable=self.info_var, fg="blue").pack(fill="x")

        # 進捗バー（リサイズに追従）
        progress_frame = Frame(main_frame)
        progress_frame.pack(fill="x", expand=True, pady=10)

        self.progress_var = StringVar(value="")
        Label(progress_frame, textvariable=self.progress_var).pack(fill="x")

        self.progressbar = Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
        )
        self.progressbar.pack(fill="x", pady=5)

        # 処理ボタン（中央揃え）
        button_frame = Frame(main_frame)
        button_frame.pack(fill="x", pady=20)

        # ボタンを中央に配置するための内部フレーム
        button_inner_frame = Frame(button_frame)
        button_inner_frame.pack(anchor="center")

        self.process_button = Button(
            button_inner_frame,
            text="背景を除去",
            command=self._start_processing,
            width=15,
            height=2,
            state="disabled",
        )
        self.process_button.pack(side="left", padx=10)

        # キャンセルボタン
        self.cancel_button = Button(
            button_inner_frame,
            text="キャンセル",
            command=self._cancel_processing,
            width=15,
            height=2,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=10)

    def _setup_drag_and_drop(self) -> None:
        """ドラッグ＆ドロップを設定する"""
        # ドロップゾーンにドラッグ＆ドロップを設定
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)
        self.drop_frame.dnd_bind("<<DragEnter>>", self._on_drag_enter)
        self.drop_frame.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        # ラベルにもドラッグ＆ドロップを設定（ラベル上でもドロップできるように）
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
        self.drop_label.dnd_bind("<<DragEnter>>", self._on_drag_enter)
        self.drop_label.dnd_bind("<<DragLeave>>", self._on_drag_leave)

    def _on_drop(self, event) -> None:
        """ファイルがドロップされたときの処理

        Args:
            event: ドロップイベント
        """
        # ドロップされたファイルパスを取得
        # 複数ファイルの場合はスペース区切り、パスにスペースが含まれる場合は{}で囲まれる
        data = event.data

        # パスの解析
        if data.startswith("{"):
            # {path}形式（スペースを含むパス）
            path = data.strip("{}")
        else:
            # 複数ファイルの場合は最初のファイルのみ使用
            path = data.split()[0] if " " in data else data

        # ドロップゾーンの色を元に戻す
        self._reset_drop_zone()

        # ファイルを設定
        self._set_input_file(path)

    def _on_drag_enter(self, event) -> None:
        """ドラッグがドロップゾーンに入ったときの処理"""
        self.drop_frame.config(bg="#d0e8ff")
        self.drop_label.config(bg="#d0e8ff", fg="#0066cc")

    def _on_drag_leave(self, event) -> None:
        """ドラッグがドロップゾーンから出たときの処理"""
        self._reset_drop_zone()

    def _reset_drop_zone(self) -> None:
        """ドロップゾーンを初期状態に戻す"""
        self.drop_frame.config(bg="#f0f0f0")
        self.drop_label.config(bg="#f0f0f0", fg="#666666")

    def _set_input_file(self, path: str) -> None:
        """入力ファイルを設定する

        Args:
            path: ファイルパス
        """
        if not path:
            return

        if not is_supported_video(path):
            messagebox.showerror(
                "エラー",
                f"サポートされていない形式です。\n"
                f"対応形式: {', '.join(SUPPORTED_INPUT_EXTENSIONS)}",
            )
            return

        self.input_path = path
        self.input_var.set(Path(path).name)

        # 出力パスを自動設定
        self.output_path = get_output_path(path)
        self.output_var.set(Path(self.output_path).name)

        # 動画情報を表示
        try:
            info = get_video_info(path)
            self.info_var.set(
                f"{info.width}x{info.height} | {info.fps:.1f}fps | "
                f"{format_time(info.duration)} ({info.frame_count}フレーム)"
            )
        except ValueError as e:
            self.info_var.set(str(e))

        # ドロップゾーンの表示を更新
        self.drop_label.config(
            text=f"選択済み: {Path(path).name}\n別のファイルをドロップして変更",
            fg="#008800",
        )

        # 処理ボタンを有効化
        self.process_button.config(state="normal")

    def _select_input(self) -> None:
        """入力ファイルを選択する"""
        filetypes = [
            ("動画ファイル", "*.mp4 *.mov *.m4v"),
            ("MP4", "*.mp4"),
            ("MOV", "*.mov"),
            ("すべてのファイル", "*.*"),
        ]

        path = filedialog.askopenfilename(
            title="入力動画を選択",
            filetypes=filetypes,
        )

        if path:
            self._set_input_file(path)

    def _select_output(self) -> None:
        """出力先を選択する"""
        if not self.input_path:
            messagebox.showwarning("警告", "先に入力ファイルを選択してください。")
            return

        default_name = Path(self.output_path).name if self.output_path else "output.mov"

        path = filedialog.asksaveasfilename(
            title="出力先を選択",
            defaultextension=".mov",
            initialfile=default_name,
            filetypes=[("MOV (ProRes 4444)", "*.mov")],
        )

        if path:
            self.output_path = path
            self.output_var.set(Path(path).name)

    def _start_processing(self) -> None:
        """処理を開始する"""
        if self.is_processing:
            return

        if not self.input_path:
            messagebox.showwarning("警告", "入力ファイルを選択してください。")
            return

        self.is_processing = True
        self.process_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.progressbar["value"] = 0
        self.progress_var.set("モデルを読み込み中...")

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
            self.progress_var.set("キャンセル中...")
            self.cancel_button.config(state="disabled")

    def _process_video(self) -> None:
        """動画を処理する（別スレッドで実行）"""
        try:
            # モデルをロード（初回のみ）
            if self.model is None:
                self.model = RVMModel()
                try:
                    self.model.load()
                except FileNotFoundError:
                    # モデルをダウンロード
                    self._update_progress_text("モデルをダウンロード中...")
                    download_model()
                    self.model.load()

                self.processor = VideoProcessor(self.model)

            # 処理を実行
            self._update_progress_text("処理中...")
            self.processor.process(
                input_path=self.input_path,
                output_path=self.output_path,
                progress_callback=self._on_progress,
            )

            # 完了
            self._on_complete()

        except ProcessingCancelled:
            self._on_cancelled()

        except Exception as e:
            self._on_error(str(e))

    def _on_progress(self, current: int, total: int) -> None:
        """進捗を更新する

        Args:
            current: 現在のフレーム番号
            total: 総フレーム数
        """
        progress = (current / total) * 100
        self.root.after(0, lambda: self._update_progress(progress, current, total))

    def _update_progress(self, progress: float, current: int, total: int) -> None:
        """進捗UIを更新する"""
        self.progressbar["value"] = progress
        self.progress_var.set(f"処理中: {current}/{total} フレーム ({progress:.1f}%)")

    def _update_progress_text(self, text: str) -> None:
        """進捗テキストを更新する"""
        self.root.after(0, lambda: self.progress_var.set(text))

    def _on_complete(self) -> None:
        """処理完了時の処理"""
        def complete():
            self.is_processing = False
            self.process_button.config(state="normal")
            self.cancel_button.config(state="disabled")
            self.progressbar["value"] = 100
            self.progress_var.set("完了!")
            messagebox.showinfo(
                "完了",
                f"背景除去が完了しました。\n\n出力: {self.output_path}",
            )

        self.root.after(0, complete)

    def _on_error(self, error_message: str) -> None:
        """エラー発生時の処理"""
        def handle_error():
            self.is_processing = False
            self.process_button.config(state="normal")
            self.cancel_button.config(state="disabled")
            self.progressbar["value"] = 0
            self.progress_var.set("エラーが発生しました")
            messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n\n{error_message}")

        self.root.after(0, handle_error)

    def _on_cancelled(self) -> None:
        """キャンセル時の処理"""
        def handle_cancelled():
            self.is_processing = False
            self.process_button.config(state="normal")
            self.cancel_button.config(state="disabled")
            self.progressbar["value"] = 0
            self.progress_var.set("キャンセルされました")
            messagebox.showinfo("キャンセル", "処理がキャンセルされました。")

        self.root.after(0, handle_cancelled)

    def _show_gpu_warning(self) -> None:
        """GPU未検出の警告を表示する"""
        messagebox.showwarning(
            "警告",
            f"{self.device_info.warning}\n\n"
            "処理を続行できますが、7分の動画の場合、数時間かかる可能性があります。"
        )


def main():
    """アプリケーションのエントリーポイント"""
    # tkinterdnd2が利用可能な場合はTkinterDnDを使用
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = Tk()
    app = BackgroundRemoverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
