"""日志查看弹窗 —— 提供"查看报错日志"和"查看运行日志"两个入口"""

from __future__ import annotations

import tkinter as tk
import os
from datetime import datetime
import customtkinter as ctk
from ui.styles import FONT_MONO
from utils import center_window
from ui.logger import get_log_dir


class LogViewer:
    """日志查看器。"""

    @staticmethod
    def _build_window(parent: ctk.CTk, title: str, content: str) -> None:
        win = ctk.CTkToplevel(parent)
        win.title(title)
        win.geometry("800x500")
        center_window(win, 800, 500)
        win.transient(parent)
        win.after(100, win.lift)

        text = ctk.CTkTextbox(
            win, font=FONT_MONO, wrap="word",
            corner_radius=8, border_width=1,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        text.insert("1.0", content)
        text.configure(state="disabled")

    @staticmethod
    def show_error(parent: ctk.CTk) -> None:
        """查看报错日志 —— 读取 logs/error.log。"""
        log_dir = get_log_dir()
        err_path = os.path.join(log_dir, "error.log")
        if os.path.exists(err_path):
            try:
                with open(err_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                content = f"读取报错日志失败: {e}"
            title = "报错日志 — error.log"
        else:
            content = "暂无报错日志。"
            title = "报错日志"
        LogViewer._build_window(parent, title, content)

    @staticmethod
    def show_run(parent: ctk.CTk) -> None:
        """查看运行日志 —— 读取当日 logs/run_YYYYMMDD.log。"""
        log_dir = get_log_dir()
        today = datetime.now().strftime("%Y%m%d")
        run_path = os.path.join(log_dir, f"run_{today}.log")
        if os.path.exists(run_path):
            try:
                with open(run_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                content = f"读取运行日志失败: {e}"
            title = f"运行日志 — run_{today}.log"
        else:
            content = "暂无运行日志。"
            title = "运行日志"
        LogViewer._build_window(parent, title, content)
