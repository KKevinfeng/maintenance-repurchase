"""维保复购数据处理程序 - 入口文件"""

import tkinter as tk
from ui import MaintenanceApp


def main():
    root = tk.Tk()
    app = MaintenanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
