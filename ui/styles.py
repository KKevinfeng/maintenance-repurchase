"""CustomTkinter 主题 & ttk Treeview 样式配置"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

# ── 字体 ──
FONT_MAIN  = ("Microsoft YaHei UI", 13)
FONT_SMALL = ("Microsoft YaHei UI", 12)
FONT_BOLD  = ("Microsoft YaHei UI", 13, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 16, "bold")
FONT_MONO  = ("Consolas", 11)

# ── CTk 全局主题 ──
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def setup_treeview_style(master: tk.Misc) -> None:
    """配置 ttk.Treeview 样式以匹配 CustomTkinter 蓝色主题。"""
    style = ttk.Style(master)
    style.theme_use("clam")

    HEADER_BG = "#E8F0F8"
    HEADER_FG = "#1F6AA5"
    CARD      = "#FCFCFC"
    TEXT      = "#1A1A1A"
    SELECT_BG = "#1F6AA5"
    SELECT_FG = "#FFFFFF"

    style.configure("Treeview",
                    background=CARD,
                    foreground=TEXT,
                    fieldbackground=CARD,
                    font=("Microsoft YaHei UI", 12),
                    rowheight=34,
                    borderwidth=1,
                    relief="flat")
    style.configure("Treeview.Heading",
                    background=HEADER_BG,
                    foreground=HEADER_FG,
                    font=("Microsoft YaHei UI", 12, "bold"),
                    padding=(10, 6),
                    relief="flat")
    style.map("Treeview.Heading",
              background=[("active", "#D0E4F0")],
              foreground=[("active", "#1F6AA5")])
    style.map("Treeview",
              background=[("selected", SELECT_BG)],
              foreground=[("selected", SELECT_FG)])
    style.configure("Vertical.TScrollbar",
                    background="#D0D0D0",
                    arrowcolor="#888888")
    style.configure("Horizontal.TScrollbar",
                    background="#D0D0D0",
                    arrowcolor="#888888")
