"""Tkinter UI 模块：界面布局与交互"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd

from data_processor import (
    compute_customer_total,
    compute_customer_category,
    compute_product_sales,
)


class MaintenanceApp:
    """维保复购数据处理程序主界面"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("维保复购数据处理程序")
        self.root.geometry("1100x700")
        self.root.minsize(900, 500)

        self.df: pd.DataFrame | None = None

        self._build_file_selector()
        self._build_notebook()
        self._build_statusbar()

    # ── 文件选择区域 ─────────────────────────────────────────

    def _build_file_selector(self):
        """构建顶部文件选择栏"""
        frame = ttk.Frame(self.root, padding=(10, 10, 10, 5))
        frame.pack(fill=tk.X)

        ttk.Label(frame, text="数据文件：").pack(side=tk.LEFT)

        self.file_path_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.file_path_var, width=70)
        entry.pack(side=tk.LEFT, padx=(5, 5))

        ttk.Button(frame, text="浏览...", command=self._browse_file).pack(side=tk.LEFT)

        ttk.Button(frame, text="加载数据", command=self._load_file).pack(
            side=tk.LEFT, padx=(5, 0)
        )

        # 提示标签
        self.hint_label = ttk.Label(frame, text="", foreground="gray")
        self.hint_label.pack(side=tk.RIGHT)

    # ── Notebook（三个 Tab） ──────────────────────────────────

    def _build_notebook(self):
        """构建 Tab 页容器"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Tab 1：客户总金额统计
        self.tab1_frame = self._create_tab(
            "客户总金额统计",
            ["客户名称", "合同总金额"],
        )

        # Tab 2：客户分类金额统计
        self.tab2_frame = self._create_tab(
            "客户分类金额统计",
            [
                "客户名称",
                "维保合同总金额",
                "产品合同总金额",
                "服务合同总金额",
                "合计总金额",
            ],
        )

        # Tab 3：产品销量统计
        self.tab3_frame = self._create_tab(
            "产品销量统计",
            ["产品名称", "售卖总台数"],
        )

    def _create_tab(self, title: str, columns: list[str]) -> ttk.Frame:
        """
        创建一个 Tab 页，内含 Treeview 表格和滚动条。

        参数:
            title: Tab 标题
            columns: Treeview 列名列表

        返回:
            包含 tree 属性的 ttk.Frame
        """
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)

        # Treeview
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=20)

        for col in columns:
            tree.heading(col, text=col, anchor="center")
            # 金额/台数列右对齐，客户名称/产品名称左对齐
            if "金额" in col or "台数" in col:
                tree.column(col, anchor="e", width=160, minwidth=120)
            else:
                tree.column(col, anchor="w", width=220, minwidth=150)

        # 垂直滚动条
        scrollbar_y = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        # 水平滚动条
        scrollbar_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(
            yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set
        )

        # 布局
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # 保存引用
        frame.tree = tree
        return frame

    # ── 底部状态栏 ────────────────────────────────────────────

    def _build_statusbar(self):
        """构建底部状态栏"""
        self.status_var = tk.StringVar(value='就绪 — 请选择 Excel 文件并点击"加载数据"')
        statusbar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(10, 3),
        )
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    # ── 文件操作 ──────────────────────────────────────────────

    def _browse_file(self):
        """打开文件选择对话框"""
        filepath = filedialog.askopenfilename(
            title="选择合同数据文件",
            filetypes=[
                ("Excel 文件", "*.xlsx *.xls"),
                ("所有文件", "*.*"),
            ],
        )
        if filepath:
            self.file_path_var.set(filepath)
            self._load_file()

    def _load_file(self):
        """加载 Excel 文件并刷新所有 Tab"""
        filepath = self.file_path_var.get().strip()
        if not filepath:
            messagebox.showwarning("提示", "请先选择 Excel 文件")
            return

        try:
            self.df = pd.read_excel(filepath)
            self._refresh_all_tabs()
            self.status_var.set(
                f"已加载 {len(self.df)} 行数据 — {filepath}"
            )
        except FileNotFoundError:
            messagebox.showerror("错误", f"文件不存在：\n{filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败：\n{e}")

    # ── 数据刷新 ──────────────────────────────────────────────

    def _refresh_all_tabs(self):
        """刷新三个 Tab 的数据"""
        if self.df is None:
            return

        try:
            # Tab 1：客户总金额
            df1 = compute_customer_total(self.df)
            self._populate_tree(self.tab1_frame.tree, df1)

            # Tab 2：客户分类金额
            df2 = compute_customer_category(self.df)
            self._populate_tree(self.tab2_frame.tree, df2)

            # Tab 3：产品销量
            df3 = compute_product_sales(self.df)
            self._populate_tree(self.tab3_frame.tree, df3)

            self.status_var.set(
                f"数据已刷新 — 共 {len(self.df)} 行合同数据"
            )
        except Exception as e:
            messagebox.showerror("错误", f"数据处理失败：\n{e}")

    def _populate_tree(self, tree: ttk.Treeview, df: pd.DataFrame):
        """
        将 DataFrame 数据填充到 Treeview 表格。

        参数:
            tree: ttk.Treeview 实例
            df: 要展示的 DataFrame
        """
        # 清空现有数据
        tree.delete(*tree.get_children())

        # 逐行插入
        for _, row in df.iterrows():
            values = []
            for col in df.columns:
                val = row[col]
                if isinstance(val, float):
                    values.append(f"{val:,.2f}")
                elif isinstance(val, int):
                    values.append(f"{val:,}")
                else:
                    values.append(str(val))
            tree.insert("", tk.END, values=values)

    # ── 公开方法：供外部直接加载 DataFrame ─────────────────────

    def load_dataframe(self, df: pd.DataFrame, file_label: str = ""):
        """
        直接加载 DataFrame（跳过文件选择）。

        参数:
            df: 合同数据 DataFrame
            file_label: 文件标识（显示在状态栏）
        """
        self.df = df
        self.file_path_var.set(file_label)
        self._refresh_all_tabs()
