"""查看重点客户弹窗 —— 支持清空、逐行删除、数据刷新"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from ui.styles import FONT_MAIN, FONT_TITLE
from utils import center_window


class StarredView:
    """重点客户弹窗 —— 从缓存展示标星客户表，支持删除与清空。"""

    ACTION_COL = "操作"

    def __init__(self, parent: ctk.CTk, cache, on_changed=None):
        self.cache = cache
        self.on_changed = on_changed
        self._dirty = False  # 是否做过了删除/清空操作
        self._build(parent)
        self._refresh_table()

    # ── 构建弹窗 ────────────────────────────────────────────

    def _build(self, parent):
        win = ctk.CTkToplevel(parent)
        win.title("重点客户")
        win.geometry("600x480")
        win.minsize(420, 300)
        center_window(win, 600, 480)
        win.grab_set()
        win.after(10, win.focus_force)
        self.win = win

        # 标题栏
        title_bar = ctk.CTkFrame(win, fg_color="transparent")
        title_bar.pack(fill=tk.X, padx=12, pady=(12, 4))

        ctk.CTkLabel(
            title_bar, text="重点客户", font=FONT_TITLE,
            text_color="#1F6AA5",
        ).pack(side=tk.LEFT)

        self.count_label = ctk.CTkLabel(
            title_bar, text="", font=FONT_MAIN, text_color="#888888",
        )
        self.count_label.pack(side=tk.RIGHT, padx=(0, 8))

        self.clear_btn = ctk.CTkButton(
            title_bar, text="清空全部", command=self._on_clear_all,
            font=FONT_MAIN, width=90, height=28,
            fg_color="#D9534F", text_color="#FFFFFF",
            hover_color="#C9302C", corner_radius=6,
        )
        self.clear_btn.pack(side=tk.RIGHT, padx=(0, 8))

    # 绑定关闭事件，关闭时通知主窗口
        win.protocol("WM_DELETE_WINDOW", self._on_close)

        # 表格
        tree_frame = ctk.CTkFrame(win, fg_color="transparent")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))

        self.columns = ["序号", "最终客户名称", self.ACTION_COL]
        tree = ttk.Treeview(tree_frame, columns=self.columns, show="headings", height=18)
        tree.tag_configure("odd", background="#F4F4F5")
        tree.tag_configure("even", background="#FCFCFC")

        tree.heading("序号", text="序号", anchor="center")
        tree.column("序号", anchor="center", width=60, minwidth=60)
        tree.heading("最终客户名称", text="最终客户名称", anchor="center")
        tree.column("最终客户名称", anchor="center", width=330, minwidth=180)
        tree.heading(self.ACTION_COL, text="操作", anchor="center")
        tree.column(self.ACTION_COL, anchor="center", width=80, minwidth=80)

        # 绑定点击删除
        tree.bind("<ButtonRelease-1>", self._on_cell_click)

        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar_y.set)

        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = tree

    # ── 数据刷新 ────────────────────────────────────────────

    def _refresh_table(self):
        """重新从缓存读取并刷新整个表格。"""
        df = self.cache.get_dataframe()
        tree = self.tree
        tree.delete(*tree.get_children())

        count = len(df)
        self.count_label.configure(text=f"共 {count} 个客户")
        # 没有数据时隐藏清空按钮
        if count == 0:
            self.clear_btn.configure(state="disabled")
        else:
            self.clear_btn.configure(state="normal")

        for idx, (_, row) in enumerate(df.iterrows(), 1):
            tag = "odd" if idx % 2 == 1 else "even"
            tree.insert(
                "",
                tk.END,
                values=[row["序号"], row["最终客户名称"], "删除"],
                tags=(tag,),
            )

    # ── 窗口关闭 ────────────────────────────────────────────

    def _on_close(self):
        """关闭窗口时通知主窗口刷新，所有操作批量生效一次。"""
        self.win.grab_release()
        self.win.destroy()
        if self._dirty and self.on_changed:
            self.on_changed()

    # ── 点击处理 ────────────────────────────────────────────

    def _on_cell_click(self, event) -> None:
        """点击"操作"列触发删除。"""
        col_id = self.tree.identify_column(event.x)
        # 操作列是第 3 列（序号=#1，名称=#2，操作=#3）
        if col_id != "#3":
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = self.tree.item(item, "values")
        if not values or len(values) < 2:
            return
        name = str(values[1]).strip()
        if not name:
            return

        confirmed = messagebox.askyesno(
            "确认删除",
            f"确定要删除重点客户「{name}」吗？\n\n此操作不可撤销。",
            parent=self.win,
        )
        if confirmed:
            self.cache.remove(name)
            self._dirty = True
            self._refresh_table()

    def _on_clear_all(self) -> None:
        """清空全部重点客户（二次确认）。"""
        df = self.cache.get_dataframe()
        count = len(df)
        if count == 0:
            return

        confirmed = messagebox.askyesno(
            "确认清空",
            f"确定要清空全部 {count} 个重点客户吗？\n\n此操作不可撤销。",
            parent=self.win,
        )
        if confirmed:
            self.cache.clear_all()
            self._dirty = True
            self._refresh_table()

    # ── 入口 ─────────────────────────────────────────────────

    @classmethod
    def show(cls, parent: ctk.CTk, cache, on_changed=None) -> None:
        """打开弹窗展示缓存中的重点客户列表。"""
        cls(parent, cache, on_changed=on_changed)
