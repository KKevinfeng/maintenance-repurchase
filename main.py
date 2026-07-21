"""合同数据处理工具 - 入口文件"""

import customtkinter as ctk
from ui import MaintenanceApp


def main():
    root = ctk.CTk()
    app = MaintenanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
