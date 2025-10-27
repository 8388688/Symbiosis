# 1.3.1 更新：
此更新影响 config.json 主配置文件中的 exec 和 download 键值对
- Fixed: deleteFile 部分优化
- Added: use_psexec(in "exec")
- Added: ignore_status(in "download")
- Modified: sample 帮助文件现在整合进二进制中而不是联网获取

# 1.3 更新：
- Fixed: 当配置文件 upgrade 项为空的时候，将会因检查更新失败而异常退出
- Added: deleteFile

# 1.2.4 更新【LTS 支持】：
- 下载时校验文件哈希值

# 1.2.3 更新【LTS 支持】：
- 下载时校验文件哈希值
- 加入 --debug 参数调试选项

# 1.2.2 更新【破坏性更新】：
- 将 update 中的 downgrade_install 参数分离出来，单独成一个文件 downgrade.json
- 修复 downgrade_install 降级安装时无法正常将旧程序重命名的问题

# 1.2.1 更新【破坏性更新】：
- 修正 download 的 replace-in-force 参数优化为 timestamp 参数
- 支持下载 console 控制台版本
- 【破坏性更新】version.json 更新数据格式做了优化，"Symbiosis-update" 现已拆分成 "Symbiosis-update-win" 和 "Symbiosis-update-con"
- "Symbiosis-update" 键值对预计在 1.5 版本移除，届时 1.2 及以下版本的程序将无法收到更新

## 1.2 更新：
- 支持 exec 和 download 在特定时间段运行和下载
- 修复时间戳缺省的问题
- 日志文件现在以 “*.log” 结尾
- 优化 disable 选项
- download 下的小项可以自定义 headers

## 1.1-release 紧急补丁：
- 修正 1.0 以及更低版本无法正确判定版本号的 bug

## 1.1 更新【破坏性更新】：
- 完成静默更新
- :art: 修正程序内部错误码
- :sparkles: 现在配置文件也可以静默更新啦

## 1.0 更新（【破坏性更新】不支持 0.4.0 以下的版本）
- :sparkles: 静默更新(BETA)
- 【破坏性更新】修整 config.json 格式
- - 加入 download, upgrade 选项
- - exec 选项可以用 disable 禁用

## 0.4 更新：
- 加入日志记录功能

## 0.3.1 紧急更新：
- 修复将全局设置项当成启动程序而读取出错 bug
- 修复在出现参数错误时静默退出的 bug —— 现在会 print 出错的参数
- 在一个版本之后，即 Symbiosis 0.4+, 将会记录日志

## 0.3.0 更新：
- 允许自定义配置文件路径（在 DOS 参数中设置）
- 修复配置文件路径错误的 bug
