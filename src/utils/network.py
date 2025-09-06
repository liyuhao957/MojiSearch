"""
网络请求优化 - Thread-local Session复用连接
"""
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class NetworkManager:
    """网络管理器 - 连接复用与重试策略"""
    
    _thread_local = threading.local()
    
    @classmethod
    def get_session(cls):
        """获取线程本地的Session"""
        if not hasattr(cls._thread_local, 'session'):
            session = requests.Session()
            
            # 配置连接池
            adapter = HTTPAdapter(
                pool_connections=10,  # 连接池大小
                pool_maxsize=10,      # 最大连接数
                max_retries=Retry(
                    total=3,
                    backoff_factor=0.3,
                    status_forcelist=[500, 502, 503, 504]
                )
            )
            
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            # 设置默认headers
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            })
            
            cls._thread_local.session = session
            
        return cls._thread_local.session
    
    @classmethod
    def close_session(cls):
        """关闭线程本地的Session"""
        if hasattr(cls._thread_local, 'session'):
            cls._thread_local.session.close()
            delattr(cls._thread_local, 'session')