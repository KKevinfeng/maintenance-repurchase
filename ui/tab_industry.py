"""行业统计 Tab：按一级行业 → 二级行业 → 客户逐层下钻。"""

import tkinter as tk
from tkinter import ttk
from typing import Optional
import pandas as pd
import customtkinter as ctk

from ui.base_tab import BaseTab
from ui.industry_dict import get_primary as dict_primary, get_secondary as dict_secondary, \
    add_primary, add_secondary, remove_primary, remove_secondary, merge_from_dataframe
from ui.industry_overrides import apply_overrides, set_override, remove_override, get_all
from ui.logger import log_info
from ui.styles import FONT_MAIN, FONT_TITLE, FONT_SMALL
from utils import center_window, export_to_csv


def _build_dict_tab(parent, title, get_items_fn, add_fn, remove_fn, on_change=None):
    """构建数据字典的单个 Tab（一级或二级行业），on_change 在增删后触发。"""
    # 工具栏
    toolbar = ctk.CTkFrame(parent, fg_color="transparent")
    toolbar.pack(fill=tk.X, padx=8, pady=(6, 4))

    ctk.CTkLabel(
        toolbar, text=f"{title}列表", font=FONT_TITLE, text_color="#1F6AA5",
    ).pack(side=tk.LEFT, padx=(4, 16))

    entry_var = tk.StringVar()
    entry = ctk.CTkEntry(toolbar, textvariable=entry_var, width=200, placeholder_text=f"输入新{title}...")
    entry.pack(side=tk.LEFT, padx=(0, 6))

    # 按钮与列表
    table_frame = ctk.CTkFrame(parent, fg_color="transparent")
    table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)

    listbox = tk.Listbox(table_frame, font=("Microsoft YaHei", 11), exportselection=False)
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=listbox.yview)
    listbox.configure(yscrollcommand=scrollbar.set)
    listbox.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    def _refresh():
        listbox.delete(0, tk.END)
        for item in get_items_fn():
            listbox.insert(tk.END, item)

    _refresh()

    def _do_add():
        name = entry_var.get().strip()
        if not name:
            return
        add_fn(name)
        entry_var.set("")
        _refresh()
        if on_change:
            on_change()

    def _do_delete():
        sel = listbox.curselection()
        if not sel:
            return
        name = listbox.get(sel[0])
        from tkinter import messagebox  # noqa: F811
        if not messagebox.askyesno("确认删除", f"确定要删除 {title}「{name}」吗？", parent=parent):
            return
        remove_fn(name)
        _refresh()
        if on_change:
            on_change()

    entry.bind("<Return>", lambda e: _do_add())

    ctk.CTkButton(
        toolbar, text="添加", command=_do_add,
        font=FONT_SMALL, width=60, height=26,
        fg_color="#1F6AA5", hover_color="#155485", corner_radius=6,
    ).pack(side=tk.LEFT)

    # 底部按钮
    btn_bar = ctk.CTkFrame(parent, fg_color="transparent")
    btn_bar.pack(fill=tk.X, padx=8, pady=(0, 6))
    ctk.CTkButton(
        btn_bar, text="删除选中", command=_do_delete,
        font=FONT_SMALL, width=80, height=26,
        fg_color="#C0392B", hover_color="#A93226", corner_radius=6,
    ).pack(side=tk.LEFT)

    return _refresh


class IndustryTab(BaseTab):
    """一级行业统计表 — 双击下钻查看二级行业和客户。"""

    # 保留原始 DataFrame 用于下钻
    _raw_df: Optional[pd.DataFrame] = None

    def __init__(self, master, on_double_click=None):
        super().__init__(
            master=master,
            tab_name="行业统计",
            columns=["一级行业", "数量", "行业总金额"],
            on_double_click=on_double_click,
            has_star=False,
        )
        self._load_df: Optional[pd.DataFrame] = None

    def build(self) -> ctk.CTkFrame:
        """构建 UI：利用基类 Treeview，在底部按钮栏添加编辑按钮。"""
        frame = super().build()

        ctk.CTkButton(
            self._btn_bar, text="编辑行业",
            command=self._open_override_manager,
            font=FONT_SMALL, width=80, height=26,
            fg_color="#E8960C", hover_color="#C47D0A",
            corner_radius=6,
        ).pack(side=tk.LEFT, padx=(4, 4))

        ctk.CTkButton(
            self._btn_bar, text="数据字典",
            command=self._show_data_dict_dialog,
            font=FONT_SMALL, width=80, height=26,
            fg_color="#1F6AA5", hover_color="#155485",
            corner_radius=6,
        ).pack(side=tk.LEFT, padx=(4, 4))
        return frame

    def compute_data(self, df: pd.DataFrame) -> pd.DataFrame:
        from data_processor import compute_industry_stats

        # 处理完整 DataFrame（含合同金额/编号列，用于行业金额统计）
        full_df = df.copy()
        full_df["一级行业"] = full_df["一级行业"].fillna("未知")
        full_df["二级行业"] = full_df["二级行业"].fillna("未知")

        # 过滤掉一级行业为"未知"的行
        full_df = full_df[full_df["一级行业"] != "未知"]

        # 保存原始数据深拷贝，供覆盖规则变更后重新计算
        self._load_df = df.copy()

        # 自动把 Excel 中出现的行业合并到数据字典
        self._raw_df = full_df[["一级行业", "二级行业", "最终客户名称"]].copy()
        merge_from_dataframe(self._raw_df)

        # 应用人工设定的行业覆盖规则（对完整 df，确保行业和金额对齐）
        full_df = apply_overrides(full_df)

        # 更新 _raw_df 以反映覆盖后的行业值（供下钻使用）
        self._raw_df = full_df[["一级行业", "二级行业", "最终客户名称"]].copy()

        return compute_industry_stats(full_df)

    def _on_header_click(self, col: str) -> None:
        """表头点击排序 — 一级行业列不参与排序（行业总金额及各年份可排序）。"""
        if col == "一级行业":
            return
        super()._on_header_click(col)

    # ------------------------------------------------------------
    # 行业覆盖管理
    # ------------------------------------------------------------
    def _open_override_manager(self) -> None:
        """打开行业覆盖管理弹窗（增删改查）。"""
        self._show_override_manager()

    def _refresh_tab_after_override(self) -> None:
        """覆盖规则变更后，刷新当前 Tab 的主表数据。"""
        from tkinter import messagebox
        if self._load_df is None or self.tree is None:
            return
        try:
            new_data = self.compute_data(self._load_df)
            self.populate(new_data)
            self.tree.update_idletasks()
            self.frame.update_idletasks()
        except Exception as e:
            messagebox.showerror("刷新失败", f"应用行业覆盖规则时出错:\n{e}", parent=self.frame)

    def _edit_customer_industry(self, customer_name: str) -> None:
        """从客户右键菜单触发：快速修正某个客户的行业。"""
        self._show_override_edit_dialog(customer_name)

    # ------------------------------------------------------------
    # 数据字典弹窗
    # ------------------------------------------------------------
    def _show_data_dict_dialog(self) -> None:
        """管理一级行业 / 二级行业字典的弹窗。"""
        popup = ctk.CTkToplevel(self.frame)
        popup.title("行业数据字典")
        popup.geometry("550x460")
        popup.resizable(True, True)
        popup.transient(self.frame)
        popup.grab_set()
        center_window(popup, 550, 460)

        notebook = ttk.Notebook(popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ------------- 一级行业 Tab -------------
        tab1 = ctk.CTkFrame(notebook, fg_color="transparent")
        notebook.add(tab1, text="一级行业")

        _build_dict_tab(tab1, "一级行业", dict_primary, add_primary, remove_primary, on_change=self._refresh_tab_after_override)

        # ------------- 二级行业 Tab -------------
        tab2 = ctk.CTkFrame(notebook, fg_color="transparent")
        notebook.add(tab2, text="二级行业")

        _build_dict_tab(tab2, "二级行业", dict_secondary, add_secondary, remove_secondary, on_change=self._refresh_tab_after_override)

        # 关闭按钮
        ctk.CTkButton(
            popup, text="关闭", command=popup.destroy,
            font=FONT_MAIN, width=80, height=30,
            fg_color="gray", hover_color="#666",
            corner_radius=6,
        ).pack(pady=(0, 10))

    # ------------------------------------------------------------
    # 弹窗：覆盖规则管理 & 编辑对话框
    # ------------------------------------------------------------
    def _show_override_manager(self) -> None:
        """管理全部行业覆盖规则的弹窗。"""
        popup = ctk.CTkToplevel(self.frame)
        popup.title("行业覆盖规则管理")
        popup.geometry("620x560")
        popup.resizable(True, True)
        popup.transient(self.frame)
        popup.grab_set()
        center_window(popup, 620, 560)

        # 工具栏
        toolbar = ctk.CTkFrame(popup, fg_color="transparent")
        toolbar.pack(fill=tk.X, padx=10, pady=(8, 4))

        count_label = ctk.CTkLabel(toolbar, text="", font=FONT_SMALL)

        def _update_count():
            data = get_all()
            count_label.configure(text=f"共 {len(data)} 条规则")

        _update_count()
        ctk.CTkLabel(
            toolbar, text="行业覆盖规则",
            font=FONT_TITLE, text_color="#1F6AA5",
        ).pack(side=tk.LEFT, padx=(4, 8))
        count_label.pack(side=tk.LEFT)

        ctk.CTkButton(
            toolbar, text="新增规则",
            command=lambda: self._show_override_edit_dialog("", popup, _fill),
            font=FONT_SMALL, width=80, height=26,
            fg_color="#1F6AA5", hover_color="#155485",
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=(4, 4))

        # 表格
        table_frame = ctk.CTkFrame(popup, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
        columns = ["#", "客户名称", "一级行业", "二级行业"]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        tree.heading("#", text="#", anchor="center")
        tree.column("#", anchor="center", width=40, minwidth=40, stretch=False)
        tree.heading("客户名称", text="客户名称", anchor="center")
        tree.column("客户名称", anchor="center", width=200, minwidth=100, stretch=True)
        tree.heading("一级行业", text="一级行业", anchor="center")
        tree.column("一级行业", anchor="center", width=150, minwidth=80, stretch=True)
        tree.heading("二级行业", text="二级行业", anchor="center")
        tree.column("二级行业", anchor="center", width=150, minwidth=80, stretch=True)

        def _fill():
            tree.delete(*tree.get_children())
            data = get_all()
            for i, (cust, mapping) in enumerate(data.items(), 1):
                tree.insert("", tk.END, values=(str(i), cust, mapping["一级行业"], mapping["二级行业"]))
            _update_count()

        _fill()

        def _on_edit():
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if not vals:
                return
            self._show_override_edit_dialog(str(vals[1]), popup, _fill)

        def _on_delete():
            sel = tree.selection()
            if not sel:
                return
            names = []
            for s in sel:
                vals = tree.item(s, "values")
                if vals:
                    names.append(str(vals[1]))

            if not names:
                return

            from tkinter import messagebox
            msg = f"确定要删除 {len(names)} 条规则吗？\n\n{chr(10).join(names)}"
            if not messagebox.askyesno("确认删除", msg, parent=popup):
                return
            for name in names:
                remove_override(name)
            _fill()
            self._refresh_tab_after_override()

        # 底部按钮
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        ctk.CTkButton(
            btn_frame, text="编辑", command=_on_edit,
            font=FONT_MAIN, width=70, height=28,
            fg_color="#E8960C", hover_color="#C47D0A",
            corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 4))
        ctk.CTkButton(
            btn_frame, text="删除", command=_on_delete,
            font=FONT_MAIN, width=70, height=28,
            fg_color="#C0392B", hover_color="#A93226",
            corner_radius=6,
        ).pack(side=tk.LEFT)
        ctk.CTkButton(
            btn_frame, text="关闭", command=popup.destroy,
            font=FONT_MAIN, width=70, height=28,
            fg_color="gray", hover_color="#666",
            corner_radius=6,
        ).pack(side=tk.RIGHT)

        # 双击编辑
        tree.bind("<Double-1>", lambda e: _on_edit())

    def _show_override_edit_dialog(self, customer_name: str = "", parent_popup=None, on_save=None) -> None:
        """新增 / 编辑单个客户的行业覆盖规则。
        - 客户名称输入框支持关联搜索已有客户
        - 一级/二级行业仅可从字典中选择（不可手动输入）
        """
        existing = get_all().get(customer_name.strip(), {})
        existing_primary = existing.get("一级行业", "")

        # 从数据字典获取行业选项；同时合并 raw_df 中出现的行业
        all_primary = dict_primary()
        all_secondary = dict_secondary()
        if self._raw_df is not None:
            from_raw = sorted(self._raw_df["一级行业"].dropna().unique().tolist())
            for v in from_raw:
                if v != "未知" and v not in all_primary:
                    all_primary.append(v)
            from_raw2 = sorted(self._raw_df["二级行业"].dropna().unique().tolist())
            for v in from_raw2:
                if v != "未知" and v not in all_secondary:
                    all_secondary.append(v)

        # 确保已有值在列表中
        if existing_primary and existing_primary not in all_primary:
            all_primary.insert(0, existing_primary)
        existing_secondary = existing.get("二级行业", "")
        if existing_secondary and existing_secondary not in all_secondary:
            all_secondary.insert(0, existing_secondary)

        # 所有客户名（用于搜索建议）
        customer_names: list[str] = []
        if self._raw_df is not None:
            customer_names = sorted(
                self._raw_df["最终客户名称"].dropna().astype(str).str.strip().unique().tolist()
            )

        dialog = ctk.CTkToplevel(parent_popup or self.frame)
        dialog.title(f"修正行业 — {customer_name}" if customer_name else "新增行业覆盖规则")
        dialog.geometry("440x340")
        dialog.resizable(False, False)
        dialog.transient(parent_popup or self.frame)
        dialog.grab_set()
        center_window(dialog, 440, 340)

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # ------ 客户名称（带搜索建议） ------
        ctk.CTkLabel(frame, text="客户名称:", font=FONT_MAIN).grid(
            row=0, column=0, sticky="ne", padx=(0, 8), pady=(8, 4))
        cust_var = tk.StringVar(value=customer_name)
        cust_entry = ctk.CTkEntry(frame, textvariable=cust_var, width=260)
        cust_entry.grid(row=0, column=1, sticky="w", pady=(8, 4))
        if customer_name:
            cust_entry.configure(state="disabled")

        # 搜索建议列表（仅新增模式下显示）
        suggest_frame = ctk.CTkFrame(frame, fg_color="transparent")
        suggest_listbox = None

        def _update_suggestions(*_):
            nonlocal suggest_listbox
            if customer_name:
                return
            query = cust_var.get().strip().lower()
            if not query:
                if suggest_listbox:
                    suggest_listbox.destroy()
                    suggest_listbox = None
                suggest_frame.grid_forget()
                return
            matches = [n for n in customer_names if query in n.lower()][:10]
            if not matches:
                if suggest_listbox:
                    suggest_listbox.destroy()
                    suggest_listbox = None
                suggest_frame.grid_forget()
                return

            suggest_frame.grid(row=1, column=1, sticky="ew", pady=(0, 4))
            if suggest_listbox:
                suggest_listbox.destroy()
            suggest_listbox = tk.Listbox(suggest_frame, height=min(len(matches), 6),
                                         font=("Microsoft YaHei", 10), exportselection=False)
            suggest_listbox.pack(fill=tk.BOTH, expand=True)
            for m in matches:
                suggest_listbox.insert(tk.END, m)

            def _on_select(event):
                if suggest_listbox and suggest_listbox.curselection():
                    cust_var.set(suggest_listbox.get(suggest_listbox.curselection()[0]))
                    if suggest_listbox:
                        suggest_listbox.destroy()
                        suggest_listbox = None
                    suggest_frame.grid_forget()

            suggest_listbox.bind("<<ListboxSelect>>", _on_select)

        cust_var.trace_add("write", _update_suggestions)

        # 失焦时收起建议列表
        def _on_focus_out(event):
            nonlocal suggest_listbox
            if suggest_listbox:
                dialog.after(150, lambda: (
                    suggest_listbox.destroy() if suggest_listbox else None,
                    suggest_frame.grid_forget(),
                ))

        cust_entry.bind("<FocusOut>", _on_focus_out)

        # ------ 一级行业（仅可选择） ------
        ctk.CTkLabel(frame, text="一级行业:", font=FONT_MAIN).grid(
            row=2, column=0, sticky="e", padx=(0, 8), pady=4)
        primary_var = tk.StringVar(value=existing_primary)
        primary_opts = all_primary if all_primary else ["（无）"]
        primary_menu = ctk.CTkOptionMenu(frame, variable=primary_var, values=primary_opts, width=260)
        primary_menu.grid(row=2, column=1, sticky="w", pady=4)

        # ------ 二级行业（仅可选择） ------
        ctk.CTkLabel(frame, text="二级行业:", font=FONT_MAIN).grid(
            row=3, column=0, sticky="e", padx=(0, 8), pady=4)
        secondary_var = tk.StringVar(value=existing_secondary)
        secondary_opts = all_secondary if all_secondary else ["（无）"]
        secondary_menu = ctk.CTkOptionMenu(frame, variable=secondary_var, values=secondary_opts, width=260)
        secondary_menu.grid(row=3, column=1, sticky="w", pady=4)

        # ------ 按钮 ------
        p = ctk.CTkFrame(dialog, fg_color="transparent")
        p.pack(fill=tk.X, padx=16, pady=(0, 16))

        def _save():
            name = cust_var.get().strip()
            primary = primary_var.get().strip()
            secondary = secondary_var.get().strip()
            if not name:
                return
            if primary == "（无）":
                primary = ""
            if secondary == "（无）":
                secondary = ""
            if not primary and not secondary:
                remove_override(name)
            else:
                set_override(name, primary, secondary)
            dialog.destroy()
            self._refresh_tab_after_override()
            if on_save:
                on_save()

        ctk.CTkButton(
            p, text="保存", command=_save,
            font=FONT_MAIN, width=80, height=30,
            fg_color="#1F6AA5", hover_color="#155485",
            corner_radius=6,
        ).pack(side=tk.LEFT, padx=(0, 4))

        ctk.CTkButton(
            p, text="取消", command=dialog.destroy,
            font=FONT_MAIN, width=80, height=30,
            fg_color="gray", hover_color="#666",
            corner_radius=6,
        ).pack(side=tk.LEFT)

    # ------------------------------------------------------------
    # 下钻弹窗
    # ------------------------------------------------------------
    def _handle_double_click(self, event) -> None:
        """双击一级行业 → 弹出二级行业统计窗口。"""
        tree = self.tree
        if tree is None:
            return
        region = tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col_id = tree.identify_column(event.x)
        item = tree.selection()
        if not item:
            return
        values = tree.item(item[0], "values")
        if not values:
            return

        primary = str(values[1])
        log_info(f"行业统计下钻: 一级行业「{primary}」")
        self._show_secondary_popup(primary)

    def _show_secondary_popup(self, primary: str) -> None:
        """弹出二级行业统计窗口。"""
        from data_processor import get_secondary_industries

        if self._raw_df is None:
            return

        popup = ctk.CTkToplevel(self.frame)
        popup.title(f"一级行业「{primary}」— 二级行业统计")
        popup.geometry("520x420")
        popup.resizable(True, True)
        popup.transient(self.frame)
        popup.grab_set()
        center_window(popup, 520, 420)

        df = get_secondary_industries(self._raw_df, primary)

        # 工具栏
        toolbar = ctk.CTkFrame(popup, fg_color="transparent")
        toolbar.pack(fill=tk.X, padx=10, pady=(8, 4))

        ctk.CTkLabel(
            toolbar,
            text=f"一级行业「{primary}」的二级行业统计",
            font=FONT_TITLE, text_color="#1F6AA5",
        ).pack(side=tk.LEFT, padx=(4, 16))

        ctk.CTkButton(
            toolbar, text="导出 CSV",
            command=lambda: export_to_csv(df, popup, f"二级行业_{primary}.csv"),
            font=FONT_SMALL, width=80, height=26,
            fg_color="#1F6AA5", hover_color="#155485",
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=(4, 4))

        # 表格区域
        table_frame = ctk.CTkFrame(popup, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ["#", "二级行业", "数量"]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 配置列（含序号列）
        tree.heading("#", text="#", anchor="center")
        tree.column("#", anchor="center", width=50, minwidth=40, stretch=False)
        tree.heading("二级行业", text="二级行业", anchor="center")
        tree.column("二级行业", anchor="center", width=300, minwidth=150, stretch=True)
        tree.heading("数量", text="数量", anchor="center",
                     command=lambda: _sort_popup_tree(tree, df, "数量"))
        tree.column("数量", anchor="center", width=100, minwidth=60, stretch=True)

        # 排序状态
        _sort_state = {"col": None, "asc": True}

        def _sort_popup_tree(tv, src_df, col):
            if col == _sort_state["col"]:
                _sort_state["asc"] = not _sort_state["asc"]
            else:
                _sort_state["col"] = col
                _sort_state["asc"] = False  # 首次点击降序
            sorted_df = src_df.sort_values(col, ascending=_sort_state["asc"]).reset_index(drop=True)
            arrow = " ▲" if _sort_state["asc"] else " ▼"
            tv.heading("数量", text="数量" + arrow,
                       command=lambda: _sort_popup_tree(tv, sorted_df, "数量"))
            tv.delete(*tv.get_children())
            for i, (_, r) in enumerate(sorted_df.iterrows(), 1):
                tv.insert("", tk.END, values=(str(i), r["二级行业"], int(r["数量"])))

        # 填入数据
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            tree.insert("", tk.END, values=(str(idx), row["二级行业"], int(row["数量"])))

        # 双击二级行业 → 显示客户名单
        def on_double_click(event):
            region_dc = tree.identify_region(event.x, event.y)
            if region_dc != "cell":
                return
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if not vals:
                return
            secondary = str(vals[1])
            log_info(f"行业统计下钻: 二级行业「{secondary}」→ 客户名单")
            self._show_customers_popup(primary, secondary, popup)

        tree.bind("<Double-1>", on_double_click)

        # 关闭按钮
        ctk.CTkButton(
            popup, text="关闭", command=popup.destroy,
            font=FONT_MAIN, width=80, height=30,
            fg_color="gray", hover_color="#666",
            corner_radius=6,
        ).pack(pady=(0, 10))

    def _show_customers_popup(self, primary: str, secondary: str, parent_popup) -> None:
        """弹出客户名单窗口。"""
        from data_processor import get_industry_customers

        if self._raw_df is None:
            return

        popup = ctk.CTkToplevel(parent_popup)
        popup.title(f"二级行业「{secondary}」— 客户名单")
        popup.geometry("480x400")
        popup.resizable(True, True)
        popup.transient(parent_popup)
        popup.grab_set()
        center_window(popup, 480, 400)

        df = get_industry_customers(self._raw_df, primary, secondary)

        # 工具栏
        toolbar = ctk.CTkFrame(popup, fg_color="transparent")
        toolbar.pack(fill=tk.X, padx=10, pady=(8, 4))

        ctk.CTkLabel(
            toolbar,
            text=f"二级行业「{secondary}」的客户名单",
            font=FONT_TITLE, text_color="#1F6AA5",
        ).pack(side=tk.LEFT, padx=(4, 16))

        ctk.CTkLabel(
            toolbar,
            text=f"共 {len(df)} 个客户",
            font=FONT_SMALL,
        ).pack(side=tk.LEFT)

        ctk.CTkButton(
            toolbar, text="导出 CSV",
            command=lambda: export_to_csv(df, popup, f"客户名单_{secondary}.csv"),
            font=FONT_SMALL, width=80, height=26,
            fg_color="#1F6AA5", hover_color="#155485",
            corner_radius=6,
        ).pack(side=tk.RIGHT, padx=(4, 4))

        # 表格区域
        table_frame = ctk.CTkFrame(popup, fg_color="transparent")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ["#", "最终客户名称"]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        tree.heading("#", text="#", anchor="center")
        tree.column("#", anchor="center", width=50, minwidth=40, stretch=False)
        tree.heading("最终客户名称", text="最终客户名称", anchor="center")
        tree.column("最终客户名称", anchor="center", width=300, minwidth=150, stretch=True)

        for idx, (_, row) in enumerate(df.iterrows(), 1):
            tree.insert("", tk.END, values=(str(idx), row["最终客户名称"]))

        # 右键菜单：修正行业
        def _on_right_click(event):
            item = tree.identify_row(event.y)
            if not item:
                return
            vals = tree.item(item, "values")
            if not vals:
                return
            customer = str(vals[1])

            menu = tk.Menu(popup, tearoff=0)
            menu.add_command(
                label=f"修正「{customer}」的行业",
                command=lambda: self._edit_customer_industry(customer),
            )
            menu.post(event.x_root, event.y_root)

        tree.bind("<Button-3>", _on_right_click)

        ctk.CTkButton(
            popup, text="关闭", command=popup.destroy,
            font=FONT_MAIN, width=80, height=30,
            fg_color="gray", hover_color="#666",
            corner_radius=6,
        ).pack(pady=(0, 10))
