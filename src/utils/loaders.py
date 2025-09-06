"""
异步图片加载器
"""

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.api import WeiboAPI


def get_large_url(url):
    """转换为大图 URL"""
    return url.replace('/orj360/', '/large/').replace('/thumb150/', '/large/').replace('/bmiddle/', '/large/')


class ImageLoader(QThread):
    """异步图片加载器 - 支持优雅停止"""
    image_loaded = pyqtSignal(int, bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, url, index):
        super().__init__()
        self.url = url
        self.index = index
        self._stop_requested = False  # 新增：停止标记
    
    def request_stop(self):
        """请求停止线程"""
        self._stop_requested = True
        self.requestInterruption()  # Qt的中断请求

    def run(self):
        try:
            # 使用更短的超时，支持快速响应中断
            for attempt in range(3):  # 最多重试3次
                if self._stop_requested or self.isInterruptionRequested():
                    return
                    
                try:
                    response = requests.get(
                        get_large_url(self.url),
                        headers=WeiboAPI.HEADERS,
                        timeout=1.5,  # 缩短到1.5秒
                        stream=True
                    )
                    break
                except requests.exceptions.Timeout:
                    if attempt == 2:  # 最后一次尝试
                        raise
                    continue
                    
            if self._stop_requested or self.isInterruptionRequested():
                return
                
            # 分块读取，支持中断
            chunks = []
            for chunk in response.iter_content(chunk_size=8192):
                if self._stop_requested or self.isInterruptionRequested():
                    response.close()
                    return
                if chunk:
                    chunks.append(chunk)
                    
            if response.status_code == 200:
                data = b''.join(chunks)
                if not self._stop_requested:
                    self.image_loaded.emit(self.index, data)
            else:
                if not self._stop_requested:
                    self.error_occurred.emit(f"图片加载失败: {response.status_code}")
        except requests.exceptions.Timeout:
            if not self._stop_requested:
                self.error_occurred.emit("图片加载超时")
        except requests.exceptions.ConnectionError:
            if not self._stop_requested:
                self.error_occurred.emit("网络连接失败")
        except Exception:
            pass  # 静默处理其他异常


class CopyLoader(QThread):
    """后台下载用于复制的图片"""
    done = pyqtSignal(bytes, str)  # data, error

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            r = requests.get(get_large_url(self.url), headers=WeiboAPI.HEADERS, timeout=10)
            if r.status_code == 200:
                self.done.emit(r.content, "")
            else:
                self.done.emit(b"", f"状态码: {r.status_code}")
        except Exception as e:
            self.done.emit(b"", str(e))