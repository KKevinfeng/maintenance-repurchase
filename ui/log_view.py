"""日志查看弹窗"""

from __future__ import annotations

import tkinter as tk
import os
import customtkinter as ctk
from ui.logger import get_log_path
from ui.styles import FONT_MONO
from utils import center_window


class LogViewer:
    """日志查看器 —— 在新窗口中显示 error.log 的内容。"""

    @staticmethod
    def show(parent: ctk.CTk) -> None:
        log_path = get_log_path()

        win = ctk.CTkToplevel(parent)
        win.title("运行日志")
        win.geometry("800x500")
        center_window(win, 800, 500)
        win.transient(parent)
        win.after(100, win.lift)

        text = ctk.CTkTextbox(
            win, font=FONT_MONO, wrap="word",
            corner_radius=8, border_width=1,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = "暂无日志记录。"

        text.insert("1.0", content)
        text.configure(state="disabled")
