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
        """搜索微博表情包 - 使用Session复用连接
        注意：此前当服务器触发反爬（HTTP 432 或 ok!=1）时，函数会在重试后直接
        返回空列表，导致 UI 误以为“没有找到相关表情”。这里将其改为明确地识别
        反爬并最终抛出异常，交由上层显示错误提示。"""
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

        anti_spider_hit = False

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
                    data = response.json()
                    # 有时 ok!=1 表示被限流/反爬，虽然返回 200，但没有数据
                    if isinstance(data, dict) and data.get('ok') not in (1, '1'):
                        anti_spider_hit = True
                        time.sleep(1.2 * (retry + 1))
                        # 轻量预热一次主页以尝试获取必要的 cookie
                        try:
                            session.get('https://m.weibo.cn/', headers=cls.HEADERS, timeout=(2, 5))
                        except Exception:
                            pass
                        continue

                    images = cls._extract_images(data)
                    if use_cache and images:
                        cls._cache.set(keyword, page, images)
                    return images
                elif response.status_code in (430, 431, 432, 418):
                    # 反爬虫/请求过于频繁
                    anti_spider_hit = True
                    time.sleep(1.2 * (retry + 1))
                    # 预热主页后再试
                    try:
                        session.get('https://m.weibo.cn/', headers=cls.HEADERS, timeout=(2, 5))
                    except Exception:
                        pass
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

        if anti_spider_hit:
            raise Exception("请求过于频繁或被微博反爬限制，请稍后重试")

        return []

    @classmethod
    def _extract_images(cls, data):
        """
        从 API 响应提取图片 URL；尽可能使用返回的尺寸元数据在源头过滤“超大图”，
        避免发起实际图片下载请求。
        """
        images = []
        seen = set()
        cards = data.get('data', {}).get('cards', [])
        MAX_PIXELS = 24_000_000  # 与线程池侧阈值保持一致
        MAX_DIM = 12000

        def is_oversize(w, h):
            try:
                if w and h:
                    w_i, h_i = int(w), int(h)
                    return (w_i * h_i > MAX_PIXELS) or (max(w_i, h_i) > MAX_DIM)
            except Exception:
                return False
            return False

        for card in cards:
            if card.get('card_type') != 9:
                continue
            mblog = card.get('mblog', {})

            # 1) 先处理 mblog.pics
            for pic in mblog.get('pics', []) or []:
                url = (pic.get('large', {}) or {}).get('url') or pic.get('url', '')
                if not url or url in seen:
                    continue
                lg = pic.get('large', {}) or {}
                geo = pic.get('geo', {}) or {}
                w = lg.get('w') or lg.get('width') or pic.get('w') or pic.get('width') or geo.get('width')
                h = lg.get('h') or lg.get('height') or pic.get('h') or pic.get('height') or geo.get('height')
                if is_oversize(w, h):
                    continue
                images.append(url)
                seen.add(url)

            # 2) 再处理 mblog.pic_infos（很多场景尺寸都在这里）
            pic_infos = mblog.get('pic_infos', {}) or {}
            if isinstance(pic_infos, dict):
                for _pid, info in pic_infos.items():
                    if not isinstance(info, dict):
                        continue
                    # 选取最佳可用 URL（优先 original/large/ largest）
                    cand = (
                        (info.get('original') or {}).get('url')
                        or (info.get('largest') or {}).get('url')
                        or (info.get('large') or {}).get('url')
                        or info.get('url')
                    )
                    if not cand or cand in seen:
                        continue
                    # 提取尺寸：优先 original/large/largest 的 width/height；否则顶层
                    size_src = info.get('original') or info.get('largest') or info.get('large') or {}
                    w = size_src.get('width') or size_src.get('w') or info.get('width') or info.get('w')
                    h = size_src.get('height') or size_src.get('h') or info.get('height') or info.get('h')
                    if is_oversize(w, h):
                        continue
                    images.append(cand)
                    seen.add(cand)

        return images