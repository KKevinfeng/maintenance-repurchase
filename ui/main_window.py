"""主窗口 —— 文件选择 / Tab 栏 / 状态栏 / 数据加载"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import customtkinter as ctk

from ui.styles import (
    FONT_MAIN, FONT_SMALL, FONT_BOLD, FONT_TITLE,
    setup_treeview_style,
)
from ui.logger import log_error, log_info
from ui.log_view import LogViewer
from ui.base_tab import BaseTab
from ui.tab_customer_total import CustomerTotalTab
from ui.tab_customer_category import CustomerCategoryTab
from ui.tab_expiry_stats import ExpiryStatsTab
from ui.tab_product_sales import ProductSalesTab
from ui.detail_window import CustomerDetailWindow
from ui.starred_cache import StarredCache
from ui.starred_view import StarredView
from ui.starred_input_dialog import StarredInputDialog
from ui.progress_popup import ProgressPopup
from utils import classify_contract, center_window


class MaintenanceApp:
    """合同数据处理工具主界面"""

    REQUIRED_COL_KEYWORDS = [
        "合同编号*",
        "产品名称型号",
        "最终客户名称",
        "合同金额（元）*",
    ]

    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("合同数据处理工具")
        self.root.geometry("1100x700")
        self.root.minsize(900, 500)
        center_window(self.root, 1100, 700)

        self.df: pd.DataFrame | None = None
        self.tabs: list[BaseTab] = []
        self.starred_cache = StarredCache()

        setup_treeview_style(self.root)

        self._build_file_selector()
        self._build_tab_bar()
        self._build_statusbar()

    # ── 文件选择区域 ──────────────────────────────────────────

    def _build_file_selector(self):
        """构建顶部文件选择栏。"""
        outer = ctk.CTkFrame(self.root, fg_color="transparent")
        outer.pack(fill=tk.X, padx=12, pady=(12, 0))

        card = ctk.CTkFrame(outer, corner_radius=10)
        card.pack(fill=tk.X, ipady=6)

        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill=tk.X, padx=16, pady=(10, 4))

        ctk.CTkLabel(
            title_row, text="数据文件", font=FONT_TITLE,
            text_color="#1F6AA5",
        ).pack(side=tk.LEFT)

        ctk.CTkButton(
            title_row, text="关于", command=self._show_about,
            font=FONT_SMALL, width=50, height=24,
            fg_color="#1F6AA5", hover_color="#155485",
            text_color="white", corner_radius=6,
        ).pack(side=tk.RIGHT)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill=tk.X, padx=16, pady=(0, 6))

        ctk.CTkLabel(
            row, text="路径:", font=FONT_MAIN, width=40,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.file_path_var = tk.StringVar()
        ctk.CTkEntry(
            row, textvariable=self.file_path_var, font=FONT_MAIN, height=34,
            corner_radius=6, border_width=1,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill=tk.X, padx=16, pady=(0, 10))

        ctk.CTkButton(
            btn_row, text="浏览...", command=self._browse_file,
            font=FONT_MAIN, width=80, height=32,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="查看重点客户", command=self._view_starred,
            font=FONT_MAIN, width=120, height=32,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="手动录入重点客户", command=self._input_starred,
            font=FONT_MAIN, width=140, height=32,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="查看报错日志", command=self._view_error_log,
            font=FONT_MAIN, width=120, height=32,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="查看运行日志", command=self._view_run_log,
            font=FONT_MAIN, width=120, height=32,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0", corner_radius=6,
        ).pack(side=tk.LEFT)

    # ── Tab 栏 + 内容区 ──────────────────────────────────────

    def _build_tab_bar(self):
        """构建靠左对齐的 Tab 栏和内容区域。"""
        outer = ctk.CTkFrame(self.root, fg_color="transparent")
        outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 8))

        # Tab 栏
        tab_bar = ctk.CTkFrame(outer, fg_color="transparent")
        tab_bar.pack(fill=tk.X, anchor="w", pady=(0, 4))

        self.tab_names = ["客户总金额统计", "客户分类金额统计", "过保情况统计", "产品销量统计"]
        # Tab 栏 - 自定义按钮实现，支持选中白色文字/未选中黑色文字
        self.tab_buttons: dict[str, ctk.CTkButton] = {}
        btn_frame = ctk.CTkFrame(tab_bar, fg_color="transparent")
        btn_frame.pack(anchor="w")

        for name in self.tab_names:
            btn = ctk.CTkButton(
                btn_frame,
                text=name,
                command=lambda n=name: self._switch_tab(n),
                font=FONT_MAIN,
                width=140,
                height=32,
                corner_radius=8,
                border_width=0,
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.tab_buttons[name] = btn

        self._update_tab_button_style(self.tab_names[0])

        # 内容区域
        self.tab_content = ctk.CTkFrame(outer, corner_radius=10)
        self.tab_content.pack(fill=tk.BOTH, expand=True)

        # 创建四个 Tab
        self.tab_customer_total = CustomerTotalTab(
            self.tab_content,
            on_double_click=self._on_tab_customer_total_double_click,
            on_star_toggle=self._on_star_toggle,
            get_starred_names=self._get_starred_names,
        )
        self.tab_customer_category = CustomerCategoryTab(
            self.tab_content,
            on_double_click=self._on_tab_customer_category_double_click,
        )
        self.tab_expiry_stats = ExpiryStatsTab(self.tab_content, starred_cache=self.starred_cache)
        self.tab_product_sales = ProductSalesTab(
            self.tab_content,
            on_double_click=None,
            on_data_change=self._on_product_sales_data_change,
        )

        self.tabs = [
            self.tab_customer_total,
            self.tab_customer_category,
            self.tab_product_sales,
        ]  # 仅包含使用共享 df 的 Tab（不含过保情况统计）

        for tab in self.tabs:
            tab.build()
        self.tab_expiry_stats.build()  # 过保情况统计独立构建

        self._switch_tab(self.tab_names[0])

    def _switch_tab(self, name: str):
        """切换 Tab 页并更新按钮样式。"""
        log_info(f"切换 Tab: {name}")
        for tab in self.tabs:
            tab.frame.pack_forget()
        self.tab_expiry_stats.frame.pack_forget()
        if name == self.tab_names[0]:
            self.tab_customer_total.frame.pack(fill=tk.BOTH, expand=True)
        elif name == self.tab_names[1]:
            self.tab_customer_category.frame.pack(fill=tk.BOTH, expand=True)
        elif name == self.tab_names[2]:
            self.tab_expiry_stats.frame.pack(fill=tk.BOTH, expand=True)
        elif name == self.tab_names[3]:
            self.tab_product_sales.frame.pack(fill=tk.BOTH, expand=True)
        self._update_tab_button_style(name)

    def _update_tab_button_style(self, active_name: str):
        """高亮当前 Tab 按钮：选中白字蓝底，未选中黑字灰底。"""
        for name, btn in self.tab_buttons.items():
            if name == active_name:
                btn.configure(
                    fg_color="#1F6AA5",
                    hover_color="#144870",
                    text_color="#FFFFFF",
                )
            else:
                btn.configure(
                    fg_color="#E0E0E0",
                    hover_color="#D0D0D0",
                    text_color="#333333",
                )

    # ── 底部状态栏 ────────────────────────────────────────────

    def _build_statusbar(self):
        """底部状态栏。"""
        bar = ctk.CTkFrame(self.root, corner_radius=0, height=36, fg_color="#E8F0FE")
        bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_var = tk.StringVar(value="就绪 — 请选择 Excel 文件")
        ctk.CTkLabel(
            bar, textvariable=self.status_var,
            font=FONT_MAIN, text_color="#1F6AA5",
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, padx=16, pady=4)

    # ── 文件操作 ──────────────────────────────────────────────

    def _browse_file(self):
        """打开文件对话框，选择后自动加载。"""
        filepath = filedialog.askopenfilename(
            title="选择合同数据文件",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")],
        )
        if filepath:
            self.file_path_var.set(filepath)
            self._load_file()

    def _view_error_log(self):
        """打开报错日志查看窗口。"""
        LogViewer.show_error(self.root)

    def _view_run_log(self):
        """打开运行日志查看窗口。"""
        LogViewer.show_run(self.root)

    def _show_about(self):
        """显示关于弹窗。"""
        win = ctk.CTkToplevel(self.root)
        win.title("关于")
        win.geometry("520x220")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        center_window(win, 520, 220)

        frame = ctk.CTkFrame(win, fg_color="transparent")
        frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            frame, text="合同数据处理工具",
            font=FONT_TITLE, text_color="#1F6AA5",
        ).pack(pady=(0, 16))

        info_lines = [
            "版本信息：2.1.3",
            "制作人：Kevin",
            "源代码：https://github.com/KKevinfeng/maintenance-repurchase.git",
            "主页：https://kkevinfeng.github.io/",
        ]
        for line in info_lines:
            ctk.CTkLabel(
                frame, text=line, font=FONT_MAIN,
                anchor="w", justify="left", wraplength=460,
            ).pack(anchor="w", pady=(0, 6), fill=tk.X)

    def _view_starred(self):
        """打开重点客户弹窗，操作后自动同步主界面标星。"""
        def on_cache_changed():
            if self.df is not None:
                self._refresh_all_tabs()
                self._check_starred_collision()

        StarredView.show(self.root, self.starred_cache, on_changed=on_cache_changed)

    def _input_starred(self):
        """打开手动录入重点客户弹窗。"""
        def on_done(count: int):
            if count > 0:
                self.status_var.set(f"已新增 {count} 个重点客户")
                # 如果已有数据，重新计算所有 Tab 以刷新标星显示
                if self.df is not None:
                    self._refresh_all_tabs()
                    self.status_var.set(
                        f"已新增 {count} 个重点客户 — 共 {len(self.df)} 行合同数据"
                    )
                    # 触发标星碰撞检测
                    self._check_starred_collision()

        StarredInputDialog(self.root, self.starred_cache, on_done=on_done)

    def _on_star_toggle(self, customer_name: str, is_starred: bool):
        """标星切换回调：更新缓存。"""
        if is_starred:
            self.starred_cache.add(customer_name)
            log_info(f"标星客户: {customer_name}")
        else:
            self.starred_cache.remove(customer_name)
            log_info(f"取消标星客户: {customer_name}")

    def _get_starred_names(self) -> list[str]:
        """供 Tab 获取当前标星客户名称列表。"""
        return self.starred_cache.get_all()

    def _load_file(self):
        """后台线程加载 Excel 文件并刷新所有 Tab，弹窗显示进度。"""
        filepath = self.file_path_var.get().strip()
        if not filepath:
            messagebox.showwarning("提示", "请先选择 Excel 文件")
            return

        if getattr(self, "_loading", False):
            return
        self._loading = True

        self._load_error: str | None = None
        self._load_df: pd.DataFrame | None = None
        self._tab_results: list | None = None
        self._load_ticks = 0

        popup = ProgressPopup(self.root, title="正在导入合同数据...")

        def worker():
            try:
                raw_df = pd.read_excel(filepath, header=1)
                col_map: dict[str, str] = {}
                missing: list[str] = []
                for keyword in self.REQUIRED_COL_KEYWORDS:
                    found = [c for c in raw_df.columns if keyword in str(c)]
                    if found:
                        col_map[keyword] = found[0]
                    else:
                        missing.append(keyword)

                if missing:
                    missing_text = "、".join(f"【{k}】" for k in missing)
                    self._load_error = f"没有{missing_text}列，请提供正确的文件"
                    log_error(f"文件 {filepath} 缺少必要列：{missing_text}")
                    return

                result_df = raw_df[list(col_map.values())].rename(
                    columns={v: k for k, v in col_map.items()}
                )
                self._load_df = result_df

                log_info(f"数据文件加载成功: {filepath}，共 {len(result_df)} 行")
                results = []
                for i, tab in enumerate(self.tabs):
                    computed = tab.compute_data(result_df)
                    results.append((tab, computed))
                self._tab_results = results
            except FileNotFoundError:
                self._load_error = f"文件不存在：\n{filepath}"
                log_error(f"文件不存在：{filepath}")
            except Exception as e:
                self._load_error = f"加载文件失败：\n{e}"
                log_error(f"加载文件失败：{filepath}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        self.root.after(100, self._poll_load_done, thread, filepath, popup)

    def _poll_load_done(self, thread: threading.Thread, filepath: str, popup: ProgressPopup):
        """轮询后台线程，更新弹窗进度；完成后回到主线程更新 UI。"""
        if thread.is_alive():
            self._load_ticks += 1
            pct = 0.9 * (1 - 0.95 ** self._load_ticks)
            popup.set_progress(pct, f"正在加载数据… {int(pct * 100)}%")
            self.root.after(100, self._poll_load_done, thread, filepath, popup)
            return

        self._loading = False

        if self._load_error:
            popup.close()
            # 延迟弹错误提示，确保进度弹窗已完全销毁
            self.root.after(100, lambda: messagebox.showerror("错误", self._load_error))
            self.status_var.set("就绪 — 请选择 Excel 文件")
            return

        self.df = self._load_df
        popup.set_progress(0.95, "正在刷新界面...")

        for tab, computed in self._tab_results:
            tab.populate(computed)

        popup.close()
        self.status_var.set(f"已加载 {len(self.df)} 行数据 — {filepath}")

        # 延迟触发碰撞检测，确保进度弹窗已完全销毁
        self.root.after(100, self._check_starred_collision)

    def _check_starred_collision(self):
        """检查重点客户缓存表中哪些客户名未在导入数据中命中。"""
        starred = self.starred_cache.get_all()
        if not starred or self.df is None:
            return

        col_names = set(self.df["最终客户名称"].dropna().unique())
        unmatched = [name for name in starred if name not in col_names]
        if not unmatched:
            return

        # 构建提示
        lines = "\n".join(f"  · {name}" for name in unmatched)
        messagebox.showwarning(
            "未碰撞提示",
            f"以下 {len(unmatched)} 个重点客户未在本次导入数据中匹配到：\n\n{lines}\n\n"
            f"如需更新缓存表，请使用「查看重点客户」管理。",
        )

    # ── 数据刷新 ──────────────────────────────────────────────

    def _refresh_all_tabs(self):
        """刷新全部 Tab 数据。"""
        if self.df is None:
            return

        try:
            for tab in self.tabs:
                computed = tab.compute_data(self.df)
                tab.populate(computed)
            log_info(f"数据已刷新 — 共 {len(self.df)} 行合同数据")
            self.status_var.set(f"数据已刷新 — 共 {len(self.df)} 行合同数据")
        except Exception as e:
            log_error("数据处理失败")
            messagebox.showerror("错误", f"数据处理失败：\n{e}")

    def _on_product_sales_data_change(self):
        """产品名称合并规则变化后，仅刷新产品销量 Tab。"""
        if self.df is None:
            return
        try:
            computed = self.tab_product_sales.compute_data(self.df)
            self.tab_product_sales.populate(computed)
            self.tab_content.update_idletasks()
            rule_count = len(self.tab_product_sales.merge_rules)
            self.status_var.set(
                f"产品合并规则已应用（{rule_count} 条）— 共 {len(self.df)} 行合同数据"
            )
            log_info(f"产品合并规则已应用，共 {rule_count} 条")
            self._switch_tab(self.tab_names[3])  # 自动切到产品销量统计页
        except Exception as e:
            log_error("产品合并刷新失败")
            messagebox.showerror("错误", f"刷新产品销量数据失败：\n{e}")

    # ── 双击事件（各 Tab） ────────────────────────────────────

    def _on_tab_customer_total_double_click(self, tree, event):
        """Tab 1 双击：展示客户全部合同。"""
        selection = tree.selection()
        if not selection:
            return
        values = tree.item(selection[0], "values")
        if values:
            self._show_customer_detail(values[2])  # ★ | # | 客户名称 | 金额

    def _on_tab_customer_category_double_click(self, tree, event):
        """Tab 2 双击：按点击的金额列展示对应类型合同。"""
        selection = tree.selection()
        if not selection:
            return
        values = tree.item(selection[0], "values")
        if not values:
            return

        col_id = tree.identify_column(event.x)
        col_index = int(col_id.replace("#", ""))
        customer_name = values[1]

        if col_index == 3:
            contract_type = "M"
        elif col_index == 4:
            contract_type = "P"
        elif col_index == 5:
            contract_type = "S"
        elif col_index == 2:
            self._show_customer_detail(customer_name)
            return
        else:
            return

        type_label = {"M": "维保", "P": "产品", "S": "服务"}[contract_type]
        self._show_customer_detail(customer_name, contract_type=contract_type,
                                   type_label=type_label)

    # ── 客户详情弹窗 ──────────────────────────────────────────

    def _show_customer_detail(
        self,
        customer_name: str,
        contract_type: str | None = None,
        type_label: str = "",
    ):
        """打开客户合同详情窗口。"""
        if self.df is None:
            return

        customer_df = self.df[self.df["最终客户名称"] == customer_name].copy()
        if customer_df.empty:
            messagebox.showinfo("提示", f'未找到客户"{customer_name}"的合同记录')
            return

        if contract_type:
            customer_df["_type"] = customer_df["合同编号*"].apply(classify_contract)
            customer_df = customer_df[customer_df["_type"] == contract_type]
            if customer_df.empty:
                messagebox.showinfo(
                    "提示",
                    f'客户"{customer_name}"没有{type_label}类合同记录',
                )
                return

        if contract_type:
            title_text = f'客户：{customer_name} — {type_label}合同（共 {len(customer_df)} 条）'
        else:
            title_text = f'客户：{customer_name}（共 {len(customer_df)} 条合同）'

        log_info(f"查看客户详情: {customer_name}，共 {len(customer_df)} 条合同")
        CustomerDetailWindow(self.root, customer_df, title_text, customer_name)
