import argparse
from traceback import format_exc
from typing import Callable
import colorlog
import ctypes
import hashlib
import platform
import json
import logging
import logging.handlers
import os
import re
import requests
import sys
import time

from os import PathLike
from urllib3.exceptions import ProtocolError
from requests.exceptions import SSLError, MissingSchema, ConnectionError, InvalidURL, InvalidSchema, RequestException
# from typing import AnyStr

__version__ = "v1.4"
K_UPDATE_CONFIG_UNDER_CONSTRUCTION = False


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


def getOSbit():
    return platform.architecture()


def is64bitPlatform() -> bool:
    return getOSbit()[0].lower() == "64bit"


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


def can_retry(code: int):
    """retry.md
    """
    # assert 0 <= code <= 255
    if 0 <= code <= 255:
        if code == 0:
            return False
        if code & 128 == 0:
            return True
        else:
            return False
    else:
        logger.error("错误，返回代码必须为 0..255 之间的整数")
        raise ValueError("错误，返回代码必须为 0..255 之间的整数")


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


def decode_config_time_version(version_str: str | int):
    if isinstance(version_str, str):
        ver_time = time.mktime(time.strptime(version_str, "%Y.%m.%d.%H.%M.%S"))
    else:
        assert isinstance(version_str, int)
        ver_time = version_str
    return ver_time


def decode_datetime(date_str: str):
    return time.mktime(time.strptime(
        date_str, "%Y/%m/%d"
    ))


def combine_timestamp_fp(fp):
    tmp = os.path.splitext(fp)
    ch = 0
    while os.path.exists(fp):
        fp = tmp[0] + time.strftime(
            ".%Y-%m-%d_%H.%M.%S",  # 前面的 “.” 不能省略
            time.localtime(time.time())) + ("" if ch == 0 else f"_{ch}") + tmp[-1]
        ch += 1
    return fp


def check_attributes(attr):
    result = dict()
    for i in dir(attr):
        result.update({i: getattr(attr, i)})
    return result


def check_time(time_str):
    return re.search(
        r"(\d+\/\d+\/\d+)?\s*\.\.\s*(\d+\/\d+\/\d+)?",
        time_str, re.I
    )


def check_time_can_do(config):
    datetime = check_time(config.get("datetime", globalsettings.get(
        "datetime", "..")))
    return datetime.group(0), (not datetime.group(1) or decode_datetime(datetime.group(1)) <= time.time()) and \
        (not datetime.group(2) or time.time()
         <= decode_datetime(datetime.group(2)))


def md5sum(fpath: str, algorithm: str, buffering: int = 8096) -> str:
    with open(fpath, 'rb') as f:
        result = hashlib.new(algorithm)
        for chunk in iter(lambda: f.read(buffering), b''):
            result.update(chunk)
        return result.hexdigest()


def md5check(fpath, algorithm, expected_hash) -> bool:
    result = md5sum(fpath, algorithm).lower()
    if result == expected_hash.lower():
        return True
    else:
        logger.error(
            f"校验失败，文件的 {algorithm} 哈希应为 {expected_hash}，实际上却是 {result}")
        return False


def run(id_, config: dict):
    logger.debug(f"运行 {id_}")
    time_ch = check_time_can_do(config)
    exec_fp: PathLike = config.get("exec")
    parameters_orig: list[str] = config.get(
        "parameters", globalsettings.get("parameters", []))
    uac_admin: bool = config.get(
        "uac_admin", globalsettings.get("uac_admin", False))
    use_psexec: bool = config.get(
        "use_psexec", globalsettings.get("use_psexec", False))
    workdir: PathLike = config.get(
        "workdir", globalsettings.get("work_dir", os.getcwd()))
    fake: bool = config.get("disable", globalsettings.get("disable", False))
    # if is_admin():
    #     logger.info(f"正在使用管理员权限运行 - 非常棒！")
    # else:
    #     logger.info(f"准备以管理员身份重启. . . . . .")
    psexec_fp = resource_path(
        "scripts", "PsExec64.exe" if is64bitPlatform() else "PsExec.exe")
    psexec_fp_exists = True
    if not os.path.exists(psexec_fp) and "use_psexec" in config.keys():
        logger.warning(f"{psexec_fp} 路径不存在，{use_psexec=} 实际成为无效设置。")
        psexec_fp_exists = False
    if not fake:
        if exec_fp is None:
            logger.error(f"键值对 exec 为必填")
            return 132
        if not os.path.exists(exec_fp):
            logger.error(f"{exec_fp} 文件不存在")
            return
        if time_ch[1]:
            logger.info(
                f"启动: {exec_fp=}, {parameters_orig=}, {uac_admin=}, {workdir=}, {use_psexec=}")
            if use_psexec and psexec_fp_exists:
                parameters: str = f"-d -i {'-s' if uac_admin else '-l'} -w {workdir} -accepteula -nobanner {exec_fp} " + \
                    " ".join((str(i) for i in parameters_orig))
                exit_code = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas" if uac_admin else "open", psexec_fp, parameters, workdir, 1)
            else:
                parameters: str = " ".join((str(i) for i in parameters_orig))
                exit_code = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas" if uac_admin else "open", exec_fp, parameters, workdir, 1)
            logger.info(f"启动完成（不一定启动成功），返回状态码为 {exit_code}")
        else:
            logger.info(f"启动时间不在 {time_ch[0]} 范围内")
    else:
        logger.info(f"假装启动: {exec_fp=}")


def download_api(url, file_path, headers, checksum: dict = dict(), ignore_status=False):
    """a simple download script

    download file on Internet in silence
    重试返回的代码参考 retry.md

    :param url: the link to download on Internet
    :param file_path: current directory if this param is None else use `file_path`
    :param file_name: auto generate if this param is None else use `file_name`
    :param savemode: 保存方式
    :param nodisplay: download without display anything if `nodisplay == True`
    """
    if not os.path.isdir(os.path.dirname(file_path)):
        logger.error(f"无法保存至 {file_path}")
        return 192
    headers = headers
    try:
        r = requests.get(url, stream=True, verify=True, headers=headers)
    except SSLError:
        logger.error(f'SSLError! {url} is not secure.')
        return 7  # SSL 证书无效或已过期
    except MissingSchema:
        logger.error(f"Invalid URL {url}: No scheme supplied")
        return 11  # 协议格式不正确
    except InvalidURL:
        logger.error(f"Invalid URL: Failed to parse {url}")
        return 8  # URL 格式不正确
    except InvalidSchema:
        logger.error(f"No connection adapters were found for {url}")
        return 10  # 无法辨识的协议
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
        return 9  # 无法连接
    except RequestException as e:
        logger.error(
            f"Request Error {url} - [Error {e.args.count}, {e.args.index}]")
        return 1
    except Exception as e:
        logger.error(f"Unexpected Error: {e.args}")
        return 127
    else:
        logger.debug("ok")
    filesize = r.headers.get("content-length", -1)
    if filesize == -1:
        logger.warning(f"{url} 文件大小未知")
    else:
        filesize = int(filesize)

    logger.info(f"校验: url: {url}, 大小: {filesize}")
    logger.debug(f"当前 UA: {headers.get('User-Agent', '<空>')}")
    if ignore_status or r.status_code == 200:
        pass
    else:
        logger.warning(f"Error downloading file: {r.status_code=}")
        return 13

    st = time.time()
    with open(file_path, "wb") as f:
        for i in r.iter_content(chunk_size=16384):
            f.write(i)
    el = time.time() - st
    if checksum:
        logger.info("校验文件中. . .")
        for k, v in checksum.items():
            logger.debug(f"校验文件的 {k} 值")
            if not md5check(file_path, k, v):
                return 12
            else:
                logger.debug(f"文件的 {k} 哈希校验无误")
        else:
            logger.info("文件哈希校验无误")

    logger.info(
        f"Download complete, time used: {el:.2f}s, average speed: {f'{filesize / el:.2f}B/s' if filesize != -1 and el != 0 else "?"}.")
    return 0


def download(id_, config):
    "返回值为 0 表示正常下载，非 0 值表示最后一次下载异常退出的错误码（对照表参考 download_api）"
    url = config["url"]
    filepath = config["filepath"]
    retry = config.get("retry", globalsettings.get("retry", 1))
    headers = config.get("headers", globalsettings.get("headers", {}))
    checksum = config.get("checksum", {})
    ignore_status = config.get(
        "ignore_status", globalsettings.get("ignore_status", False))
    if config.get("timestamp", False):
        filepath = combine_timestamp_fp(filepath)
    cnt = 0
    status = 1
    time_ch = check_time_can_do(config)
    if time_ch[1]:
        while not (0 <= retry - cnt < 1):
            status = download_api(
                url, filepath, headers, checksum, ignore_status)
            if can_retry(status):
                cnt += 1
                logger.warning(
                    f"Download failed, still trying... ({cnt}/{retry if retry >= 0 else 'Infinity'})")
            else:
                break
        else:
            logger.error(f"Discard: {id_}")
    else:
        logger.info(f"启动时间不在 {time_ch[0]} 范围内")
    return status


def deleteFile(id_, config):
    logger.debug(f"刪除文件 {id_}")
    fp = config.get("src")
    del_folder = config.get("folders", globalsettings.get("folders", True))
    only_subfolder = config.get(
        "only_subfolders", globalsettings.get("only_subfolders", False))
    logger.info(f"删除 [{fp}] 及其所属文件")
    tot_file, tot_dir, tot_size = 0, 0, 0
    exclude_dirs = []
    if not os.path.exists(fp):
        logger.error(f"{fp} - 文件不存在")
        return
    for i in tree_fp_gen(fp, del_folder, True):
        try:
            if i in exclude_dirs:
                logger.debug(f"skip: {i}")
                continue
            if os.path.isfile(i):
                tmp = os.path.getsize(i)
                # 这一行取消只读属性
                ctypes.windll.kernel32.SetFileAttributesW(i, 0)
                os.unlink(i)
                logger.debug(f"del file: {i}")
                tot_size += tmp
                tot_file += 1
            else:
                if not only_subfolder or i != fp:
                    os.rmdir(i)
                    logger.debug(f"del dir: {i}")
                    tot_dir += 1
        except OSError as e:
            logger.warning(
                f"Delete failed, error {e.winerror}: {e.strerror} (Code {e.errno}) {e.filename=}, {e.filename2=}.")
            tmp = i
            while os.path.normpath(tmp) == os.path.normpath(fp):
                tmp = os.path.dirname(tmp)
                exclude_dirs.append(tmp)
        else:
            pass
    else:
        logger.info(f"总计删除 {tot_size} 字节，{tot_file} 个文件，{tot_dir} 个文件夹。")


def update_single_file(config: dict, local_make_time, save_path):
    old_file_fp = save_path + ".orig"
    upgrade_content = []
    for k, v in config.items():
        if local_make_time == 0:
            logger.warning(
                f"make-time 键值对未设置，Symbiosis 将默认为您填入缺省参数 {local_make_time}")
        if decode_config_time_version(k) > decode_config_time_version(local_make_time):
            upgrade_content.append([k, v])
    upgrade_content.sort(
        key=lambda x: decode_config_time_version(x[0]), reverse=True)
    if upgrade_content:
        if len(upgrade_content) > 1:
            logger.info(
                f"检查到多个配置文件的累积更新：{", ".join([i[0] for i in upgrade_content])}。"
                f"将自动为您更新到最新的一个版本 {upgrade_content[0][0]}")
        upgrade_content[0][1].update({"make-time": k})
        if os.path.exists(old_file_fp):
            os.unlink(old_file_fp)
        if os.path.exists(save_path):
            os.rename(save_path, old_file_fp)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(upgrade_content[0][1], indent=4))
    else:
        logger.info("没有新的配置文件可用")


def get_update():
    upgrade_config = fr_json.get("upgrade", dict())
    if not upgrade_config:
        logger.error(f"无法更新，因为 upgrade 键值对没有任何内容 [Error {131}]")
        return 131
    local_make_time = fr_json.get("make-time", 0)
    retry = upgrade_config.get("retry", globalsettings.get("retry", 1))
    upgrade_json_fp = get_exec() + ".upgrade"
    upgrade_execute_fp = get_exec() + ".tmp"
    upgrade_old_execute_fp = get_exec() + ".orig"
    upgrade_content = []
    if retry == 0:
        logger.info("Self-upgrade is disabled.")
        return 128
    logger.debug("检查 downgrade.json 文件")
    if os.path.exists(get_resource("downgrade.json")):
        with open(get_resource("downgrade.json"), "rb") as f:
            downgrade_config = json.loads(f.read())
    else:
        logger.warning("找不到 downgrade.json 文件")
        downgrade_config = dict()
    downgrade_sign = downgrade_config.get("downgrade", None)
    logger.info("Downloading version of configure file. . .")
    exit_code = download("get-update",
                         {"url": upgrade_config["json-url"], "filepath": upgrade_json_fp, "retry": retry, "timestamp": False})
    if exit_code != 0:
        logger.error(
            f"Cannot download version of configure file (Error {exit_code})")
        return exit_code
    logger.info("Resolving configure file. . .")
    with open(upgrade_json_fp, "r", encoding="utf-8") as f:
        head_json = json.loads(f.read())
    if os.path.exists(upgrade_json_fp):
        os.unlink(upgrade_json_fp)
    if K_UPDATE_CONFIG_UNDER_CONSTRUCTION:
        logger.warning(f"更新配置文件")
    else:
        if upgrade_config.get("enable-config-update", False):
            logger.info("更新配置文件")
            update_single_file(head_json.get(
                "config-file-update", dict()), local_make_time, get_resource(args.cfgfile))
            logger.info("更新临时配置文件")
            update_single_file(head_json.get(
                "temp-config-update", dict()), local_make_time, get_resource(args.tmp_cfg))
        else:
            logger.info("更新配置文件 - 选项已禁用")

    upgrade_content = []
    #########################################################
    if upgrade_config.get("console", False):
        up_list_key = "symbiosis-update-con"
        up_hash_key = "checksum-sha256-con"
    else:
        up_list_key = "symbiosis-update-win"
        up_hash_key = "checksum-sha256-win"
    if not head_json.get(up_list_key, []):
        logger.error(f"Read configure file ERROR: {up_list_key} 键值对为空")
        return 129
    if downgrade_sign is not None:
        logger.info(f"发现无视版本的强制更新标志，准备更新至 {downgrade_sign}")
        if downgrade_sign in head_json[up_list_key].keys():
            download("downgrade",
                     {"url": head_json[up_list_key][downgrade_sign],
                      "filepath": upgrade_execute_fp, "retry": retry, "timestamp": False,
                      "checksum": {"sha256": head_json[up_hash_key][downgrade_sign]}})
            if not downgrade_config.get("permanent", False):
                logger.debug("已清除一次性更新标志")
                downgrade_config.update({"downgrade": None})
            else:
                logger.warning(
                    "永久更新标志会在 Symbiosis 每次启动时都尝试一次降级更新，"
                    "这可能会扰乱正常更新进度，"
                    "除非你确定自己在干什么，否则请使用一次性更新标志（permanent=false）")
            with open(get_resource("downgrade.json"), "w") as f:
                f.write(json.dumps(downgrade_config, indent=4))
        else:
            logger.error(
                f"强制更新标志应该是 {', '.join(head_json[up_list_key].keys())} 之一，而不是 {downgrade_sign}")
            return 130
    else:
        for k, v in head_json[up_list_key].items():
            if decode_version(k) > decode_version(__version__) and k not in upgrade_config.get("specific_version_exclude", []):
                upgrade_content.append([k, v])
        upgrade_content.sort(key=lambda x: decode_version(x[0]), reverse=True)
        if upgrade_content:
            if len(upgrade_content) > 1:
                logger.info(
                    f"检查到多个版本的累积更新: {', '.join([i[0] for i in upgrade_content])}。"
                    f"将自动为您更新到最新版本 {upgrade_content[0][0]}")
            download(
                "get-update",
                {"url": upgrade_content[0][1], "filepath": upgrade_execute_fp,
                 "retry": retry, "timestamp": False,
                 "checksum": {"sha256": head_json[up_hash_key][upgrade_content[0][0]]}})
        else:
            logger.info("主程序暂无更新")
            return exit_code
    if os.path.exists(upgrade_old_execute_fp):
        logger.debug(f"移除旧版本程序 - {upgrade_old_execute_fp}")
        os.unlink(upgrade_old_execute_fp)
    os.rename(get_exec(), upgrade_old_execute_fp)
    os.rename(upgrade_execute_fp, get_exec())

    return exit_code


def get_assistance():
    fname = "assistance.txt"
    can_delete = True
    if not os.path.exists(get_resource(fname)):
        return -1
    logger.info(f"检测到 {fname}，准备获取帮助文件。")
    with open(get_resource(fname), "r", encoding="utf-8") as f:
        config = f.read().strip().splitlines()
    for i in config:
        # tmp = download(
        #     {
        #         "url": f"https://github.com/8388688/Symbiosis/raw/refs/heads/main/samples/{i}.sample",
        #         "headers": {},
        #         "filepath": get_resource(i + ".sample"),
        #         "retry": 10
        #     }
        # )
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
    params = argparse.ArgumentParser()
    params.add_argument("cfgfile", nargs="?", default="config.json")
    params.add_argument("tmp_cfg", nargs="?", default="config.temp.json")
    params.add_argument("--debug", action="store_true")
    args, unknown = params.parse_known_args()
    if args.debug:
        logger.setLevel(colorlog.DEBUG)
    else:
        logger.setLevel(colorlog.INFO)
    if unknown:
        logger.warning(f"未知 {len(unknown)} 参数: {', '.join(unknown)}")
    else:
        logger.debug(f"传参：{args}")
        logger.info(f"参数规范 :)")
    return args


def merge_config(conf1, conf2):
    pass


def get_config(conf_fp, temp_conf_fp):
    config = dict()
    tmp = dict()
    tmp.update({"ignore_case": False})
    with open(temp_conf_fp, "r", encoding="utf-8") as f:
        tmp.update(json.loads(f.read()))
    if tmp.get("ignore_case"):
        pass
    else:
        with open(conf_fp, "r", encoding="utf-8") as f:
            config.update(json.loads(f.read()))
    tmp.pop("ignore_case")
    # TODO: 这个 update 操作，会将 config.temp.json 部分覆盖 config.json 中的原有内容，即使 ignore_case 被设为 false 也会造成信息丢失。
    # FIXME: 用 merge_config 解决，实现无损合并。
    config.update(tmp)
    ##
    with open(temp_conf_fp, "w", encoding="utf-8") as f:
        f.write(r"{}")
    del tmp
    return config


def put_config(config, conf_fp):
    with open(conf_fp, "w", encoding="utf-8") as f:
        f.write(json.dumps(config, indent=4))


def init_logger() -> logging.Logger:
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

    # 使用按天轮转的文件日志处理器，保留最近 30 个日志文件（可根据需要调整 backupCount）
    rotating_fp = get_resource("logs", "symbiosis.log")
    time_rotate_file = logging.handlers.TimedRotatingFileHandler(
        filename=rotating_fp,
        when="midnight",
        interval=1,
        backupCount=1999998,
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
    logger.debug(f"执行 {type_} 操作")
    eaten = []
    tmp: dict = config
    for k, v in tmp.items():
        if v.get("TTL", -1) == 0:
            eaten.append(k)
        else:
            fx(k, v)
            tmp[k].update({"TTL": v.get("TTL", -1) - 1})
    logger.debug(f"{eaten=}")
    for i in eaten:
        tmp.pop(i)
    del eaten
    return tmp


def main():
    logger.info(f"当前版本：{__version__}")
    logger.info(f"操作系统版本：{platform.platform()}")
    try:
        get_assistance()
        for i, fx in OPERATORS:
            fr_json.update({i: run_series(i, fr_json.get(i, dict()), fx)})
        get_update()
        put_config(fr_json, fp)
    except Exception as e:
        exc_type, exc_value, exc_obj = sys.exc_info()
        logger.critical("======= FATAL ERROR =======")
        logger.critical("exception_type: \t%s" % exc_type)
        logger.critical("exception_value: \t%s" % exc_value)
        logger.critical("exception_object: \t%s" % exc_obj)
        logger.critical(f"======= FULL EXCEPTION =======\n{format_exc()}")
    else:
        pass
    finally:
        pass


OPERATORS = (("execute", run), ("deleteFile", deleteFile),
             ("download", download))
logger = init_logger()
args = parse_args()
fp = os.path.join(get_resource(args.cfgfile))
temporary_fp = os.path.join(get_resource(args.tmp_cfg))
try:
    fr_json = get_config(fp, temporary_fp)
except Exception as e:
    logger.critical(f"读取文件时出错: {e}")
    sys.exit(0)
else:
    globalsettings = fr_json.get("globalsettings", {})


if __name__ == "__main__":
    main()
