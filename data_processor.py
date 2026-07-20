"""数据处理模块：三个 Tab 页的数据计算逻辑"""

import pandas as pd
from utils import (
    classify_contract,
    parse_product_lines,
    normalize_product_name,
    extract_contract_year,
)


# 客户总金额统计的年份范围
YEAR_RANGE = list(range(2018, 2027))  # 2018 ~ 2026


def compute_customer_total(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tab 1：按客户汇总全部合同金额，并按年份分列展示，降序排列。

    返回:
        DataFrame[最终客户名称, 合同总金额, 2018, 2019, ..., 2026]
    """
    df = df.copy()
    df["年份"] = df["合同编号*"].apply(extract_contract_year)

    # 按客户 × 年份透视
    pivot = df.pivot_table(
        values="合同金额（元）*",
        index="最终客户名称",
        columns="年份",
        aggfunc="sum",
        fill_value=0.0,
    )

    # 确保 2018~2026 每年都有列
    for y in YEAR_RANGE:
        if y not in pivot.columns:
            pivot[y] = 0.0

    # 按年份排序
    pivot = pivot[YEAR_RANGE]

    # 合同总金额 = 各年之和
    pivot["合同总金额"] = pivot.sum(axis=1)

    # 列名处理：年份列保持整数，便于排序
    pivot.columns = [str(col) for col in pivot.columns[: len(YEAR_RANGE)]] + ["合同总金额"]

    # 调整列顺序：客户名称 → 合同总金额 → 2018...2026
    pivot = pivot.reset_index()
    pivot = pivot[["最终客户名称", "合同总金额"] + [str(y) for y in YEAR_RANGE]]
    pivot = pivot.sort_values("合同总金额", ascending=False).reset_index(drop=True)
    return pivot


def compute_customer_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tab 2：按客户分别统计维保(M)、产品(P)、服务(S)三类合同金额。

    返回:
        DataFrame[最终客户名称, 维保合同总金额, 产品合同总金额, 服务合同总金额, 合计总金额]
    """
    df = df.copy()
    df["合同类型"] = df["合同编号*"].apply(classify_contract)

    # 透视表：客户 × 合同类型
    pivot = df.pivot_table(
        values="合同金额（元）*",
        index="最终客户名称",
        columns="合同类型",
        aggfunc="sum",
        fill_value=0,
    )

    # 确保 M/P/S 三列都存在
    for col in ["M", "P", "S"]:
        if col not in pivot.columns:
            pivot[col] = 0.0

    pivot = pivot[["M", "P", "S"]]
    pivot.columns = ["维保合同总金额", "产品合同总金额", "服务合同总金额"]
    pivot["合计总金额"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("合计总金额", ascending=False).reset_index()

    return pivot


def compute_product_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tab 3：按产品名称汇总售卖台数。
    - 排除 M（维保）类合同
    - 从产品名称型号列解析每行数据

    返回:
        DataFrame[产品名称, 售卖总台数]
    """
    df = df.copy()
    df["合同类型"] = df["合同编号*"].apply(classify_contract)

    # 排除维保合同
    df_non_m = df[df["合同类型"] != "M"]

    # 解析产品行并汇总（先归一化产品名称）
    product_totals: dict[str, int] = {}
    for _, row in df_non_m.iterrows():
        products = parse_product_lines(row["产品名称型号"])
        for p in products:
            name = normalize_product_name(p["name"])
            product_totals[name] = product_totals.get(name, 0) + p["qty"]

    result = pd.DataFrame(
        [{"产品名称": k, "售卖总台数": v} for k, v in product_totals.items()]
    ).sort_values("售卖总台数", ascending=False).reset_index(drop=True)

    return result
