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
    """异步图片加载器"""
    image_loaded = pyqtSignal(int, bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, url, index):
        super().__init__()
        self.url = url
        self.index = index

    def run(self):
        try:
            response = requests.get(get_large_url(self.url), headers=WeiboAPI.HEADERS, timeout=5)
            if response.status_code == 200:
                self.image_loaded.emit(self.index, response.content)
            else:
                self.error_occurred.emit(f"图片加载失败: {response.status_code}")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("图片加载超时")
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("网络连接失败")
        except Exception:
            pass


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