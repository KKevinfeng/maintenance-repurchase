"""Tab 7：过保数据分析 — 基于 Tab3 数据，展示 P 类合同，管理续保明细，筛选已续保/年份。"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import customtkinter as ctk

from ui.styles import FONT_MAIN, FONT_SMALL, FONT_TITLE, FONT_BOLD
from ui.column_filter_popup import ColumnFilterPopup
from ui.logger import log_error, log_info
from utils import classify_contract, extract_contract_year, center_window, export_to_csv

RENEWAL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "renewal_details.xlsx")
GIFT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gift_channels.xlsx")


class RenewalAnalysisTab:
    """过保数据分析页 — 数据来源于 Tab3，统计续保情况。"""

    SEQ_COL = "#"

    RENEWED_FILTER = {1: "已有续保合同", 2: "未有续保合同"}
    FILTER_KEYWORDS = ["客户意向", "不续保原因"]

    def __init__(self, master: ctk.CTkFrame, expiry_tab, main_df_provider=None):
        self.master = master
        self.expiry_tab = expiry_tab  # Tab3 引用
        self.main_df_provider = main_df_provider  # 主合同文件数据（用于维保金额查询）
        self.frame: ctk.CTkFrame | None = None
        self.tree: ttk.Treeview | None = None
        self.source_df: pd.DataFrame | None = None
        self.columns_display: list[str] = []
        self.sort_col: str | None = None
        self.sort_asc: bool = True

        # 筛选状态
        self.filter_has_renewed: set[str] | None = None  # None=不筛选，{"Y"}=已有续保，{"N"}=未有续保，{"Y","N"}=全选(不筛选)
        self.filter_year: set[str] | None = None  # None=未筛选，set=按年份集合筛选，空集合=无结果
        self.active_filters: dict[str, set[str] | None] = {}  # 列值筛选（客户意向、不续保原因等）

        # 续保明细 [(关联老合同, 续保合同号, 客户名称), ...] — 支持一对多
        self._renewal_details: list[tuple[str, str, str]] = []

        # 大礼包渠道名称集合（命中 Tab3 最终客户时标红）
        self._gift_channels: set[str] = set()

    # ── 构建 UI ──────────────────────────────────────────────

    def build(self) -> ctk.CTkFrame:
        """构建 Tab7 界面。"""
        frame = ctk.CTkFrame(self.master, fg_color="transparent", corner_radius=0)
        frame.grid_rowconfigure(0, weight=0)  # top_bar
        frame.grid_rowconfigure(1, weight=0)  # filter_bar
        frame.grid_rowconfigure(2, weight=1)  # tree_frame (expand)
        frame.grid_rowconfigure(3, weight=0)  # btn_bar
        frame.grid_columnconfigure(0, weight=1)

        # 顶部提示
        top_bar = ctk.CTkFrame(frame, fg_color="transparent", height=32)
        top_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))
        top_bar.pack_propagate(False)
        self._hint_label = ctk.CTkLabel(
            top_bar, text="请先在「过保情况统计」中导入过保数据表",
            font=FONT_SMALL, text_color="#888",
        )
        self._hint_label.pack(side=tk.LEFT, padx=4)

        # 筛选栏（初始隐藏，数据加载后显示）
        filter_bar = ctk.CTkFrame(frame, fg_color="transparent", height=32)
        filter_bar.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 4))
        filter_bar.grid_remove()
        filter_bar.pack_propagate(False)
        self.filter_bar = filter_bar

        ctk.CTkLabel(
            filter_bar, text="筛选：", font=FONT_SMALL, text_color="#888",
        ).pack(side=tk.LEFT, padx=(0, 6))

        # 是否续保按钮
        self._renewed_btn = ctk.CTkButton(
            filter_bar, text="是否续保", command=self._open_renewed_filter,
            font=FONT_SMALL, width=110, height=24, corner_radius=4,
            fg_color="#E8E8E8", hover_color="#D0D0D0", text_color="#555",
        )
        self._renewed_btn.pack(side=tk.LEFT, padx=(0, 4))

        # 筛选年份按钮
        self._year_btn = ctk.CTkButton(
            filter_bar, text="筛选年份", command=self._open_year_filter,
            font=FONT_SMALL, width=110, height=24, corner_radius=4,
            fg_color="#E8E8E8", hover_color="#D0D0D0", text_color="#555",
        )
        self._year_btn.pack(side=tk.LEFT, padx=(0, 4))

        # 客户意向按钮
        self._intent_btn = ctk.CTkButton(
            filter_bar, text="客户意向", command=lambda: self._open_column_filter("*客户意向"),
            font=FONT_SMALL, width=110, height=24, corner_radius=4,
            fg_color="#E8E8E8", hover_color="#D0D0D0", text_color="#555",
        )
        self._intent_btn.pack(side=tk.LEFT, padx=(0, 4))

        # 不续保原因按钮
        self._reason_btn = ctk.CTkButton(
            filter_bar, text="不续保原因", command=lambda: self._open_column_filter("不续保原因"),
            font=FONT_SMALL, width=110, height=24, corner_radius=4,
            fg_color="#E8E8E8", hover_color="#D0D0D0", text_color="#555",
        )
        self._reason_btn.pack(side=tk.LEFT, padx=(0, 4))

        # 清除筛选按钮（初始隐藏）
        self._clear_filter_btn = ctk.CTkButton(
            filter_bar, text="清除筛选", command=self._clear_filters,
            font=FONT_SMALL, width=80, height=24, corner_radius=4,
            fg_color="#D9534F", hover_color="#C9302C", text_color="#FFFFFF",
        )

        # Treeview
        tree_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))

        self.columns = [
            self.SEQ_COL, "最终客户名称", "合同编码", "合同金额", "负责销售", "过保年份",
            "*客户意向", "不续保原因", "维保合同", "维保金额",
        ]
        tree = ttk.Treeview(tree_frame, columns=self.columns, show="", height=16)
        tree.column(self.SEQ_COL, anchor="center", width=50, minwidth=50, stretch=False)
        tree.heading(self.SEQ_COL, text="#", anchor="center")
        tree.column("最终客户名称", anchor="center", width=200, minwidth=140, stretch=True)
        tree.heading("最终客户名称", text="最终客户名称", anchor="center",
                     command=lambda: self._on_header_click("最终客户名称"))
        tree.column("合同编码", anchor="center", width=180, minwidth=130, stretch=True)
        tree.heading("合同编码", text="合同编码", anchor="center",
                     command=lambda: self._on_header_click("合同编码"))
        tree.column("合同金额", anchor="center", width=140, minwidth=110, stretch=True)
        tree.heading("合同金额", text="合同金额", anchor="center",
                     command=lambda: self._on_header_click("合同金额"))
        tree.column("负责销售", anchor="center", width=110, minwidth=90, stretch=True)
        tree.heading("负责销售", text="负责销售", anchor="center",
                     command=lambda: self._on_header_click("负责销售"))
        tree.column("过保年份", anchor="center", width=90, minwidth=80, stretch=False)
        tree.heading("过保年份", text="过保年份", anchor="center",
                     command=lambda: self._on_header_click("过保年份"))
        tree.column("*客户意向", anchor="center", width=110, minwidth=90, stretch=True)
        tree.heading("*客户意向", text="客户意向", anchor="center",
                     command=lambda: self._on_header_click("*客户意向"))
        tree.column("不续保原因", anchor="center", width=200, minwidth=140, stretch=True)
        tree.heading("不续保原因", text="不续保原因", anchor="center",
                     command=lambda: self._on_header_click("不续保原因"))
        tree.column("维保合同", anchor="center", width=150, minwidth=110, stretch=True)
        tree.heading("维保合同", text="维保合同", anchor="center")
        tree.column("维保金额", anchor="center", width=120, minwidth=100, stretch=False)
        tree.heading("维保金额", text="维保金额", anchor="center")

        tree.tag_configure("odd", background="#F4F4F5")
        tree.tag_configure("even", background="#FCFCFC")
        tree.tag_configure("renewed", background="#66BB6A", foreground="#FFFFFF")
        tree.tag_configure("gift_renewed", background="#66BB6A", foreground="#C62828")
        tree.tag_configure("gift_odd", background="#F4F4F5", foreground="#C62828")
        tree.tag_configure("gift_even", background="#FCFCFC", foreground="#C62828")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = tree

        # 双击行显示产品名称型号
        tree.bind("<Double-1>", self._on_double_click_row)

        # 底部按钮栏（使用 grid 保证固定在底部）
        btn_bar = ctk.CTkFrame(frame, fg_color="transparent", height=36)
        btn_bar.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 6))
        btn_bar.pack_propagate(False)

        # 续保明细按钮（左下角）
        ctk.CTkButton(
            btn_bar, text="续保明细", command=self._open_renewal_detail,
            font=FONT_SMALL, width=100, height=28,
            fg_color="#1F6AA5", hover_color="#144870", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 6), pady=4)

        # 大礼包标记按钮
        self._gift_btn = ctk.CTkButton(
            btn_bar, text="大礼包标记", command=self._open_gift_channel_manager,
            font=FONT_SMALL, width=120, height=28,
            fg_color="#D35400", hover_color="#A04000", corner_radius=6,
        )
        self._gift_btn.pack(side=tk.LEFT, padx=(0, 6), pady=4)

        # 导出 CSV（右下角）
        ctk.CTkButton(
            btn_bar, text="导出 CSV", command=self._export_csv,
            font=FONT_SMALL, width=80, height=28,
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=4, pady=4)

        self.frame = frame
        self._btn_bar = btn_bar
        return frame

    # ── 数据加载 ──────────────────────────────────────────────

    def load_data(self) -> None:
        """从 Tab3 获取数据（切到 Tab7 时自动调用）。"""
        self.refresh()

    def _find_columns(self, df: pd.DataFrame):
        """查找 Tab3 数据中的关键列。"""
        contract_col = gift_col = enduser_col = expiry_col = intent_col = reason_col = sales_col = product_amount_col = None
        for c in df.columns:
            s = str(c).replace("\n", " ")
            if contract_col is None and ("合同编码" in s or "合同编号" in s):
                contract_col = c
            if gift_col is None and "渠道大礼包最终客户" in s:
                gift_col = c
            if enduser_col is None and "最终客户" in s and "大礼包" not in s:
                enduser_col = c
            if expiry_col is None and "过保日期" in s:
                expiry_col = c
            if intent_col is None and "客户意向" in s:
                intent_col = c
            if reason_col is None and "不续保原因" in s:
                reason_col = c
            if sales_col is None and "销售跟踪人" in s:
                sales_col = c
            if product_amount_col is None and "产品金额" in s:
                product_amount_col = c
        return contract_col, gift_col, enduser_col, expiry_col, intent_col, reason_col, sales_col, product_amount_col

    @staticmethod
    def _resolve_customer(row, gift_col, enduser_col):
        """解析最终客户名称：优先使用渠道大礼包最终客户。"""
        if gift_col:
            val = row.get(gift_col, "")
            if pd.notna(val) and str(val).strip():
                return str(val).strip()
        if enduser_col:
            val = row.get(enduser_col, "")
            if pd.notna(val):
                return str(val).strip()
        return ""

    @staticmethod
    def _format_year(values) -> list[str]:
        """将过保日期格式化为 YYYY（仅保留年份）。"""
        result = []
        for v in values:
            if pd.isna(v):
                result.append("")
                continue
            try:
                dt = pd.to_datetime(v, errors="coerce")
                if pd.notna(dt):
                    result.append(dt.strftime("%Y"))
                else:
                    result.append(str(v).strip()[:4])
            except Exception:
                result.append(str(v).strip()[:4])
        return result

    # ── 表格填充 ──────────────────────────────────────────────

    def _fill_tree(self) -> None:
        """填充 / 刷新表格数据。"""
        df = self.source_df
        if df is None:
            return

        # 应用筛选
        display_df = self._apply_filters(df)

        tree = self.tree
        tree.delete(*tree.get_children())

        if display_df.empty:
            count = len(df)
            renewed_count = len({o for o, _, _ in self._renewal_details})
            self._hint_label.configure(
                text=f"已加载 {count} 条 P 类合同 / 已续保 {renewed_count} 条"
                + ("（当前筛选结果为空）" if count > 0 else "")
            )
            return

        for idx, (_, row) in enumerate(display_df.iterrows(), 1):
            contract = str(row["合同编码"]) if pd.notna(row["合同编码"]) else ""
            customer = str(row["最终客户名称"]) if pd.notna(row["最终客户名称"]) else ""
            expiry_year = str(row["过保年份"]) if pd.notna(row["过保年份"]) else ""
            # 大礼包碰撞使用原始"最终客户"字段，而非 _resolve_customer 解析后的值
            orig_enduser = str(row["_原始最终客户"]) if pd.notna(row["_原始最终客户"]) else ""
            is_renewed = self._is_contract_renewed(contract, customer, expiry_year)
            is_gift = orig_enduser in self._gift_channels
            if is_gift:
                if is_renewed:
                    tags = ("gift_renewed",)
                else:
                    tags = ("gift_odd",) if idx % 2 == 1 else ("gift_even",)
            elif is_renewed:
                tags = ("renewed",)
            else:
                tags = ("odd" if idx % 2 == 1 else "even",)
            values = (
                str(idx),
                customer,
                contract,
                str(row["合同金额"]) if pd.notna(row["合同金额"]) else "",
                str(row["负责销售"]) if pd.notna(row["负责销售"]) else "",
                str(row["过保年份"]) if pd.notna(row["过保年份"]) else "",
                str(row["*客户意向"]) if pd.notna(row["*客户意向"]) else "",
                str(row["不续保原因"]) if pd.notna(row["不续保原因"]) else "",
                str(row["维保合同"]) if pd.notna(row["维保合同"]) else "",
                str(row["维保金额"]) if pd.notna(row["维保金额"]) else "",
            )
            tree.insert("", tk.END, values=values, tags=tags)

        count = len(df)
        renewed_count = len({o for o, _, _ in self._renewal_details})
        self._hint_label.configure(
            text=f"已加载 {count} 条 P 类合同 / 已续保 {renewed_count} 条"
        )

    def _apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """应用所有筛选（是否续保、年份、列值筛选），返回过滤后的 DataFrame。"""
        result = self._apply_renewed_filter(df)
        result = self._apply_year_filter(result)
        result = self._apply_column_filters(result)
        return result

    def _apply_renewed_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """应用是否续保筛选。"""
        if df is None or df.empty:
            return df
        result = df.copy()
        if self.filter_has_renewed is not None and self.filter_has_renewed != {"Y", "N"}:
            if "Y" in self.filter_has_renewed and "N" not in self.filter_has_renewed:
                # 仅显示已有续保合同（标绿的），同时考虑客户名称匹配
                result = result[result.apply(
                    lambda r: self._is_contract_renewed(
                        str(r["合同编码"]) if pd.notna(r["合同编码"]) else "",
                        str(r["最终客户名称"]) if pd.notna(r["最终客户名称"]) else "",
                        str(r["过保年份"]) if pd.notna(r["过保年份"]) else "",
                    ), axis=1,
                )]
            elif "N" in self.filter_has_renewed and "Y" not in self.filter_has_renewed:
                # 仅显示未有续保合同（未标绿的），同时考虑客户名称匹配和年份匹配
                result = result[~result.apply(
                    lambda r: self._is_contract_renewed(
                        str(r["合同编码"]) if pd.notna(r["合同编码"]) else "",
                        str(r["最终客户名称"]) if pd.notna(r["最终客户名称"]) else "",
                        str(r["过保年份"]) if pd.notna(r["过保年份"]) else "",
                    ), axis=1,
                )]
            else:
                # 空集合 → 无结果
                result = result.iloc[:0].copy()
        return result

    def _apply_year_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """应用过保年份筛选。"""
        if df is None or df.empty:
            return df
        result = df.copy()
        if self.filter_year is not None:
            if not self.filter_year:
                result = result.iloc[:0].copy()
            else:
                result = result[result["过保年份"].astype(str).isin(self.filter_year)]
        return result

    def _apply_column_filters(self, df: pd.DataFrame, exclude_col: str | None = None) -> pd.DataFrame:
        """应用列值筛选（AND 关系），可排除指定列以计算联动选项。"""
        if df is None or df.empty:
            return df
        result = df.copy()
        for col, allowed in self.active_filters.items():
            if col == exclude_col or col not in result.columns:
                continue
            if allowed is None or not allowed:
                result = result.iloc[:0].copy()
                break
            ser = result[col].fillna("（空）").astype(str)
            result = result[ser.isin(allowed)]
        return result

    # ── 双击查看产品 ──────────────────────────────────────────

    def _on_double_click_row(self, event: tk.Event) -> None:
        """双击行时，弹出该合同的产品明细（从 Tab3 数据匹配）。"""
        tree = self.tree
        if tree is None:
            return
        sel = tree.selection()
        if not sel:
            return
        values = tree.item(sel[0], "values")
        if len(values) < 3:
            return
        contract = str(values[2]).strip()  # 第 3 列是合同编码
        customer = str(values[1]).strip()
        if not contract:
            return

        # 从 Tab3 数据匹配
        expiry_df = self.expiry_tab.source_df
        if expiry_df is None or expiry_df.empty:
            messagebox.showinfo("提示", "Tab3 过保数据未加载，无法查询产品信息。", parent=self.frame)
            return

        contract_col, gift_col, enduser_col, _, _, _, _, _ = self._find_columns(expiry_df)
        if contract_col is None:
            messagebox.showinfo("提示", "Tab3 数据中未找到合同编码列。", parent=self.frame)
            return

        # 匹配逻辑：合同编码相同 AND 客户名称相同（渠道大礼包优先，与 _resolve_customer 一致）
        matched_rows = []
        for _, row in expiry_df.iterrows():
            code = str(row.get(contract_col, "")).strip()
            if code != contract:
                continue
            row_cust = self._resolve_customer(row, gift_col, enduser_col).strip()
            if row_cust == customer:
                matched_rows.append(row)

        if not matched_rows:
            messagebox.showinfo(
                "产品明细",
                f"合同编码: {contract}\n客户: {customer}\n\n未在 Tab3 数据中找到匹配记录。",
                parent=self.frame,
            )
            return

        # 收集产品名称、产品型号、产品模块
        product_lines = []
        for row in matched_rows:
            parts = []
            for col_key in ("产品名称", "产品型号", "产品模块"):
                found = None
                for c in expiry_df.columns:
                    if col_key in str(c).replace("\n", " "):
                        found = c
                        break
                val = ""
                if found:
                    v = row.get(found, "")
                    val = str(v).strip() if pd.notna(v) else ""
                parts.append(val)
            line = " | ".join(parts)
            if line.strip("| "):
                product_lines.append(line)

        # 收集续保明细：合同编码 + 客户名称 匹配，展示 续保合同 | 续保金额
        renewal_lines = []
        for old, new, cust in self._renewal_details:
            if old != contract:
                continue
            map_cust = cust.strip() if cust else ""
            if map_cust and map_cust != customer:
                continue
            amount = self._lookup_main_amount(new)
            renewal_lines.append(f"{new} | {amount}")

        product_text = "\n".join(f"{i}. {line}" for i, line in enumerate(product_lines, 1)) if product_lines else "无产品明细"
        renewal_text = "\n".join(f"{i}. {line}" for i, line in enumerate(renewal_lines, 1)) if renewal_lines else "无续保明细"

        dlg = ctk.CTkToplevel(self.frame)
        dlg.title(f"合同明细 - {contract}")
        dlg.geometry("700x550")
        dlg.resizable(True, True)
        dlg.minsize(500, 400)
        dlg.transient(self.frame)
        dlg.grab_set()
        center_window(dlg, 700, 550)

        header = ctk.CTkLabel(
            dlg,
            text=f"合同编码: {contract}    客户: {customer}",
            font=FONT_BOLD,
            anchor="w",
        )
        header.pack(fill=tk.X, padx=16, pady=(12, 4))

        # ── 产品明细 ──
        product_label = ctk.CTkLabel(
            dlg, text=f"产品明细（共 {len(product_lines)} 条）", font=FONT_BOLD, anchor="w",
        )
        product_label.pack(fill=tk.X, padx=16, pady=(8, 2))

        product_box = tk.Text(
            dlg, wrap=tk.WORD, font=("Microsoft YaHei UI", 11),
            relief=tk.FLAT, borderwidth=0,
        )
        product_box.insert("1.0", product_text)
        product_box.configure(state="disabled")
        product_box.pack(fill=tk.BOTH, expand=True, padx=16, pady=(2, 8))

        # ── 续保明细 ──
        renewal_label = ctk.CTkLabel(
            dlg, text=f"续保明细（共 {len(renewal_lines)} 条）", font=FONT_BOLD, anchor="w",
        )
        renewal_label.pack(fill=tk.X, padx=16, pady=(8, 2))

        renewal_box = tk.Text(
            dlg, wrap=tk.WORD, font=("Microsoft YaHei UI", 11),
            relief=tk.FLAT, borderwidth=0,
        )
        renewal_box.insert("1.0", renewal_text)
        renewal_box.configure(state="disabled")
        renewal_box.pack(fill=tk.BOTH, expand=True, padx=16, pady=(2, 12))

        ctk.CTkButton(
            dlg, text="关闭", command=dlg.destroy,
            font=FONT_MAIN, width=80, height=30, corner_radius=6,
        ).pack(pady=(0, 12))

    # ── 排序 ─────────────────────────────────────────────────

    def _on_header_click(self, col: str) -> None:
        df = self.source_df
        if df is None or col not in df.columns:
            return
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True

        # 数字列按数值排序，避免字符串比较 "900,000.00" < "99,630.00"
        if col in ("合同金额", "维保金额"):
            sort_key = lambda s: pd.to_numeric(
                s.astype(str).str.replace(",", ""), errors="coerce"
            ).fillna(-1)
            sorted_df = df.sort_values(
                col, ascending=self.sort_asc, key=sort_key,
            ).reset_index(drop=True)
        else:
            sorted_df = df.sort_values(col, ascending=self.sort_asc).reset_index(drop=True)

        self.source_df = sorted_df
        self._fill_tree()

    # ── 筛选 ─────────────────────────────────────────────────

    def _open_renewed_filter(self) -> None:
        """打开是否续保筛选弹窗（固定选项：已有续保合同 / 未有续保合同）。"""
        values = ["已有续保合同", "未有续保合同"]
        # 确定当前选中状态：Y → "已有续保合同", N → "未有续保合同"
        selected = set(values)  # 默认全选
        if self.filter_has_renewed is not None:
            selected = set()
            if "Y" in self.filter_has_renewed:
                selected.add("已有续保合同")
            if "N" in self.filter_has_renewed:
                selected.add("未有续保合同")
        ColumnFilterPopup(
            parent=self.frame,
            col_name="是否续保",
            all_values=values,
            selected=selected,
            on_apply=self._on_renewed_filter_apply,
        )

    def _on_renewed_filter_apply(self, col_name: str, selected: set[str]) -> None:
        """续保状态筛选回调。"""
        # 转换：已有续保合同 → Y，未有续保合同 → N
        mapped = set()
        if "已有续保合同" in selected:
            mapped.add("Y")
        if "未有续保合同" in selected:
            mapped.add("N")

        if not mapped or mapped == {"Y", "N"}:
            self.filter_has_renewed = None
        else:
            self.filter_has_renewed = mapped
        self._refresh_filter_buttons()
        self._fill_tree()

    def _open_year_filter(self) -> None:
        """打开年份筛选弹窗（基于过保年份列 YYYY，选项与所有其他筛选联动）。"""
        if self.source_df is None or self.source_df.empty:
            return
        # 应用除年份筛选外的其他筛选，确保年份选项联动
        df = self._apply_renewed_filter(self.source_df)
        df = self._apply_column_filters(df)
        years = sorted(
            {str(y) for y in df["过保年份"].dropna().astype(str).unique()},
            reverse=True,
        )
        if not years:
            return
        values = sorted(years)
        ColumnFilterPopup(
            parent=self.frame,
            col_name="过保年份",
            all_values=values,
            selected=set(values) if self.filter_year is None else set(self.filter_year),
            on_apply=self._on_year_filter_apply,
        )

    def _on_year_filter_apply(self, col_name: str, selected: set[str]) -> None:
        """年份筛选回调：支持多选；全选/未选均视为不筛选。"""
        # 必须与弹窗生成选项时使用同样的数据范围（含其他筛选联动），否则全选判断会失效
        df = self._apply_renewed_filter(self.source_df)
        df = self._apply_column_filters(df)
        all_years = {str(y) for y in df["过保年份"].dropna().astype(str).unique()}

        selected = {str(s) for s in selected}

        if not selected or selected == all_years:
            self.filter_year = None
        else:
            self.filter_year = selected
        self._refresh_filter_buttons()
        self._fill_tree()


    def _clear_filters(self) -> None:
        """清除所有筛选。"""
        self.filter_has_renewed = None
        self.filter_year = None
        self.active_filters.clear()
        self._refresh_filter_buttons()
        self._fill_tree()

    def _has_active_filters(self) -> bool:
        """检查是否存在任何激活的筛选条件。"""
        if self.filter_has_renewed is not None and self.filter_has_renewed != {"Y", "N"}:
            return True
        if self.filter_year is not None:
            return True
        return bool(self.active_filters)

    def _show_filter_bar(self) -> None:
        """数据加载后显示筛选栏并刷新按钮状态。"""
        self.filter_bar.grid()
        self._refresh_filter_buttons()

    def _set_tree_header_visible(self, visible: bool) -> None:
        """控制 Treeview 表头显示/隐藏。"""
        if self.tree:
            self.tree.configure(show="headings" if visible else "")

    def _refresh_filter_buttons(self) -> None:
        """根据当前筛选状态更新按钮颜色和文本（不销毁重建）。"""
        # 是否续保
        renewed_active = (
            self.filter_has_renewed is not None
            and self.filter_has_renewed != {"Y", "N"}
        )
        renewed_count = len(self.filter_has_renewed) if renewed_active else 0
        renewed_text = f"▼ 是否续保({renewed_count})" if renewed_active else "▽ 是否续保"
        self._renewed_btn.configure(
            text=renewed_text,
            fg_color="#2F8BCC" if renewed_active else "#E8E8E8",
            hover_color="#1F6AA5" if renewed_active else "#D0D0D0",
            text_color="#FFFFFF" if renewed_active else "#555",
        )

        # 筛选年份
        year_active = self.filter_year is not None
        year_count = len(self.filter_year) if year_active else 0
        year_text = f"▼ 筛选年份({year_count})" if year_active else "▽ 筛选年份"
        self._year_btn.configure(
            text=year_text,
            fg_color="#2F8BCC" if year_active else "#E8E8E8",
            hover_color="#1F6AA5" if year_active else "#D0D0D0",
            text_color="#FFFFFF" if year_active else "#555",
        )

        # 客户意向
        self._update_column_btn(self._intent_btn, "*客户意向")
        # 不续保原因
        self._update_column_btn(self._reason_btn, "不续保原因")

        # 清除筛选按钮
        if self._has_active_filters():
            self._clear_filter_btn.pack(side=tk.LEFT, padx=(4, 0))
        else:
            self._clear_filter_btn.pack_forget()

    def _update_column_btn(self, btn: ctk.CTkButton, col: str) -> None:
        """更新单个列筛选按钮的样式和文本。"""
        if self.source_df is None or col not in self.source_df.columns:
            btn.configure(text=str(col), fg_color="#E8E8E8", hover_color="#D0D0D0", text_color="#555")
            return
        all_values = self._get_filter_values(col)
        selected = self.active_filters.get(col, set(all_values))
        if not selected:
            selected = set(all_values)
        is_active = selected != set(all_values)
        display_name = str(col).replace("*", "").strip()
        text = f"▼ {display_name}({len(selected)})" if is_active else f"▽ {display_name}"
        btn.configure(
            text=text,
            fg_color="#2F8BCC" if is_active else "#E8E8E8",
            hover_color="#1F6AA5" if is_active else "#D0D0D0",
            text_color="#FFFFFF" if is_active else "#555",
        )

    def _get_filter_values(self, col: str) -> list[str]:
        """获取某列在当前其他筛选下的可选值（联动）。"""
        if self.source_df is None or col not in self.source_df.columns:
            return []
        df = self._apply_renewed_filter(self.source_df)
        df = self._apply_year_filter(df)
        df = self._apply_column_filters(df, exclude_col=col)
        if df is None or df.empty:
            return []
        vals = df[col].dropna().astype(str).unique().tolist()
        if df[col].isna().any():
            vals.append("（空）")
        return sorted(set(vals), key=lambda x: (x == "（空）", x))

    def _open_column_filter(self, col: str) -> None:
        """打开列值筛选弹窗。"""
        if self.source_df is None or self.source_df.empty:
            return
        all_values = self._get_filter_values(col)
        if not all_values:
            return
        selected = self.active_filters.get(col, set(all_values))
        if not selected:
            selected = set(all_values)
        ColumnFilterPopup(
            parent=self.frame,
            col_name=str(col).replace("*", "").strip(),
            all_values=all_values,
            selected=selected,
            on_apply=lambda _, sel: self._on_column_filter_apply(col, sel),
        )

    def _on_column_filter_apply(self, col: str, selected: set[str]) -> None:
        """列值筛选回调。"""
        all_values = set(self._get_filter_values(col))
        selected = {str(s) for s in selected}
        if not selected or selected == all_values:
            self.active_filters.pop(col, None)
        else:
            self.active_filters[col] = selected
        self._refresh_filter_buttons()
        self._fill_tree()

    # ── 续保明细 ──────────────────────────────────────────────


    def _open_renewal_detail(self) -> None:
        """打开续保明细管理弹窗。"""
        self._load_renewal_details()

        # 数据列表直接来自 _renewal_details
        details = list(self._renewal_details)

        win = ctk.CTkToplevel(self.frame)
        win.title("续保明细管理")
        win.geometry("750x480")
        win.resizable(True, True)
        win.minsize(600, 350)
        win.transient(self.frame)
        win.grab_set()
        center_window(win, 750, 480)

        # 表格
        table_frame = ctk.CTkFrame(win, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 4))

        dt = ttk.Treeview(
            table_frame,
            columns=("#", "续保合同号", "关联老合同", "客户名称"),
            show="headings", height=10,
        )
        dt.heading("#", text="#", anchor="center")
        dt.column("#", anchor="center", width=50, minwidth=50, stretch=False)
        dt.heading("续保合同号", text="续保合同号", anchor="center")
        dt.column("续保合同号", anchor="center", width=200, minwidth=130, stretch=True)
        dt.heading("关联老合同", text="关联老合同", anchor="center")
        dt.column("关联老合同", anchor="center", width=200, minwidth=130, stretch=True)
        dt.heading("客户名称", text="客户名称", anchor="center")
        dt.column("客户名称", anchor="center", width=200, minwidth=130, stretch=True)

        dt.tag_configure("odd", background="#F4F4F5")
        dt.tag_configure("even", background="#FCFCFC")

        def _refresh_table():
            dt.delete(*dt.get_children())
            for i, (old, new, cust) in enumerate(details, 1):
                tag = "odd" if i % 2 == 1 else "even"
                dt.insert("", tk.END, values=(str(i), new, old, cust), tags=(tag,))

        _refresh_table()

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=dt.yview)
        dt.configure(yscrollcommand=vsb.set)
        dt.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # 按钮栏
        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=12, pady=(4, 12))

        def _add():
            dlg = ctk.CTkToplevel(win)
            dlg.title("新增续保明细")
            dlg.geometry("420x280")
            dlg.resizable(False, False)
            dlg.transient(win)
            dlg.grab_set()
            center_window(dlg, 420, 280)

            f = ctk.CTkFrame(dlg, fg_color="transparent")
            f.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

            ctk.CTkLabel(f, text="续保合同号:", font=FONT_MAIN).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=(8, 4))
            new_var = tk.StringVar()
            ctk.CTkEntry(f, textvariable=new_var, width=240).grid(row=0, column=1, sticky="w", pady=(8, 4))

            ctk.CTkLabel(f, text="关联老合同:", font=FONT_MAIN).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
            old_var = tk.StringVar()
            ctk.CTkEntry(f, textvariable=old_var, width=240).grid(row=1, column=1, sticky="w", pady=4)

            ctk.CTkLabel(f, text="客户名称:", font=FONT_MAIN).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
            cust_var = tk.StringVar()
            ctk.CTkEntry(f, textvariable=cust_var, width=240).grid(row=2, column=1, sticky="w", pady=4)

            def _save():
                o = old_var.get().strip()
                n = new_var.get().strip()
                c = cust_var.get().strip()
                if not n:
                    return
                if not o:
                    o = n  # 无老合同时用续保合同号做主键
                # 一对多：老合同号重复时仍追加为新行
                details.append((o, n, c))
                _refresh_table()
                dlg.destroy()

            ctk.CTkButton(
                dlg, text="保存", command=_save,
                font=FONT_MAIN, width=80, height=30,
                fg_color="#1F6AA5", hover_color="#155485", corner_radius=6,
            ).pack(pady=(12, 0))

        def _edit():
            sel = dt.selection()
            if not sel:
                messagebox.showwarning("提示", "请先选择一条记录", parent=win)
                return
            idx = int(dt.item(sel[0], "values")[0]) - 1
            old_contract, new_contract, cust_name = details[idx]

            dlg = ctk.CTkToplevel(win)
            dlg.title("编辑续保明细")
            dlg.geometry("420x280")
            dlg.resizable(False, False)
            dlg.transient(win)
            dlg.grab_set()
            center_window(dlg, 420, 280)

            f = ctk.CTkFrame(dlg, fg_color="transparent")
            f.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

            ctk.CTkLabel(f, text="续保合同号:", font=FONT_MAIN).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=(8, 4))
            new_var = tk.StringVar(value=new_contract)
            ctk.CTkEntry(f, textvariable=new_var, width=240).grid(row=0, column=1, sticky="w", pady=(8, 4))

            ctk.CTkLabel(f, text="关联老合同:", font=FONT_MAIN).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
            old_var = tk.StringVar(value=old_contract)
            ctk.CTkEntry(f, textvariable=old_var, width=240).grid(row=1, column=1, sticky="w", pady=4)

            ctk.CTkLabel(f, text="客户名称:", font=FONT_MAIN).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
            cust_var = tk.StringVar(value=cust_name)
            ctk.CTkEntry(f, textvariable=cust_var, width=240).grid(row=2, column=1, sticky="w", pady=4)

            def _save():
                details[idx] = (old_var.get().strip(), new_var.get().strip(), cust_var.get().strip())
                _refresh_table()
                dlg.destroy()

            ctk.CTkButton(
                dlg, text="保存", command=_save,
                font=FONT_MAIN, width=80, height=30,
                fg_color="#1F6AA5", hover_color="#155485", corner_radius=6,
            ).pack(pady=(12, 0))

        def _delete():
            sel = dt.selection()
            if not sel:
                messagebox.showwarning("提示", "请先选择一条记录", parent=win)
                return
            idx = int(dt.item(sel[0], "values")[0]) - 1
            old_c, new_c, _ = details[idx]
            if not messagebox.askyesno("确认删除", f"确定要删除续保明细？\n\n续保合同号: {new_c}\n关联老合同: {old_c}", parent=win):
                return
            details.pop(idx)
            _refresh_table()

        def _save_and_close():
            self._renewal_details = list(details)
            self._save_renewal_details()
            self._recalculate_renewal_columns()
            self._fill_tree()
            win.destroy()

        ctk.CTkButton(
            btn_frame, text="新增", command=_add,
            font=FONT_SMALL, width=70, height=28,
            fg_color="#1F6AA5", hover_color="#155485", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="编辑", command=_edit,
            font=FONT_SMALL, width=70, height=28,
            fg_color="#E0E0E0", hover_color="#D0D0D0", text_color="#333", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="删除", command=_delete,
            font=FONT_SMALL, width=70, height=28,
            fg_color="#C0392B", hover_color="#A93226", corner_radius=6,
        ).pack(side=tk.LEFT)

        win.protocol("WM_DELETE_WINDOW", _save_and_close)

    # ── 续保明细 Excel 缓存 ──────────────────────────────────

    def _load_renewal_details(self) -> None:
        """从 Excel 文件加载续保明细（支持一对多）。"""
        self._renewal_details.clear()
        try:
            if os.path.exists(RENEWAL_FILE):
                df = pd.read_excel(RENEWAL_FILE)
                for _, row in df.iterrows():
                    old = str(row.get("关联老合同", "")).strip()
                    new = str(row.get("续保合同号", "")).strip()
                    cust = str(row.get("客户名称", "")).strip() if "客户名称" in df.columns else ""
                    if old and new:
                        self._renewal_details.append((old, new, cust))
        except Exception as e:
            log_error(f"加载续保明细失败: {e}")

    def _save_renewal_details(self) -> None:
        """保存续保明细到 Excel 文件。"""
        try:
            df = pd.DataFrame([
                {"关联老合同": old, "续保合同号": new, "客户名称": cust}
                for old, new, cust in self._renewal_details
            ])
            df.to_excel(RENEWAL_FILE, index=False)
            log_info(f"续保明细已保存: {len(df)} 条")
        except Exception as e:
            log_error(f"保存续保明细失败: {e}")

    def _is_contract_renewed(self, contract: str, customer: str, expiry_year: str = "") -> bool:
        """判断合同是否已续保：合同编码命中续保明细，且客户名称一致，且续保合同年份等于过保年份。"""
        if not contract:
            return False
        for old, n, cust in self._renewal_details:
            if old != contract:
                continue
            # 年份匹配：续保合同年份必须等于过保年份
            if expiry_year:
                renewal_year = extract_contract_year(n)
                if renewal_year is None or str(renewal_year) != expiry_year:
                    continue
            map_cust = cust.strip() if cust else ""
            if not map_cust:
                # 续保明细中无客户名称（历史数据），仅按合同编码匹配
                return True
            if map_cust == customer:
                return True
        return False

    def _recalculate_renewal_columns(self) -> None:
        """根据当前续保明细重新计算 source_df 中的维保合同和维保金额列。"""
        if self.source_df is None or self.source_df.empty:
            return
        # 构建 {旧合同: [续保合同列表]}
        renewal_lookup: dict[str, list[str]] = {}
        for old, new, _ in self._renewal_details:
            renewal_lookup.setdefault(old, []).append(new)
        self.source_df["维保合同"] = self.source_df["合同编码"].apply(
            lambda c: ", ".join(renewal_lookup.get(c, [])) if c else ""
        )
        # 维保金额：对每条续保合同分别查金额后求和
        def _sum_amount(codes_str: str) -> str:
            if not codes_str:
                return ""
            total = 0.0
            for code in codes_str.split(", "):
                amt = self._lookup_main_amount(code)
                if amt:
                    try:
                        total += float(amt.replace(",", ""))
                    except (ValueError, TypeError):
                        pass
            return f"{total:,.2f}" if total else ""
        self.source_df["维保金额"] = self.source_df["维保合同"].apply(_sum_amount)

    # ── 大礼包渠道标记 ───────────────────────────────────────

    def _load_gift_channels(self) -> None:
        """从 Excel 文件加载大礼包渠道名称。"""
        self._gift_channels.clear()
        try:
            if os.path.exists(GIFT_FILE):
                df = pd.read_excel(GIFT_FILE)
                for _, row in df.iterrows():
                    name = str(row.get("渠道名称", "")).strip()
                    if name:
                        self._gift_channels.add(name)
        except Exception as e:
            log_error(f"加载大礼包渠道失败: {e}")
        self._update_gift_btn()

    def _update_gift_btn(self) -> None:
        """更新大礼包按钮文字，显示已加载渠道数量。"""
        count = len(self._gift_channels)
        self._gift_btn.configure(
            text=f"大礼包标记({count})" if count else "大礼包标记"
        )

    def _save_gift_channels(self) -> None:
        """保存大礼包渠道名称到 Excel 文件。"""
        try:
            df = pd.DataFrame(
                sorted(self._gift_channels),
                columns=["渠道名称"],
            )
            df.to_excel(GIFT_FILE, index=False)
            log_info(f"大礼包渠道已保存: {len(df)} 条")
        except Exception as e:
            log_error(f"保存大礼包渠道失败: {e}")

    def _open_gift_channel_manager(self) -> None:
        """打开大礼包渠道管理弹窗。"""
        self._load_gift_channels()
        channels = sorted(self._gift_channels)

        win = ctk.CTkToplevel(self.frame)
        win.title("大礼包渠道标记")
        win.geometry("480x520")
        win.resizable(True, True)
        win.minsize(400, 350)
        win.transient(self.frame)
        win.grab_set()
        center_window(win, 480, 520)

        table_frame = ctk.CTkFrame(win, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 4))

        dt = ttk.Treeview(
            table_frame,
            columns=("#", "渠道名称"),
            show="headings", height=12,
        )
        dt.heading("#", text="#", anchor="center")
        dt.column("#", anchor="center", width=50, minwidth=50, stretch=False)
        dt.heading("渠道名称", text="渠道名称", anchor="center")
        dt.column("渠道名称", anchor="w", width=350, minwidth=200, stretch=True)

        dt.tag_configure("odd", background="#F4F4F5")
        dt.tag_configure("even", background="#FCFCFC")

        def _refresh_table():
            dt.delete(*dt.get_children())
            for i, name in enumerate(channels, 1):
                tag = "odd" if i % 2 == 1 else "even"
                dt.insert("", tk.END, values=(str(i), name), tags=(tag,))

        _refresh_table()

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=dt.yview)
        dt.configure(yscrollcommand=vsb.set)
        dt.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=12, pady=(4, 12))

        def _add():
            dlg = ctk.CTkToplevel(win)
            dlg.title("新增渠道")
            dlg.geometry("400x150")
            dlg.resizable(False, False)
            dlg.transient(win)
            dlg.grab_set()
            center_window(dlg, 400, 150)

            f = ctk.CTkFrame(dlg, fg_color="transparent")
            f.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

            ctk.CTkLabel(f, text="渠道名称:", font=FONT_MAIN).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=(8, 4))
            name_var = tk.StringVar()
            entry = ctk.CTkEntry(f, textvariable=name_var, width=260)
            entry.grid(row=0, column=1, sticky="w", pady=(8, 4))
            entry.focus()

            def _save():
                name = name_var.get().strip()
                if not name:
                    messagebox.showwarning("提示", "渠道名称不能为空", parent=dlg)
                    return
                if name in channels:
                    messagebox.showwarning("提示", "该渠道名称已存在", parent=dlg)
                    return
                channels.append(name)
                channels.sort()
                _refresh_table()
                dlg.destroy()

            ctk.CTkButton(
                dlg, text="保存", command=_save,
                font=FONT_MAIN, width=80, height=30,
                fg_color="#1F6AA5", hover_color="#155485", corner_radius=6,
            ).pack(pady=(12, 0))

        def _edit():
            sel = dt.selection()
            if not sel:
                messagebox.showwarning("提示", "请先选择一条记录", parent=win)
                return
            idx = int(dt.item(sel[0], "values")[0]) - 1
            old_name = channels[idx]

            dlg = ctk.CTkToplevel(win)
            dlg.title("编辑渠道")
            dlg.geometry("400x150")
            dlg.resizable(False, False)
            dlg.transient(win)
            dlg.grab_set()
            center_window(dlg, 400, 150)

            f = ctk.CTkFrame(dlg, fg_color="transparent")
            f.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

            ctk.CTkLabel(f, text="渠道名称:", font=FONT_MAIN).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=(8, 4))
            name_var = tk.StringVar(value=old_name)
            entry = ctk.CTkEntry(f, textvariable=name_var, width=260)
            entry.grid(row=0, column=1, sticky="w", pady=(8, 4))
            entry.focus()

            def _save():
                name = name_var.get().strip()
                if not name:
                    messagebox.showwarning("提示", "渠道名称不能为空", parent=dlg)
                    return
                if name != old_name and name in channels:
                    messagebox.showwarning("提示", "该渠道名称已存在", parent=dlg)
                    return
                channels[idx] = name
                channels.sort()
                _refresh_table()
                dlg.destroy()

            ctk.CTkButton(
                dlg, text="保存", command=_save,
                font=FONT_MAIN, width=80, height=30,
                fg_color="#1F6AA5", hover_color="#155485", corner_radius=6,
            ).pack(pady=(12, 0))

        def _delete():
            sel = dt.selection()
            if not sel:
                messagebox.showwarning("提示", "请先选择一条记录", parent=win)
                return
            idx = int(dt.item(sel[0], "values")[0]) - 1
            name = channels[idx]
            if not messagebox.askyesno("确认删除", f"确定要删除渠道？\n\n渠道名称: {name}", parent=win):
                return
            channels.pop(idx)
            _refresh_table()

        def _save_and_close():
            self._gift_channels = set(channels)
            self._save_gift_channels()
            self._update_gift_btn()
            self._fill_tree()
            win.destroy()

        ctk.CTkButton(
            btn_frame, text="新增", command=_add,
            font=FONT_SMALL, width=70, height=28,
            fg_color="#1F6AA5", hover_color="#155485", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="编辑", command=_edit,
            font=FONT_SMALL, width=70, height=28,
            fg_color="#E0E0E0", hover_color="#D0D0D0", text_color="#333", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="删除", command=_delete,
            font=FONT_SMALL, width=70, height=28,
            fg_color="#C0392B", hover_color="#A93226", corner_radius=6,
        ).pack(side=tk.LEFT)

        win.protocol("WM_DELETE_WINDOW", _save_and_close)

    # ── 导出 ─────────────────────────────────────────────────

    def _export_csv(self) -> None:
        """导出当前表格数据。"""
        df = self.source_df
        if df is None or df.empty:
            messagebox.showwarning("提示", "没有数据可导出", parent=self.frame)
            return
        export_df = self._apply_filters(df)
        # 添加续保合同号列（一对多：逗号合并）
        renewal_lookup: dict[str, list[str]] = {}
        for old, new, _ in self._renewal_details:
            renewal_lookup.setdefault(old, []).append(new)
        export_df["续保合同号"] = export_df["合同编码"].apply(
            lambda c: ", ".join(renewal_lookup.get(c, [])) if c in renewal_lookup else ""
        )
        export_to_csv(export_df, self.frame, "过保数据分析.csv")

    # ── 数据刷新 ──────────────────────────────────────────────

    def refresh(self) -> None:
        """外部调用：Tab3 数据变化时刷新（后台线程处理，避免阻塞 UI）。"""
        if self.expiry_tab.source_df is None:
            self.source_df = None
            self._set_tree_header_visible(False)
            return
        if getattr(self, "_loading", False):
            return
        self._loading = True
        self._hint_label.configure(text="正在分析过保数据...")
        self._result_df: pd.DataFrame | None = None
        self._load_error: str | None = None

        # 主线程预先加载续保明细快照，避免线程竞争
        self._load_renewal_details()
        renewal_snapshot = list(self._renewal_details)

        expiry_df = self.expiry_tab.source_df

        def worker():
            try:
                self._result_df = self._process_data(expiry_df.copy(), renewal_snapshot)
            except Exception as e:
                log_error(f"过保数据分析失败: {e}")
                self._load_error = str(e)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        self.frame.after(100, self._poll_result, thread)

    def _poll_result(self, thread: threading.Thread) -> None:
        """轮询后台线程，完成后更新 UI。"""
        if thread.is_alive():
            self.frame.after(100, self._poll_result, thread)
            return
        self._loading = False
        if self._load_error:
            self._hint_label.configure(text=f"分析失败: {self._load_error}")
            return
        if self._result_df is not None:
            self.source_df = self._result_df
            self._load_renewal_details()
            self._load_gift_channels()
            self._set_tree_header_visible(True)
            self._show_filter_bar()
            self._fill_tree()

    def _process_data(self, expiry_df: pd.DataFrame, renewal_snapshot: list) -> pd.DataFrame:
        """后台线程：处理 Tab3 数据，返回整理后的 DataFrame。"""
        df = expiry_df.copy()

        contract_col, gift_col, enduser_col, expiry_col, intent_col, reason_col, sales_col, product_amount_col = self._find_columns(df)
        if contract_col is None:
            raise ValueError("未找到合同编号列")

        df["_type"] = df[contract_col].apply(classify_contract)
        df = df[df["_type"] == "P"].copy()
        if df.empty:
            raise ValueError("过保数据中无 P 类合同")

        df["最终客户名称"] = df.apply(
            lambda r: self._resolve_customer(r, gift_col, enduser_col), axis=1
        )

        # 负责销售映射：{最终客户名称: 首次匹配的销售跟踪人}
        sales_map: dict[str, str] = {}
        if sales_col:
            for _, r in df.iterrows():
                cust = str(r["最终客户名称"]).strip()
                if not cust or cust in sales_map:
                    continue
                v = r.get(sales_col, "")
                if pd.notna(v) and str(v).strip():
                    sales_map[cust] = str(v).strip()

        # 合同金额：从 Tab3 数据对 (合同编码, 最终客户名称) 的"产品金额"求和
        # 客户名称匹配规则：渠道大礼包最终客户优先（与 _resolve_customer 一致）
        contract_amount_map: dict[tuple, float] = {}
        if product_amount_col:
            for _, r in df.iterrows():
                code = str(r[contract_col]).strip()
                cust = str(r["最终客户名称"]).strip()
                if not code or not cust:
                    continue
                key = (code, cust)
                try:
                    amt = float(r[product_amount_col]) if pd.notna(r[product_amount_col]) else 0.0
                except (TypeError, ValueError):
                    amt = 0.0
                contract_amount_map[key] = contract_amount_map.get(key, 0.0) + amt

        result = pd.DataFrame()
        result["最终客户名称"] = df["最终客户名称"]
        # 保留原始"最终客户"字段，用于大礼包渠道碰撞（不经 _resolve_customer 处理）
        if enduser_col:
            result["_原始最终客户"] = df[enduser_col].astype(str).str.strip()
        else:
            result["_原始最终客户"] = df["最终客户名称"]
        result["合同编码"] = df[contract_col].astype(str).str.strip()
        result["过保年份"] = self._format_year(df[expiry_col]) if expiry_col else ""
        result["*客户意向"] = df[intent_col] if intent_col else ""
        result["不续保原因"] = df[reason_col] if reason_col else ""

        # 方案 A：按 (最终客户名称, 合同编码) 合并，取最新过保年份
        def _first_non_empty(series):
            for v in series:
                if pd.notna(v) and str(v).strip():
                    return v
            return ""

        result = result.sort_values(
            ["最终客户名称", "合同编码", "过保年份"], ascending=[True, True, False]
        )
        result = result.groupby(
            ["最终客户名称", "合同编码"], as_index=False,
        ).agg({
            "_原始最终客户": "first",
            "过保年份": "first",           # 取最新年份（已按降序排列）
            "*客户意向": _first_non_empty,
            "不续保原因": _first_non_empty,
        })

        # 合同金额：从 Tab3 汇总匹配 (合同编码, 最终客户名称) 的产品金额
        def _lookup_amount(row):
            key = (str(row["合同编码"]).strip(), str(row["最终客户名称"]).strip())
            total = contract_amount_map.get(key, 0.0)
            return f"{total:,.2f}" if total else ""
        result["合同金额"] = result.apply(_lookup_amount, axis=1)

        # 负责销售：按最终客户名称取首次匹配的销售跟踪人
        result["负责销售"] = result["最终客户名称"].map(sales_map).fillna("")

        # 维保合同（从续保明细查 续保合同号，支持一对多，逗号合并）
        renewal_lookup: dict[str, list[str]] = {}
        for old, new, _ in renewal_snapshot:
            renewal_lookup.setdefault(old, []).append(new)
        result["维保合同"] = result["合同编码"].apply(
            lambda c: ", ".join(renewal_lookup.get(c, [])) if c in renewal_lookup else ""
        )
        # 维保金额：对每条续保合同分别查金额后求和
        def _sum_amount(codes_str: str) -> str:
            if not codes_str:
                return ""
            total = 0.0
            for code in codes_str.split(", "):
                amt = self._lookup_main_amount(code)
                if amt:
                    try:
                        total += float(amt.replace(",", ""))
                    except (ValueError, TypeError):
                        pass
            return f"{total:,.2f}" if total else ""
        result["维保金额"] = result["维保合同"].apply(_sum_amount)

        result["_year"] = result["合同编码"].apply(extract_contract_year)
        result["_year"] = result["_year"].fillna(0).astype(int)
        result = result.sort_values(
            ["_year", "过保年份", "合同编码"], ascending=[False, False, True]
        ).reset_index(drop=True)
        result = result.drop(columns=["_year"])
        return result



    def _lookup_main_amount(self, wb_contract: str) -> str:
        """在主合同文件中查找 合同编号* == wb_contract 的合同金额。"""
        if not wb_contract:
            return ""
        df = self.main_df_provider() if self.main_df_provider else None
        if df is None or df.empty or "合同编号*" not in df.columns:
            return ""
        mask = df["合同编号*"].astype(str).str.strip() == wb_contract
        if not mask.any():
            return ""
        amt = df.loc[mask, "合同金额（元）*"].iloc[0]
        if pd.isna(amt):
            return ""
        return f"{float(amt):,.2f}"
