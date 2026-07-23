"""产品名称合并对话框 —— 用户选择和配置产品名称合并规则"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from ui.logger import log_info


class ProductMergeDialog:
    """产品名称合并配置弹窗。

    左侧：全部产品列表（多选、搜索、A-Z 排序）
    右侧：已有合并规则展示
    底部：显示名称输入 + 操作按钮
    """

    def __init__(
        self,
        parent,
        product_names: list[str],
        merge_rules: dict,
        on_apply,
    ):
        self.parent = parent
        # A-Z 排序（英文不区分大小写，中文按 Unicode 顺序兜底）
        self.all_product_names = sorted(product_names, key=lambda s: s.lower())
        self.displayed_product_names = list(self.all_product_names)
        self.merge_rules: dict[str, set[str]] = {
            k: set(v) for k, v in merge_rules.items()
        }
        self.on_apply = on_apply

        self._build()

    @classmethod
    def show(cls, parent, product_names, merge_rules, on_apply):
        dialog = cls(parent, product_names, merge_rules, on_apply)
        dialog.win.focus()
        dialog.win.wait_window()

    # ── 构建 UI ────────────────────────────────────────────

    def _build(self):
        self.win = ctk.CTkToplevel(self.parent)
        self.win.title("产品名称合并")
        self.win.geometry("800x600")
        self.win.resizable(True, True)
        self.win.minsize(780, 460)
        self.win.transient(self.parent)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self.win.grab_set()

        self._center_on_parent()

        # 标题说明
        title_frame = ctk.CTkFrame(self.win, fg_color="transparent")
        title_frame.pack(fill=tk.X, padx=16, pady=(14, 6))
        ctk.CTkLabel(
            title_frame,
            text="将名称相似、实为同一类的产品合并为一个名称进行统计",
            font=("Microsoft YaHei", 13),
            text_color="#666666",
        ).pack(anchor="w")

        # ── 主体区域 ──
        content = ctk.CTkFrame(self.win, fg_color="transparent")
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self._build_left_panel(content)
        self._build_right_panel(content)
        self._build_bottom_bar()

        # 初始刷新右侧规则的计数显示
        self._update_rule_count()

    def _center_on_parent(self):
        self.win.update_idletasks()
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()
        px = self.parent.winfo_rootx()
        py = self.parent.winfo_rooty()
        x = px + (pw - 800) // 2
        y = py + (ph - 600) // 2
        self.win.geometry(f"+{x}+{y}")

    # ── 左侧：产品列表（含搜索） ─────────────────────────────

    def _build_left_panel(self, content):
        left = ctk.CTkFrame(content, corner_radius=8, fg_color="#FAFAFA")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(left, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        ctk.CTkLabel(
            header, text="全部产品",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(side=tk.LEFT)
        self.product_count_label = ctk.CTkLabel(
            header,
            text=f"（共 {len(self.all_product_names)} 个，Ctrl/Shift 多选）",
            font=("Microsoft YaHei", 10),
            text_color="#999999",
        )
        self.product_count_label.pack(side=tk.LEFT, padx=(6, 0))

        # 搜索框
        search_frame = ctk.CTkFrame(left, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 4))
        search_frame.columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            font=("Microsoft YaHei", 11),
            height=28,
            placeholder_text="输入关键词搜索产品名称",
            corner_radius=6,
        )
        search_entry.grid(row=0, column=0, sticky="ew")

        # Listbox 容器
        lb_container = tk.Frame(left, bg="#1F6AA5")  # 边框色
        lb_container.grid(row=2, column=0, sticky="nsew", padx=8, pady=(2, 8))
        lb_container.rowconfigure(0, weight=1)
        lb_container.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            lb_container,
            selectmode=tk.EXTENDED,
            font=("Microsoft YaHei", 11),
            bg="#FFFFFF",
            fg="#333333",
            selectbackground="#1F6AA5",
            selectforeground="#FFFFFF",
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            exportselection=False,
        )
        scrollbar = tk.Scrollbar(lb_container, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=1)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)

        self._fill_listbox()

    def _fill_listbox(self):
        """根据当前 displayed_product_names 填充列表。"""
        self.listbox.delete(0, tk.END)
        for name in self.displayed_product_names:
            self.listbox.insert(tk.END, name)

    def _on_search_change(self, *args):
        """搜索框内容变化时过滤产品列表。"""
        keyword = self.search_var.get().strip().lower()
        if keyword:
            self.displayed_product_names = [
                n for n in self.all_product_names
                if keyword in n.lower()
            ]
        else:
            self.displayed_product_names = list(self.all_product_names)

        self._fill_listbox()
        self.product_count_label.configure(
            text=f"（共 {len(self.all_product_names)} 个，显示 {len(self.displayed_product_names)} 个）"
        )

    # ── 右侧：合并规则 ─────────────────────────────────────

    def _build_right_panel(self, content):
        right = ctk.CTkFrame(content, corner_radius=8, fg_color="#FAFAFA")
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(right, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        ctk.CTkLabel(
            header, text="合并规则",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(side=tk.LEFT)
        self.rule_count_label = ctk.CTkLabel(
            header, text="",
            font=("Microsoft YaHei", 11),
            text_color="#888888",
        )
        self.rule_count_label.pack(side=tk.LEFT, padx=(8, 0))

        self.rules_scroll = ctk.CTkScrollableFrame(
            right, corner_radius=6, fg_color="transparent",
        )
        self.rules_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=(2, 4))

        self._refresh_rules()

    def _update_rule_count(self):
        count = len(self.merge_rules)
        self.rule_count_label.configure(text=f"共 {count} 条")

    # ── 底部操作栏（使用 grid 避免按钮被挤压） ───────────────

    def _build_bottom_bar(self):
        bottom = ctk.CTkFrame(self.win, fg_color="transparent")
        bottom.pack(fill=tk.X, padx=16, pady=(4, 12))
        bottom.columnconfigure(3, weight=1)  # 中间弹性占位

        ctk.CTkLabel(
            bottom, text="合并后显示名称：",
            font=("Microsoft YaHei", 11),
        ).grid(row=0, column=0, sticky="w")

        self.display_name_var = tk.StringVar()
        ctk.CTkEntry(
            bottom,
            textvariable=self.display_name_var,
            font=("Microsoft YaHei", 11),
            width=200, height=30,
            placeholder_text="输入统一显示的名称",
            corner_radius=6,
        ).grid(row=0, column=1, sticky="w", padx=(4, 10))

        ctk.CTkButton(
            bottom, text="添加规则", command=self._add_rule,
            font=("Microsoft YaHei", 11), width=90, height=30,
            corner_radius=6, fg_color="#1F6AA5", hover_color="#144870",
        ).grid(row=0, column=2, sticky="w")

        ctk.CTkButton(
            bottom, text="清空全部", command=self._clear_all,
            font=("Microsoft YaHei", 11), width=100, height=30,
            corner_radius=6,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0",
        ).grid(row=0, column=4, sticky="e", padx=(8, 0))

        ctk.CTkButton(
            bottom, text="应用并刷新", command=self._apply,
            font=("Microsoft YaHei", 11, "bold"), width=130, height=30,
            corner_radius=6, fg_color="#1F6AA5", hover_color="#144870",
        ).grid(row=0, column=5, sticky="e", padx=(8, 0))

    # ── 规则显示 ───────────────────────────────────────────

    def _refresh_rules(self):
        for w in self.rules_scroll.winfo_children():
            w.destroy()

        self._update_rule_count()

        if not self.merge_rules:
            ctk.CTkLabel(
                self.rules_scroll,
                text="暂无合并规则\n\n在左侧选择多个产品，\n输入合并后的显示名称，\n点击「添加规则」即可",
                font=("Microsoft YaHei", 12),
                text_color="#BBBBBB",
                justify="center",
            ).pack(pady=40)
            return

        for display_name, names in self.merge_rules.items():
            card = ctk.CTkFrame(
                self.rules_scroll, corner_radius=8,
                fg_color="#E8F0FE",
            )
            card.pack(fill=tk.X, pady=(0, 8), padx=2)

            # 显示名称
            name_row = ctk.CTkFrame(card, fg_color="transparent")
            name_row.pack(fill=tk.X, padx=10, pady=(8, 2))
            ctk.CTkLabel(
                name_row,
                text=display_name,
                font=("Microsoft YaHei", 13, "bold"),
                text_color="#1F6AA5",
            ).pack(side=tk.LEFT)

            # 包含产品
            products_text = "、".join(sorted(names))
            ctk.CTkLabel(
                card,
                text=f"包含：{products_text}",
                font=("Microsoft YaHei", 10),
                text_color="#555555",
                wraplength=310,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 2))

            # 删除按钮
            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.pack(fill=tk.X, padx=8, pady=(0, 8))
            ctk.CTkButton(
                btn_row,
                text="删除此规则",
                command=lambda dn=display_name: self._delete_rule(dn),
                font=("Microsoft YaHei", 10),
                width=90, height=24,
                corner_radius=4,
                fg_color="#E57373", hover_color="#EF5350",
            ).pack(side=tk.RIGHT)

    # ── 交互逻辑 ───────────────────────────────────────────

    def _add_rule(self):
        selected = self.listbox.curselection()
        if not selected:
            messagebox.showwarning("提示", "请先在左侧列表中勾选要合并的产品（支持多选）")
            return

        names = [self.displayed_product_names[i] for i in selected]
        display_name = self.display_name_var.get().strip()

        if not display_name:
            messagebox.showwarning("提示", "请输入合并后的显示名称")
            return

        # 检查是否与已有规则冲突
        for exist_dn, exist_names in self.merge_rules.items():
            overlap = set(names) & exist_names
            if overlap:
                messagebox.showwarning(
                    "产品冲突",
                    f"以下产品已在规则「{exist_dn}」中：\n"
                    + "\n".join(f"  · {n}" for n in overlap)
                    + "\n\n请先删除冲突的规则后再添加。",
                )
                return

        self.merge_rules[display_name] = set(names)
        log_info(f"产品合并规则添加: {display_name} ← {names}")
        self.display_name_var.set("")
        self.listbox.selection_clear(0, tk.END)
        self._refresh_rules()

    def _delete_rule(self, display_name):
        del self.merge_rules[display_name]
        log_info(f"产品合并规则删除: {display_name}")
        self._refresh_rules()

    def _clear_all(self):
        if not self.merge_rules:
            return
        if messagebox.askyesno("确认", "确定要清空所有合并规则吗？"):
            self.merge_rules.clear()
            log_info("产品合并规则全部清空")
            self._refresh_rules()

    def _apply(self):
        # 释放 grab 后销毁对话框，再回调主窗口刷新
        rules = dict(self.merge_rules)
        self.win.grab_release()
        self.win.destroy()
        self.on_apply(rules)

    def _on_close(self):
        """通过 X 按钮关闭时释放 grab 并销毁。"""
        self.win.grab_release()
        self.win.destroy()
