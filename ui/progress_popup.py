"""进度弹窗 —— 带百分比显示的模态进度窗口，用于导入时展示。"""

from __future__ import annotations

import customtkinter as ctk
from utils import center_window


class ProgressPopup:
    """模态进度弹窗，显示状态文字、百分比和进度条。"""

    def __init__(self, parent, title: str = "正在导入..."):
        self.win = ctk.CTkToplevel(parent)
        self.win.title(title)
        self.win.geometry("420x160")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)

        center_window(self.win, 420, 160)

        self.win.protocol("WM_DELETE_WINDOW", lambda: None)  # 禁止关闭

        # 状态文字
        self.status_label = ctk.CTkLabel(
            self.win, text="正在读取文件...",
            font=ctk.CTkFont(size=13), text_color="#555555",
        )
        self.status_label.pack(anchor="w", padx=28, pady=(16, 2))

        # 百分比
        self.pct_label = ctk.CTkLabel(
            self.win, text="0%",
            font=ctk.CTkFont(size=28, weight="bold"), text_color="#1F6AA5",
        )
        self.pct_label.pack(anchor="w", padx=28, pady=(0, 4))

        # 进度条
        self.bar = ctk.CTkProgressBar(
            self.win, mode="determinate", height=12,
            fg_color="#E8F0FE", progress_color="#1F6AA5",
            corner_radius=6,
        )
        self.bar.set(0)
        self.bar.pack(fill="x", padx=28, pady=(0, 16))
        self.win.grab_set()

    def set_progress(self, value: float, status: str = ""):
        """设置进度 0.0 ~ 1.0，可附带状态文字。"""
        self.bar.set(value)
        self.pct_label.configure(text=f"{int(value * 100)}%")
        if status:
            self.status_label.configure(text=status)
        self.win.update_idletasks()

    def close(self):
        """快速跳到 100% 然后立即关闭，释放模态抓取。"""
        self.bar.set(1.0)
        self.pct_label.configure(text="100%")
        self.status_label.configure(text="加载完成")
        self.win.update_idletasks()
        self.win.grab_release()
        self.win.destroy()
