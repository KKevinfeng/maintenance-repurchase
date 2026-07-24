"""行业统计 Tab：按一级行业 → 二级行业 → 客户逐层下钻。"""

import tkinter as tk
from tkinter import ttk
from typing import Optional
import pandas as pd
import customtkinter as ctk

from ui.base_tab import BaseTab
from ui.logger import log_info
from ui.styles import FONT_MAIN, FONT_TITLE, FONT_SMALL
from utils import center_window, export_to_csv


class IndustryTab(BaseTab):
    """一级行业统计表 — 双击下钻查看二级行业和客户。"""

    # 保留原始 DataFrame 用于下钻
    _raw_df: Optional[pd.DataFrame] = None

    def __init__(self, master, on_double_click=None):
        super().__init__(
            master=master,
            tab_name="行业统计",
            columns=["一级行业", "数量"],
            on_double_click=on_double_click,
            has_star=False,
        )

    def build(self) -> ctk.CTkFrame:
        """构建 UI：利用基类 Treeview，在底部按钮栏添加标题。"""
        frame = super().build()
        ctk.CTkLabel(
            self._btn_bar, text="行业统计",
            font=FONT_TITLE, text_color="#1F6AA5",
        ).pack(side=tk.LEFT, padx=(4, 16))
        return frame

    def compute_data(self, df: pd.DataFrame) -> pd.DataFrame:
        from data_processor import compute_industry_stats

        self._raw_df = df[["一级行业", "二级行业", "最终客户名称"]].copy()
        self._raw_df["一级行业"] = self._raw_df["一级行业"].fillna("未知")
        self._raw_df["二级行业"] = self._raw_df["二级行业"].fillna("未知")
        return compute_industry_stats(self._raw_df)

    def _handle_double_click(self, event) -> None:
        """双击一级行业 → 弹出二级行业统计窗口。"""
        tree = self.tree
        if tree is None:
            return
        region = tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col_id = tree.identify_column(event.x)
        item = tree.selection()
        if not item:
            return
        values = tree.item(item[0], "values")
        if not values:
            return

        primary = str(values[1])
        log_info(f"行业统计下钻: 一级行业「{primary}」")
        self._show_secondary_popup(primary)

    def _show_secondary_popup(self, primary: str) -> None:
        """弹出二级行业统计窗口。"""
        from data_processor import get_secondary_industries

        if self._raw_df is None:
            return

        popup = ctk.CTkToplevel(self.frame)
        popup.title(f"一级行业「{primary}」— 二级行业统计")
        popup.geometry("520x420")
        popup.resizable(True, True)
        popup.transient(self.frame)
        popup.grab_set()
        center_window(popup, 520, 420)

        df = get_secondary_industries(self._raw_df, primary)

        # 工具栏
        toolbar = ctk.CTkFrame(popup, fg_color="transparent")
        toolbar.pack(fill=tk.X, padx=10, pady=(8, 4))

        ctk.CTkLabel(
            toolbar,
            text=f"一级行业「{primary}」的二级行业统计",
            font=FONT_TITLE, text_color="#1F6AA5",
        ).pack(side=tk.LEFT, padx=(4, 16))

        ctk.CTkButton(
            toolbar, text="导出 CSV",
            command=lambda: export_to_csv(df, popup, f"二级行业_{primary}.csv"),
            font=FONT_SMALL, width=80, height=26,
            fg_color="#1F6AA5", hover_color="#155485",
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=(4, 4))

        # 表格区域
        table_frame = ctk.CTkFrame(popup, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ["二级行业", "数量"]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 配置列
        tree.heading("二级行业", text="二级行业", anchor="center")
        tree.column("二级行业", anchor="center", width=300, minwidth=150, stretch=True)
        tree.heading("数量", text="数量", anchor="center")
        tree.column("数量", anchor="center", width=100, minwidth=60, stretch=True)

        # 填入数据
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            tree.insert("", tk.END, values=(str(idx), row["二级行业"], int(row["数量"])))

        # 双击二级行业 → 显示客户名单
        def on_double_click(event):
            region_dc = tree.identify_region(event.x, event.y)
            if region_dc != "cell":
                return
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if not vals:
                return
            secondary = str(vals[1])
            log_info(f"行业统计下钻: 二级行业「{secondary}」→ 客户名单")
            self._show_customers_popup(primary, secondary, popup)

        tree.bind("<Double-1>", on_double_click)

        # 关闭按钮
        ctk.CTkButton(
            popup, text="关闭", command=popup.destroy,
            font=FONT_MAIN, width=80, height=30,
            fg_color="gray", hover_color="#666",
            corner_radius=6,
        ).pack(pady=(0, 10))

    def _show_customers_popup(self, primary: str, secondary: str, parent_popup) -> None:
        """弹出客户名单窗口。"""
        from data_processor import get_industry_customers

        if self._raw_df is None:
            return

        popup = ctk.CTkToplevel(parent_popup)
        popup.title(f"二级行业「{secondary}」— 客户名单")
        popup.geometry("480x400")
        popup.resizable(True, True)
        popup.transient(parent_popup)
        popup.grab_set()
        center_window(popup, 480, 400)

        df = get_industry_customers(self._raw_df, primary, secondary)

        # 工具栏
        toolbar = ctk.CTkFrame(popup, fg_color="transparent")
        toolbar.pack(fill=tk.X, padx=10, pady=(8, 4))

        ctk.CTkLabel(
            toolbar,
            text=f"二级行业「{secondary}」的客户名单",
            font=FONT_TITLE, text_color="#1F6AA5",
        ).pack(side=tk.LEFT, padx=(4, 16))

        ctk.CTkLabel(
            toolbar,
            text=f"共 {len(df)} 个客户",
            font=FONT_SMALL,
        ).pack(side=tk.LEFT)

        ctk.CTkButton(
            toolbar, text="导出 CSV",
            command=lambda: export_to_csv(df, popup, f"客户名单_{secondary}.csv"),
            font=FONT_SMALL, width=80, height=26,
            fg_color="#1F6AA5", hover_color="#155485",
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=(4, 4))

        # 表格区域
        table_frame = ctk.CTkFrame(popup, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ["最终客户名称"]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        tree.heading("最终客户名称", text="最终客户名称", anchor="center")
        tree.column("最终客户名称", anchor="center", width=300, minwidth=150, stretch=True)

        for idx, (_, row) in enumerate(df.iterrows(), 1):
            tree.insert("", tk.END, values=(str(idx), row["最终客户名称"]))

        ctk.CTkButton(
            popup, text="关闭", command=popup.destroy,
            font=FONT_MAIN, width=80, height=30,
            fg_color="gray", hover_color="#666",
            corner_radius=6,
        ).pack(pady=(0, 10))
