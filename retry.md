code:
\[1..127\] 是网络问题
\[128..191\] 是用户问题
\[192..223\] 是 OS 问题

触发重试机制
code 取值范围：\[0..255\] 的整数
0 表示正常，不会触发重试机制
\[1..127\] 表示会触发重试机制的异常
\[128..255\] 表示【不会】触发重试机制的异常

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
127 = unexpected error

128 = 用户禁用了更新
129 = Read configure file ERROR: symbiosis-update 键值对为空
130 = 强制更新的版本号标志错误

192 = 保存的目标文件所在的目录不存在
