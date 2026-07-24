"""BaseTab —— 所有 Tab 页共用的 Treeview 创建/填充/排序逻辑"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import pandas as pd
import customtkinter as ctk

from ui.logger import log_info
from utils import export_to_csv


class BaseTab:
    """可复用的 Tab 页基类。子类只需指定列名、实现 compute_data()。"""

    SEQ_COL = "#"
    STAR_COL = "★"

    def __init__(
        self,
        master: ctk.CTkFrame,
        tab_name: str,
        columns: list[str],
        on_double_click=None,
        has_star: bool = False,
        on_star_toggle=None,
        get_starred_names=None,
    ):
        self.master = master
        self.tab_name = tab_name
        self.columns = columns
        self.on_double_click_callback = on_double_click
        self.has_star = has_star
        self._star_toggle_callback = on_star_toggle
        self._get_starred = get_starred_names

        self.frame: ctk.CTkFrame | None = None
        self.tree: ttk.Treeview | None = None
        self.source_df: pd.DataFrame | None = None
        self.columns_display: list[str] = []
        self.sort_col: str | None = None
        self.sort_asc: bool = True

    # ── 构建 UI ──────────────────────────────────────────────

    def build(self) -> ctk.CTkFrame:
        """创建 Tab 的 Treeview + 滚动条，返回 CTkFrame。"""
        frame = ctk.CTkFrame(self.master, fg_color="transparent", corner_radius=0)

        tree = ttk.Treeview(frame, columns=self.columns, show="headings", height=20)

        for col in self.columns:
            tree.heading(col, text=col, anchor="center")
            tree.heading(
                col, command=lambda c=col: self._on_header_click(c)
            )
            w = self._column_width(col)
            tree.column(col, anchor="center", width=w, minwidth=min(w, 90), stretch=True)

        tree["show"] = ""  # 初始状态隐藏表头

        tree.tag_configure("odd", background="#F4F4F5")
        tree.tag_configure("even", background="#FCFCFC")
        tree.tag_configure("center", anchor="center")

        tree.bind("<Double-1>", lambda e: self._handle_double_click(e))
        if self.has_star:
            tree.bind("<ButtonRelease-1>", self._on_cell_click)

        scrollbar_y = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # 底部导出按钮栏
        btn_bar = ctk.CTkFrame(frame, fg_color="transparent", height=36)
        btn_bar.pack_propagate(False)
        btn_bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ctk.CTkButton(
            btn_bar, text="导出 CSV", command=self._export_csv,
            font=("Microsoft YaHei", 11), width=100, height=28,
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=4, pady=4)

        self._btn_bar = btn_bar  # 暴露给子类添加额外按钮
        self.frame = frame
        self.tree = tree
        return frame

    @staticmethod
    def _column_width(col: str) -> int:
        """根据列名类型返回合适的列宽。"""
        if col.isdigit() and len(col) == 4:
            return 110
        if "名称" in col:
            return 220
        return 160

    # ── 数据计算（子类实现） ────────────────────────────────

    def compute_data(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """子类必须实现：从原始 DataFrame 计算出本 Tab 所需的汇总数据。"""
        raise NotImplementedError

    # ── 数据填充 ────────────────────────────────────────────

    def populate(self, df: pd.DataFrame) -> None:
        """加载 DataFrame 到表格。"""
        self.source_df = df.copy()
        self.tree["show"] = "headings"  # 加载数据后显示表头
        self._fill_tree(df)

    def _fill_tree(self, df: pd.DataFrame) -> None:
        """内部：将 DataFrame 填入 Treeview（不更新 source_df）。"""
        self._sync_columns(df)
        self.tree.delete(*self.tree.get_children())
        self._update_headers()

        df_cols = list(df.columns)
        starred = set(self._get_starred()) if self.has_star and self._get_starred else set()

        for idx, (_, row) in enumerate(df.iterrows(), 1):
            # 格式化数据值
            formatted = []
            for col in df_cols:
                val = row[col]
                if isinstance(val, float):
                    formatted.append(f"{val:,.2f}")
                elif isinstance(val, int):
                    formatted.append(f"{val:,}")
                else:
                    formatted.append(str(val))

            # 标星列
            if self.has_star:
                name_val = str(row[df_cols[0]]) if df_cols else ""
                star = "★" if name_val in starred else "☆"
                values = [star, str(idx)] + formatted
            else:
                values = [str(idx)] + formatted

            tag = "odd" if idx % 2 == 1 else "even"
            self.tree.insert("", tk.END, values=values, tags=(tag, "center"))

    # ── 列同步 ──────────────────────────────────────────────

    def _sync_columns(self, df: pd.DataFrame) -> None:
        """确保 Treeview 列与 DataFrame 列一致（含序号列 # 和标星列）。"""
        tree = self.tree
        if self.has_star:
            display = [self.STAR_COL, self.SEQ_COL] + list(df.columns)
        else:
            display = [self.SEQ_COL] + list(df.columns)
        self.columns_display = display

        current = list(tree["columns"])
        if current == display:
            return

        # 列变化时才重置排序状态
        self.sort_col = None
        self.sort_asc = True

        tree["columns"] = display

        # 标星列
        if self.has_star:
            tree.heading(self.STAR_COL, text="★", anchor="center")
            tree.column(self.STAR_COL, anchor="center", width=50, minwidth=50)

        tree.heading(self.SEQ_COL, text="#", anchor="center")
        tree.column(self.SEQ_COL, anchor="center", width=50, minwidth=50)

        data_cols = list(df.columns)
        for col in data_cols:
            tree.heading(col, text=col, anchor="center")
            tree.heading(col, command=lambda c=col: self._on_header_click(c))
            w = self._column_width(col)
            tree.column(col, anchor="center", width=w, minwidth=min(w, 90), stretch=True)

    # ── 排序 ─────────────────────────────────────────────────

    def _on_header_click(self, col: str) -> None:
        """表头点击排序 — 仅金额/数字列可排序，名称列和标星列跳过。"""
        if col in (self.SEQ_COL, self.STAR_COL):
            return
        if "名称" in col:
            return

        df = self.source_df
        if df is None or col not in df.columns:
            return

        direction = "降序" if not self.sort_asc else "升序"
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
            direction = "升序" if self.sort_asc else "降序"
        else:
            self.sort_col = col
            self.sort_asc = True
        log_info(f"排序 [{self.tab_name}]: {col} {direction}")

        sorted_df = df.sort_values(col, ascending=self.sort_asc).reset_index(drop=True)
        self._fill_tree(sorted_df)

    def _update_headers(self) -> None:
        """更新表头文字，排序列加 ▲/▼ 箭头。"""
        tree = self.tree
        for col in self.columns_display:
            if col == self.sort_col:
                arrow = " ▲" if self.sort_asc else " ▼"
                tree.heading(
                    col, text=col + arrow, anchor="center",
                    command=lambda c=col: self._on_header_click(c),
                )
            else:
                tree.heading(
                    col, text=col, anchor="center",
                    command=lambda c=col: self._on_header_click(c),
                )

    # ── 标星交互 ──────────────────────────────────────────────

    def _on_cell_click(self, event) -> None:
        """点击标星列切换星标状态。"""
        col_id = self.tree.identify_column(event.x)
        if col_id != "#1":  # 第一列 = 标星列
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = list(self.tree.item(item, "values"))
        if not values:
            return
        # values[0] = ★/☆, values[1] = #, values[2] = 客户名称
        current_star = values[0]
        new_star = "☆" if current_star == "★" else "★"
        values[0] = new_star
        self.tree.item(item, values=values)

        if self._star_toggle_callback:
            customer_name = values[2]  # 第三个值 = 客户名称
            self._star_toggle_callback(customer_name, new_star == "★")

    # ── 双击 ─────────────────────────────────────────────────

    def _handle_double_click(self, event) -> None:
        """处理双击事件，委托给回调函数。"""
        if self.on_double_click_callback:
            self.on_double_click_callback(self.tree, event)

    # ── 导出 ─────────────────────────────────────────────────

    def _export_csv(self) -> None:
        """导出当前表格数据为 CSV 文件。"""
        if self.source_df is None or self.source_df.empty:
            from tkinter import messagebox
            messagebox.showwarning("提示", "没有数据可导出")
            return
        log_info(f"导出CSV [{self.tab_name}]: {self.tab_name}.csv，共 {len(self.source_df)} 行")
        export_to_csv(self.source_df, self.frame, f"{self.tab_name}.csv")
