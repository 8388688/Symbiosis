from collections import defaultdict


DEFAULT_EXECUTE_CONFIG = {
    "exec": None,
    "parameters": [],
    "uac_admin": False,
    "use_psexec": None,
    "workdir": ".",

    "disable": False,
    "datetime": "..",
    "TTL": -1,
    "keep": False
}
DEFAULT_DOWNLOAD_CONFIG = {
    "url": None,
    "filepath": None,

    "disable": False,
    "datetime": "..",
    "TTL": -1,
    "keep": False
}

execute_factory = defaultdict()

DEFAULT_CONFIG = {
    "execute": {},
    "download": {},
    "deleteFile": {},
    "upgrade": {},
    "globalsettings": {}
}
DEFAULT_DOWNGRADE_CONFIG = {
    "downgrade": None,
    "permanent": False
}
DEFAULT_DOWNGRADE_CONFIG = defaultdict()
