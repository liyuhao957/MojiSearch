"""
线程池管理器 - 优化图片加载性能
"""

from PyQt6.QtCore import QThreadPool, QRunnable, pyqtSignal, QObject, Qt, QBuffer
from PyQt6.QtGui import QImageReader
import requests

class TaskSignals(QObject):
    """任务信号 - 改进版包含index"""
    loaded = pyqtSignal(int, bytes)     # index, data
    error = pyqtSignal(int, str, str)   # index, code, message

class CancelToken:
    """取消令牌 - 支持取消正在进行的任务"""
    def __init__(self):
        self.is_cancelled = False
    
    def cancel(self):
        self.is_cancelled = True
    
    def reset(self):
        self.is_cancelled = False

class ImageLoadTask(QRunnable):
    """可取消的图片加载任务 - 支持真正的中断"""
    
    def __init__(self, url, index, cancel_token):
        super().__init__()
        self.url = url
        self.index = index
        self.cancel_token = cancel_token
        self.signals = TaskSignals()
        self.setAutoDelete(True)
        
    def run(self):
        """执行图片加载 - 支持缓存"""
        if self.cancel_token.is_cancelled:
            return
        
        # 先检查缓存
        from src.utils.image_cache import image_cache
        cached_data = image_cache.get(self.url)
        if cached_data:
            if not self.cancel_token.is_cancelled:
                self.signals.loaded.emit(self.index, cached_data)
            return
            
        try:
            # 延迟导入以避免循环依赖
            from src.utils.network import NetworkManager
            from src.utils.loaders import get_original_url
            from src.core.api import WeiboAPI
            
            # 使用thread-local session
            session = NetworkManager.get_session()
            
            # 分离超时，支持快速取消
            response = session.get(
                get_original_url(self.url),
                headers=WeiboAPI.HEADERS,
                timeout=(2, 5),  # 连接2秒，读取5秒
                stream=True
            )
            
            if self.cancel_token.is_cancelled:
                response.close()
                return
                
            if response.status_code == 200:
                # 分块读取，支持中断；在下载过程中尽早探测尺寸，过大则立刻中止
                chunks = []
                total_size = 0
                max_size = 10 * 1024 * 1024  # 10MB限制（兜底）
                header_probe = bytearray()
                header_checked = False
                MAX_PIXELS = 24_000_000   # 约24MP
                MAX_DIM = 12000           # 任一边超过12000视为过大

                for chunk in response.iter_content(chunk_size=16384):
                    if self.cancel_token.is_cancelled:
                        response.close()
                        return
                    if not chunk:
                        continue

                    chunks.append(chunk)
                    total_size += len(chunk)

                    # 1) 边下边探测尺寸，尽量只凭前面少量字节即可判断
                    if not header_checked:
                        try:
                            header_probe.extend(chunk)
                            if len(header_probe) >= 4096:  # 有足够头部数据再尝试
                                buf = QBuffer()
                                buf.setData(bytes(header_probe))
                                if buf.open(QBuffer.OpenModeFlag.ReadOnly):
                                    reader = QImageReader(buf)
                                    size = reader.size()
                                    buf.close()
                                    if size.isValid():
                                        w, h = size.width(), size.height()
                                        if w * h > MAX_PIXELS or max(w, h) > MAX_DIM:
                                            self.signals.error.emit(self.index, "TOO_LARGE", f"图片尺寸过大: {w}x{h}")
                                            response.close()
                                            return
                                        header_checked = True
                        except Exception:
                            pass

                    # 2) 字节数限制（兜底，防止少数格式长头部导致大流量）
                    if total_size > max_size:
                        self.signals.error.emit(self.index, "SIZE_LIMIT", "图片过大")
                        response.close()
                        return

                # 完成下载
                data = b''.join(chunks)

                # 存入缓存并回调
                image_cache.set(self.url, data)
                if not self.cancel_token.is_cancelled:
                    self.signals.loaded.emit(self.index, data)
            else:
                self.signals.error.emit(
                    self.index, f"HTTP_{response.status_code}", 
                    f"服务器错误 {response.status_code}"
                )
                
        except requests.exceptions.Timeout:
            if not self.cancel_token.is_cancelled:
                self.signals.error.emit(self.index, "TIMEOUT", "连接超时")
        except requests.exceptions.ConnectionError:
            if not self.cancel_token.is_cancelled:
                self.signals.error.emit(self.index, "CONNECTION", "网络错误")
        except Exception as e:
            if not self.cancel_token.is_cancelled:
                self.signals.error.emit(self.index, "UNKNOWN", str(e))

class ImageThreadPool:
    """图片加载线程池管理器"""
    
    def __init__(self, max_threads=8):
        """
        初始化线程池
        max_threads: 最大并发线程数（建议 4-8）
        """
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(max_threads)
        self.cancel_token = CancelToken()
        self.active_tasks = {}  # {index: task}
        
    def load_image(self, url, index, callback, error_callback=None):
        """
        提交图片加载任务
        url: 图片 URL
        index: 图片索引
        callback: 成功回调 (index, data)
        error_callback: 错误回调 (index, code, message)
        """
        # 如果该索引已有任务，不重复提交
        if index in self.active_tasks:
            return
            
        task = ImageLoadTask(url, index, self.cancel_token)
        
        # 使用QueuedConnection确保主线程执行
        task.signals.loaded.connect(
            lambda idx, data: self._on_loaded(idx, data, callback),
            Qt.ConnectionType.QueuedConnection
        )
        
        if error_callback:
            task.signals.error.connect(
                error_callback,
                Qt.ConnectionType.QueuedConnection
            )
            
        self.active_tasks[index] = task
        self.pool.start(task)
        
    def _on_loaded(self, index, data, callback):
        """加载完成处理"""
        self.active_tasks.pop(index, None)
        callback(index, data)
        
    def cancel_all(self):
        """取消所有任务"""
        self.cancel_token.cancel()
        self.active_tasks.clear()
        # 等待当前正在执行的任务完成
        self.pool.waitForDone(100)  # 最多等待 100ms
        # 重置令牌供下次使用
        self.cancel_token.reset()
        
    def set_priority(self, index, priority):
        """设置任务优先级（为未来扩展预留）"""
        # QThreadPool 不直接支持优先级
        # 可以通过自定义调度实现
        pass