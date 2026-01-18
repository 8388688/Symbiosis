import os
import time
import requests
import hashlib
from typing import Optional, Dict
from requests.exceptions import (
    SSLError, MissingSchema, ConnectionError, InvalidURL,
    InvalidSchema, RequestException
)
from urllib3.exceptions import ProtocolError


class DownloadError(Exception):
    """下载操作异常"""
    pass


class Downloader:
    """负责文件下载、验证和重试逻辑"""

    # 错误映射表
    ERROR_MAP = {
        SSLError: (7, 'SSLError! [{url}] is not secure.'),
        MissingSchema: (11, "Invalid URL [{url}]: No scheme supplied"),
        InvalidURL: (8, "Invalid URL: Failed to parse [{url}]"),
        InvalidSchema: (10, "No connection adapters were found for [{url}]"),
        ProtocolError: (2, "ProtocolError"),
        TimeoutError: (6, "Connection Timeout"),
        ConnectionError: (9, "Failed to connect {url}"),
        RequestException: (1, "Request Error {url}"),
    }

    def __init__(self, logger, enable_future=True):
        self.logger = logger
        self.K_ENABLE_FUTURE = enable_future
        self.CHUNK_SIZE = 16384

    def _handle_request(self, url: str, headers: dict) -> tuple:
        """处理 HTTP 请求，返回 (response, error_code)"""
        try:
            r = requests.get(
                url, stream=True, verify=True,
                headers=headers, allow_redirects=False
            )
            return r, 0
        except tuple(self.ERROR_MAP.keys()) as e:
            code, msg = self.ERROR_MAP[type(e)]
            self.logger.error(msg.format(url=url))
            return None, code
        except Exception as e:
            self.logger.error(f"Unexpected Error: {e.args}")
            return None, 127

    def _handle_redirects(self, url: str, headers: dict, r) -> tuple:
        """处理 HTTP 重定向"""
        if not (300 <= r.status_code < 400 and self.K_ENABLE_FUTURE):
            return r, 0

        visited_urls = {url}
        while True:
            latest_url = r.headers.get('Location')
            if not latest_url:
                break

            self.logger.warning(f"Redirect: {url} -> {latest_url}")

            if latest_url in visited_urls:
                self.logger.error("检测到重定向循环")
                return None, 14

            r, error_code = self._handle_request(latest_url, headers)
            if error_code != 0:
                return None, error_code

            visited_urls.add(latest_url)
            url = latest_url

        return r, 0

    def _save_file(self, response, file_path: str, safe_write: bool = True) -> int:
        """保存响应内容到文件"""
        orig_file_path = file_path
        if safe_write:
            file_path += ".tmp"

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        try:
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                    f.write(chunk)
        except OSError as e:
            self.logger.error(
                f"无法保存至 {file_path} (Error {e.winerror}: {e.strerror})"
            )
            return 192

        self.logger.debug(f"下载为 {file_path}")

        if safe_write:
            if os.path.exists(orig_file_path):
                os.unlink(orig_file_path)
            os.rename(file_path, orig_file_path)

        return 0

    def _verify_checksum(self, file_path: str, checksum: Dict[str, str]) -> int:
        """验证文件哈希"""
        self.logger.debug("校验文件中. . .")
        for algorithm, expected_hash in checksum.items():
            self.logger.debug(f"校验文件的 {algorithm} 值")

            actual_hash = self._calculate_hash(file_path, algorithm)
            if actual_hash.lower() != expected_hash.lower():
                self.logger.error(
                    f"校验失败，文件的 {algorithm} 哈希应为 {expected_hash}，"
                    f"实际上却是 {actual_hash}"
                )
                return 12

            self.logger.debug(f"文件的 {algorithm} 哈希校验无误")

        self.logger.debug("文件所有哈希校验无误")
        return 0

    @staticmethod
    def _calculate_hash(file_path: str, algorithm: str, buffering: int = 8096) -> str:
        """计算文件哈希"""
        with open(file_path, 'rb') as f:
            result = hashlib.new(algorithm)
            for chunk in iter(lambda: f.read(buffering), b''):
                result.update(chunk)
            return result.hexdigest()

    def download(
        self,
        url: str,
        file_path: str,
        headers: dict,
        checksum: Optional[Dict[str, str]] = None,
        ignore_status: bool = False,
        safe_write: bool = True
    ) -> int:
        """
        下载文件主方法
        返回值: 0=成功，其他=错误码（参考 retry.md）
        """
        checksum = checksum or {}

        # 请求并处理重定向
        r, error_code = self._handle_request(url, headers)
        if error_code != 0:
            return error_code

        # 处理重定向
        r, error_code = self._handle_redirects(url, headers, r)
        if error_code != 0:
            return error_code

        # 检查状态码
        filesize = r.headers.get("content-length", -1)
        if filesize != -1:
            filesize = int(filesize)

        self.logger.info(
            f"校验: url: {url}, 大小: {filesize if filesize != -1 else '?'}")
        self.logger.debug(f"当前 UA: {headers.get('User-Agent', '<空>')}")
        self.logger.debug(f"{r.status_code=}, {r.history=}, {r.elapsed=}")

        if not (ignore_status or r.status_code == 200):
            self.logger.warning(f"Error downloading file: {r.status_code=}")
            return 13

        # 保存文件
        st = time.time()
        error_code = self._save_file(r, file_path, safe_write)
        if error_code != 0:
            return error_code

        el = time.time() - st

        # 校验哈希
        if checksum:
            error_code = self._verify_checksum(file_path, checksum)
            if error_code != 0:
                return error_code

        self.logger.info(
            f"Download complete, Time used: response={r.elapsed.total_seconds():.2f}s, download={el:.2f}s."
        )
        return 0
