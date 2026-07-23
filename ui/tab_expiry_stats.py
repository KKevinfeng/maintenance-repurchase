"""Tab 3：过保情况统计 —— 独立导入 Excel 并展示，支持筛选重点客户过保合同"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import customtkinter as ctk

from ui.styles import FONT_MAIN, FONT_SMALL, FONT_TITLE, setup_treeview_style
from ui.expiry_starred_view import ExpiryStarredView
from ui.progress_popup import ProgressPopup
from ui.column_filter_popup import ColumnFilterPopup
from utils import classify_contract, center_window, export_to_csv


class ExpiryStatsTab:
    """过保情况统计页 —— 自带导入按钮，展示独立 Excel 数据。"""

    SEQ_COL = "#"

    def __init__(self, master: ctk.CTkFrame, starred_cache=None):
        self.master = master
        self.starred_cache = starred_cache
        self.frame: ctk.CTkFrame | None = None
        self.tree: ttk.Treeview | None = None
        self.file_path_var = tk.StringVar()
        self.source_df: pd.DataFrame | None = None
        self.columns_display: list[str] = []
        self.sort_col: str | None = None
        self.sort_asc: bool = True
        self.active_filters: dict[str, set] = {}  # 列名 -> 已选值集合
        self.filter_btns: dict[str, ctk.CTkButton] = {}

    def build(self) -> ctk.CTkFrame:
        """构建 Tab 内容：导入区 + 表格。"""
        frame = ctk.CTkFrame(self.master, fg_color="transparent", corner_radius=0)

        # ── 导入区 ──
        import_bar = ctk.CTkFrame(frame, fg_color="transparent")
        import_bar.pack(fill=tk.X, padx=8, pady=(8, 4))

        ctk.CTkLabel(
            import_bar, text="过保文件:", font=FONT_MAIN, width=60,
        ).pack(side=tk.LEFT, padx=(0, 6))

        ctk.CTkEntry(
            import_bar, textvariable=self.file_path_var, font=FONT_MAIN, height=32,
            corner_radius=6, border_width=1,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        ctk.CTkButton(
            import_bar, text="浏览...", command=self._browse_file,
            font=FONT_MAIN, width=80, height=32,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0", corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 6))

        ctk.CTkButton(
            import_bar, text="筛选重点客户过保合同",
            command=self._filter_starred_expiry,
            font=FONT_MAIN, width=180, height=32,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0", corner_radius=6,
        ).pack(side=tk.LEFT)

        # ── 筛选栏（初始隐藏，有数据后显示）──
        self.filter_bar = ctk.CTkFrame(frame, fg_color="transparent")
        # 不立即 pack，等数据加载后再显示

        # 底部导出按钮栏（先 pack 到底部，避免被 tree_frame 的 expand 顶出可视区）
        btn_bar = ctk.CTkFrame(frame, fg_color="transparent", height=36)
        btn_bar.pack_propagate(False)
        ctk.CTkButton(
            btn_bar, text="导出 CSV", command=self._export_csv,
            font=FONT_MAIN, width=100, height=28,
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=4, pady=4)
        btn_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 8))

        # ── 表格 ──
        tree_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        tree = ttk.Treeview(tree_frame, show="", height=20)
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

        self.frame = frame
        self.tree = tree
        self.tree_frame = tree_frame

        return frame

    # ── 文件浏览 & 加载 ──────────────────────────────────────

    def _browse_file(self):
        """打开文件对话框，选择后自动加载。"""
        filepath = filedialog.askopenfilename(
            title="选择过保情况统计文件",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")],
        )
        if filepath:
            self.file_path_var.set(filepath)
            self._load_file()

    def _load_file(self):
        """后台线程加载 Excel 并展示，弹窗显示进度。"""
        filepath = self.file_path_var.get().strip()
        if not filepath:
            messagebox.showwarning("提示", "请先选择 Excel 文件")
            return

        if getattr(self, "_loading", False):
            return
        self._loading = True

        self._load_error: str | None = None
        self._load_df: pd.DataFrame | None = None
        self._load_ticks = 0

        root = self.master.winfo_toplevel()
        popup = ProgressPopup(root, title="正在导入过保情况数据...")

        def worker():
            try:
                df = pd.read_excel(filepath)
                if df.empty:
                    self._load_error = "文件内容为空"
                    return
                self._load_df = df
            except FileNotFoundError:
                self._load_error = f"文件不存在：\n{filepath}"
            except Exception as e:
                self._load_error = f"加载文件失败：\n{e}"

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        root.after(100, self._poll_load_done, thread, popup)

    def _poll_load_done(self, thread: threading.Thread, popup: ProgressPopup):
        """轮询后台线程，更新弹窗进度；完成后回到主线程更新 UI。"""
        if thread.is_alive():
            self._load_ticks += 1
            pct = 0.9 * (1 - 0.95 ** self._load_ticks)
            popup.set_progress(pct, f"正在加载数据… {int(pct * 100)}%")
            root = self.master.winfo_toplevel()
            root.after(100, self._poll_load_done, thread, popup)
            return

        self._loading = False

        if self._load_error:
            popup.close()
            messagebox.showerror("错误", self._load_error)
            return

        self.source_df = self._load_df
        self.active_filters.clear()
        self.sort_col = None
        self.sort_asc = True
        popup.set_progress(0.95, "正在生成表格...")
        self._fill_tree(self._load_df)
        self._build_filter_bar()
        popup.close()

    # ── 筛选重点客户过保合同 ─────────────────────────────────

    def _filter_starred_expiry(self) -> None:
        """筛选缓存表中标星客户的 P 类过保合同，在弹窗中展示。"""
        df = self.source_df
        if df is None:
            messagebox.showwarning("提示", "请先导入过保情况数据")
            return

        if self.starred_cache is None:
            messagebox.showwarning("提示", "缓存功能未初始化")
            return

        starred_names = self.starred_cache.get_all()
        if not starred_names:
            messagebox.showwarning("提示", "暂无重点客户，请先在Tab1内标星或手动添加重点客户")
            return

        # 查找关键列
        gift_col = None       # 渠道大礼包最终客户
        enduser_col = None    # 最终客户（不包含大礼包）
        for col in df.columns:
            col_str = str(col).replace("\n", " ")
            if gift_col is None and "渠道大礼包最终客户" in col_str:
                gift_col = col
            if enduser_col is None and "最终客户" in col_str and "大礼包" not in col_str:
                enduser_col = col

        if gift_col is None and enduser_col is None:
            messagebox.showerror("错误", "未在导入文件中找到【渠道大礼包最终客户】或【最终客户】列")
            return

        # 查找合同编号/编码列（用于识别 P/M/S 类型）
        contract_col = None
        for col in df.columns:
            col_str = str(col)
            if "合同编号" in col_str or "合同编码" in col_str:
                contract_col = col
                break

        if contract_col is None:
            messagebox.showerror("错误", "未在导入文件中找到【合同编号】或【合同编码】列")
            return

        # 筛选：优先用"渠道大礼包最终客户"匹配，未命中再用"最终客户"匹配
        starred_set = set(starred_names)
        mask = pd.Series(False, index=df.index)

        if gift_col is not None:
            gift_mask = df[gift_col].isin(starred_set)
            mask = mask | gift_mask  # 渠道大礼包最终客户命中的行

        if enduser_col is not None:
            # 仅对渠道大礼包未命中的行，再用"最终客户"列碰撞
            unmatched = ~mask
            enduser_mask = df.loc[unmatched, enduser_col].isin(starred_set)
            mask = mask | enduser_mask.reindex(df.index, fill_value=False)

        filtered = df[mask].copy()

        if filtered.empty:
            messagebox.showinfo("提示", "没有找到重点客户的过保合同")
            return

        # 仅保留 P 类合同
        before_p = len(filtered)
        filtered["_type"] = filtered[contract_col].apply(classify_contract)
        type_counts = filtered["_type"].value_counts().to_dict()
        filtered = filtered[filtered["_type"] == "P"].drop(columns=["_type"])

        if filtered.empty:
            detail = ", ".join(f"{k}: {v} 条" for k, v in sorted(type_counts.items()) if k)
            unknown = type_counts.get(None, 0)
            if unknown:
                detail += (", " if detail else "") + f"未识别: {unknown} 条"
            msg = f"重点客户共匹配 {before_p} 条记录，其中无 P 类合同。\n合同类型分布：{detail}"
            messagebox.showinfo("提示", msg)
            return

        # 弹窗展示
        top = self.master.winfo_toplevel()
        ExpiryStarredView.show(top, filtered)

    # ── 表格填充 ─────────────────────────────────────────────

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
        self._display_df = df.copy()  # 保存当前显示数据，供导出使用
        tree = self.tree
        tree["show"] = "headings"

        # 列重排序：过保日期、客户意向、不续保原因前置
        reordered_cols = self._reorder_columns(list(df.columns))
        clean_columns = [self._clean_col(c) for c in reordered_cols]

        display = [self.SEQ_COL] + reordered_cols
        self.columns_display = display

        # 列变化时才重置排序状态
        current = list(tree["columns"])
        if current != display:
            self.sort_col = None
            self.sort_asc = True

        tree["columns"] = display
        tree.heading(self.SEQ_COL, text="#", anchor="center")
        tree.column(self.SEQ_COL, anchor="center", width=50, minwidth=50)

        for col, clean in zip(reordered_cols, clean_columns):
            tree.heading(col, text=clean, anchor="center")
            tree.heading(col, command=lambda c=col: self._on_header_click(c))
            w = self._column_width(col)
            tree.column(col, anchor="center", width=w, minwidth=min(w, 100), stretch=True)

        tree.delete(*tree.get_children())

        for idx, (_, row) in enumerate(df.iterrows(), 1):
            values = [str(idx)]
            for col in reordered_cols:
                val = row[col]
                val = self._fmt_val(val)
                values.append(val)
            tag = "odd" if idx % 2 == 1 else "even"
            tree.insert("", tk.END, values=values, tags=(tag, "center"))

    # ── 筛选栏 ───────────────────────────────────────────────

    FILTER_KEYWORDS = ["客户意向", "不续保原因"]

    def _get_filter_columns(self) -> list[str]:
        """返回当前数据中可筛选的列名。"""
        df = self.source_df
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
        if self.source_df is None or col not in self.source_df.columns:
            return []
        # 先应用所有其他列的筛选条件
        df = self.source_df.copy()
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
        """根据当前数据重建筛选按钮。"""
        # 清除旧按钮
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

        # 清除筛选按钮
        if any(v != set(self._get_filter_values(c)) for c, v in self.active_filters.items()
               if v):
            ctk.CTkButton(
                self.filter_bar, text="清除筛选", font=FONT_SMALL,
                width=70, height=24, corner_radius=4,
                fg_color="#D9534F", text_color="#FFFFFF",
                hover_color="#C9302C",
                command=self._clear_filters,
            ).pack(side=tk.LEFT, padx=(4, 0))

        self.filter_bar.pack(fill=tk.X, padx=8, pady=(4, 0), before=self.tree_frame)

    def _open_filter_popup(self, col: str, all_vals: list[str], selected: set):
        """打开列值多选弹窗。"""
        top = self.master.winfo_toplevel()
        ColumnFilterPopup(top, self._clean_col(col), all_vals, selected,
                          on_apply=self._apply_filter)

    def _apply_filter(self, col: str, selected: set):
        """应用筛选并刷新表格。"""
        self.active_filters[col] = selected
        # 筛选变化时取消排序
        self.sort_col = None
        self.sort_asc = True
        self._fill_tree(self._get_display_df())
        self._build_filter_bar()

    def _clear_filters(self):
        """清除所有筛选条件。"""
        self.active_filters.clear()
        self.sort_col = None
        self.sort_asc = True
        self._fill_tree(self.source_df)
        self._build_filter_bar()

    def _get_display_df(self):
        """按当前筛选 + 排序返回展示用 DataFrame。"""
        df = self.source_df
        if df is None:
            return None
        df = df.copy()
        for col, allowed in self.active_filters.items():
            if col not in df.columns:
                continue
            if not allowed:
                # 用户取消全选 → 返回空结果
                return df.iloc[:0].copy()
            # 将列转为字符串匹配（处理"（空）"代表 NaN 的情况）
            ser = df[col].fillna("（空）").astype(str)
            mask = ser.isin(allowed)
            df = df[mask]
        if self.sort_col and self.sort_col in df.columns:
            df = df.sort_values(self.sort_col, ascending=self.sort_asc).reset_index(drop=True)
        return df

    @staticmethod
    def _clean_col(col: str) -> str:
        """将列名中的换行符替换为空格，便于表格表头显示。"""
        if isinstance(col, str):
            return col.replace("\n", " ")
        return str(col)

    @staticmethod
    def _fmt_val(val) -> str:
        """格式化单元格值：数字加千分位，NaN 显示为空。"""
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

    # ── 排序 ─────────────────────────────────────────────────

    def _on_header_click(self, col: str) -> None:
        """表头点击排序 — 在筛选基础上排序，仅非名称列可排序。"""
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

        sorted_df = display_df.sort_values(col, ascending=self.sort_asc).reset_index(drop=True)
        self._fill_tree(sorted_df)

    # ── 导出 ─────────────────────────────────────────────────

    def _export_csv(self) -> None:
        """导出当前表格数据为 CSV 文件（包含筛选和排序结果）。"""
        df = getattr(self, "_display_df", None)
        if df is None or df.empty:
            messagebox.showwarning("提示", "没有数据可导出")
            return
        export_to_csv(df, self.frame, "过保情况统计.csv")
