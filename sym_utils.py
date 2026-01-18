import ctypes
import os
import sys
from typing import Mapping

__all__ = [
    "is_exec", "get_orig_path", "get_exec", "resource_path", "get_resource",
    "is_admin", "is64bitPlatform", "listdir_p_gen", "tree_fp_gen",
    "merge_config", "ConfigReader"
]


def is_exec():
    return hasattr(sys, "_MEIPASS")


def get_orig_path():
    # 获取脚本的【py文件】所在路径
    return os.path.dirname(os.path.abspath(__file__))


def get_exec():
    if is_exec():
        return sys.executable
    else:
        return os.path.abspath(__file__)


def resource_path(*relative):
    return os.path.join(os.path.dirname(get_exec()), *relative)


get_resource = resource_path


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        return False


def is64bitPlatform() -> bool:
    return sys.maxsize == 2 ** 63 - 1


def listdir_p_gen(__fp):
    for i in os.listdir(__fp):
        yield os.path.join(__fp, i)


def tree_fp_gen(__fp, folders, topdown=True):
    if os.path.isfile(__fp):
        yield __fp
    else:
        if folders and not topdown:
            yield __fp
        for i in listdir_p_gen(__fp):
            for j in tree_fp_gen(i, folders, topdown):
                yield j
        if folders and topdown:
            yield __fp


def merge_config(conf1, conf2, ip=False):
    # conf1 <-- conf2
    res = conf1.copy()
    for k, v in conf2.items():
        if k in res.keys() and isinstance(v, Mapping):
            res[k].update(merge_config(res[k], v))
        else:
            res.update({k: v})
    if ip:
        conf1.clear()
        conf1.update(res)
    return res


class ConfigReader:
    """统一的配置读取工具

    优先级：
    1. 从 config 参数中读取
    2. 从 global_settings 中读取
    3. 使用内置缺省参数
    """

    def __init__(self, global_settings: dict = None):
        """初始化配置读取器

        Args:
            global_settings: 全局设置字典
        """
        self.global_settings = global_settings or {}

    def get(self, config: dict, key: str, default=None):
        """读取配置值

        Args:
            config: 本地配置字典
            key: 配置键
            default: 内置缺省参数

        Returns:
            配置值，优先级：config > global_settings > default
        """
        # 首先从 config 中读取
        if key in config:
            value = config.get(key)
            if value is not None:
                return value

        # 其次从 global_settings 中读取
        if key in self.global_settings:
            value = self.global_settings.get(key)
            if value is not None:
                return value

        # 最后使用缺省参数
        return default

    def get_multi(self, config: dict, keys: dict) -> dict:
        """批量读取配置值

        Args:
            config: 本地配置字典
            keys: {配置键: 缺省值} 的字典

        Returns:
            {配置键: 配置值} 的字典
        """
        result = {}
        for key, default in keys.items():
            result[key] = self.get(config, key, default)
        return result

    def update_global_settings(self, global_settings: dict):
        """更新全局设置

        Args:
            global_settings: 新的全局设置字典
        """
        self.global_settings = global_settings or {}
