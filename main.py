import argparse
from collections import defaultdict
from genericpath import isfile
import colorlog
import ctypes
import hashlib
import json
import logging
import logging.handlers
import os
import platform
import requests
import sys
import time

from os import PathLike
from requests.exceptions import SSLError, MissingSchema, ConnectionError, InvalidURL, InvalidSchema, RequestException
from traceback import format_exc
from typing import Callable, Generator, Mapping
from urllib3.exceptions import ProtocolError

from constants import *
from sym_ops import *
from sym_utils import *
# from typing import AnyStr

__version__ = "v1.5.3"
K_ENABLE_FUTURE = True
# Symbiosis/scripts/eraser/Eraserl.exe -folder /Temp/0 -subfolders -keepfolder -method "Gutmann" -silent


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


def check_time_can_do(config: defaultdict):
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


def run(id_, config: defaultdict):
    logger.info(f"运行 {id_=}")
    time_ch = check_time_can_do(config)
    exec_fp: PathLike = config.get("exec")
    parameters_orig: list[str] = config.get(
        "parameters", globalsettings.get("parameters", []))
    uac_admin: bool = config.get(
        "uac_admin", globalsettings.get("uac_admin", False))
    use_psexec: bool = config.get(
        "use_psexec", globalsettings.get("use_psexec", None))
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
    if not os.path.exists(psexec_fp) and config.get("use_psexec") is not None:
        logger.warning(f"{psexec_fp} 路径不存在，{use_psexec=} 实际成为无效设置。")
        psexec_fp_exists = False
    if not fake:
        if exec_fp is None:
            logger.error(f"键值对 exec 为必填")
            return 133
        if not os.path.exists(exec_fp):
            logger.error(f"{exec_fp=} 文件不存在")
            return 132
        if time_ch[1]:
            logger.debug(
                f"启动: {exec_fp=}, {parameters_orig=}, {uac_admin=}, {workdir=}, {use_psexec=}")
            if use_psexec and psexec_fp_exists:
                parameters: str = f"-d -i {'-s' if uac_admin else '-l'} -w {workdir} -accepteula -nobanner {exec_fp} " + \
                    " ".join((str(i) for i in parameters_orig))
                exec_fp_impass = psexec_fp
            else:
                parameters: str = " ".join((str(i) for i in parameters_orig))
                exec_fp_impass = exec_fp
            exit_code = ctypes.windll.shell32.ShellExecuteW(
                None, "runas" if uac_admin else "open", exec_fp_impass, parameters, workdir, 1)
            logger.info(f"启动 {exec_fp} 完成（不一定启动成功），返回状态码为 {exit_code}")
        else:
            logger.warning(f"启动时间不在 {time_ch[0]} 范围内")
    else:
        logger.info(f"假装启动: {exec_fp=}")


def download_api(url, file_path, headers, checksum: dict = dict(), ignore_status=False, safe_write=True):
    """a simple download script
    重试返回的代码参考 retry.md
    """
    headers = headers
    try:
        r = requests.get(
            url, stream=True, verify=True,
            headers=headers, allow_redirects=False)
    except SSLError:
        logger.error(f'SSLError! [{url}] is not secure.')
        return 7  # SSL 证书无效或已过期
    except MissingSchema:
        logger.error(f"Invalid URL [{url}]: No scheme supplied")
        return 11  # 协议格式不正确
    except InvalidURL:
        logger.error(f"Invalid URL: Failed to parse [{url}]")
        return 8  # URL 格式不正确
    except InvalidSchema:
        logger.error(f"No connection adapters were found for [{url}]")
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

    logger.info(f"校验: url: {url}, 大小: {filesize if filesize != -1 else '?'}")
    logger.debug(f"当前 UA: {headers.get('User-Agent', '<空>')}")
    logger.debug(f"{r.status_code=}, {r.history=}, {r.elapsed=}")
    if ignore_status or r.status_code == 200:
        pass
    else:
        if 300 <= r.status_code < 400 and K_ENABLE_FUTURE:
            visited_urls = set()
            tmp = url
            r2 = r
            while True:
                latest_url = r2.headers.get('Location')
                if latest_url is None:
                    break
                else:
                    logger.warning(
                        f"Redirect: {tmp} -> {latest_url}")
                if latest_url in visited_urls:
                    logger.error("检测到重定向循环")
                    return 14

                r2 = requests.get(
                    latest_url, stream=True, verify=True,
                    headers=headers, allow_redirects=False)
                visited_urls.add(latest_url)
                tmp = latest_url
            r = r2

        else:
            logger.warning(f"Error downloading file: {r.status_code=}")
            return 13

    st = time.time()
    if safe_write:
        orig_file_path = file_path
        file_path += ".tmp"
    if not os.path.exists(os.path.dirname(file_path)):
        logger.debug(f"{file_path=}")
        os.makedirs(os.path.dirname(file_path), exist_ok=False)
    try:
        with open(file_path, "wb") as f:
            for i in r.iter_content(chunk_size=16384):
                f.write(i)
    except OSError as e:
        logger.error(f"无法保存至 {file_path} (Error {e.winerror}: {e.strerror})")
        return 192
    else:
        logger.debug(f"{url} 下载为 {file_path}")
    el = time.time() - st
    if checksum:
        logger.debug("校验文件中. . .")
        for k, v in checksum.items():
            logger.debug(f"校验文件的 {k} 值")
            if not md5check(file_path, k, v):
                return 12
            else:
                logger.debug(f"文件的 {k} 哈希校验无误")
        else:
            logger.debug("文件所有哈希校验无误")
    if safe_write:
        if os.path.exists(orig_file_path):
            os.unlink(orig_file_path)
        os.rename(file_path, orig_file_path)

    logger.info(
        f"Download complete, Time used: response={r.elapsed.total_seconds()}s, download={el:.2f}s.")
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
    safe_write = config.get(
        "safe_write", globalsettings.get("safe_write", True))
    if url is None or filepath is None:
        logger.error(f"{url=} and/or {filepath=} is empty.")
        return 135
    if config.get("timestamp", False):
        filepath = combine_timestamp_fp(filepath)
    cnt = 0
    status = 1
    time_ch = check_time_can_do(config)
    if time_ch[1]:
        while not (0 <= retry - cnt < 1):
            status = download_api(
                url, filepath, headers, checksum, ignore_status, safe_write)
            if can_retry(status):
                cnt += 1
                logger.warning(
                    f"Download failed, still trying... ({cnt}/{retry if retry >= 0 else 'Infinity'})")
            else:
                break
        else:
            logger.error(f"Discard: {id_}")
    else:
        logger.warning(f"启动时间不在 {time_ch[0]} 范围内")
    return status


def deleteFile(id_, config):
    logger.debug(f"刪除文件 {id_}")
    fp = config.get("src")
    del_folder = config.get("folders", globalsettings.get("folders", True))
    only_subfolder = config.get(
        "only_subfolders", globalsettings.get("only_subfolders", False))
    time_ch = check_time_can_do(config)
    if not time_ch[1]:
        logger.warning(f"启动时间不在 {time_ch[0]} 范围内")
    logger.info(f"删除 [{fp}] 及其所属文件")
    tot_file, tot_dir, tot_size = 0, 0, 0
    exclude_dirs = []
    if not os.path.exists(fp):
        logger.error(f"{fp} - 文件不存在")
        return
    if os.path.isfile(fp):
        file_list: list | Generator = [fp, ]
    else:
        file_list: list | Generator = tree_fp_gen(fp, del_folder, True)
    for i in file_list:
        try:
            if i in exclude_dirs:
                logger.debug(f"skip: {i}")
                continue
            if os.path.isfile(i):
                tmp = os.path.getsize(i)
                # 这一行取消只读属性
                # ctypes.windll.kernel32.SetFileAttributesW(i, 0)
                os.chmod(i, 0o777)
                os.unlink(i)
                logger.debug(f"del file: {i}")
                tot_size += tmp
                tot_file += 1
            else:
                if not only_subfolder or i != fp:
                    os.chmod(i, 0o777)
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


def update_single_file_api(config: dict, local_make_time, save_path, channel):
    old_file_fp = save_path + ".orig"
    upgrade_content = []
    logger.debug(f"{config=}, {save_path=}")
    for k, v in config.items():
        if local_make_time == 0:
            logger.warning(
                f"make-time 键值对未设置，Symbiosis 将默认为您填入缺省参数 {local_make_time}")
        if "channel" not in v.keys():
            logger.warning(f"远程配置 {k} 的 channel 未设置，Symbiosis 将默认其为全版本更新的补丁")
            remote_channel = []
        else:
            remote_channel = v.get("channel")
        logger.debug(f"{k=}, {channel=}, {remote_channel=}")
        if decode_config_time_version(k) > decode_config_time_version(local_make_time) and (not remote_channel or channel in remote_channel):
            upgrade_content.append([k, v])
    upgrade_content.sort(
        key=lambda x: decode_config_time_version(x[0]), reverse=True)
    if upgrade_content:
        if len(upgrade_content) > 1:
            logger.info(
                f"检查到多个文件的累积更新：{", ".join([i[0] for i in upgrade_content])}。"
                f"将自动为您更新到最新的一个版本 {upgrade_content[0][0]}")
        upgrade_content[0][1].update({"make-time": upgrade_content[0][0]})
        if os.path.exists(old_file_fp):
            os.unlink(old_file_fp)
        if os.path.exists(save_path):
            os.rename(save_path, old_file_fp)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(upgrade_content[0][1], indent=4))
        logger.info("complete.")
    else:
        logger.info("没有更新可用")


def update_single_file(id_, dl_config: dict, local_make_time, save_path, channel):
    # dl_config 中的 filepath 为保存临时下载的路径
    # save_path 为更新的目标路径
    dl_config.update({"timestamp": False})
    ex_code = download(id_, dl_config)
    logger.debug(f"{dl_config=}, {save_path=}")
    if ex_code == 0:
        with open(dl_config.get("filepath"), "rb") as f:
            tmp = json.loads(f.read())
        exit_code = update_single_file_api(
            tmp, local_make_time, save_path, channel)
        logger.debug(f"delete: {dl_config.get('filepath')}")
        os.unlink(dl_config.get("filepath"))
        return exit_code
    else:
        logger.error(f"无法更新 {id_} - Error {ex_code}")
        return 134


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

    if os.path.exists(resource_path("downgrade.json")):
        with open(resource_path("downgrade.json"), "rb") as f:
            downgrade_config = json.loads(f.read())
        tmp = {"upgrade": {"downgrade": downgrade_config}}
        merge_config(fr_json, tmp, ip=True)
        os.unlink(resource_path("downgrade.json"))
    else:
        downgrade_config: dict = upgrade_config.get(
            "downgrade", DEFAULT_DOWNGRADE_CONFIG)
    downgrade_sign = downgrade_config.get("downgrade", None)
    logger.debug("Downloading version of configure file. . .")
    exit_code = download(
        "get-update", {
            "url": upgrade_config["json-url"],
            "filepath": upgrade_json_fp, "retry": retry, "timestamp": False})
    if exit_code != 0:
        logger.error(
            f"Cannot download version of configure file (Error {exit_code})")
        return exit_code
    logger.debug("Resolving configure file. . .")
    with open(upgrade_json_fp, "r", encoding="utf-8") as f:
        head_json = json.loads(f.read())
    os.unlink(upgrade_json_fp)

    #########################################################
    if upgrade_config.get("console", False):
        up_url_key = "url-con"
        up_hash_key = "sha256-con"
    else:
        up_url_key = "url-win"
        up_hash_key = "sha256-win"
    if downgrade_sign is not None:
        logger.info(f"发现无视版本的强制更新标志，准备更新至 {downgrade_sign}")
        if downgrade_sign in head_json["update-14pp"].keys():
            download("downgrade",
                     {"url": head_json["update-14pp"][downgrade_sign][up_url_key],
                      "filepath": upgrade_execute_fp, "retry": retry, "timestamp": False,
                      "checksum": {"sha256": head_json["update-14pp"][downgrade_sign][up_hash_key]}})
            if not downgrade_config.get("permanent", False):
                logger.debug("已清除一次性更新标志")
                downgrade_config.update({"downgrade": None})
            else:
                logger.warning(
                    "永久更新标志会在 Symbiosis 每次启动时都尝试一次降级更新，"
                    "这可能会扰乱正常更新进度，"
                    "除非你确定自己在干什么，否则请使用一次性更新标志（permanent=false）。")
            with open(get_resource("downgrade.json"), "w") as f:
                f.write(json.dumps(downgrade_config, indent=4))
        else:
            logger.error(
                f"强制更新标志应该是 {', '.join(head_json["update-14pp"].keys())} 之一，而不是 {downgrade_sign}")
            return 130
    else:
        for k, v in head_json["update-14pp"].items():
            if decode_version(k) > decode_version(__version__) and k not in upgrade_config.get("specific_version_exclude", []):
                upgrade_content.append([k, v])
        upgrade_content.sort(
            key=lambda x: decode_version(x[0]), reverse=True)
        if upgrade_content:
            if len(upgrade_content) > 1:
                logger.info(
                    f"检查到多个版本的累积更新: {', '.join([i[0] for i in upgrade_content])}。"
                    f"将自动为您更新到最新版本 {upgrade_content[0][0]}")
            ex_code = download(
                "get-update.14pp",
                {"url": upgrade_content[0][1][up_url_key], "filepath": upgrade_execute_fp,
                 "retry": retry, "timestamp": False,
                 "checksum": {"sha256": head_json["update-14pp"][upgrade_content[0][0]][up_hash_key]}}
            )
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
            logger.info(f"主程序暂无更新 {exit_code=}")

    if upgrade_config.get("enable-config-update", True):
        logger.info("更新主配置文件")
        update_single_file("configFile.up", {
            "url": fr_json["upgrade"]["config-url"],
            "filepath": resource_path(args.configFile + ".upgrade"),
            "retry": retry
        }, local_make_time, get_resource(args.configFile), channel=0)
        #######
        logger.info("更新补丁配置文件，补丁将在下一次启动时应用到主配置文件中。")
        update_single_file("patchFile.up", {
            "url": fr_json["upgrade"]["patch-url"],
            "filepath": resource_path(args.patchFile + ".upgrade"),
            "retry": retry
        }, local_make_time, get_resource(args.patchFile),
            fr_json["upgrade"].get(
            "channel", fr_json["upgrade"].get("channel2", 0))
        )
    else:
        logger.info("更新配置文件 - 选项已禁用")

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
    params.add_argument("configFile", nargs="?", default="config.json")
    params.add_argument("patchFile", nargs="?", default="config.temp.json")
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
        logger.debug(f"参数规范 :)")
    return args


def get_config(conf_fp, patch_fp):
    config = dict()
    tmp = dict()
    tmp.update({"ignore_case": False})
    if not os.path.exists(patch_fp):
        logger.error(f"{patch_fp} 不存在，你可以将其视为空值，该文件在后续将自动创建。")
    else:
        with open(patch_fp, "r", encoding="utf-8") as f:
            tmp.update(json.loads(f.read()))
    if tmp.get("ignore_case"):
        pass
    else:
        with open(conf_fp, "r", encoding="utf-8") as f:
            config.update(json.loads(f.read()))
    tmp.pop("ignore_case")
    config.update(merge_config(config, tmp))
    with open(patch_fp, "w", encoding="utf-8") as f:
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
    logger.debug(f"执行 {type_} 操作")
    eaten = []
    tmp: dict = config
    for k, v in tmp.items():
        if v.get("TTL", -1) == 0:
            if v.get("keep", globalsettings.get("keep", False)):
                eaten.append(k)
            else:
                logger.debug(f"id={k} 的 keep 项被设置为 true，保留其值。")
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
        logger.critical(f"======= FULL EXCEPTION =======\n{format_exc()}\n")
    else:
        pass
    finally:
        logger.info("Done.\n")


OPERATORS = (("execute", run), ("deleteFile", deleteFile),
             ("download", download))
logger = init_logger()
args = parse_args()
fp = os.path.join(get_resource(args.configFile))
patch_fp = os.path.join(get_resource(args.patchFile))
try:
    fr_json = get_config(fp, patch_fp)
except Exception as e:
    logger.critical(f"读取文件时出错: {e}")
    sys.exit(0)
else:
    globalsettings = fr_json.get("globalsettings", {})


if __name__ == "__main__":
    main()
