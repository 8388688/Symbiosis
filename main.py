"""
1.1-release 紧急补丁：
- 修正 1.0 以及更低版本无法正确判定版本号的 bug
1.1 更新【破坏性更新】：
- 完成静默更新
- :art: 修正程序内部错误码
- :sparkles: 现在配置文件也可以静默更新啦
1.0 更新（【破坏性更新】不支持 0.4.0 以下的版本）
- :sparkles: 静默更新(BETA)
- 【破坏性更新】修整 config.json 格式
- - 加入 download, upgrade 选项
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
from urllib3.exceptions import ProtocolError
from requests.exceptions import SSLError, MissingSchema, ConnectionError, InvalidURL, InvalidSchema, RequestException
# from typing import AnyStr

__version__ = "v1.1"
CAN_RETRY_CODE = tuple(range(1, 100)) + ()


def is_exec():
    return hasattr(sys, "_MEIPASS")


def get_exec():
    if is_exec():
        return sys.executable
    else:
        return os.path.abspath(__file__)


def get_resource(relative=""):
    return os.path.join(os.path.dirname(get_exec()), relative)


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        return False


def decode_version(version_str: str):
    RATE = 1000
    # 高版本号相对低一级的版本号的进制
    # 如：在 RATE = 100 的情况下，v0.4.1 等价于 v0.3.101 和 v0.2.201
    dot_rate = version_str.count(".")
    lst_ver_code = version_str.removeprefix("v").removeprefix("V").split(".")
    ver_code = 0
    ch = 0
    for i in (int(j) for j in lst_ver_code[::-1]):
        ver_code += RATE ** ch * i
        ch += 1
    ver_code *= RATE ** (4 - dot_rate)
    # 理论上 `ver_code *= RATE ** -dot_rate` 也是可以的
    return ver_code


def decode_config_time_version(version_str: str):
    ver_time = time.mktime(time.strptime(version_str, "%Y.%m.%d.%H.%M.%S"))
    return ver_time


def check_attributes(attr):
    result = dict()
    for i in dir(attr):
        result.update({i: getattr(attr, i)})
    return result


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


def download_api(url, file_path):
    """a simple download script

    download file on Internet in silence
    code:
    [1..99] 是网络问题（会触发重试机制）
    [100..199] 是用户问题（【不会】触发重试机制）
    [200..299] 是 OS 问题（【不会】触发重试机制）
    0 = normal(正常)
    1 = unknown error
    2 = Protocol Error
    3 = the file is not recognizable
    4 = 未使用
    5 = python.SSLError
    6 = timeout error
    7 = SSL 证书无效或已过期
    8 = URL 格式不正确
    9 = 无法连接
    10 = 无法辨识的协议
    11 = 协议格式不正确

    100 = 用户禁用了更新
    101 = Read configure file ERROR: symbiosis-update 键值对为空
    102 = 强制更新的版本号标志错误

    201 = 保存的目标文件所在的目录不存在

    :param url: the link to download on Internet
    :param file_path: current directory if this param is None else use `file_path`
    :param file_name: auto generate if this param is None else use `file_name`
    :param savemode: 保存方式
    :param nodisplay: download without display anything if `nodisplay == True`
    """
    if not os.path.isdir(os.path.dirname(file_path)):
        logger.error(f"无法保存至 {file_path}")
        return 201
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, '
                      'like Gecko) Chrome/107.0.0.0 Safari/537.36',
        # 'Connection': 'close'  # 不使用持久连接
    }
    try:
        r = requests.get(url, stream=True, verify=True, headers=headers)
    except SSLError:
        logger.error(f'SSLError! {url} is not secure.')
        return 7 # SSL 证书无效或已过期
    except MissingSchema:
        logger.error(f"Invalid URL {url}: No scheme supplied")
        return 11 # 协议格式不正确
    except InvalidURL:
        logger.error(f"Invalid URL: Failed to parse {url}")
        return 8 # URL 格式不正确
    except InvalidSchema:
        logger.error(f"No connection adapters were found for {url}")
        return 10 # 无法辨识的协议
    except ProtocolError as e:
        logger.error(f"ProtocolError")
        for k, v in check_attributes(e.args[0]).items():
            logger.error(f"{k}: {v}")
        return 2
    except TimeoutError as e:
        logger.error(f"Connection Timeout ({e.winerror}): {e.strerror}")
        return 6
    except ConnectionError as e:
        # logger.error(f"Failed to connect {url}: {e.args[0].reason}")
        logger.error(f"Failed to connect {url}: {e.args}")
        # for k, v in check_attributes(e.args[0]).items():
        #     logger.error(f"{k}: {v}")
        return 9 # 无法连接
    except RequestException as e:
        logger.error(f"Request Error {url} - [Error {e.args.count}, {e.args.index}]")
        return 1
    except Exception as e:
        logger.error(f"Unexpected Error: {e.args}")
        return 1
    else:
        logger.debug("ok")
    filesize = r.headers.get("content-length", -1)
    if filesize == -1:
        logger.warning(f"{url} 文件大小未知")
    else:
        filesize = int(filesize)

    logger.info(f"校验: url: {url}, 大小: {filesize}")
    logger.debug(f"当前 UA: {headers.get('User-Agent', '<空>')}")
    if filesize >= 32 * 1024 * 1024:
        logger.warning("这个文件太大了，下载可能需要很长的时间。")

    st = time.time()
    with open(file_path, "wb") as f:
        for i in r.iter_content(chunk_size=16384):
            f.write(i)
    el = time.time() - st
    logger.info(f"Download complete, time used: {el:.2f}s, average speed: {f'{filesize / el:.2f}B/s' if filesize != -1 and el != 0 else "?"}.")
    return 0


def download(config):
    "返回值为 0 表示正常下载，非 0 值表示最后一次下载异常退出的错误码（对照表参考 download_api）"
    url = config["url"]
    filepath = config["filepath"]
    if os.path.exists(config["filepath"]) and not config.get("replace-in-force", True):
        tmp = os.path.splitext(filepath)
        filepath = tmp[0] + time.strftime(".%Y-%m-%d_%H.%M.%S", time.localtime(time.time())) + tmp[-1]  # 前面的 “.” 不能省略
    cnt = 0
    status = 1
    while not (0 <= config["retry"] - cnt < 1):
        status = download_api(url, filepath)
        if status != 0 and status in CAN_RETRY_CODE:
            cnt += 1
            logger.info(f"Download failed, still trying... ({cnt}/{config['retry'] if config['retry'] >= 0 else 'Infinity'})")
        else:
            break
    else:
        logger.error(f"Discard: {k}")
    return status


def get_update():
    upgrade_config = fr_json.get("upgrade", dict())
    local_make_time = fr_json.get("make-time", -1)
    retry = upgrade_config.get("retry", 1)
    upgrade_json_fp = get_exec() + ".upgrade"
    upgrade_execute_fp = get_exec() + ".tmp"
    upgrade_old_execute_fp = get_exec() + ".old"
    downgrade_sign = upgrade_config.get("downgrade_install", None)
    upgrade_content = []
    logger.info("Downloading version of configure file. . .")
    exit_code = download({"url": upgrade_config["json-url"], "filepath": upgrade_json_fp, "retry": retry, "replace-in=force": True})
    if retry == 0:
        logger.info("更新已禁用")
        return 100
    if exit_code != 0:
        logger.error(f"Cannot download version of configure file (Error {exit_code})")
        return exit_code
    logger.info("Resolving configure file. . .")
    with open(upgrade_json_fp, "r", encoding="utf-8") as f:
        head_json = json.loads(f.read())
    if os.path.exists(upgrade_json_fp): os.unlink(upgrade_json_fp)
    if upgrade_config.get("enable-config-update", False):
        for k, v in head_json.get("config-file-update", dict()).items():
            if local_make_time == -1:
                logger.warning(f"make-time 键值对未设置，Symbiosis 将默认为您填入缺省参数 1970.1.1.0.0.0")
                local_make_time = "1970.1.1.0.0.0"
            if decode_config_time_version(k) > decode_config_time_version(local_make_time):
                upgrade_content.append([k, v])
        upgrade_content.sort(key=lambda x: decode_config_time_version(x[0]), reverse=True)
        if upgrade_content:
            if len(upgrade_content) > 1:
                logger.info(f"检查到多个配置文件的累积更新，{", ".join([i[0] for i in upgrade_content])}")
                logger.info(f"将自动为您更新到最新的一个版本 {upgrade_content[0][0]}")
            else:
                pass
            upgrade_content[0][1].update({"make-time": k})
            with open(get_resource(args.cfgfile), "w", encoding="utf-8") as f:
                f.write(json.dumps(upgrade_content[0][1]))
        else:
            logger.info("没有新的配置文件可用")
    else:
        logger.info("更新配置文件 - 选项已禁用")

    upgrade_content = []
    #########################################################
    if not head_json.get("symbiosis-update", []):
        logger.error("Read configure file ERROR: symbiosis-update 键值对为空")
        return 101
    if downgrade_sign is not None:
        logger.info(f"发现无视版本的强制更新标志，准备更新至 {downgrade_sign}")
        if downgrade_sign in head_json["symbiosis-update"].keys():
            download({"url": head_json["symbiosis-update"][downgrade_sign], "filepath": upgrade_execute_fp, "retry": retry, "replace-in=force": True})
        else:
            logger.error(f"强制更新标志应该是 {', '.join(head_json["symbiosis-update"].keys())} 之一，而不是 {downgrade_sign}")
            exit_code = 102
    else:
        for k, v in head_json["symbiosis-update"].items():
            if decode_version(k) > decode_version(__version__) and k not in upgrade_config.get("specific_version_exclude", []):
                upgrade_content.append([k, v])
        upgrade_content.sort(key=lambda x: decode_version(x[0]), reverse=True)
        if upgrade_content:
            if len(upgrade_content) > 1:
                logger.info(f"检查到多个版本的累积更新: {', '.join([i[0] for i in upgrade_content])}")
                logger.info(f"将自动为您更新到最新版本 {upgrade_content[0][0]}")
            else:
                pass
            download({"url": upgrade_content[0][1], "filepath": upgrade_execute_fp, "retry": retry, "replace-in=force": True})
            if os.path.exists(upgrade_old_execute_fp): os.unlink(upgrade_old_execute_fp)
            os.rename(get_exec(), upgrade_old_execute_fp)
            os.rename(upgrade_execute_fp, get_exec())
        else:
            logger.info("暂无更新")
    """head_json
    {
        "symbiosis-update": {
            "v0.3": download url 0.3,
            "v0.4": download url 0.4,
            "v1.0": download url 1.0,
            ...
        },
        "config-file-update: {
            "2025.07.02.00.00.00": {
                <config-file-entity>, // 此子字典中【不】含有 make-time 键值
            }
        }
    }

    """

    # else:
        # json_0 = req.json()
        # for i in json_0["content"]:
            # pass

    return exit_code


if not os.path.exists(get_resource("__SymbiosisLogs__")): os.mkdir(get_resource("__SymbiosisLogs__"))
os.chdir(get_resource())
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
file_log = logging.FileHandler(get_resource(f"__SymbiosisLogs__\\{time.time() // 86400}"), encoding="utf-8")
file_log.setFormatter(file_formatter)
time_rotate_file = logging.handlers.TimedRotatingFileHandler(filename=get_resource(f"__SymbiosisLogs__\\time_rotate"), encoding="utf-8", when="D", interval=1)
time_rotate_file.setFormatter(file_formatter)
time_rotate_file.setLevel(logging.INFO)

logger = colorlog.getLogger("Symbiosis")
logger.addHandler(console)
logger.addHandler(file_log)
logger.addFilter(time_rotate_file)
logger.setLevel(colorlog.INFO)
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
fp = os.path.join(get_resource(args.cfgfile))
with open(fp, "r", encoding="utf-8") as f:
    fr_json: dict = json.loads(f.read())

"""
{
    "execute": {
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
    "download": {
        "t": {
            "url": ...,
            "filepath": ...,
            "replace-in-force": bool, // true = 替换, false = rename
            "level": [0..4000], // 优先级，决定下载顺序
            "retry": int, 
            /* 0 = 禁用此项下载
            * 1 = 不重试
            * n（n 为大于 1 的整数）最多 n - 1 次重试
            * -1 = 无限重试
            */
            "keep": bool, // 下载完成后是否在配置文件中删除此下载项。
            "expire": bool, // 此项不应由用户设定，表示是否成功下载过该任务。
        }, 
        ...
    },
    "upgrade": {
        "json-url": "",
        "config-url": "https://raw.githubusercontent.com/8388688/Symbiosis/refs/heads/main/cloud-config.json", // 实际上并未使用
        "channel": ..., // 实际尚未使用
        "retry": -1, // 此配置选项同时兼顾主程序和配置文件的更新。
        "enable-config-update": true, // 此选项优先级高于 retry，但只决定配置文件的更新，主程序更新不受此影响。
        "download": "", // 实际尚未使用
        "specific_version_exclude": [], // 空序列表示接受所有更新，序列中的元素表示排除特定版本更新。
        "downgrade_install": "v0.1" || null, // 强制降级安装, null 表示不启用降级安装，此选项无视 specific_version_exclude 的排除设置。
    }
    "run": {// 仍在可行性分析中}
}
"""

if __name__ == "__main__":
    logger.info(f"当前版本：{__version__}")
    for k, v in fr_json.get("execute", dict()).items():
        run(v)
    for k, v in fr_json.get("download", dict()).items():
        download(v)
    get_update()
