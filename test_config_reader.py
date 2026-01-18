#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ConfigReader 统一配置读取工具演示"""

from sym_utils import ConfigReader

# 定义全局设置
global_settings = {
    "retry": 3,
    "timeout": 30,
    "headers": {"User-Agent": "Mozilla/5.0"},
    "folders": True,
    "disable": False,
}

# 创建配置读取器
reader = ConfigReader(global_settings)

print("=" * 60)
print("ConfigReader 统一配置读取工具演示")
print("=" * 60)

# 测试1：配置优先级演示
print("\n【测试1】配置优先级演示")
print("-" * 60)

config1 = {
    "url": "https://example.com/file.zip",
    "retry": 5,  # 覆盖全局设置
    "timeout": None,  # None 值会被忽略，使用全局设置
}

result = reader.get(config1, "url", "http://default.com")
print(f"url (config 有值):      {result}")
print(f"  优先级: config > global_settings > default")

result = reader.get(config1, "retry", 1)
print(f"\nretry (config 覆盖):    {result}")
print(f"  优先级: config (5) > global_settings (3) > default (1)")

result = reader.get(config1, "timeout", 10)
print(f"\ntimeout (config 为 None):  {result}")
print(f"  优先级: global_settings (30) > default (10)")

result = reader.get(config1, "headers", {})
print(f"\nheaders (config 无):    {result}")
print(f"  优先级: global_settings {global_settings['headers']}")

result = reader.get(config1, "unknown_key", "fallback_value")
print(f"\nunknown_key (都没有):   {result}")
print(f"  优先级: default (fallback_value)")

# 测试2：批量读取配置
print("\n\n【测试2】批量读取配置 (get_multi)")
print("-" * 60)

config2 = {
    "filepath": "/tmp/download.zip",
    "safe_write": False,
}

keys = {
    "url": None,
    "filepath": None,
    "retry": 1,
    "headers": {},
    "safe_write": True,
    "folders": False,
}

results = reader.get_multi(config2, keys)
for key, value in results.items():
    print(f"  {key:15} = {value}")

# 测试3：更新全局设置
print("\n\n【测试3】动态更新全局设置")
print("-" * 60)

new_global_settings = {
    "retry": 5,
    "timeout": 60,
    "disable": True,
}

reader.update_global_settings(new_global_settings)
print(f"更新全局设置后:")

config3 = {"retry": None}  # 配置中没有 retry

result = reader.get(config3, "retry", 1)
print(f"  retry: {result} (从新的全局设置读取)")

result = reader.get(config3, "timeout", 30)
print(f"  timeout: {result} (从新的全局设置读取)")

result = reader.get(config3, "disable", False)
print(f"  disable: {result} (从新的全局设置读取)")

# 测试4：实际应用场景
print("\n\n【测试4】实际应用场景 - 下载配置")
print("-" * 60)

# 假设这是从配置文件读取的
download_config = {
    "url": "https://example.com/app.exe",
    "filepath": "/path/to/app.exe",
    "retry": 5,  # 这个任务需要更多重试
}

# 全局缺省
global_download_defaults = {
    "retry": 3,
    "headers": {"User-Agent": "MyApp/1.0"},
    "checksum": {"sha256": "abc123"},
    "ignore_status": False,
    "safe_write": True,
}

reader2 = ConfigReader(global_download_defaults)

download_params = reader2.get_multi(download_config, {
    "url": None,
    "filepath": None,
    "retry": 1,
    "headers": {},
    "checksum": {},
    "ignore_status": False,
    "safe_write": True,
})

print("下载任务配置:")
for key, value in download_params.items():
    if isinstance(value, dict) and value:
        print(f"  {key:15} = {value} (来自 global_settings)")
    elif key in download_config and download_config[key]:
        print(f"  {key:15} = {value} (来自 local config)")
    else:
        print(f"  {key:15} = {value} (来自 global_settings 或 default)")

print("\n" + "=" * 60)
print("✓ 所有测试完成！")
print("=" * 60)
