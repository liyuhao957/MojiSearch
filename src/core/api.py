"""
微博 API 封装和缓存管理
"""

import requests
import time
from urllib.parse import quote
from collections import OrderedDict
from datetime import datetime, timedelta
from src.utils.network import NetworkManager


class SearchCache:
    """搜索结果缓存，减少重复请求"""
    def __init__(self, max_age=300):  # 5分钟缓存
        self._cache = OrderedDict()  # 保持插入顺序
        self.max_age = max_age
        self.max_size = 50  # 最多缓存50个搜索结果

    def get(self, keyword, page):
        key = f"{keyword}_{page}"
        if key in self._cache:
            timestamp, data = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.max_age):
                # 移到最后（LRU）
                self._cache.move_to_end(key)
                return data
            else:
                del self._cache[key]
        return None

    def set(self, keyword, page, data):
        key = f"{keyword}_{page}"
        # 限制缓存大小
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # 删除最旧的
        self._cache[key] = (datetime.now(), data)


class WeiboAPI:
    """微博API封装 - 带缓存支持"""
    BASE_URL = "https://m.weibo.cn/api/container/getIndex"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
        'Referer': 'https://m.weibo.cn/'
    }

    # 类级别缓存
    _cache = SearchCache()

    @classmethod
    def search(cls, keyword, page=1, max_retries=3, use_cache=True):
        """搜索微博表情包 - 使用Session复用连接"""
        # 检查缓存
        if use_cache:
            cached = cls._cache.get(keyword, page)
            if cached:
                return cached
        
        params = {
            'containerid': f'100103type=63&q={quote(keyword)}&t=',
            'page': page
        }
        
        # 使用Session复用连接
        session = NetworkManager.get_session()
        
        for retry in range(max_retries):
            try:
                # 分离连接和读取超时
                response = session.get(
                    cls.BASE_URL,
                    params=params,
                    headers=cls.HEADERS,
                    timeout=(2, 5),  # (连接超时, 读取超时)
                    stream=False
                )
                
                if response.status_code == 200:
                    images = cls._extract_images(response.json())
                    if use_cache and images:
                        cls._cache.set(keyword, page, images)
                    return images
                elif response.status_code == 432:
                    # 反爬虫，等待后重试
                    time.sleep(2 * (retry + 1))
                    continue
                else:
                    raise Exception(f"API错误: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                if retry == max_retries - 1:
                    raise Exception("请求超时")
            except requests.exceptions.ConnectionError:
                if retry == max_retries - 1:
                    raise Exception("网络连接失败")
            except Exception as e:
                if retry == max_retries - 1:
                    raise e
        
        return []

    @classmethod
    def _extract_images(cls, data):
        images = []
        cards = data.get('data', {}).get('cards', [])
        for card in cards:
            if card.get('card_type') == 9:
                mblog = card.get('mblog', {})
                pics = mblog.get('pics', [])
                for pic in pics:
                    url = pic.get('large', {}).get('url') or pic.get('url', '')
                    if url:
                        images.append(url)
        return images