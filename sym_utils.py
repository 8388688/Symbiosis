import ctypes
import os
import sys
from typing import Mapping

__all__ = [
    "is_exec", "get_orig_path", "get_exec", "resource_path", "get_resource",
    "is_admin", "is64bitPlatform", "listdir_p_gen", "tree_fp_gen",
    "merge_config"
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
