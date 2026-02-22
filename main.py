# 1.6 版本的部分代码使用了 Github Copilot 辅助设计
import argparse
from collections import defaultdict
import colorlog
import json
import logging
import logging.handlers
import os
import sys
import time
import warnings

from traceback import format_exc
from typing import Callable

from constants import *
from sym_ops import check_time, decode_datetime, Executor, Downloader, FileDeleter
from sym_utils import *
from update_utils import *
from update_action import parse_update_action

__version__ = "v1.6.3"
version_entity = Version(__version__)
K_ENABLE_FUTURE = True


def can_retry(code: int):
    """retry.md: 判断错误码是否可重试"""
    if 0 <= code <= 255:
        if code == 0:
            return False
        return (code & 128) == 0
    else:
        raise ValueError("错误，返回代码必须为 0..255 之间的整数")


def decode_version(version_str: str):
    """版本号解码（已弃用，保留向后兼容）"""
    warnings.warn(
        "decode_version 即将废弃，请使用 decode_config_time_version 代替", DeprecationWarning)
    RATE = 1000
    dot_rate = version_str.count(".")
    lst_ver_code = version_str.removeprefix("v").removeprefix("V").split(".")
    ver_code = sum(RATE ** ch * int(i)
                   for ch, i in enumerate(reversed(lst_ver_code)))
    return ver_code * (RATE ** (4 - dot_rate))


def decode_config_time_version(version_str: str | int):
    """配置时间版本解码"""
    if isinstance(version_str, str):
        return time.mktime(time.strptime(version_str, "%Y.%m.%d.%H.%M.%S"))
    return version_str


def combine_timestamp_fp(fp):
    """为文件名添加时间戳"""
    tmp = os.path.splitext(fp)
    ch = 0
    while os.path.exists(fp):
        fp = tmp[0] + time.strftime(".%Y-%m-%d_%H.%M.%S", time.localtime(
            time.time())) + ("" if ch == 0 else f"_{ch}") + tmp[-1]
        ch += 1
    return fp


def check_attributes(attr):
    """检查属性"""
    return {i: getattr(attr, i) for i in dir(attr)}


def check_time_can_do(config: defaultdict):
    """检查是否在允许的时间范围内"""
    datetime_str = config_reader.get(config, "datetime", "..")
    datetime = check_time(datetime_str)
    return datetime.group(0), (
        (not datetime.group(1) or decode_datetime(datetime.group(1)) <= time.time()) and
        (not datetime.group(2) or time.time()
         <= decode_datetime(datetime.group(2)))
    )


def run(id_, config: defaultdict):
    """执行程序操作"""
    logger.info(f"运行 {id_=}")
    time_ch = check_time_can_do(config)

    if not time_ch[1]:
        logger.warning(f"启动时间不在 {time_ch[0]} 范围内")
        return

    # 使用统一配置读取器获取参数
    params = config_reader.get_multi(config, {
        "exec": None,
        "parameters": [],
        "uac_admin": False,
        "use_psexec": False,
        "workdir": os.getcwd(),
        "disable": False
    })

    executor.execute(
        exec_fp=params["exec"],
        parameters=params["parameters"],
        uac_admin=params["uac_admin"],
        use_psexec=params["use_psexec"],
        workdir=params["workdir"],
        disable=params["disable"]
    )


def download(id_, config):
    """下载文件，支持重试机制"""
    # 使用统一配置读取器获取参数
    params = config_reader.get_multi(config, {
        "url": None,
        "filepath": None,
        "retry": 1,
        "headers": {},
        "checksum": {},
        "ignore_status": False,
        "safe_write": True,
        "timestamp": False
    })

    url = params["url"]
    filepath = params["filepath"]
    retry = params["retry"]
    headers = params["headers"]
    checksum = params["checksum"]
    ignore_status = params["ignore_status"]
    safe_write = params["safe_write"]

    if url is None or filepath is None:
        logger.error(f"{url=} and/or {filepath=} is empty.")
        return 135

    time_ch = check_time_can_do(config)
    if not time_ch[1]:
        logger.warning(f"启动时间不在 {time_ch[0]} 范围内")
        return 1

    if params["timestamp"]:
        filepath = combine_timestamp_fp(filepath)

    # 重试逻辑
    status = 1
    for attempt in range(retry):
        status = downloader.download(
            url, filepath, headers, checksum, ignore_status, safe_write)
        if status == 0 or not can_retry(status):
            break
        logger.warning(
            f"Download failed, still trying... ({attempt + 1}/{retry})")

    return status


def deleteFile(id_, config):
    """删除文件/目录"""
    logger.debug(f"删除文件 {id_}")
    time_ch = check_time_can_do(config)

    if not time_ch[1]:
        logger.warning(f"启动时间不在 {time_ch[0]} 范围内")
        return

    # 使用统一配置读取器获取参数
    params = config_reader.get_multi(config, {
        "src": None,
        "folders": True,
        "only_subfolders": False
    })

    fp = params["src"]
    del_folder = params["folders"]
    only_subfolder = params["only_subfolders"]

    file_deleter.delete(file_path=fp, del_folders=del_folder,
                        only_subfolders=only_subfolder)


def update_single_file_api(config: dict, local_make_time, save_path, channel, uptodate=True):
    """更新单个文件API"""
    old_file_fp = save_path + ".orig"
    upgrade_content = []
    logger.debug(f"{config=}, {save_path=}")

    for k, v in config.items():
        if local_make_time == 0:
            logger.warning(
                f"make-time 键值对未设置，Symbiosis 将默认为您填入缺省参数 {local_make_time}")

        remote_channel = v.get("channel", [])
        if "channel" not in v.keys():
            logger.warning(f"远程配置 {k} 的 channel 未设置，Symbiosis 将默认其为全版本更新的补丁")

        logger.debug(f"{k=}, {channel=}, {remote_channel=}")

        if decode_config_time_version(k) > decode_config_time_version(local_make_time) and (not remote_channel or channel in remote_channel):
            upgrade_content.append([k, v])

    upgrade_content.sort(
        key=lambda x: decode_config_time_version(x[0]), reverse=True)

    if upgrade_content:
        if len(upgrade_content) > 1:
            if not uptodate:
                logger.info(f"available for update (local version: {local_make_time}, remote version: {upgrade_content[0][0]}). "
                            f"Current database is {len(upgrade_content)} versions behind.")
                tmp = upgrade_content[-1][1]
                for i in (j[1] for j in upgrade_content[::-1]):
                    merge_config(tmp, i, ip=True)
            else:
                logger.info(f"检查到多个文件的累积更新：{', '.join([i[0] for i in upgrade_content])}。"
                            f"将自动为您更新到最新的一个版本 {upgrade_content[0][0]}")
                tmp = upgrade_content[0][1]
        else:
            tmp = upgrade_content[0][1]

        tmp.update({"make-time": upgrade_content[0][0]})
        if "channel" in tmp.keys():
            tmp.pop("channel")
        if os.path.exists(old_file_fp):
            os.unlink(old_file_fp)
        if os.path.exists(save_path):
            os.rename(save_path, old_file_fp)

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(tmp, indent=4))
        logger.info("complete.")
    else:
        logger.info("没有更新可用")


def update_single_file(id_, dl_config: dict, local_make_time, save_path, channel, uptodate):
    """更新单个文件"""
    dl_config.update({"timestamp": False})
    ex_code = download(id_, dl_config)
    logger.debug(f"{dl_config=}, {save_path=}")

    if ex_code == 0:
        with open(dl_config.get("filepath"), "rb") as f:
            tmp = json.loads(f.read())
        update_single_file_api(tmp, local_make_time,
                               save_path, channel, uptodate)
        logger.debug(f"delete: {dl_config.get('filepath')}")
        os.unlink(dl_config.get("filepath"))
        return ex_code
    else:
        logger.error(f"无法更新 {id_} - Error {ex_code}")
        return 134


def get_update():
    """获取和应用更新"""
    upgrade_config = fr_json.get("upgrade", {})
    if not upgrade_config:
        logger.error(f"无法更新，因为 upgrade 键值对没有任何内容 [Error {131}]")
        return 131

    local_make_time = fr_json.get("make-time", 0)
    retry = upgrade_config.get("retry", globalsettings.get("retry", 1))
    upgrade_json_fp = get_exec() + ".upgrade"
    upgrade_execute_fp = get_exec() + ".tmp"
    upgrade_old_execute_fp = get_exec() + ".orig"

    if retry == 0:
        logger.info("Self-upgrade is disabled.")
        return 128

    # 处理降级配置
    downgrade_config = upgrade_config.get(
        "downgrade", DEFAULT_DOWNGRADE_CONFIG)
    downgrade_sign = downgrade_config.get("downgrade", None)

    # 下载版本配置文件
    logger.debug("Downloading version of configure file. . .")
    exit_code = download("get-update", {
        "url": upgrade_config["json-url"],
        "filepath": upgrade_json_fp,
        "retry": retry,
        "timestamp": False
    })

    if exit_code != 0:
        logger.error(
            f"Cannot download version of configure file (Error {exit_code})")
        return exit_code

    logger.debug("Resolving configure file. . .")
    with open(upgrade_json_fp, "r", encoding="utf-8") as f:
        head_json = json.loads(f.read())
    os.unlink(upgrade_json_fp)

    # 确定 URL 和哈希键
    up_url_key = "url-con" if upgrade_config.get(
        "console", False) else "url-win"
    up_hash_key = "sha256-con" if upgrade_config.get(
        "console", False) else "sha256-win"

    # 处理强制降级更新
    if downgrade_sign is not None:
        logger.info(f"发现无视版本的强制更新标志，准备更新至 {downgrade_sign}")
        if downgrade_sign in head_json["update-14pp"].keys():
            download("downgrade", {
                "url": head_json["update-14pp"][downgrade_sign][up_url_key],
                "filepath": upgrade_execute_fp,
                "retry": retry,
                "timestamp": False,
                "checksum": {"sha256": head_json["update-14pp"][downgrade_sign][up_hash_key]}
            })
            if not downgrade_config.get("permanent", False):
                logger.debug("已清除一次性更新标志")
                downgrade_config.update({"downgrade": None})
            else:
                logger.warning("永久更新标志会在 Symbiosis 每次启动时都尝试一次降级更新")

            fr_json["upgrade"].update({"downgrade": downgrade_config})
        else:
            logger.error(
                f"强制更新标志应该是 {', '.join(head_json['update-14pp'].keys())} 之一")
            return 130
    else:
        # 检查常规更新
        upgrade_content = [
            [k, v] for k, v in head_json["update-14pp"].items()
            if version_entity < Version(k) and k not in upgrade_config.get("specific_version_exclude", [])
        ]
        upgrade_content.sort(key=lambda x: decode_version(x[0]), reverse=True)

        if upgrade_content:
            if len(upgrade_content) > 1:
                logger.info(f"检查到多个版本的累积更新: {', '.join([i[0] for i in upgrade_content])}。"
                            f"将自动为您更新到最新版本 {upgrade_content[0][0]}")
            else:
                logger.info(f"检查到新版本 {upgrade_content[0][0]} 可用。")

            ex_code = download("get-update.14pp", {
                "url": upgrade_content[0][1][up_url_key],
                "filepath": upgrade_execute_fp,
                "retry": retry,
                "timestamp": False,
                "checksum": {"sha256": upgrade_content[0][1][up_hash_key]}
            })

            if ex_code == 0:
                if os.path.exists(upgrade_old_execute_fp):
                    logger.debug(f"移除旧版本程序 - {upgrade_old_execute_fp}")
                    os.unlink(upgrade_old_execute_fp)
                os.rename(get_exec(), upgrade_old_execute_fp)
                os.rename(upgrade_execute_fp, get_exec())

            tmp = upgrade_content[0][1].get("enable-config-update", None)
            if tmp is not None:
                fr_json["upgrade"].update({"enable-config-update": tmp})
        else:
            logger.info(f"主程序暂无更新")

    # 更新配置文件
    if upgrade_config.get("enable-config-update", True):
        if "config-url" in fr_json["upgrade"].keys():
            logger.warning("cloud-config 已弃用")
            if decode_version(__version__) < decode_version("v1.6"):
                logger.info("更新主配置文件")
                update_single_file("configFile.up", {
                    "url": fr_json["upgrade"]["config-url"],
                    "filepath": resource_path(args.configFile + ".upgrade"),
                    "retry": retry
                }, local_make_time, get_resource(args.configFile), channel=0, uptodate=False)
            else:
                logger.error("跳过主配置文件更新 - 版本过高")
                fr_json["upgrade"].pop("config-url")

        logger.info("更新补丁配置文件，补丁将在下一次启动时应用到主配置文件中。")
        if "channel" not in fr_json["userdata"]:
            logger.error("注意到 channel 未设置，Symbiosis 将无法接收到任何更新。")
        update_single_file("patchFile.up", {
            "url": fr_json["upgrade"]["patch-url"],
            "filepath": resource_path(args.patchFile + ".upgrade"),
            "retry": retry
        }, local_make_time, get_resource(args.patchFile),
            fr_json["userdata"].get("channel", 0),
            uptodate=False)
    else:
        logger.info("更新配置文件 - 选项已禁用")

    return exit_code


def get_assistance():
    """获取帮助文件"""
    fname = "assistance.txt"
    if not os.path.exists(get_resource(fname)):
        return -1

    logger.info(f"检测到 {fname}，准备获取帮助文件。")
    with open(get_resource(fname), "r", encoding="utf-8") as f:
        config = f.read().strip().splitlines()

    can_delete = True
    for i in config:
        tmp_fp = os.path.join(get_orig_path(), "samples", i + ".sample")
        dst_fp = resource_path(i + ".sample.txt")

        if not os.path.exists(tmp_fp):
            logger.warning(f"{tmp_fp} not found.")
            can_delete = False
        else:
            logger.info(f"Extract: {tmp_fp} -> {dst_fp}")
            with open(tmp_fp, "rb") as f:
                with open(dst_fp, "wb") as f2:
                    f2.write(f.read())

    if can_delete:
        logger.debug(f"删除 {get_resource(fname)}")
        os.unlink(get_resource(fname))


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument("configFile", nargs="?", default="config.json")
    parser.add_argument("patchFile", nargs="?", default="config.temp.json")
    parser.add_argument("--debug", action="store_true")
    args, unknown = parser.parse_known_args()

    if args.debug:
        logger.setLevel(colorlog.DEBUG)
    else:
        logger.setLevel(colorlog.INFO)

    if unknown:
        logger.warning(f"未知 {len(unknown)} 参数: {', '.join(unknown)}")
    else:
        logger.debug(f"传参：{args}")

    return args


def get_config(conf_fp, patch_fp):
    """获取合并后的配置"""
    config = {}
    tmp = {"ignore_case": False}

    if not os.path.exists(patch_fp):
        logger.error(f"{patch_fp} 不存在，你可以将其视为空值，该文件在后续将自动创建。")
    else:
        with open(patch_fp, "r", encoding="utf-8") as f:
            tmp.update(json.loads(f.read()))

    if not tmp.get("ignore_case"):
        with open(conf_fp, "r", encoding="utf-8") as f:
            config.update(json.loads(f.read()))

    tmp.pop("ignore_case")
    config.update(merge_config(config, tmp))

    with open(patch_fp, "w", encoding="utf-8") as f:
        f.write("{}")

    return config


def put_config(config, conf_fp):
    """保存配置到文件"""
    with open(conf_fp, "w", encoding="utf-8") as f:
        f.write(json.dumps(config, indent=4))


def init_logger() -> logging.Logger:
    """初始化日志"""
    if not os.path.exists(get_resource("logs")):
        os.makedirs(get_resource("logs"), exist_ok=True)

    os.chdir(get_resource())

    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s.%(msecs)03d] %(filename)s -> %(funcName)s line:%(lineno)d [%(levelname)s]: %(message)s",
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
        "[%(asctime)s.%(msecs)03d] %(filename)s -> %(funcName)s line:%(lineno)d [%(levelname)s]: %(message)s",
        datefmt="%Y-%m-%dT%H.%M.%SZ",
    )

    console = colorlog.StreamHandler()
    console.setFormatter(console_formatter)

    rotating_fp = get_resource("logs", "symbiosis.log")
    time_rotate_file = logging.handlers.TimedRotatingFileHandler(
        filename=rotating_fp,
        when="midnight",
        interval=1,
        backupCount=0,
        encoding="utf-8",
        utc=False,
    )
    time_rotate_file.setFormatter(file_formatter)
    time_rotate_file.setLevel(logging.DEBUG)

    logger = colorlog.getLogger("Symbiosis")
    logger.addHandler(console)
    logger.addHandler(time_rotate_file)
    logger.propagate = False

    return logger


def run_series(type_, config, fx: Callable):
    """运行一系列操作"""
    logger.debug(f"执行 {type_} 操作")
    eaten = []
    tmp = config

    for k, v in tmp.items():
        ttl = v.get("TTL", -1)
        if ttl == 0:
            if v.get("keep", globalsettings.get("keep", False)):
                eaten.append(k)
                logger.debug(f"id={k} 的 keep 项被设置为 true，保留其值。")
        else:
            fx(k, v)
            tmp[k].update({"TTL": ttl - 1})

    logger.debug(f"{eaten=}")
    for i in eaten:
        tmp.pop(i)

    return tmp


def main():
    logger.info(f"当前版本：{__version__}")

    try:
        if Version(fr_json.get("userdata", {}).get("lastrun_version", None)) != Version(__version__):
            for i in parse_update_action(fr_json, logger):
                # 直接在 fr_json 主配置上做修改
                i.run(Version(__version__))
        put_config(fr_json, fp)
        # TOTA 相关代码
        if "DESTRUCTION" in fr_json["TOTA"]:
            fr_json.update({"destruction": 1})
        if "destruction" in fr_json["TOTA"]:
            tmp = fr_json["TOTA"].get("destruction")
            fr_json["TOTA"].update({"destruction": tmp - 1})
            logger.critical(f"再启动 {tmp} 次之后自毁")
            if tmp == 0:
                logger.critical("启动自毁程序！")
                # TODO: 未完成！
                deleteFile()
        get_assistance()

        for i, fx in OPERATORS:
            fr_json.update({i: run_series(i, fr_json.get(i, {}), fx)})

        get_update()
        fr_json["userdata"].update(
            {"lastrun_version": Version(__version__).__str__()})
        put_config(fr_json, fp)
    except Exception as e:
        exc_type, exc_value, exc_obj = sys.exc_info()
        logger.critical("======= FATAL ERROR =======")
        logger.critical("exception_type: \t%s" % exc_type)
        logger.critical("exception_value: \t%s" % exc_value)
        logger.critical("exception_object: \t%s" % exc_obj)
        logger.critical(f"======= FULL EXCEPTION =======\n{format_exc()}\n")
    finally:
        logger.info("Done.\n")


# 初始化全局对象
logger = init_logger()
args = parse_args()
fp = os.path.join(get_resource(args.configFile))
patch_fp = os.path.join(get_resource(args.patchFile))

try:
    fr_json = get_config(fp, patch_fp)
except Exception as e:
    logger.critical(f"读取文件时出错: {e}")
    sys.exit(1)

globalsettings = fr_json.get("globalsettings", {})

# 初始化配置读取器
config_reader = ConfigReader(globalsettings)

# 初始化操作实例
executor = Executor(logger, resource_path, is64bitPlatform)
downloader = Downloader(logger)
file_deleter = FileDeleter(logger, tree_fp_gen)

# 操作映射表
OPERATORS = (("execute", run), ("deleteFile", deleteFile),
             ("download", download))


if __name__ == "__main__":
    main()
