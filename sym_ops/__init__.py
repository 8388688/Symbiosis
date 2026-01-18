# 保留原有的时间检查相关函数（向后兼容）
from .file_deleter import FileDeleter, DeletionError
from .downloader import Downloader, DownloadError
from .executor import Executor, ExecutionError
import re
import time

__all__ = [
    "check_time",
    "decode_datetime",
    "Executor",
    "Downloader",
    "FileDeleter",
    "ExecutionError",
    "DownloadError",
    "DeletionError",
]


def decode_datetime(date_str: str):
    return time.mktime(time.strptime(date_str, "%Y/%m/%d"))


def check_time(time_str):
    return re.search(
        r"(\d+\/\d+\/\d+)?\s*\.\.\s*(\d+\/\d+\/\d+)?",
        time_str, re.I
    )


# 导入新的操作类
