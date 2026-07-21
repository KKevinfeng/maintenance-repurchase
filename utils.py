"""工具函数模块：合同类型识别、产品名称型号列解析、窗口居中"""

from __future__ import annotations

import re
import tkinter as tk
import pandas as pd


def center_window(win: tk.Tk | tk.Toplevel, width: int, height: int) -> None:
    """将窗口定位到屏幕中央。

    参数:
        win: Tk 或 Toplevel 窗口实例
        width: 窗口宽度（像素）
        height: 窗口高度（像素）

    调用时机: 在 win.geometry(...) 之后调用。
    """
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - width) // 2
    y = (sh - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")

# 合同编号正则：匹配 -M/P/S 后跟数字的模式
CONTRACT_TYPE_PATTERN = re.compile(r'-(M|P|S)\d')

# 合同年份正则：提取第一个 "-" 前的两位数字年份
CONTRACT_YEAR_PATTERN = re.compile(r'(\d{2})-')

# 合同类型中文映射
TYPE_LABEL = {
    "M": "维保",
    "P": "产品",
    "S": "服务",
}


def extract_contract_year(contract_id: str) -> int | None:
    """
    从合同编号中提取年份。
    规则：第一个 "-" 前面的两位数字代表年份，如 "26" → 2026。

    参数:
        contract_id: 合同编号字符串，如 "AH26-M07-0091"

    返回:
        四位年份整数，无法识别返回 None

    示例:
        "AH26-M07-0091" -> 2026
        "AH18-P03-0012" -> 2018
    """
    if pd.isna(contract_id):
        return None
    match = CONTRACT_YEAR_PATTERN.search(str(contract_id))
    if match:
        yy = int(match.group(1))
        return 2000 + yy
    return None


def classify_contract(contract_id: str) -> str | None:
    """
    根据合同编号识别合同类型。

    参数:
        contract_id: 合同编号字符串

    返回:
        "M"（维保）/ "P"（产品）/ "S"（服务），无法识别返回 None

    示例:
        "AH26-M07-0091" -> "M"
        "AH26-P07-0058" -> "P"
        "AH26-S07-0037" -> "S"
    """
    if pd.isna(contract_id):
        return None
    match = CONTRACT_TYPE_PATTERN.search(str(contract_id))
    return match.group(1) if match else None


# 产品名称需要去掉的前缀，用于归一化
_PRODUCT_NAME_PREFIXES = ["明御", "明鉴"]


def normalize_product_name(name: str) -> str:
    """
    归一化产品名称：去掉"明御""明鉴"等品牌前缀，
    使得"明御综合日志审计平台"和"综合日志审计平台"被视为同一产品。

    参数:
        name: 原始产品名称

    返回:
        归一化后的产品名称
    """
    name = name.strip()
    for prefix in _PRODUCT_NAME_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix):
            return name[len(prefix):].strip()
    return name


def parse_product_lines(cell_value) -> list[dict]:
    """
    解析产品名称型号列，提取每条产品信息。

    该列可能包含多行（\\n 分隔），每行格式：
      - "产品名称 | 产品型号 | 数量"（3 段）
      - "产品名称 | 数量"（2 段，无型号）

    参数:
        cell_value: 单元格原始值

    返回:
        [{"name": str, "model": str|None, "qty": int}, ...]

    示例:
        "设备A | X100 | 5\\n设备B | 3"
        -> [{"name": "设备A", "model": "X100", "qty": 5},
            {"name": "设备B", "model": None, "qty": 3}]
    """
    if pd.isna(cell_value):
        return []

    results = []
    for line in str(cell_value).split('\n'):
        line = line.strip()
        if not line:
            continue

        parts = [p.strip() for p in line.split('|')]

        if len(parts) == 3:
            # 产品名称 | 产品型号 | 数量
            try:
                qty = int(float(parts[2]))
                results.append({"name": parts[0], "model": parts[1], "qty": qty})
            except (ValueError, IndexError):
                continue
        elif len(parts) == 2:
            # 产品名称 | 数量（无型号）
            try:
                qty = int(float(parts[1]))
                results.append({"name": parts[0], "model": None, "qty": qty})
            except (ValueError, IndexError):
                continue
        # 其他格式（1段或>3段）跳过

    return results
