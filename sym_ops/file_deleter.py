import os
from typing import Generator, List, Dict


class DeletionError(Exception):
    """删除操作异常"""
    pass


class FileDeleter:
    """负责文件删除逻辑"""

    def __init__(self, logger, tree_gen_fn):
        self.logger = logger
        self.tree_gen = tree_gen_fn

    def _get_file_list(
        self,
        fp: str,
        del_folders: bool = True,
        recursive: bool = True
    ) -> Generator | List:
        """获取要删除的文件列表"""
        if os.path.isfile(fp):
            return [fp]
        return self.tree_gen(fp, del_folders, recursive)

    def _delete_file(self, file_path: str) -> int:
        """删除单个文件，返回文件大小"""
        try:
            file_size = os.path.getsize(file_path)
            os.chmod(file_path, 0o777)
            os.unlink(file_path)
            self.logger.debug(f"del file: {file_path}")
            return file_size
        except OSError as e:
            self.logger.warning(
                f"Delete failed, error {e.winerror}: {e.strerror} "
                f"(Code {e.errno}) {e.filename=}, {e.filename2=}."
            )
            raise

    def _delete_directory(
        self,
        dir_path: str,
        root_path: str,
        only_subfolders: bool = False
    ) -> bool:
        """删除单个目录"""
        try:
            # 不删除根路径本身（如果 only_subfolders=True）
            if only_subfolders and os.path.normpath(dir_path) == os.path.normpath(root_path):
                return True

            os.chmod(dir_path, 0o777)
            os.rmdir(dir_path)
            self.logger.debug(f"del dir: {dir_path}")
            return True
        except OSError as e:
            self.logger.warning(
                f"Delete failed, error {e.winerror}: {e.strerror} "
                f"(Code {e.errno}) {e.filename=}, {e.filename2=}."
            )
            return False

    def delete(
        self,
        file_path: str,
        del_folders: bool = True,
        only_subfolders: bool = False
    ) -> Dict[str, int]:
        """
        删除文件/目录
        返回值: {"files": 删除文件数, "dirs": 删除目录数, "size": 总字节数}
        """
        if not os.path.exists(file_path):
            self.logger.error(f"{file_path} - 文件不存在")
            return {"files": 0, "dirs": 0, "size": 0}

        self.logger.info(f"删除 [{file_path}] 及其所属文件")

        stats = {"files": 0, "dirs": 0, "size": 0}
        exclude_dirs = set()

        file_list = self._get_file_list(file_path, del_folders, True)

        for item in file_list:
            # 跳过已标记为失败的目录
            if item in exclude_dirs:
                self.logger.debug(f"skip: {item}")
                continue

            try:
                if os.path.isfile(item):
                    file_size = self._delete_file(item)
                    stats["size"] += file_size
                    stats["files"] += 1
                else:
                    if self._delete_directory(item, file_path, only_subfolders):
                        stats["dirs"] += 1
            except OSError:
                # 标记该目录及其父目录为失败
                tmp = item
                while os.path.normpath(tmp) != os.path.normpath(file_path):
                    tmp = os.path.dirname(tmp)
                    exclude_dirs.add(tmp)

        self.logger.info(
            f"总计删除 {stats['size']} 字节，{stats['files']} 个文件，"
            f"{stats['dirs']} 个文件夹。"
        )

        return stats
