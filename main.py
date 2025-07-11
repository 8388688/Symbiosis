"""
0.5 更新：
- :construction: 静默更新(BETA)
- 【破坏性更新】修整 config.json 格式
- - 加入 globalsettings
- - exec 选项可以用 disable 禁用
0.4 更新：
- 加入日志记录功能
0.3.1 紧急更新：
- 修复将全局设置项当成启动程序而读取出错 bug
- 修复在出现参数错误时静默退出的 bug —— 现在会 print 出错的参数
- 在一个版本之后，即 Symbiosis 0.4+, 将会记录日志
0.3.0 更新：
- 允许自定义配置文件路径（在 DOS 参数中设置）
- 修复配置文件路径错误的 bug
"""
import argparse
import logging.handlers
import colorlog
import ctypes
import json
import logging
import requests
import os
import sys
import time

from os import PathLike


def is_exec():
    return hasattr(sys, "_MEIPASS")


def get_exec(relative=""):
    if is_exec():
        return os.path.join(os.path.dirname(sys.executable), relative)
    else:
        # return __file__
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        return False


def run(config: dict):
    parameters_orig: list[str] = config.get("parameters", fr_json.get("parameters", []))
    parameters: str = " ".join((str(i) for i in parameters_orig))
    exec_fp: PathLike = config.get("exec")
    uac_admin: bool = config.get("uac_admin", fr_json.get("uac_admin", False))
    workdir: PathLike = config.get("workdir", fr_json.get("work_dir", os.getcwd()))
    fake: bool = config.get("disable", False)
    # if is_admin():
    #     logger.info(f"正在使用管理员权限运行 - 非常棒！")
    # else:
    #     logger.info(f"准备以管理员身份重启. . . . . .")
    if not fake:
        logger.info(f"启动: {exec_fp=}, {parameters_orig=}, {uac_admin=}, {workdir=}")
        ctypes.windll.shell32.ShellExecuteW(None, "runas" if uac_admin else None, exec_fp, parameters, workdir, 1)
    else:
        logger.info(f"假装启动: {exec_fp=}")
    # sys.exit(0)


def get_update():
    exit_code = 0

    exit_code = 1
    logger.error(f"{get_update.__name__} 尚未实现")
    return exit_code
    try:
        req = requests.get("https://raw.githubusercontent.com/8388688/Symbiosis/main/version.json")
    except ConnectionError as e:
        logger.error(f"Connect Error {e.winerror}: {e.strerror}")
        exit_code = 1
    except Exception as e:
        logger.error(f"Wildcard Error: {e.args}, {e}")
        exit_code = 1
    else:
        json_0 = req.json()
        # for i in json_0["content"]:
            # pass

    return exit_code


if not os.path.exists(get_exec("__Logs__")): os.mkdir("__Logs__")
console_formatter = colorlog.ColoredFormatter(
    "%(log_color)s[%(asctime)s.%(msecs)03d] %(filename)s -> %(name)s %(funcName)s line:%(lineno)d [%(levelname)s] : %(message)s",
    datefmt="%Y-%m-%dT%H.%M.%SZ",
    log_colors={
        "DEBUG": "white",
        "INFO": "green",
        "NOTICE": "cyan",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red,bg_white",
    }
)
file_formatter = logging.Formatter(
    "[%(asctime)s.%(msecs)03d] %(filename)s -> %(name)s %(funcName)s line:%(lineno)d [%(levelname)s] : %(message)s",
    datefmt="%Y-%m-%dT%H.%M.%SZ",
)
console = colorlog.StreamHandler()
console.setFormatter(console_formatter)
file_log = logging.FileHandler(get_exec(f"__Logs__\\{time.time() // 86400}"), encoding="utf-8")
file_log.setFormatter(file_formatter)
time_rotate_file = logging.handlers.TimedRotatingFileHandler(filename=get_exec(f"__Logs__\\time_rotate"), encoding="utf-8", when="D", interval=1)
time_rotate_file.setFormatter(file_formatter)
time_rotate_file.setLevel(logging.DEBUG)

logger = colorlog.getLogger("Symbiosis")
logger.addHandler(console)
logger.addHandler(file_log)
logger.addFilter(time_rotate_file)
logger.setLevel(colorlog.DEBUG)
console.close()
file_log.close()
time_rotate_file.close()

params = argparse.ArgumentParser()
params.add_argument("cfgfile", nargs="?", default="config.json")
args, unknown = params.parse_known_args()
if unknown:
    logger.warning(f"未知参数: {unknown}")
else:
    logger.info(f"参数规范 :)")
fp = os.path.join(get_exec(args.cfgfile))
with open(fp, "r", encoding="utf-8") as f:
    fr_json: dict = json.loads(f.read())

"""
{
    "exec": {
        "1": {
            "parameters": List[str] = ["p1", "p2", ...]
            "exec": PathLike,
            "uac_admin": bool,
            "workdir": PathLike,
            "disable": false
        },
        "2": {
            ...
        },
    },
    "self-upgrade": {
        "retry": -1,
        "json-url": "",
        "download": ""
    }
}
"""

if fr_json.get("exec", None) is not None:
    run(fr_json)
for k, v in fr_json.items():
    if k not in ("exec", "parameters", "uac_admin", "workdir"):
        run(v)
