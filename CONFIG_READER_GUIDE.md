# ConfigReader 统一配置读取工具

## 概述

`ConfigReader` 是一个统一的配置读取工具，用于在 Symbiosis 项目中以一致的方式管理配置参数。

## 设计思想

配置参数的优先级如下：

1. **本地配置 (config)** - 最高优先级
2. **全局设置 (global_settings)** - 中等优先级
3. **内置缺省值 (default)** - 最低优先级

这样设计的好处是：
- 全局配置提供统一的缺省值
- 特定任务可以覆盖全局缺省值
- 代码清晰，易于维护

## 基本用法

### 1. 初始化

```python
from sym_utils import ConfigReader

# 定义全局设置
global_settings = {
    "retry": 3,
    "timeout": 30,
    "headers": {"User-Agent": "MyApp/1.0"},
    "safe_write": True,
}

# 创建配置读取器
config_reader = ConfigReader(global_settings)
```

### 2. 单个参数读取

```python
config = {
    "url": "https://example.com/file.zip",
    "retry": 5,  # 覆盖全局设置
}

# 读取单个参数，带缺省值
url = config_reader.get(config, "url", "http://default.com")
# 返回: "https://example.com/file.zip" (来自 config)

retry = config_reader.get(config, "retry", 1)
# 返回: 5 (来自 config，覆盖全局设置的 3)

timeout = config_reader.get(config, "timeout", 10)
# 返回: 30 (来自全局设置，config 中没有)

headers = config_reader.get(config, "headers", {})
# 返回: {"User-Agent": "MyApp/1.0"} (来自全局设置)

unknown = config_reader.get(config, "unknown_key", "fallback")
# 返回: "fallback" (都没有，使用缺省值)
```

### 3. 批量参数读取

```python
config = {
    "filepath": "/tmp/download.zip",
    "safe_write": False,
}

# 定义需要读取的参数及其缺省值
params_spec = {
    "url": None,
    "filepath": None,
    "retry": 1,
    "headers": {},
    "safe_write": True,
}

# 批量读取
params = config_reader.get_multi(config, params_spec)
# 返回:
# {
#     "url": None,                        # 都没有，使用缺省值
#     "filepath": "/tmp/download.zip",  # 来自 config
#     "retry": 3,                        # 来自全局设置
#     "headers": {...},                  # 来自全局设置
#     "safe_write": False,               # 来自 config
# }
```

### 4. 动态更新全局设置

```python
new_global_settings = {
    "retry": 5,
    "timeout": 60,
}

config_reader.update_global_settings(new_global_settings)
```

## 在 Symbiosis 中的应用

### 执行操作 (run)

```python
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
```

### 下载操作 (download)

```python
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
    # ... 使用参数进行下载
```

### 删除操作 (deleteFile)

```python
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

    file_deleter.delete(file_path=fp, del_folders=del_folder, only_subfolders=only_subfolder)
```

## 配置示例

### config.json 中的全局设置

```json
{
  "globalsettings": {
    "retry": 3,
    "headers": {
      "User-Agent": "Symbiosis/1.6"
    },
    "folders": true,
    "only_subfolders": false,
    "parameters": [],
    "uac_admin": false,
    "use_psexec": false,
    "work_dir": ".",
    "disable": false,
    "ignore_status": false,
    "safe_write": true,
    "datetime": ".."
  },
  "execute": [
    {
      "id": "task1",
      "exec": "notepad.exe",
      "parameters": ["file.txt"]
      // retry, uac_admin 等使用全局设置
    },
    {
      "id": "task2",
      "exec": "cmd.exe",
      "uac_admin": true,  // 覆盖全局设置
      "retry": 5          // 覆盖全局设置
    }
  ]
}
```

## 优势

1. **代码重复率低** - 避免重复的 `config.get(..., globalsettings.get(...))` 调用
2. **易于维护** - 统一的配置读取逻辑
3. **灵活性高** - 支持三层配置优先级
4. **类型安全** - 明确指定每个参数的缺省值
5. **易于测试** - 配置读取逻辑可单独测试

## API 参考

### `ConfigReader` 类

#### 初始化

```python
ConfigReader(global_settings: dict = None)
```

- `global_settings`: 全局设置字典，默认为空字典

#### 方法

##### `get(config: dict, key: str, default=None) -> Any`

读取单个配置值。

**参数：**
- `config`: 本地配置字典
- `key`: 配置键名
- `default`: 缺省值

**返回值：** 配置值，优先级为 config > global_settings > default

**示例：**
```python
value = config_reader.get(config, "retry", 1)
```

##### `get_multi(config: dict, keys: dict) -> dict`

批量读取配置值。

**参数：**
- `config`: 本地配置字典
- `keys`: `{配置键: 缺省值}` 的字典

**返回值：** `{配置键: 配置值}` 的字典

**示例：**
```python
params = config_reader.get_multi(config, {
    "url": None,
    "retry": 1,
    "headers": {}
})
```

##### `update_global_settings(global_settings: dict)`

更新全局设置。

**参数：**
- `global_settings`: 新的全局设置字典

**示例：**
```python
config_reader.update_global_settings(new_settings)
```

## 注意事项

1. **None 值处理** - 如果 config 中的值为 None，会被视为"未设置"，会继续查找 global_settings
2. **字典和列表** - 如果参数是字典或列表，建议在全局设置中设置缺省值，避免引用共享
3. **大小写敏感** - 配置键名区分大小写
4. **内存效率** - 使用 `get_multi()` 比多次调用 `get()` 更高效

## 参考

- 原始实现：[sym_utils.py](sym_utils.py)
- 测试脚本：[test_config_reader.py](test_config_reader.py)
- 主程序集成：[main.py](main.py)
