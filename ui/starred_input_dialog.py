"""手动录入重点客户弹窗 —— 粘贴文本自动解析，校验重复，确认导入。"""

from __future__ import annotations

import re
import tkinter as tk
import customtkinter as ctk
from ui.starred_cache import StarredCache
from utils import center_window


class StarredInputDialog:
    """弹窗：粘贴客户名（任意分隔符/换行），解析后导入缓存表。"""

    def __init__(self, parent, starred_cache: StarredCache, on_done=None):
        self.starred_cache = starred_cache
        self.on_done = on_done
        self._duplicate_names: list[str] = []
        self._new_names: list[str] = []

        self.win = ctk.CTkToplevel(parent)
        self.win.title("手动录入重点客户")
        self.win.geometry("600x500")
        self.win.resizable(True, True)
        self.win.minsize(480, 360)
        self.win.attributes("-topmost", True)

        center_window(self.win, 600, 500)

        self._build_ui()

    # ── UI ──────────────────────────────────────────────────

    def _build_ui(self):
        # 提示
        ctk.CTkLabel(
            self.win,
            text="请输入/粘贴重点客户名称，支持任意符号或换行分隔：",
            font=ctk.CTkFont(size=13), text_color="#555555",
        ).pack(anchor="w", padx=20, pady=(16, 6))

        # 文本输入框
        self.textbox = ctk.CTkTextbox(
            self.win, font=ctk.CTkFont(size=13), corner_radius=8,
            border_width=1, border_color="#D0D0D0",
        )
        self.textbox.pack(fill="both", expand=True, padx=20, pady=(0, 6))

        # 重复提示区域（初始隐藏）
        self.dup_frame = ctk.CTkFrame(self.win, fg_color="#FFF3CD", corner_radius=8)

        self.dup_label = ctk.CTkLabel(
            self.dup_frame, text="",
            font=ctk.CTkFont(size=12), text_color="#856404",
            wraplength=540, justify="left",
        )
        self.dup_label.pack(side="left", fill="x", expand=True, padx=12, pady=8)

        # 按钮栏
        btn_frame = ctk.CTkFrame(self.win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(6, 14))

        ctk.CTkButton(
            btn_frame, text="取消", command=self.win.destroy,
            font=ctk.CTkFont(size=13), width=80, height=32,
            fg_color="#E0E0E0", text_color="#333333",
            hover_color="#D0D0D0", corner_radius=6,
        ).pack(side="right", padx=(6, 0))

        self.confirm_btn = ctk.CTkButton(
            btn_frame, text="确认录入", command=self._on_confirm,
            font=ctk.CTkFont(size=13), width=100, height=32,
            fg_color="#1F6AA5", text_color="#FFFFFF",
            hover_color="#144870", corner_radius=6,
        )
        self.confirm_btn.pack(side="right")

        self.filter_btn = ctk.CTkButton(
            btn_frame, text="过滤重复项并导入", command=self._on_filter_import,
            font=ctk.CTkFont(size=13), width=160, height=32,
            fg_color="#E8A838", text_color="#FFFFFF",
            hover_color="#D49622", corner_radius=6,
        )

        # 解析后的预览
        self.preview_label = ctk.CTkLabel(
            self.win, text="",
            font=ctk.CTkFont(size=12), text_color="#888888",
        )
        self.preview_label.pack(anchor="w", padx=20, pady=(0, 4))

    # ── 解析 ────────────────────────────────────────────────

    @staticmethod
    def _parse_names(text: str) -> list[str]:
        """将粘贴内容按任意分隔符拆分为客户名称列表。"""
        # 先按行、逗号、分号、中文标点等拆分
        parts = re.split(r'[\n\r,;，；、。|/\\\s\t]+', text)
        # 过滤空串，去首尾空白
        names = []
        for p in parts:
            p = p.strip().strip("'").strip('"')
            if p:
                names.append(p)
        return names

    # ── 确认 ────────────────────────────────────────────────

    def _on_confirm(self):
        """解析文本，检查重复，展示结果。"""
        text = self.textbox.get("1.0", "end-1c").strip()
        if not text:
            self._set_state("请输入客户名称")
            return

        names = self._parse_names(text)
        if not names:
            self._set_state("未识别到有效的客户名称")
            return

        # 去重（输入文本内）
        seen = set()
        unique_input: list[str] = []
        for n in names:
            if n not in seen:
                seen.add(n)
                unique_input.append(n)

        # 与缓存表碰撞
        existing = set(self.starred_cache.get_all())
        self._new_names = [n for n in unique_input if n not in existing]
        self._duplicate_names = [n for n in unique_input if n in existing]

        count_input = len(unique_input)
        count_new = len(self._new_names)
        count_dup = len(self._duplicate_names)

        self.preview_label.configure(
            text=f"共识别 {count_input} 个客户，其中新客户 {count_new} 个，与缓存重复 {count_dup} 个"
        )

        if count_new == 0:
            # 全部重复
            dup_text = "、".join(self._duplicate_names[:10])
            if len(self._duplicate_names) > 10:
                dup_text += f" 等共 {len(self._duplicate_names)} 个"
            self._set_state(f"全部 {count_input} 个客户名已在缓存表中存在：{dup_text}")
            return

        if count_dup == 0:
            # 无重复，直接导入
            self._do_import()
            return

        # 有重复，展示重复项，提供过滤按钮
        dup_display = "、".join(self._duplicate_names[:8])
        if len(self._duplicate_names) > 8:
            dup_display += f" 等共 {len(self._duplicate_names)} 个"
        self.dup_label.configure(
            text=f"以下 {len(self._duplicate_names)} 个客户名已在缓存表中存在，将被跳过：\n{dup_display}"
        )
        self.dup_frame.pack(fill="x", padx=20, pady=(0, 6))
        self.filter_btn.pack(side="right", padx=(6, 0))
        self.confirm_btn.configure(text=f"全部导入（含 {count_dup} 个重复）")

    def _on_filter_import(self):
        """过滤重复项后导入。"""
        self._do_import()

    def _do_import(self):
        """执行导入。"""
        if self._new_names:
            self.starred_cache.add_batch(self._new_names)
        self.win.destroy()
        if self.on_done:
            self.on_done(len(self._new_names))

    def _set_state(self, msg: str):
        """设置底部提示文字。"""
        self.preview_label.configure(text=msg)
