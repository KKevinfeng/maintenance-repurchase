"""列筛选弹窗 —— 点击列头下拉按钮后弹出，多选框勾选进行筛选"""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from ui.styles import FONT_MAIN, FONT_SMALL
from utils import center_window


class ColumnFilterPopup:
    """可复用的列值多选筛选弹窗。"""

    def __init__(self, parent, col_name: str, all_values: list[str],
                 selected: set[str], on_apply):
        self.col_name = col_name
        self.on_apply = on_apply
        self.selected = set(selected) if selected else set(all_values)
        self.all_values = all_values
        self.cb_vars: dict[str, tk.BooleanVar] = {}

        self._build(parent)

    # ── 构建弹窗 ────────────────────────────────────────────

    def _build(self, parent):
        win = ctk.CTkToplevel(parent)
        win.title(f"筛选 - {self.col_name}")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.grab_set()
        self.win = win

        # 计算窗口高度（确保顶部按钮区、列表、底部确定按钮都完整显示）
        item_count = len(self.all_values)
        visible = min(item_count, 12)  # 最多展示 12 行
        list_h = max(visible * 30 + 8, 80)
        pad = 16
        top_bar_h = 26 + pad + 4       # 全选/取消全选按钮行 + 上下 padding
        bottom_btn_h = 30 + pad        # 确定按钮 + 上下 padding
        win_h = list_h + top_bar_h + bottom_btn_h + 24  # 额外留白给滚动条/边框
        win_h = max(win_h, 280)        # 最小高度，防止按钮被截掉

        # 按钮区
        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=pad, pady=(pad, 4))

        ctk.CTkButton(
            btn_frame, text="全选", font=FONT_SMALL, width=60, height=26,
            corner_radius=4, fg_color="#E0E0E0", text_color="#333333",
            hover_color="#C8C8C8", command=self._select_all,
        ).pack(side=tk.LEFT, padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="取消全选", font=FONT_SMALL, width=80, height=26,
            corner_radius=4, fg_color="#E0E0E0", text_color="#333333",
            hover_color="#C8C8C8", command=self._select_none,
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(
            btn_frame, text=f"共 {item_count} 项",
            font=FONT_SMALL, text_color="#888888",
        ).pack(side=tk.RIGHT, padx=(0, 4))

        # 确定按钮（先 pack 在底部，确保不被滚动区域挤出）
        ctk.CTkButton(
            win, text="确定", font=FONT_MAIN, height=30,
            corner_radius=6, command=self._apply,
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=pad, pady=(0, pad))

        # 可滚动的复选框列表（填充剩余空间）
        list_frame = ctk.CTkScrollableFrame(
            win, height=list_h, fg_color="transparent",
        )
        list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=pad, pady=(0, 8))

        for val in self.all_values:
            display_text = str(val) if val else "（空）"
            var = tk.BooleanVar(value=(val in self.selected))
            self.cb_vars[val] = var
            cb = ctk.CTkCheckBox(
                list_frame, text=display_text, variable=var,
                font=FONT_MAIN, checkbox_width=18, checkbox_height=18,
                border_width=2, corner_radius=3,
            )
            cb.pack(anchor=tk.W, pady=1)

        # 点击 X 关闭时也应用筛选
        win.protocol("WM_DELETE_WINDOW", self._apply)

        # 计算宽度
        max_len = max((len(str(v)) for v in self.all_values), default=8)
        win_w = max(min(int(max_len * 10) + 60, 500), 240)
        win.geometry(f"{win_w}x{win_h}")
        center_window(win, win_w, win_h)

        # 定位到父窗口按钮附近
        win.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            win.geometry(f"{win_w}x{win_h}+{px}+{py + 40}")
        except Exception:
            pass

    def _select_all(self):
        self.selected = set(self.all_values)
        for v in self.cb_vars:
            self.cb_vars[v].set(True)

    def _select_none(self):
        self.selected = set()
        for v in self.cb_vars:
            self.cb_vars[v].set(False)

    def _apply(self):
        """收集勾选值，关闭弹窗并回调。"""
        self.selected = {v for v, var in self.cb_vars.items() if var.get()}
        self.win.grab_release()
        self.win.destroy()
        if self.on_apply:
            self.on_apply(self.col_name, self.selected)
