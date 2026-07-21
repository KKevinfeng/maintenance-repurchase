"""Tab 3：产品销量统计"""

from ui.base_tab import BaseTab
from data_processor import compute_product_sales


class ProductSalesTab(BaseTab):
    """产品销量统计页 —— 展示各产品售卖台数。"""

    def __init__(self, master, on_double_click=None):
        super().__init__(
            master=master,
            tab_name="产品销量统计",
            columns=["产品名称", "售卖总台数"],
            on_double_click=on_double_click,
        )

    def compute_data(self, raw_df):
        return compute_product_sales(raw_df)
