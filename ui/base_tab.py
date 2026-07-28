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
        search_column: str | None = None,
    ):
        self.master = master
        self.tab_name = tab_name
        self.columns = columns
        self.on_double_click_callback = on_double_click
        self.has_star = has_star
        self._star_toggle_callback = on_star_toggle
        self._get_starred = get_starred_names
        self._search_column = search_column

        self.frame: ctk.CTkFrame | None = None
        self.tree: ttk.Treeview | None = None
        self.source_df: pd.DataFrame | None = None
        self.columns_display: list[str] = []
        self.sort_col: str | None = None
        self.sort_asc: bool = True

        # 列宽自适应相关
        self._last_tree_width: int = 0
        self._resize_after_id: str | None = None

        # 搜索相关
        self._search_var: tk.StringVar | None = None
        self._search_text: str = ""
        self._suggest_popup: tk.Toplevel | None = None
        self._suggest_listbox: tk.Listbox | None = None

    # ── 构建 UI ──────────────────────────────────────────────

    def build(self) -> ctk.CTkFrame:
        """创建 Tab 的 Treeview + 滚动条，返回 CTkFrame。"""
        frame = ctk.CTkFrame(self.master, fg_color="transparent", corner_radius=0)

        tree = ttk.Treeview(frame, columns=self.columns, show="headings", height=20)

        for idx, col in enumerate(self.columns):
            tree.heading(col, text=col, anchor="center")
            tree.heading(
                col, command=lambda c=col: self._on_header_click(c)
            )
            w = self._column_width(col)
            tree.column(col, anchor="center", width=w, minwidth=min(w, 90), stretch=False)

        tree["show"] = ""  # 初始状态隐藏表头

        tree.tag_configure("odd", background="#F4F4F5")
        tree.tag_configure("even", background="#FCFCFC")
        tree.tag_configure("center", anchor="center")

        tree.bind("<Double-1>", lambda e: self._handle_double_click(e))
        if self.has_star:
            tree.bind("<ButtonRelease-1>", self._on_cell_click)

        # 窗口大小变化时自动重新均分列宽，避免放大后留白
        frame.bind("<Configure>", self._on_frame_configure)

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

        # 搜索栏（如果配置了搜索列）
        if self._search_column:
            self._build_search_bar(btn_bar)

        ctk.CTkButton(
            btn_bar, text="导出 CSV", command=self._export_csv,
            font=("Microsoft YaHei", 11), width=100, height=28,
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=4, pady=4)

        self._btn_bar = btn_bar  # 暴露给子类添加额外按钮
        self.frame = frame
        self.tree = tree
        return frame

    # ── 搜索栏 ──────────────────────────────────────────────

    def _build_search_bar(self, parent: ctk.CTkFrame) -> None:
        """在底部栏左侧创建搜索框。"""
        search_frame = ctk.CTkFrame(parent, fg_color="transparent")
        search_frame.pack(side=tk.LEFT, padx=(4, 8))

        ctk.CTkLabel(
            search_frame,
            text=f"搜索 {self._search_column}:",
            font=("Microsoft YaHei", 11),
            text_color="#888",
        ).pack(side=tk.LEFT, padx=(0, 4))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        entry = ctk.CTkEntry(
            search_frame, textvariable=self._search_var,
            font=("Microsoft YaHei", 11), width=180, height=28,
            corner_radius=6, border_width=1,
        )
        entry.pack(side=tk.LEFT, padx=(0, 4))
        entry.bind("<Return>", lambda e: self._select_first_suggestion())
        entry.bind("<FocusOut>", lambda e: self.frame.after(200, self._hide_suggestions))

        ctk.CTkButton(
            search_frame, text="×", command=self._clear_search,
            font=("Microsoft YaHei", 11), width=28, height=28,
            fg_color="#E0E0E0", hover_color="#D0D0D0",
            text_color="#333", corner_radius=6,
        ).pack(side=tk.LEFT)

        self._search_entry = entry

    def _on_search_change(self, *args) -> None:
        """搜索文本变化时，显示联想建议并过滤表格。"""
        self._search_text = self._search_var.get().strip()
        self._apply_search_filter()
        self._update_suggestions()

    def _apply_search_filter(self) -> None:
        """应用搜索过滤并刷新表格。"""
        if self.source_df is None:
            return
        self._fill_tree(self.source_df.copy())

    def _get_filtered_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """对 DataFrame 按搜索文本过滤（子类覆盖的 _fill_tree 也应调用此方法）。"""
        if not self._search_text or not self._search_column:
            return df
        if self._search_column not in df.columns:
            return df
        return df[df[self._search_column].astype(str).str.contains(
            self._search_text, case=False, na=False
        )]

    # ── 搜索联想建议 ────────────────────────────────────────

    def _update_suggestions(self) -> None:
        """根据输入内容显示联想建议下拉。"""
        self._hide_suggestions()
        if not self._search_text or self.source_df is None:
            return
        if self._search_column not in self.source_df.columns:
            return
        names = self.source_df[self._search_column].dropna().astype(str).str.strip().unique()
        matches = sorted([n for n in names if self._search_text.lower() in n.lower()])[:10]
        if not matches:
            return
        self._show_suggest_popup(matches)

    def _show_suggest_popup(self, matches: list[str]) -> None:
        """弹出联想建议 Toplevel。"""
        if not self._search_entry:
            return
        popup = tk.Toplevel(self.frame)
        popup.wm_overrideredirect(True)
        popup.attributes("-topmost", True)

        # 定位到搜索框正下方
        x = self._search_entry.winfo_rootx()
        y = self._search_entry.winfo_rooty() + self._search_entry.winfo_height()
        popup.geometry(f"+{x}+{y}")

        listbox = tk.Listbox(
            popup, height=min(len(matches), 8),
            font=("Microsoft YaHei", 10), exportselection=False,
            width=28,
        )
        listbox.pack(fill=tk.BOTH, expand=True)
        for m in matches:
            listbox.insert(tk.END, m)

        def _on_select(event):
            if listbox.curselection():
                self._search_var.set(listbox.get(listbox.curselection()[0]))
                self._hide_suggestions()

        listbox.bind("<ButtonRelease-1>", _on_select)
        popup.bind("<FocusOut>", lambda e: self.frame.after(100, self._hide_suggestions))

        self._suggest_popup = popup
        self._suggest_listbox = listbox

    def _select_first_suggestion(self) -> None:
        """回车选择第一条联想建议。"""
        if self._suggest_listbox and self._suggest_listbox.size():
            self._search_var.set(self._suggest_listbox.get(0))
        self._hide_suggestions()

    def _hide_suggestions(self) -> None:
        """关闭联想建议弹窗。"""
        if self._suggest_popup:
            try:
                self._suggest_popup.destroy()
            except Exception:
                pass
            self._suggest_popup = None
        self._suggest_listbox = None

    def _clear_search(self) -> None:
        """清除搜索，显示全部数据。"""
        self._search_var.set("")
        self._search_text = ""
        self._hide_suggestions()
        self._apply_search_filter()

    def _has_search_text(self) -> bool:
        """子类可调用以判断是否有搜索条件。"""
        return bool(self._search_text)

    @staticmethod
    def _column_width(col: str) -> int:
        """根据列名类型返回初始列宽（仅 build 阶段使用，无数据时的 fallback）。"""
        if col.isdigit() and len(col) == 4:
            return 110
        if "名称" in col:
            return 220
        return 160

    # ── 内容自适应列宽 ──────────────────────────────────────

    @staticmethod
    def _format_cell(val) -> str:
        """将单元格值转为展示字符串，用于计算列宽。"""
        import pandas as _pd
        if _pd.isna(val):
            return ""
        if isinstance(val, float):
            return f"{val:,.2f}"
        elif isinstance(val, int):
            return f"{val:,}"
        return str(val)

    def _measure_font(self) -> tk.font.Font:
        """获取 Treeview 实际使用字体，用于精确计算文字像素宽度。"""
        try:
            return tk.font.Font(family="Microsoft YaHei UI", size=12)
        except Exception:
            return tk.font.Font(font=("Microsoft YaHei", 12))

    def _estimate_text_width(self, text: str) -> int:
        """估算文字像素宽度，优先用实际字体度量，失败则回退到经验值。"""
        try:
            font = self._measure_font()
            return font.measure(str(text))
        except Exception:
            width = 0
            for ch in str(text):
                code = ord(ch)
                if 0x4E00 <= code <= 0x9FFF or 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF:
                    width += 14
                elif code < 128:
                    width += 7
                else:
                    width += 10
            return width

    def _calc_content_widths(self, df: pd.DataFrame) -> dict[str, int]:
        """按每列最长内容计算像素宽度，返回 {列名: 像素宽}。"""
        data_cols = list(df.columns)
        widths: dict[str, int] = {}
        for col in data_cols:
            # 表头宽度
            max_px = self._estimate_text_width(col)
            # 内容宽度（最多采样 200 行）
            sample = df[col].head(200)
            for val in sample:
                cell_text = self._format_cell(val)
                px = self._estimate_text_width(cell_text)
                if px > max_px:
                    max_px = px
            # 加 28px 内边距，最小 80px（避免打包后字体回退导致列宽被压得过窄）
            widths[col] = max(80, max_px + 28)
        return widths

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
        df = self._get_filtered_df(df)
        self._sync_columns(df)
        self.tree.delete(*self.tree.get_children())
        self._update_headers()

        df_cols = list(df.columns)
        starred = set(self._get_starred()) if self.has_star and self._get_starred else set()

        for idx, (_, row) in enumerate(df.iterrows(), 1):
            # 格式化数据值
            formatted = []
            for col in df_cols:
                formatted.append(self._format_cell(row[col]))

            # 标星列
            if self.has_star:
                name_val = str(row[df_cols[0]]) if df_cols else ""
                star = "★" if name_val in starred else "☆"
                values = [star, str(idx)] + formatted
            else:
                values = [str(idx)] + formatted

            tag = "odd" if idx % 2 == 1 else "even"
            self.tree.insert("", tk.END, values=values, tags=(tag, "center"))

        # 打包成 exe 后，Treeview 首次布局时可能尚未拿到真实宽度；延迟重算一次列宽
        self.frame.after(100, lambda: self._sync_widths(df))

    # ── 列同步 ──────────────────────────────────────────────

    def _on_frame_configure(self, event: tk.Event) -> None:
        """容器大小变化时防抖重新计算列宽，解决窗口放大后留白问题。"""
        if self.tree is None or self.source_df is None or not self.columns_display:
            return
        if event.widget is not self.frame:
            return

        new_width = event.width
        if abs(new_width - self._last_tree_width) < 50:
            return

        if self._resize_after_id:
            self.frame.after_cancel(self._resize_after_id)
        self._resize_after_id = self.frame.after(150, lambda: self._resize_columns(new_width))

    def _resize_columns(self, new_width: int) -> None:
        """根据新宽度重新均分列宽。"""
        if self.tree is None or self.source_df is None or not self.columns_display:
            return
        self._last_tree_width = new_width
        self._sync_widths(self.source_df)

    def _sync_columns(self, df: pd.DataFrame) -> None:
        """确保 Treeview 列与 DataFrame 列一致。"""
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
        self._sync_widths(df)

    def _sync_widths(self, df: pd.DataFrame) -> None:
        """按内容自适应设置列宽：非名称列固定内容宽度，名称列填充剩余空间（不会被压缩）。"""
        tree = self.tree
        data_cols = list(df.columns)

        # 内容自适应宽度（数据列）
        content_widths = self._calc_content_widths(df)

        # 固定列宽度
        star_fixed = 50 if self.has_star else 0
        seq_fixed = 50

        # 获取 Treeview 实际可用宽度
        try:
            self.master.update_idletasks()
            tree_width = self.tree.winfo_width()
            if tree_width <= 1:
                tree_width = self.master.winfo_width()
            # 减去滚动条/边距预留
            avail = max(300, tree_width - star_fixed - seq_fixed - 16)
        except Exception:
            avail = 1200

        # 找出名称列（最多一个），其余为非拉伸列
        name_col: str | None = None
        non_name_total = 0
        for col in data_cols:
            if name_col is None and "名称" in col:
                name_col = col
            else:
                non_name_total += content_widths.get(col, 160)

        # 名称列宽度：优先填充剩余空间，但不会小于自身内容宽度
        if name_col:
            name_content_w = content_widths.get(name_col, 160)
            name_width = max(name_content_w, avail - non_name_total)
        else:
            name_width = 0

        # 标星列（始终固定 50px，不拉伸）
        if self.has_star:
            tree.heading(self.STAR_COL, text="★", anchor="center")
            tree.column(
                self.STAR_COL, anchor="center",
                width=50, minwidth=50, stretch=False,
            )

        # 序号列固定 50px，不拉伸
        tree.heading(self.SEQ_COL, text="#", anchor="center")
        tree.column(
            self.SEQ_COL, anchor="center",
            width=50, minwidth=50, stretch=False,
        )

        # 数据列：名称列手动分配宽度并 stretch=False，防止被 ttk 压缩；其余列按内容宽度
        for col in data_cols:
            tree.heading(col, text=col, anchor="center")
            tree.heading(col, command=lambda c=col: self._on_header_click(c))
            if col == name_col:
                tree.column(col, anchor="center", width=name_width, minwidth=80, stretch=False)
            else:
                w = content_widths.get(col, 160)
                tree.column(col, anchor="center", width=w, minwidth=80, stretch=False)

        # 记录本次同步时的 Treeview 宽度，作为 resize 判断基准
        try:
            self._last_tree_width = self.tree.winfo_width()
        except Exception:
            pass

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
        """导出当前表格数据为 CSV 文件（包含搜索过滤后的结果）。"""
        if self.source_df is None or self.source_df.empty:
            from tkinter import messagebox
            messagebox.showwarning("提示", "没有数据可导出")
            return
        export_df = self._get_filtered_df(self.source_df)
        if export_df.empty:
            from tkinter import messagebox
            messagebox.showwarning("提示", "没有数据可导出")
            return
        log_info(f"导出CSV [{self.tab_name}]: {self.tab_name}.csv，共 {len(export_df)} 行")
        export_to_csv(export_df, self.frame, f"{self.tab_name}.csv")
