"""Tkinter UI 模块：界面布局与交互"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd

from data_processor import (
    compute_customer_total,
    compute_customer_category,
    compute_product_sales,
)
from utils import classify_contract


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
            tree.column(col, anchor="center", width=180, minwidth=140)

        # 绑定表头点击排序
        for col in columns:
            tree.heading(
                col,
                command=lambda c=col, t=tree: self._on_header_click(t, c),
            )

        # 双击事件绑定（用于弹窗展示原始数据）
        tree.bind("<Double-1>", lambda e, f=frame: self._on_double_click(f, e))

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

        # 保存引用及排序状态
        frame.tree = tree
        frame.columns = columns
        frame.sort_col = None       # 当前排序列
        frame.sort_asc = True       # 是否升序
        frame.source_df = None      # 原始 DataFrame（用于排序）
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
            self._populate_tree(self.tab1_frame, df1)

            # Tab 2：客户分类金额
            df2 = compute_customer_category(self.df)
            self._populate_tree(self.tab2_frame, df2)

            # Tab 3：产品销量
            df3 = compute_product_sales(self.df)
            self._populate_tree(self.tab3_frame, df3)

            self.status_var.set(
                f"数据已刷新 — 共 {len(self.df)} 行合同数据"
            )
        except Exception as e:
            messagebox.showerror("错误", f"数据处理失败：\n{e}")

    def _populate_tree(self, frame: ttk.Frame, df: pd.DataFrame):
        """
        将 DataFrame 数据填充到 Treeview 表格。

        参数:
            frame: Tab 页的 ttk.Frame（含 tree 引用和排序状态）
            df: 要展示的 DataFrame
        """
        tree = frame.tree

        # 保存 DataFrame 引用用于后续排序
        frame.source_df = df.copy()

        # 用 DataFrame 的列名同步 Treeview 列名
        self._sync_columns(frame, list(df.columns))

        # 清空现有数据
        tree.delete(*tree.get_children())

        # 配置居中 tag
        tree.tag_configure("center", anchor="center")

        # 更新表头箭头
        self._update_headers(frame)

        # 逐行插入（用 DataFrame 列名遍历）
        df_columns = list(df.columns)
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            values = [str(idx)]
            for col in df_columns:
                val = row[col]
                if isinstance(val, float):
                    values.append(f"{val:,.2f}")
                elif isinstance(val, int):
                    values.append(f"{val:,}")
                else:
                    values.append(str(val))
            tree.insert("", tk.END, values=values, tags=("center",))

    # ── 排序功能 ──────────────────────────────────────────────

    # 序号列标识
    SEQ_COL = "#"

    def _sync_columns(self, frame: ttk.Frame, df_columns: list[str]):
        """
        将 Treeview 的列配置同步为 DataFrame 的列名，并在最前面加一列序号。
        """
        tree = frame.tree
        display_columns = [self.SEQ_COL] + df_columns
        if frame.columns != display_columns:
            tree["columns"] = display_columns
            # 序号列窄一些
            tree.heading(self.SEQ_COL, text="#", anchor="center")
            tree.column(self.SEQ_COL, anchor="center", width=50, minwidth=50)
            for col in df_columns:
                tree.heading(col, text=col, anchor="center")
                # 年份列（纯数字如 "2018"）窄一些，名称列宽一些
                if col.isdigit() and len(col) == 4:
                    tree.column(col, anchor="center", width=110, minwidth=90)
                elif "名称" in col:
                    tree.column(col, anchor="center", width=220, minwidth=160)
                else:
                    tree.column(col, anchor="center", width=160, minwidth=130)
            # 绑定排序事件（仅数据列）
            for col in df_columns:
                tree.heading(
                    col,
                    command=lambda c=col, t=tree: self._on_header_click(t, c),
                )
            frame.columns = display_columns
            frame.sort_col = None
            frame.sort_asc = True

    def _on_header_click(self, tree: ttk.Treeview, col: str):
        """表头点击回调：对该列进行排序（序号列忽略）"""
        if col == self.SEQ_COL:
            return
        # 找到 tree 所属的 frame
        for name in ("tab1_frame", "tab2_frame", "tab3_frame"):
            frame = getattr(self, name, None)
            if frame is not None and frame.tree is tree:
                break
        else:
            return

        df = frame.source_df
        if df is None or col not in df.columns:
            return

        # 切换排序方向
        if frame.sort_col == col:
            frame.sort_asc = not frame.sort_asc
        else:
            frame.sort_col = col
            frame.sort_asc = True

        # 排序
        sorted_df = df.sort_values(col, ascending=frame.sort_asc).reset_index(drop=True)

        # 重新填充（但传入 frame 而非 tree）
        self._repopulate_sorted(frame, sorted_df)

    def _repopulate_sorted(self, frame: ttk.Frame, df: pd.DataFrame):
        """用排序后的 DataFrame 重新填充表格（不改变 source_df）"""
        tree = frame.tree
        tree.delete(*tree.get_children())

        # 更新表头箭头
        self._update_headers(frame)

        df_columns = list(df.columns)
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            values = [str(idx)]
            for col in df_columns:
                val = row[col]
                if isinstance(val, float):
                    values.append(f"{val:,.2f}")
                elif isinstance(val, int):
                    values.append(f"{val:,}")
                else:
                    values.append(str(val))
            tree.insert("", tk.END, values=values, tags=("center",))

    def _update_headers(self, frame: ttk.Frame):
        """更新表头文字，在排序的列上加上 ▲/▼ 箭头"""
        tree = frame.tree
        for col in frame.columns:
            base_text = col
            if col == frame.sort_col:
                arrow = " ▲" if frame.sort_asc else " ▼"
                base_text = col + arrow
            tree.heading(col, text=base_text, anchor="center",
                         command=lambda c=col, t=tree: self._on_header_click(t, c))

    # ── 双击弹窗：展示客户原始合同详情 ─────────────────────────

    # Tab 2 列名到合同类型的映射
    TAB2_COL_TYPE_MAP = {
        "维保合同总金额": "M",
        "产品合同总金额": "P",
        "服务合同总金额": "S",
    }

    def _on_double_click(self, frame: ttk.Frame, event):
        """处理 Treeview 双击事件"""
        tree = frame.tree
        selection = tree.selection()
        if not selection:
            return

        item = selection[0]
        values = tree.item(item, "values")
        if not values:
            return

        # Tab 1：双击任意位置 → 展示该客户全部合同
        if frame is self.tab1_frame:
            # values 格式：[序号, 客户名称, 2018, ..., 2026, 合同总金额]
            customer_name = values[1]
            self._show_customer_detail(customer_name)
            return

        # Tab 2：双击金额列 → 展示该客户对应类型的合同
        if frame is self.tab2_frame:
            # 判断双击的是哪一列
            col_id = tree.identify_column(event.x)  # 返回如 "#3"
            col_index = int(col_id.replace("#", ""))  # 转为数字索引
            # values 格式：[序号, 客户名称, 维保合同总金额, 产品合同总金额, 服务合同总金额, 合计总金额]
            # col_index=1:序号, col_index=2:客户名称, col_index=3:维保, col_index=4:产品, col_index=5:服务, col_index=6:合计
            customer_name = values[1]

            # 确定合同类型
            contract_type = None
            if col_index == 3:
                contract_type = "M"  # 维保
            elif col_index == 4:
                contract_type = "P"  # 产品
            elif col_index == 5:
                contract_type = "S"  # 服务
            elif col_index == 2:
                # 双击客户名称 → 展示该客户全部合同（和 Tab 1 行为一致）
                self._show_customer_detail(customer_name)
                return

            if contract_type:
                type_label = {"M": "维保", "P": "产品", "S": "服务"}[contract_type]
                self._show_customer_detail(customer_name, contract_type=contract_type,
                                           type_label=type_label)
                return

    def _show_customer_detail(self, customer_name: str, contract_type: str | None = None,
                              type_label: str = ""):
        """弹出窗口，展示该客户在原始数据中的合同记录。
        若指定 contract_type（M/P/S），则只展示该类型的合同。
        """
        if self.df is None:
            return

        # 筛选该客户的所有行
        customer_df = self.df[self.df["最终客户名称"] == customer_name].copy()
        if customer_df.empty:
            messagebox.showinfo("提示", f'未找到客户"{customer_name}"的合同记录')
            return

        # 如果指定了合同类型，进一步筛选
        if contract_type:
            customer_df["_type"] = customer_df["合同编号*"].apply(classify_contract)
            customer_df = customer_df[customer_df["_type"] == contract_type]
            if customer_df.empty:
                messagebox.showinfo("提示",
                    f'客户"{customer_name}"没有{type_label}类合同记录')
                return

        # 标题文本
        if contract_type:
            title_text = f'客户：{customer_name} — {type_label}合同（共 {len(customer_df)} 条）'
        else:
            title_text = f'客户：{customer_name}（共 {len(customer_df)} 条合同）'

        # 创建弹窗
        detail_win = tk.Toplevel(self.root)
        detail_win.title(f'客户合同详情 — {customer_name}')
        detail_win.geometry("1200x650")
        detail_win.minsize(800, 450)

        # 标题标签
        title_label = ttk.Label(
            detail_win,
            text=title_text,
            font=("", 12, "bold"),
            padding=(10, 10),
        )
        title_label.pack(fill=tk.X)

        # 主内容区域（表格 + 滚动条）
        main_frame = ttk.Frame(detail_win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        # 创建 Treeview 展示原始数据
        columns = list(customer_df.columns)
        tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=12)

        for col in columns:
            tree.heading(col, text=col, anchor="center")
            tree.column(col, anchor="center", width=140, minwidth=100)

        # 滚动条
        scrollbar_y = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar_x = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(
            yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set
        )

        # 布局
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # 居中 tag
        tree.tag_configure("center", anchor="center")

        # 保存行数据引用，key 为 item iid
        row_data_map: dict[str, dict] = {}

        # 逐行填充（将 \n 替换为 | 避免换行重叠）
        for idx, (_, row) in enumerate(customer_df.iterrows()):
            vals = []
            for col in columns:
                val = row[col]
                if isinstance(val, float):
                    vals.append(f"{val:,.2f}")
                elif isinstance(val, int):
                    vals.append(f"{val:,}")
                else:
                    vals.append(str(val).replace("\n", " | ") if not pd.isna(val) else "")
            iid = tree.insert("", tk.END, values=vals, tags=("center",))
            row_data_map[iid] = {col: row[col] for col in columns}

        # ── 鼠标悬停 tooltip ──
        tooltip_label = ttk.Label(detail_win, text="", foreground="gray",
                                  wraplength=1150, justify=tk.LEFT,
                                  padding=(10, 2), anchor=tk.W)
        tooltip_label.pack(fill=tk.X, padx=10, pady=(2, 0))

        def _on_motion(event):
            """鼠标移动时，在底部显示当前行的产品名称型号完整内容"""
            item = tree.identify_row(event.y)
            if item and item in row_data_map:
                raw = row_data_map[item]
                # 找"产品名称型号"列，找不到则用第一列内容
                product_col = None
                for c in columns:
                    if "产品名称" in c and "型号" in c:
                        product_col = c
                        break
                if product_col:
                    content = str(raw[product_col]) if not pd.isna(raw[product_col]) else ""
                    # 将 \n 替换为可视化分隔符
                    content = content.replace("\n", " │ ")
                    tooltip_label.config(text=f"产品名称型号：{content}")
                else:
                    tooltip_label.config(text="")
            else:
                tooltip_label.config(text="")

        tree.bind("<Motion>", _on_motion)

        # ── 底部展开区域 ──
        detail_text = tk.Text(
            detail_win, height=6, wrap=tk.WORD,
            font=("Microsoft YaHei UI", 9),
            state=tk.DISABLED,
        )
        detail_text.pack(fill=tk.BOTH, padx=10, pady=(0, 5))

        def _on_select(event):
            """选中行时，在底部文本区域展开显示该行的产品名称型号"""
            selection = tree.selection()
            if not selection:
                return
            item = selection[0]
            if item not in row_data_map:
                return
            raw = row_data_map[item]

            # 找"产品名称型号"列
            product_col = None
            for c in columns:
                if "产品名称" in c and "型号" in c:
                    product_col = c
                    break

            detail_text.config(state=tk.NORMAL)
            detail_text.delete("1.0", tk.END)

            if product_col:
                content = str(raw[product_col]) if not pd.isna(raw[product_col]) else ""
                detail_text.insert(tk.END, "【产品名称型号】\n", "header")
                detail_text.insert(tk.END, content)
            else:
                # 没有产品名称型号列，展示整行所有字段
                detail_text.insert(tk.END, "【行详情】\n", "header")
                for c in columns:
                    val = raw[c]
                    val_str = str(val) if not pd.isna(val) else ""
                    detail_text.insert(tk.END, f"{c}：{val_str}\n")

            detail_text.config(state=tk.DISABLED)

        tree.bind("<<TreeviewSelect>>", _on_select)

        # 配置 Text 标签样式
        detail_text.tag_configure("header", font=("Microsoft YaHei UI", 9, "bold"))

        # ── 关闭按钮 ──
        btn_frame = ttk.Frame(detail_win)
        btn_frame.pack(side=tk.BOTTOM, pady=(0, 10))
        ttk.Button(btn_frame, text="关闭", command=detail_win.destroy).pack()

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
