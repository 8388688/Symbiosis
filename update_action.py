import os

import json
from logging import Logger

from sym_utils import get_resource
from update_utils import *

__all__ = ["parse_update_action"]


def fx1(main_json: dict, logger_entity: Logger):
    content = f"应用 {fx1.__name__} 更新补丁。" \
        f"此补丁将移除 downgrade.json 文件。" \
        f"移除 config-url 等 1 个废弃的参数。" \
        f"移动 channel 和 lastrun_version 2 个参数" \
        f"建立 userdata 子配置。"
    logger_entity.info(content)
    if os.path.exists(get_resource("downgrade.json")):
        with open(get_resource("downgrade.json"), "r") as f:
            tmp = json.loads(f.read())
        if not main_json["upgrade"].get("downgrade"):
            main_json["upgrade"].update({"downgrade": tmp})
        del tmp
    if "userdata" not in main_json.keys():
        main_json.update({"userdata": dict()})
        for i in ("channel", "lastrun_version"):
            if i in main_json["upgrade"].keys():
                tmp = main_json["upgrade"].pop(i)
                main_json["userdata"].update({i: tmp})
                del tmp
    if "channel" in main_json.keys():
        tmp = main_json.pop("channel")
        if "channel" not in main_json["userdata"].keys():
            main_json["userdata"].update({"channel": tmp})
        del tmp
    if "config-url" in main_json["upgrade"].keys():
        main_json["upgrade"].pop("config-url")
    if "downgrade_install" in main_json["upgrade"].keys():
        tmp = main_json["upgrade"].pop("downgrade_install")
        if tmp:
            main_json["upgrade"].update({"downgrade": tmp})
        del tmp


def fx2(main_json: dict, logger_entity: Logger):
    content = f"应用 {fx2.__name__} 更新补丁。" \
        f"此补丁将创建 TOTA 一次性配置（目前为空）。"
    logger_entity.info(content)

    main_json.update({"TOTA": {}})


def parse_update_action(main_json: dict, logger_entity: Logger):
    up_content: list[UpgradeSlice] = []
    up_content.append(UpgradeSlice("1.6", "1.7"))
    up_content[0].action = lambda: fx1(main_json, logger_entity)
    up_content.append(UpgradeSlice("1.6.3", "1.7"))
    up_content[1].action = lambda: fx2(main_json, logger_entity)
    # up_content.append(UpgradeSlice(""))

    return up_content
