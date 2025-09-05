"""
虚拟滚动管理器
"""

from src.ui.widgets import EmojiWidget


class VirtualScrollManager:
    """虚拟滚动管理器 - 只渲染可视区域"""
    def __init__(self, visible_rows=3, cols=4):
        self.visible_rows = visible_rows
        self.cols = cols
        self.buffer_rows = 1  # 上下各缓冲1行
        self.row_height = 80  # 单行高度(像素)，72卡片 + vertical spacing(8) 更精确
        self.total_visible = (visible_rows + self.buffer_rows * 2) * cols
        self.widgets_pool = []  # 组件池
        self.all_urls = []  # 所有图片URL
        self.current_offset = 0

    def set_urls(self, urls):
        """设置所有URL"""
        self.all_urls = urls
        self.current_offset = 0  # 重置偏移量，保持状态一致

    def append_urls(self, urls):
        """追加URL"""
        self.all_urls.extend(urls)

    def get_visible_range(self, scroll_position, container_height):
        """获取当前应该显示的URL范围"""
        rh = getattr(self, 'row_height', 84)
        rows_visible = max(1, int(container_height / rh))
        row = int(scroll_position / rh)
        start_idx = max(0, (row - self.buffer_rows) * self.cols)
        end_idx = min(len(self.all_urls), (row + rows_visible + self.buffer_rows) * self.cols)
        return start_idx, end_idx, self.all_urls[start_idx:end_idx]

    def recycle_widget(self, widget):
        """回收widget到池中"""
        parent = widget.parentWidget()
        if parent and parent.layout():
            parent.layout().removeWidget(widget)
        widget.hide()
        widget.setParent(None)
        widget.url = ""
        widget.clear()
        self.widgets_pool.append(widget)

    def get_widget(self):
        """从池中获取或创建widget"""
        if self.widgets_pool:
            return self.widgets_pool.pop()
        return EmojiWidget()