"""日志配置与工具"""

from __future__ import annotations

import logging
import os
import sys
import traceback


def get_log_path() -> str:
    """返回日志文件路径（项目根目录下的 error.log）。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        # ui/logger.py → ui/ → 项目根目录
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "error.log")


def _setup_logger() -> logging.Logger:
    """创建仅写入文件的日志记录器（utf-8）。"""
    logger = logging.getLogger("maintenance_app")
    logger.setLevel(logging.ERROR)
    logger.handlers.clear()
    handler = logging.FileHandler(get_log_path(), encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s]  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


APP_LOGGER = _setup_logger()


def log_error(message: str) -> None:
    """向日志文件写入一条带时间戳和堆栈的错误条目。"""
    APP_LOGGER.error(f"{message}\n{traceback.format_exc()}")
