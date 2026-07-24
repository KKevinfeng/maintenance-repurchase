# 合同数据处理工具

合同数据处理桌面应用，支持多维度的合同统计、客户分类、行业分析及过保情况追踪。

## 项目结构

```
maintenance-repurchase-1/
│
├── main.py                         # 程序入口，初始化日志、启动 GUI
├── data_processor.py               # 核心数据处理逻辑（统计计算、合同分类、年份提取）
├── utils.py                        # 工具函数（合同编号解析、产品行拆分、年份提取、CSV 导出）
├── requirements.txt                # Python 依赖清单
├── CHANGELOG.txt                   # 版本更新日志
│
├── merge_rules.json                # 产品合并规则持久化文件
├── industry_dict.json              # 行业数据字典（一级/二级行业映射）
├── industry_overrides.json         # 行业覆盖规则（人工修正客户行业）
├── starred_customers.xlsx          # 重点客户缓存文件
│
├── logs/                           # 运行日志目录（按天归档，5MB 轮转）
│   ├── run_YYYY-MM-DD.log          # 运行日志
│   └── error.log                   # 错误日志
│
└── ui/                             # 界面模块
    ├── __init__.py                 # 包初始化，导出公共常量（字体、颜色）
    ├── main_window.py              # 主窗口：Tab 容器、菜单栏、导入进度、碰撞检测、日志入口
    ├── base_tab.py                 # Tab 基类：Treeview 表格、排序、筛选、搜索、Star、CSV 导出
    │
    ├── tab_customer_total.py       # Tab1 — 客户总金额统计（分年透视）
    ├── tab_customer_category.py    # Tab2 — 客户分类金额统计（维保/产品/服务）
    ├── tab_expiry_stats.py         # Tab3 — 过保情况统计（含意向筛选）
    ├── tab_product_sales.py        # Tab4 — 产品销量统计（含产品合并规则）
    ├── tab_industry.py             # Tab5 — 行业统计（客户数/金额/分年，支持下钻）
    │
    ├── industry_dict.py            # 行业数据字典管理（增删一级/二级行业）
    ├── industry_overrides.py       # 行业覆盖规则管理（客户行业人工修正）
    │
    ├── detail_window.py            # 客户合同详情弹窗（双击客户行打开）
    ├── merge_dialog.py             # 产品合并规则编辑弹窗
    ├── column_filter_popup.py      # 列多选筛选弹窗（Tab3 及过保弹窗共用）
    ├── starred_view.py             # 查看重点客户弹窗
    ├── starred_input_dialog.py     # 手动添加重点客户弹窗
    ├── starred_cache.py            # 重点客户缓存读写
    ├── expiry_starred_view.py      # 重点客户过保合同弹窗
    ├── log_view.py                 # 查看运行日志弹窗
    ├── logger.py                   # 日志系统（按天归档、级别过滤、文件轮转）
    ├── progress_popup.py           # 导入进度弹窗
    └── styles.py                   # UI 样式常量
```

## 功能概览

| Tab | 名称 | 功能 |
|-----|------|------|
| Tab1 | 客户总金额统计 | 按客户分年统计合同总金额，支持标星重点客户 |
| Tab2 | 客户分类金额统计 | 按维保(M)/产品(P)/服务(S)三类统计各客户金额 |
| Tab3 | 过保情况统计 | 追踪重点客户的续保意向和不续保原因 |
| Tab4 | 产品销量统计 | 按产品名称汇总售卖台数，支持产品名称合并 |
| Tab5 | 行业统计 | 按一级行业统计客户数量、总金额及分年金额，支持下钻到二级行业和客户明细 |

## 运行环境

- Python 3.10+
- 依赖：`pip install -r requirements.txt`

## 启动方式

```bash
# 开发模式
python main.py

# 打包为 exe（Nuitka）
python -m nuitka --standalone --windows-console-mode=disable --enable-plugin=tk-inter --include-package-data=customtkinter --remove-output --output-dir=dist main.py
```
