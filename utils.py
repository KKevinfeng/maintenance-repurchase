"""工具函数模块：合同类型识别、产品名称型号列解析"""

import re
import pandas as pd

# 合同编号正则：匹配 -M/P/S 后跟数字的模式
CONTRACT_TYPE_PATTERN = re.compile(r'-(M|P|S)\d')

# 合同类型中文映射
TYPE_LABEL = {
    "M": "维保",
    "P": "产品",
    "S": "服务",
}


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
