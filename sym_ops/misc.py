import subprocess


__all__ = ["add_startup_task"]


def add_startup_task(task_name, exe_path, arguments=""):
    """
    将指定程序添加为 Windows 登录时执行的计划任务。

    :param task_name: 任务名称（唯一）
    :param exe_path: 可执行文件完整路径
    :param arguments: 启动参数（可选）
    :return: True 表示成功，False 表示失败
    """
    # 构造 schtasks 命令
    cmd = [
        "schtasks",
        "/Create",
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",
        "/TN", task_name,
        "/TR", f'"{exe_path}" {arguments}'.strip(),
        "/F"
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True)
        return result, True
    except subprocess.CalledProcessError as e:
        # print(f"添加计划任务失败: {e.stderr}")
        return e.stderr, False


# 示例用法
if __name__ == "__main__":
    # 例如: 将 C:\MyApp\myapp.exe 加入登录启动
    add_startup_task("MyAppAutoStart", r"C:\MyApp\myapp.exe")
