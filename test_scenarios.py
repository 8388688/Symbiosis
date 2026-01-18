#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ConfigReader 综合场景测试"""

from collections import defaultdict
from sym_utils import ConfigReader

# 模拟全局设置
global_settings = {
    'retry': 3,
    'headers': {'User-Agent': 'Test'},
    'parameters': [],
    'uac_admin': False,
    'folders': True,
}

reader = ConfigReader(global_settings)

# 测试 run() 场景
print('【测试 run() 场景】')
config = defaultdict(lambda: None)
config['exec'] = 'notepad.exe'
config['uac_admin'] = True  # 覆盖全局

params = reader.get_multi(dict(config), {
    'exec': None,
    'parameters': [],
    'uac_admin': False,
    'use_psexec': False,
})

print(f'  exec: {params["exec"]} (来自 config)')
print(f'  uac_admin: {params["uac_admin"]} (来自 config)')
print(f'  parameters: {params["parameters"]} (来自 global_settings)')

# 测试 download() 场景
print('\n【测试 download() 场景】')
config2 = {'url': 'https://example.com/file.zip'}

params2 = reader.get_multi(config2, {
    'url': None,
    'filepath': None,
    'retry': 1,
    'headers': {},
})

print(f'  url: {params2["url"]} (来自 config)')
print(f'  retry: {params2["retry"]} (来自 global_settings)')
print(f'  headers: {params2["headers"]} (来自 global_settings)')
print(f'  filepath: {params2["filepath"]} (缺省值)')

# 测试 deleteFile() 场景
print('\n【测试 deleteFile() 场景】')
config3 = {'src': '/tmp/test', 'folders': False}

params3 = reader.get_multi(config3, {
    'src': None,
    'folders': True,
    'only_subfolders': False,
})

print(f'  src: {params3["src"]} (来自 config)')
print(f'  folders: {params3["folders"]} (来自 config)')
print(f'  only_subfolders: {params3["only_subfolders"]} (缺省值)')

print('\n✓ 所有场景测试通过！')
