"""
图片内存缓存 - 避免重复下载
"""

from collections import OrderedDict
import hashlib
import time

class ImageMemoryCache:
    """图片字节缓存管理器 - 基于LRU和字节数限制"""
    
    def __init__(self, max_size_mb=50):
        """
        初始化缓存
        max_size_mb: 最大缓存大小（MB）
        """
        self._cache = OrderedDict()  # URL -> (bytes, size, time)
        self._max_bytes = max_size_mb * 1024 * 1024  # 转换为字节
        self._current_bytes = 0
        self._hit_count = 0
        self._miss_count = 0
        
    def get_key(self, url):
        """生成缓存键"""
        return hashlib.md5(url.encode()).hexdigest()
        
    def get(self, url):
        """获取缓存的图片数据"""
        key = self.get_key(url)
        
        if key in self._cache:
            # 移到末尾（LRU）
            self._cache.move_to_end(key)
            data, size, _ = self._cache[key]
            self._hit_count += 1
            return data
        
        self._miss_count += 1
        return None
        
    def set(self, url, data):
        """缓存图片数据"""
        key = self.get_key(url)
        data_size = len(data)
        
        # 如果单个文件超过缓存限制的一半，不缓存
        if data_size > self._max_bytes // 2:
            return
        
        # 如果已存在，先移除旧的
        if key in self._cache:
            _, old_size, _ = self._cache[key]
            self._current_bytes -= old_size
            del self._cache[key]
        
        # 清理空间直到能容纳新数据
        while self._current_bytes + data_size > self._max_bytes and self._cache:
            # 删除最旧的（最前面的）
            old_key, (_, old_size, _) = self._cache.popitem(last=False)
            self._current_bytes -= old_size
        
        # 添加新数据
        self._cache[key] = (data, data_size, time.time())
        self._current_bytes += data_size
        
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._current_bytes = 0
        self._hit_count = 0
        self._miss_count = 0
    
    def get_stats(self):
        """获取缓存统计"""
        return {
            'size_mb': self._current_bytes / 1024 / 1024,
            'count': len(self._cache),
            'hit_rate': self._hit_count / max(1, self._hit_count + self._miss_count),
            'hits': self._hit_count,
            'misses': self._miss_count
        }

# 全局缓存实例
image_cache = ImageMemoryCache()