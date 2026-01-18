import os
import ctypes
from typing import List, Optional
from os import PathLike


class ExecutionError(Exception):
    """执行操作异常"""
    pass


class Executor:
    """负责程序执行逻辑"""

    def __init__(self, logger, resource_path_fn, is64bit_fn):
        self.logger = logger
        self.resource_path = resource_path_fn
        self.is64bit = is64bit_fn

    def _get_psexec_path(self) -> str:
        """获取 PsExec 可执行文件路径"""
        psexec_name = "PsExec64.exe" if self.is64bit() else "PsExec.exe"
        return self.resource_path("scripts", psexec_name)

    def _validate_executable(self, exec_fp: PathLike) -> int:
        """验证可执行文件存在性"""
        if exec_fp is None:
            self.logger.error("键值对 exec 为必填")
            return 133

        if not os.path.exists(exec_fp):
            self.logger.error(f"{exec_fp=} 文件不存在")
            return 132

        return 0

    def _build_psexec_command(
        self,
        exec_fp: str,
        parameters: List[str],
        workdir: str,
        use_admin: bool,
        psexec_fp: str
    ) -> tuple:
        """构建 PsExec 命令"""
        params_str = " ".join((str(p) for p in parameters))
        cmd = (
            f"-d -i {'-s' if use_admin else '-l'} -w {workdir} "
            f"-accepteula -nobanner {exec_fp} {params_str}"
        )
        return psexec_fp, cmd

    def _build_direct_command(
        self,
        exec_fp: str,
        parameters: List[str]
    ) -> tuple:
        """构建直接执行命令"""
        params_str = " ".join((str(p) for p in parameters))
        return exec_fp, params_str

    def execute(
        self,
        exec_fp: PathLike,
        parameters: Optional[List[str]] = None,
        uac_admin: bool = False,
        use_psexec: bool = False,
        workdir: Optional[PathLike] = None,
        disable: bool = False
    ) -> int:
        """
        执行程序
        返回值: ShellExecute 返回码
        """
        if disable:
            self.logger.info(f"假装启动: {exec_fp=}")
            return 0

        # 验证可执行文件
        error_code = self._validate_executable(exec_fp)
        if error_code != 0:
            return error_code

        parameters = parameters or []
        workdir = workdir or os.getcwd()

        # 确定执行方式
        psexec_fp = self._get_psexec_path()
        psexec_exists = os.path.exists(psexec_fp)

        if use_psexec and psexec_exists:
            final_exec_fp, final_params = self._build_psexec_command(
                exec_fp, parameters, str(workdir), uac_admin, psexec_fp
            )
        else:
            if use_psexec and not psexec_exists:
                self.logger.warning(
                    f"{psexec_fp} 路径不存在，use_psexec 实际成为无效设置。"
                )
            final_exec_fp, final_params = self._build_direct_command(
                exec_fp, parameters)

        self.logger.debug(
            f"启动: {exec_fp=}, {parameters=}, {uac_admin=}, {workdir=}, {use_psexec=}"
        )

        # 执行
        exit_code = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas" if uac_admin else "open",
            final_exec_fp,
            final_params,
            str(workdir),
            1
        )

        self.logger.info(
            f"启动 {exec_fp} 完成（不一定启动成功），返回状态码为 {exit_code}"
        )

        return exit_code
