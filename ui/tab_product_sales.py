"""Tab 4：产品销量统计"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import customtkinter as ctk

from ui.base_tab import BaseTab
from data_processor import compute_product_sales, get_product_p_contracts
from ui.merge_dialog import ProductMergeDialog
from ui.logger import log_error, log_info
from utils import center_window, export_to_csv
from ui.styles import FONT_TITLE, FONT_BOLD

RULES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "merge_rules.json")


def _load_rules() -> dict[str, set[str]]:
    """从 JSON 文件加载合并规则。"""
    try:
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {k: set(v) for k, v in raw.items()}
    except Exception as e:
        log_error(f"加载产品合并规则失败: {e}")
    return {}


def _save_rules(rules: dict[str, set[str]]):
    """将合并规则保存到 JSON 文件。"""
    try:
        # 将 set 转为 list 以便 JSON 序列化
        data = {k: sorted(v) for k, v in rules.items()}
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error(f"保存产品合并规则失败: {e}")


class ProductSalesTab(BaseTab):
    """产品销量统计页 —— 展示各产品售卖台数，支持产品名称合并。"""

    def __init__(self, master, on_double_click=None, on_data_change=None):
        super().__init__(
            master=master,
            tab_name="产品销量统计",
            columns=["产品名称", "售卖总台数"],
            on_double_click=on_double_click,
        )
        self.merge_rules: dict[str, set[str]] = _load_rules()
        self._on_data_change = on_data_change  # 合并规则变化时触发的回调

    # ── 构建 UI（在基类基础上添加合并按钮） ──────────────────

    def build(self):
        frame = super().build()

        merge_btn = ctk.CTkButton(
            self._btn_bar,
            text="产品名称合并",
            command=self._open_merge_dialog,
            font=("Microsoft YaHei", 11),
            width=120, height=28,
            corner_radius=6,
            fg_color="#1F6AA5", hover_color="#144870",
        )
        merge_btn.pack(side=tk.LEFT, padx=4, pady=4)

        return frame

    # ── 数据计算（应用合并规则） ──────────────────────────────

    def compute_data(self, raw_df):
        # 缓存原始数据，供后续获取原始产品名称列表
        self._raw_df = raw_df
        return compute_product_sales(raw_df, merge_rules=self.merge_rules or None)

    # ── 合并对话框 ──────────────────────────────────────────

    # ── 双击产品名：显示关联 P 类合同明细 ────────────────────

    def _handle_double_click(self, event):
        """双击产品名称，弹出该产品关联的 P 类合同明细窗口。"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        col_id = self.tree.identify_column(event.x)
        if not col_id:
            return

        # 获取产品名称列（第 3 列，因为 #1=#, #2=产品名称, #3=售卖总台数）
        values = self.tree.item(item, "values")
        if not values or len(values) < 2:
            return
        # values[0] = 序号, values[1] = 产品名称, values[2] = 售卖总台数
        product_name = str(values[1])
        log_info(f"查询产品关联合同: {product_name}")

        if not hasattr(self, "_raw_df") or self._raw_df is None:
            return

        try:
            contract_df = get_product_p_contracts(
                self._raw_df, product_name, merge_rules=self.merge_rules or None
            )
        except Exception as e:
            log_error(f"查询产品关联合同明细失败: {e}")
            messagebox.showerror("错误", f"查询合同明细失败：\n{e}")
            return

        if contract_df.empty:
            messagebox.showinfo("提示", f"未找到与「{product_name}」关联的 P 类合同")
            return

        self._show_contract_detail_window(product_name, contract_df)

    def _show_contract_detail_window(self, product_name: str, contract_df):
        """弹出合同明细窗口（仿照 CustomerDetailWindow 布局）。"""
        self._export_df = contract_df
        self._export_name = product_name

        win = ctk.CTkToplevel(self.frame.winfo_toplevel())
        win.title(f"关联合同明细 — {product_name}")
        win.geometry("1000x650")
        win.minsize(780, 480)
        center_window(win, 1000, 650)
        win.after(100, win.lift)
        self._detail_win = win

        # 标题
        ctk.CTkLabel(
            win,
            text=f"产品「{product_name}」关联的 P 类合同（共 {len(contract_df)} 条）",
            font=FONT_TITLE, text_color="#1F6AA5", anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(12, 4))

        # 表格容器
        table_frame = ctk.CTkFrame(win, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 4))

        columns = list(contract_df.columns)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)

        for col in columns:
            tree.heading(col, text=col, anchor="center")
            tree.column(col, anchor="center", width=self._detail_col_width(col), minwidth=80)

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

        for idx, (_, row) in enumerate(contract_df.iterrows(), 1):
            vals = []
            for col in columns:
                val = row[col]
                if isinstance(val, float):
                    vals.append(f"{val:,.2f}")
                elif isinstance(val, int):
                    vals.append(f"{val:,}")
                else:
                    vals.append(str(val) if not pd.isna(val) else "")
            tag = "odd" if idx % 2 == 1 else "even"
            tree.insert("", tk.END, values=vals, tags=(tag, "center"))

        # 详情文本区域
        detail_text = ctk.CTkTextbox(
            win, height=90, font=("Microsoft YaHei UI", 11),
            wrap="word", corner_radius=6, border_width=1,
        )
        detail_text.pack(fill=tk.BOTH, padx=12, pady=(2, 8))
        detail_text.configure(state="disabled")

        def _on_select(event):
            selection = tree.selection()
            if not selection:
                return
            item = selection[0]
            item_values = tree.item(item, "values")
            detail_text.configure(state="normal")
            detail_text.delete("1.0", tk.END)
            for col, val in zip(columns, item_values):
                detail_text.insert(tk.END, f"{col}：{val}\n")
            detail_text.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", _on_select)

        # 底部按钮栏
        btn_bar = ctk.CTkFrame(win, fg_color="transparent", height=46)
        btn_bar.pack_propagate(False)
        btn_bar.pack(fill=tk.X, padx=12, pady=(0, 12))

        ctk.CTkButton(
            btn_bar, text="导出 CSV", command=self._export_detail_csv,
            font=FONT_BOLD, width=100, height=32, corner_radius=6,
        ).pack(side=tk.RIGHT, padx=(0, 8), pady=6)

        ctk.CTkButton(
            btn_bar, text="关闭", command=win.destroy,
            font=FONT_BOLD, width=80, height=32, corner_radius=6,
        ).pack(side=tk.RIGHT, padx=(0, 8), pady=6)

    def _export_detail_csv(self):
        """导出当前弹窗中的合同明细为 CSV。"""
        df = getattr(self, "_export_df", None)
        if df is None or df.empty:
            messagebox.showwarning("提示", "没有数据可导出")
            return
        name = getattr(self, "_export_name", "产品")
        export_to_csv(df, self._detail_win, f"{name}_合同明细.csv")

    @staticmethod
    def _detail_col_width(col: str) -> int:
        """合同明细窗口的列宽。"""
        if "编号" in col:
            return 200
        if "名称" in col:
            return 240
        if "金额" in col:
            return 160
        return 180

    # ── 合并对话框 ──────────────────────────────────────────

    def _open_merge_dialog(self):
        """打开产品名称合并配置对话框。"""
        if not hasattr(self, "_raw_df") or self._raw_df is None:
            from tkinter import messagebox
            messagebox.showwarning("提示", "请先加载数据文件")
            return

        # 获取原始产品名称列表（未应用合并规则）
        original = compute_product_sales(self._raw_df, merge_rules=None)
        product_names = sorted(original["产品名称"].unique().tolist())

        def on_apply(rules: dict):
            self.merge_rules = {k: set(v) for k, v in rules.items()}
            _save_rules(self.merge_rules)
            # 通知主窗口刷新
            if self._on_data_change:
                self._on_data_change()

        ProductMergeDialog.show(
            self.frame.winfo_toplevel(),
            product_names,
            self.merge_rules,
            on_apply,
        )
