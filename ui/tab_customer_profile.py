"""Tab 6：客户画像展示 — 展示所有客户的重点标记、序号、名称，双击查看详细画像。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
import pandas as pd

from ui.base_tab import BaseTab
from data_processor import compute_customer_total
from utils import classify_contract, parse_product_lines, center_window
from ui.styles import FONT_MAIN, FONT_TITLE, FONT_SMALL, FONT_BOLD


class CustomerProfileTab(BaseTab):
    """客户画像展示页 — 支持重点客户标记展示，点击客户名查看详细画像。"""

    def __init__(self, master, on_double_click=None, get_starred_names=None):
        # 跟 Tab4 一样用 has_star=False，"是否重点客户"作为普通数据列
        super().__init__(
            master=master,
            tab_name="客户画像展示",
            columns=["是否重点客户", "客户名称"],
            on_double_click=on_double_click,
            has_star=False,
            get_starred_names=get_starred_names,
            search_column="客户名称",
        )
        self._raw_df: pd.DataFrame | None = None

    # ── 数据计算 ────────────────────────────────────────────────

    def compute_data(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """计算客户画像数据：按总金额排序，重点客户置顶。"""
        self._raw_df = raw_df.copy()

        totals = compute_customer_total(raw_df)

        starred = set(self._get_starred()) if self._get_starred else set()
        totals["_sort"] = totals["最终客户名称"].apply(lambda n: 0 if n in starred else 1)

        totals = totals.sort_values(
            ["_sort", "合同总金额"], ascending=[True, False]
        ).reset_index(drop=True)

        result = pd.DataFrame()
        result["是否重点客户"] = totals["最终客户名称"].apply(
            lambda n: "重点客户" if n in starred else ""
        )
        result["客户名称"] = totals["最终客户名称"]
        return result

    # ── 双击事件 ───────────────────────────────────────────────

    def _handle_double_click(self, event) -> None:
        """双击客户名称 → 显示客户画像详情弹窗。"""
        tree = self.tree
        if tree is None:
            return
        item = tree.selection()
        if not item:
            return
        values = tree.item(item[0], "values")
        if not values or len(values) < 3:
            return
        # 列顺序：# | 是否重点客户 | 客户名称
        customer_name = str(values[2])
        if not customer_name:
            return
        self._show_profile_detail(customer_name)

    # ── 客户画像详情弹窗 ────────────────────────────────────────

    def _show_profile_detail(self, customer_name: str) -> None:
        """展示单个客户的画像详情窗口。"""
        raw_df = self._raw_df
        if raw_df is None:
            return

        from ui.industry_overrides import get_all as get_overrides

        cust_df = raw_df[raw_df["最终客户名称"] == customer_name].copy()
        if cust_df.empty:
            return

        overrides = get_overrides()
        override = overrides.get(customer_name, {})
        primary = override.get("一级行业", "") or str(
            cust_df["一级行业"].dropna().iloc[0]
        ) if "一级行业" in cust_df.columns and not cust_df["一级行业"].dropna().empty else ""
        secondary = override.get("二级行业", "") or str(
            cust_df["二级行业"].dropna().iloc[0]
        ) if "二级行业" in cust_df.columns and not cust_df["二级行业"].dropna().empty else ""

        total_amount = cust_df["合同金额（元）*"].sum()
        cust_df["合同类型"] = cust_df["合同编号*"].apply(classify_contract)
        p_amount = cust_df[cust_df["合同类型"] == "P"]["合同金额（元）*"].sum()
        m_amount = cust_df[cust_df["合同类型"] == "M"]["合同金额（元）*"].sum()
        s_amount = cust_df[cust_df["合同类型"] == "S"]["合同金额（元）*"].sum()

        product_totals: dict[str, int] = {}
        ps_df = cust_df[cust_df["合同类型"].isin(["P", "S"])]
        for _, r in ps_df.iterrows():
            for prod in parse_product_lines(r["产品名称型号"]):
                name = prod["name"]
                product_totals[name] = product_totals.get(name, 0) + prod["qty"]

        win = ctk.CTkToplevel(self.frame)
        win.title(f"{customer_name} - 客户画像")
        win.geometry("780x600")
        win.resizable(True, True)
        win.minsize(600, 450)
        win.transient(self.frame)
        win.grab_set()
        center_window(win, 780, 600)

        title_frame = ctk.CTkFrame(win, fg_color="transparent")
        title_frame.pack(fill=tk.X, padx=20, pady=(16, 8))
        ctk.CTkLabel(
            title_frame, text=customer_name,
            font=FONT_TITLE, text_color="#1F6AA5",
        ).pack(side=tk.LEFT)

        info_card = ctk.CTkFrame(win, corner_radius=10, fg_color="#F4F6FA")
        info_card.pack(fill=tk.X, padx=16, pady=(4, 12), ipady=8)

        info_grid = ctk.CTkFrame(info_card, fg_color="transparent")
        info_grid.pack(fill=tk.X, padx=16, pady=10)

        row0 = ctk.CTkFrame(info_grid, fg_color="transparent")
        row0.pack(fill=tk.X, pady=(0, 4))
        self._info_label(row0, "一级行业:", primary or "未知", "#333").pack(side=tk.LEFT, padx=(0, 24))
        self._info_label(row0, "二级行业:", secondary or "未知", "#333").pack(side=tk.LEFT)

        row1 = ctk.CTkFrame(info_grid, fg_color="transparent")
        row1.pack(fill=tk.X, pady=(4, 0))
        self._info_label(row1, "下单总额:", f"{total_amount:,.2f} 元", "#1F6AA5").pack(side=tk.LEFT, padx=(0, 24))
        self._info_label(row1, "P 产品:", f"{p_amount:,.2f} 元", "#E67E22").pack(side=tk.LEFT, padx=(0, 16))
        self._info_label(row1, "M 维保:", f"{m_amount:,.2f} 元", "#27AE60").pack(side=tk.LEFT, padx=(0, 16))
        self._info_label(row1, "S 服务:", f"{s_amount:,.2f} 元", "#8E44AD").pack(side=tk.LEFT)

        prod_header = ctk.CTkFrame(win, fg_color="transparent")
        prod_header.pack(fill=tk.X, padx=16, pady=(4, 4))
        ctk.CTkLabel(
            prod_header, text="下单产品清单（P / S 类）",
            font=FONT_BOLD, text_color="#555",
        ).pack(side=tk.LEFT)

        table_frame = ctk.CTkFrame(win, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        ptree = ttk.Treeview(
            table_frame,
            columns=("#", "产品名称", "数量"),
            show="headings",
            height=12,
        )
        ptree.heading("#", text="#", anchor="center")
        ptree.column("#", anchor="center", width=50, minwidth=50, stretch=False)
        ptree.heading("产品名称", text="产品名称", anchor="center")
        ptree.column("产品名称", anchor="center", width=400, minwidth=150, stretch=True)
        ptree.heading("数量", text="数量", anchor="center")
        ptree.column("数量", anchor="center", width=100, minwidth=80, stretch=False)

        ptree.tag_configure("odd", background="#F4F4F5")
        ptree.tag_configure("even", background="#FCFCFC")

        sorted_products = sorted(product_totals.items(), key=lambda x: x[1], reverse=True)
        for pi, (pname, pqty) in enumerate(sorted_products, 1):
            tag = "odd" if pi % 2 == 1 else "even"
            ptree.insert("", tk.END, values=(str(pi), pname, f"{pqty:,}"), tags=(tag,))

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=ptree.yview)
        ptree.configure(yscrollcommand=vsb.set)
        ptree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    @staticmethod
    def _info_label(parent, label_text: str, value_text: str, value_color: str) -> ctk.CTkFrame:
        """创建 标签: 值 的行内组件。"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(row, text=label_text, font=FONT_MAIN, text_color="#888").pack(side=tk.LEFT)
        ctk.CTkLabel(row, text=value_text, font=FONT_BOLD, text_color=value_color).pack(side=tk.LEFT)
        return row
