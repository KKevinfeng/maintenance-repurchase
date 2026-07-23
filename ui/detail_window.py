"""客户合同详情弹窗"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import pandas as pd
import customtkinter as ctk
from ui.logger import log_info
from ui.styles import FONT_TITLE, FONT_BOLD
from utils import center_window, export_to_csv


class CustomerDetailWindow:
    """弹出窗口：展示某客户在原始数据中的合同记录。"""

    def __init__(
        self,
        parent,
        df: pd.DataFrame,
        title_text: str,
        customer_name: str,
    ):
        self._show(parent, df, title_text, customer_name)

    # ── 窗口构建 ─────────────────────────────────────────────

    def _show(self, parent, df, title_text, customer_name):
        self._export_df = df
        self._export_name = customer_name

        win = ctk.CTkToplevel(parent)
        win.title(f"客户合同详情 — {customer_name}")
        win.geometry("1200x680")
        win.minsize(800, 450)
        center_window(win, 1200, 680)
        win.after(100, win.lift)
        self._win = win

        # 标题
        ctk.CTkLabel(
            win, text=title_text, font=FONT_TITLE,
            text_color="#1F6AA5", anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(12, 4))

        # 表格容器
        table_frame = ctk.CTkFrame(win, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 4))

        columns = list(df.columns)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)

        for col in columns:
            tree.heading(col, text=col, anchor="center")
            tree.column(col, anchor="center", width=140, minwidth=100)

        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        tree.tag_configure("center", anchor="center")
        tree.tag_configure("odd", background="#F4F4F5")
        tree.tag_configure("even", background="#FCFCFC")

        # 存原始数据用于 tooltip
        row_data_map: dict[str, dict] = {}

        for idx, (_, row) in enumerate(df.iterrows(), 1):
            vals = []
            for col in columns:
                val = row[col]
                if isinstance(val, float):
                    vals.append(f"{val:,.2f}")
                elif isinstance(val, int):
                    vals.append(f"{val:,}")
                else:
                    vals.append(
                        str(val).replace("\n", " | ") if not pd.isna(val) else ""
                    )
            tag = "odd" if idx % 2 == 1 else "even"
            iid = tree.insert("", tk.END, values=vals, tags=(tag, "center"))
            row_data_map[iid] = {col: row[col] for col in columns}

        # 悬浮提示
        tooltip_label = ctk.CTkLabel(
            win, text="", font=("Microsoft YaHei UI", 11),
            text_color="#888888", anchor="w",
        )
        tooltip_label.pack(fill=tk.X, padx=16, pady=(0, 2))

        product_col = self._find_product_col(columns)

        def _on_motion(event):
            item = tree.identify_row(event.y)
            if item and item in row_data_map and product_col:
                raw = row_data_map[item]
                content = str(raw.get(product_col, ""))
                content = content.replace("\n", " │ ") if not pd.isna(raw.get(product_col, "")) else ""
                tooltip_label.configure(text=f"产品名称型号：{content}")
            else:
                tooltip_label.configure(text="")

        tree.bind("<Motion>", _on_motion)

        # 详情文本区域
        detail_text = ctk.CTkTextbox(
            win, height=100, font=("Microsoft YaHei UI", 11),
            wrap="word", corner_radius=6, border_width=1,
        )
        detail_text.pack(fill=tk.BOTH, padx=12, pady=(2, 8))
        detail_text.configure(state="disabled")

        def _on_select(event):
            selection = tree.selection()
            if not selection:
                return
            item = selection[0]
            if item not in row_data_map:
                return
            raw = row_data_map[item]

            detail_text.configure(state="normal")
            detail_text.delete("1.0", tk.END)

            if product_col:
                content = str(raw[product_col]) if not pd.isna(raw[product_col]) else ""
                detail_text.insert(tk.END, content)
            else:
                for c in columns:
                    val = raw[c]
                    val_str = str(val) if not pd.isna(val) else ""
                    detail_text.insert(tk.END, f"{c}：{val_str}\n")

            detail_text.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", _on_select)

        # 底部按钮栏
        btn_bar = ctk.CTkFrame(win, fg_color="transparent", height=40)
        btn_bar.pack_propagate(False)
        btn_bar.pack(fill=tk.X, padx=12, pady=(0, 12))

        ctk.CTkButton(
            btn_bar, text="导出 CSV", command=self._export_csv,
            font=FONT_BOLD, width=100, height=32, corner_radius=6,
        ).pack(side=tk.RIGHT, padx=(0, 8), pady=4)

        ctk.CTkButton(
            btn_bar, text="关闭", command=win.destroy,
            font=FONT_BOLD, width=80, height=32, corner_radius=6,
        ).pack(side=tk.RIGHT, pady=4)

    @staticmethod
    def _find_product_col(columns: list[str]) -> str | None:
        """在列名列表中查找「产品名称型号」列。"""
        for c in columns:
            if "产品名称" in c and "型号" in c:
                return c
        return None

    # ── 导出 ─────────────────────────────────────────────────

    def _export_csv(self) -> None:
        """导出当前详情数据为 CSV 文件。"""
        df = getattr(self, "_export_df", None)
        if df is None or df.empty:
            from tkinter import messagebox
            messagebox.showwarning("提示", "没有数据可导出")
            return
        name = getattr(self, "_export_name", "客户")
        log_info(f"导出CSV [客户详情]: 合同详情_{name}.csv，共 {len(df)} 行")
        export_to_csv(df, self._win, f"合同详情_{name}.csv")
