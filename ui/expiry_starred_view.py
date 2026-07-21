"""重点客户过保合同弹窗 —— 筛选标星客户的 P 类过保合同，支持排序"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import pandas as pd
import customtkinter as ctk

from ui.styles import FONT_MAIN, FONT_TITLE, FONT_SMALL
from ui.column_filter_popup import ColumnFilterPopup
from utils import center_window


class ExpiryStarredView:
    """弹窗展示重点客户的过保合同（仅 P 类），具备与 Tab3 一致的表结构和排序功能。"""

    SEQ_COL = "#"

    def __init__(self, parent, df: pd.DataFrame):
        self.original_df = df
        self.sort_col: str | None = None
        self.sort_asc: bool = True
        self.active_filters: dict[str, set] = {}
        self.filter_btns: dict[str, ctk.CTkButton] = {}
        self._build(parent)

    # ── 构建弹窗 ────────────────────────────────────────────

    def _build(self, parent):
        win = ctk.CTkToplevel(parent)
        win.title("重点客户过保合同")
        win.geometry("1000x620")
        win.minsize(600, 400)
        center_window(win, 1000, 620)
        win.grab_set()
        win.after(10, win.focus_force)

        self.win = win

        # 标题栏
        title_bar = ctk.CTkFrame(win, fg_color="transparent")
        title_bar.pack(fill=tk.X, padx=12, pady=(12, 4))

        ctk.CTkLabel(
            title_bar,
            text=f"重点客户过保合同（仅 P 类）— 共 {len(self.original_df)} 条记录",
            font=FONT_TITLE,
            text_color="#1F6AA5",
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(
            title_bar,
            text="基于缓存表标星客户筛选",
            font=FONT_MAIN,
            text_color="#888888",
        ).pack(side=tk.RIGHT)

        # 筛选栏（初始隐藏）
        self.filter_bar = ctk.CTkFrame(win, fg_color="transparent")

        # 表格区域
        tree_frame = ctk.CTkFrame(win, fg_color="transparent")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))

        tree = ttk.Treeview(tree_frame, show="headings", height=20)
        tree.tag_configure("odd", background="#F4F4F5")
        tree.tag_configure("even", background="#FCFCFC")
        tree.tag_configure("center", anchor="center")

        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = tree
        self.tree_frame = tree_frame
        self._fill_tree(self.original_df)
        self._build_filter_bar()

    # ── 数据填充 ────────────────────────────────────────────

    @staticmethod
    def _reorder_columns(columns) -> list:
        """将过保日期、客户意向、不续保原因列前置。"""
        cols = list(columns)
        priority = []
        for kw in ["过保日期", "客户意向", "不续保原因"]:
            for c in cols:
                if kw in str(c) and c not in priority:
                    priority.append(c)
                    break
        result = [c for c in priority if c in cols]
        result += [c for c in cols if c not in result]
        return result

    def _fill_tree(self, df: pd.DataFrame) -> None:
        """将 DataFrame 填入 Treeview。"""
        tree = self.tree
        reordered_cols = self._reorder_columns(list(df.columns))
        display = [self.SEQ_COL] + reordered_cols

        # 列变化时才重置排序状态
        current = list(tree["columns"])
        if current != display:
            self.sort_col = None
            self.sort_asc = True

        tree["columns"] = display
        tree.heading(self.SEQ_COL, text="#", anchor="center")
        tree.column(self.SEQ_COL, anchor="center", width=50, minwidth=50)

        for col in reordered_cols:
            clean = self._clean_col(col)
            tree.heading(col, text=clean, anchor="center")
            tree.heading(col, command=lambda c=col: self._on_header_click(c))
            w = self._column_width(col)
            tree.column(col, anchor="center", width=w, minwidth=min(w, 100), stretch=True)

        self._update_headers()

        tree.delete(*tree.get_children())
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            values = [str(idx)] + [self._fmt_val(row[c]) for c in reordered_cols]
            tag = "odd" if idx % 2 == 1 else "even"
            tree.insert("", tk.END, values=values, tags=(tag, "center"))

    # ── 筛选栏 ───────────────────────────────────────────────

    FILTER_KEYWORDS = ["客户意向", "不续保原因"]

    def _get_filter_columns(self) -> list[str]:
        df = self.original_df
        if df is None:
            return []
        result = []
        for col in df.columns:
            for kw in self.FILTER_KEYWORDS:
                if kw in str(col) and col not in result:
                    result.append(col)
        return result

    def _get_filter_values(self, col: str) -> list[str]:
        """返回当前筛选结果中该列的去重值（考虑其他列已生效的筛选）。"""
        if self.original_df is None or col not in self.original_df.columns:
            return []
        # 先应用所有其他列的筛选条件
        df = self.original_df.copy()
        for f_col, allowed in self.active_filters.items():
            if f_col == col or f_col not in df.columns:
                continue
            if not allowed:
                return []
            ser = df[f_col].fillna("（空）").astype(str)
            df = df[ser.isin(allowed)]
        vals = df[col].dropna().astype(str).unique().tolist()
        if df[col].isna().any():
            vals.append("（空）")
        vals = sorted(set(vals), key=lambda x: (x == "（空）", x))
        return vals

    def _build_filter_bar(self):
        for w in self.filter_bar.winfo_children():
            w.destroy()
        self.filter_btns.clear()

        filter_cols = self._get_filter_columns()
        if not filter_cols:
            self.filter_bar.pack_forget()
            return

        ctk.CTkLabel(
            self.filter_bar, text="筛选：", font=FONT_SMALL, text_color="#888888",
        ).pack(side=tk.LEFT, padx=(0, 6))

        for col in filter_cols:
            clean = self._clean_col(col)
            vals = self._get_filter_values(col)
            selected = self.active_filters.get(col, set(vals))
            is_active = selected != set(vals)

            text = f"▽ {clean}"
            if is_active:
                text = f"▼ {clean}({len(selected)})"

            btn = ctk.CTkButton(
                self.filter_bar, text=text, font=FONT_SMALL,
                width=120, height=24, corner_radius=4,
                fg_color="#2F8BCC" if is_active else "#E8E8E8",
                text_color="#FFFFFF" if is_active else "#555555",
                hover_color="#2674AA" if is_active else "#D0D0D0",
                command=lambda c=col, vs=vals: self._open_filter_popup(c, vs, selected),
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self.filter_btns[col] = btn

        # 清除筛选
        if any(v != set(self._get_filter_values(c)) for c, v in self.active_filters.items()
               if v):
            ctk.CTkButton(
                self.filter_bar, text="清除筛选", font=FONT_SMALL,
                width=70, height=24, corner_radius=4,
                fg_color="#D9534F", text_color="#FFFFFF",
                hover_color="#C9302C",
                command=self._clear_filters,
            ).pack(side=tk.LEFT, padx=(4, 0))

        self.filter_bar.pack(fill=tk.X, padx=12, pady=(4, 0), before=self.tree_frame)

    def _open_filter_popup(self, col: str, all_vals: list[str], selected: set):
        ColumnFilterPopup(self.win, self._clean_col(col), all_vals, selected,
                          on_apply=self._apply_filter)

    def _apply_filter(self, col: str, selected: set):
        self.active_filters[col] = selected
        self.sort_col = None
        self.sort_asc = True
        self._fill_tree(self._get_display_df())
        self._build_filter_bar()

    def _clear_filters(self):
        self.active_filters.clear()
        self.sort_col = None
        self.sort_asc = True
        self._fill_tree(self.original_df)
        self._build_filter_bar()

    def _get_display_df(self):
        df = self.original_df
        if df is None:
            return None
        df = df.copy()
        for col, allowed in self.active_filters.items():
            if col not in df.columns:
                continue
            if not allowed:
                # 用户取消全选 → 返回空结果
                return df.iloc[:0].copy()
            ser = df[col].fillna("（空）").astype(str)
            mask = ser.isin(allowed)
            df = df[mask]
        if self.sort_col and self.sort_col in df.columns:
            df = df.sort_values(self.sort_col, ascending=self.sort_asc).reset_index(drop=True)
        return df

    # ── 排序 ─────────────────────────────────────────────────

    def _on_header_click(self, col: str) -> None:
        """表头点击排序 — 在筛选基础上排序，名称列跳过。"""
        if col == self.SEQ_COL:
            return
        if "名称" in col:
            return

        display_df = self._get_display_df()
        if display_df is None or col not in display_df.columns:
            return

        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True

        sorted_df = (
            display_df
            .sort_values(col, ascending=self.sort_asc)
            .reset_index(drop=True)
        )
        self._fill_tree(sorted_df)

    def _update_headers(self) -> None:
        """更新表头文字，排序列添加 ▲/▼ 箭头。"""
        tree = self.tree
        df_cols = list(self.original_df.columns)
        all_cols = [self.SEQ_COL] + df_cols

        for col in all_cols:
            if col == self.sort_col:
                arrow = " ▲" if self.sort_asc else " ▼"
                text = col if col == self.SEQ_COL else self._clean_col(col)
                tree.heading(
                    col, text=text + arrow, anchor="center",
                    command=lambda c=col: self._on_header_click(c),
                )
            elif col == self.SEQ_COL:
                tree.heading(col, text="#", anchor="center")
            else:
                tree.heading(
                    col, text=self._clean_col(col), anchor="center",
                    command=lambda c=col: self._on_header_click(c),
                )

    # ── 格式化工具（与 ExpiryStatsTab 相同） ─────────────────

    @staticmethod
    def _clean_col(col: str) -> str:
        if isinstance(col, str):
            return col.replace("\n", " ")
        return str(col)

    @staticmethod
    def _fmt_val(val) -> str:
        import math
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return ""
            if val == int(val):
                return f"{int(val):,}"
            return f"{val:,.2f}"
        if isinstance(val, int):
            return f"{val:,}"
        if pd.isna(val):
            return ""
        return str(val)

    @staticmethod
    def _column_width(col: str) -> int:
        if "编码" in col or "编号" in col:
            return 240
        if "客户" in col or "单位" in col or "名称" in col:
            return 220
        if "合同" in col:
            return 200
        if "型号" in col or "模块" in col:
            return 180
        if "金额" in col:
            return 160
        if "跟踪" in col or "接收" in col or "核算" in col:
            return 140
        if "备注" in col or "原因" in col:
            return 320
        if "时间" in col:
            return 150
        if "行业" in col:
            return 150
        return 160

    # ── 入口 ─────────────────────────────────────────────────

    @classmethod
    def show(cls, parent, df: pd.DataFrame) -> None:
        """打开弹窗展示筛选后的过保合同。"""
        cls(parent, df)
