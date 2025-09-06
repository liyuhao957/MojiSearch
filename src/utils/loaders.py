"""
异步图片加载器
"""

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.api import WeiboAPI


# --- Weibo CDN size helpers -------------------------------------------------
# 常见尺寸段：thumb150 / orj360 / bmiddle / mw690 / mw1024 / large
# 我们统一通过替换路径段的方式选择合适尺寸，避免下载超大原图。
SIZE_SEGMENTS = (
    '/thumb150/', '/orj360/', '/bmiddle/', '/mw690/', '/mw1024/', '/large/'
)

def _replace_size_segment(url: str, target_segment: str) -> str:
    """将 URL 中的尺寸段替换为 target_segment；如果不存在已知尺寸段，则尽量插入。
    仅替换域名后的首个路径段，不改变其余部分。
    """
    for seg in SIZE_SEGMENTS:
        if seg in url:
            return url.replace(seg, target_segment)
    # 未命中任何尺寸段，尝试在域名后的第一个斜杠后插入目标段
    try:
        parts = url.split('/', 3)  # [scheme, '', host, rest]
        if len(parts) >= 4:
            scheme, empty, host, rest = parts
            if not rest.startswith(('http', 'https')):
                return f"{scheme}//{host}{target_segment}{rest}"
    except Exception:
        pass
    return url

def get_display_url(url: str) -> str:
    """网格/预览用的显示 URL：优先 bmiddle，其次 orj360，尽量避免 large。"""
    # 先统一成 bmiddle，如果 CDN 不支持该段，会回退到 orj360
    url_b = _replace_size_segment(url, '/bmiddle/')
    if url_b != url:
        return url_b
    return _replace_size_segment(url, '/orj360/')

def get_copy_url(url: str) -> str:
    """复制用的 URL：使用 mw1024（质量和体积的折中），避免动辄 4K+ 的 large。"""
    return _replace_size_segment(url, '/mw1024/')

def get_original_url(url: str) -> str:
    return _replace_size_segment(url, '/large/')

# 兼容旧接口名：get_large_url 返回原图 large

def get_large_url(url: str) -> str:
    return get_original_url(url)


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
                        get_display_url(self.url),
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
            r = requests.get(get_copy_url(self.url), headers=WeiboAPI.HEADERS, timeout=10)
            if r.status_code == 200:
                self.done.emit(r.content, "")
            else:
                self.done.emit(b"", f"状态码: {r.status_code}")
        except Exception as e:
            self.done.emit(b"", str(e))