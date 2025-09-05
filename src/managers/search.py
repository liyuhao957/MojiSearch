"""
搜索逻辑管理器
"""

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap
from src.core.api import WeiboAPI
from src.utils.loaders import ImageLoader
from src.managers.virtual_scroll import VirtualScrollManager


class SearchManager(QObject):
    """搜索逻辑管理器"""

    # 信号定义
    error_occurred = pyqtSignal(str)
    loading_status_changed = pyqtSignal(bool, str)  # loading, message
    image_loaded = pyqtSignal(int, bytes)

    def __init__(self, grid_layout, scroll_area):
        super().__init__()
        self.grid_layout = grid_layout
        self.scroll_area = scroll_area

        self.page = 1
        self.keyword = ""
        self.loading = False
        self.no_more = False

        # 虚拟滚动管理
        self.virtual_manager = VirtualScrollManager(visible_rows=4, cols=4)
        self.active_widgets = {}  # 当前活动的widget {index: widget}

        # 托管图片加载线程，防止提前销毁
        self.loaders = {}

        # 使用顶部/底部占位，避免 QGridLayout 折叠离屏行
        self._use_spacers = True
        self._top_spacer = None
        self._bottom_spacer = None

        self._stretch_row = -1  # 用于将多余空间压到底部的拉伸行索引（spacer 启用时将跳过）

    def do_search(self, keyword):
        """执行搜索"""
        if not keyword or keyword == self.keyword:
            return

        self.keyword = keyword
        self.page = 1
        self.no_more = False

        # 1. 先复位滚动条（在清空之前）
        self.scroll_area.verticalScrollBar().setValue(0)

        # 2. 清空现有内容
        self.clear_grid()
        self.virtual_manager.set_urls([])  # 清空URL列表

        # 3. 开始新搜索
        self.load_images()

    def clear_grid(self):
        """清理网格 - 回收所有widget到池中"""
        for widget in self.active_widgets.values():
            self.virtual_manager.recycle_widget(widget)
        self.active_widgets.clear()

        # 清理布局
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)

    def load_images(self):
        """加载图片"""
        if self.loading or not self.keyword:
            return

        self.loading = True
        self.loading_status_changed.emit(True, "正在搜索...")

        try:
            images = WeiboAPI.search(self.keyword, self.page)

            if images:
                # 添加到虚拟管理器
                self.virtual_manager.append_urls(images)
                # 更新容器最小高度，制造可滚动空间
                self.update_container_height()
                print(f"[load_images] page={self.page}, images={len(images)}, total={len(self.virtual_manager.all_urls)}, "
                      f"viewport_h={self.scroll_area.viewport().height()}, "
                      f"min_h={self.grid_layout.parentWidget().minimumHeight()}", flush=True)

                # 首次搜索根据可视范围渲染，后续翻页由滚动事件触发渲染
                if self.page == 1:
                    # 确保首屏渲染时滚动条在顶部；将首屏渲染延后一拍，等布局与视口高度稳定
                    self.scroll_area.verticalScrollBar().setValue(0)
                    QTimer.singleShot(0, self._first_render)

                self.page += 1
                self.loading_status_changed.emit(False, "向下滚动加载更多")
            else:
                print(f"[load_images] page={self.page}, images=0", flush=True)
                if self.page == 1:
                    self.loading_status_changed.emit(False, "没有找到相关表情")
                else:
                    self.loading_status_changed.emit(False, "没有更多了")
                    self.no_more = True

        except Exception as e:
            self.error_occurred.emit(str(e))
            self.loading_status_changed.emit(False, "")

        self.loading = False

    def load_more(self):
        """加载更多图片"""
        if not self.loading and self.keyword and not self.no_more:
            self.load_images()

    def update_container_height(self):
        """根据总图片数量，设置容器最小高度，保证可滚动区域存在；并把多余空间压到底部"""
        cols = 4
        total = len(self.virtual_manager.all_urls)
        total_rows = max(1, (total + cols - 1) // cols)
        margins = self.grid_layout.contentsMargins()
        spacing = self.grid_layout.spacing()
        rh = self.virtual_manager.row_height
        total_height = total_rows * rh + margins.top() + margins.bottom()

        grid_widget = self.grid_layout.parentWidget()
        if grid_widget:
            viewport_h = self.scroll_area.viewport().height() if self.scroll_area else 0
            # 至少比视口高一行，确保可以触发滚动事件与"加载更多"
            min_h = max(total_height, viewport_h + rh)
            grid_widget.setMinimumHeight(min_h)

        # 关键：将多余高度压到底部（使用 spacer 时不再需要 rowStretch）
        try:
            if not getattr(self, '_use_spacers', False):
                if self._stretch_row is not None and self._stretch_row >= 0:
                    self.grid_layout.setRowStretch(self._stretch_row, 0)
                # 选择内容行之后的一行作为拉伸行
                self._stretch_row = total_rows
                self.grid_layout.setRowStretch(self._stretch_row, 1)
        except Exception:
            pass

    def update_visible_widgets(self, start_idx, urls):
        """更新可视区域的widget，并用顶部/底部占位避免布局折叠"""
        cols = 4
        total = len(self.virtual_manager.all_urls)
        rh = self.virtual_manager.row_height
        total_rows = max(1, (total + cols - 1) // cols)

        start_row = start_idx // cols
        # end_row_exclusive：可视范围的“最后一行之后”的行号
        end_row_exclusive = (start_idx + len(urls) + cols - 1) // cols
        visible_rows = max(0, end_row_exclusive - start_row)

        # 1) 顶/底占位：用 setRowMinimumHeight 精确撑起离屏行高
        if getattr(self, '_use_spacers', False):
            top_h = start_row * rh
            bottom_h = max(0, (total_rows - end_row_exclusive) * rh)
            # 顶部占位固定在 row=0，底部占位固定在 row = visible_rows + 1
            bottom_row = visible_rows + 1
            # 清除上次的 bottom_row 高度
            if hasattr(self, '_prev_bottom_row') and self._prev_bottom_row is not None and self._prev_bottom_row != bottom_row:
                try:
                    self.grid_layout.setRowMinimumHeight(self._prev_bottom_row, 0)
                except Exception:
                    pass
            # 设置当前占位高度
            try:
                self.grid_layout.setRowMinimumHeight(0, top_h)
                self.grid_layout.setRowMinimumHeight(bottom_row, bottom_h)
            except Exception:
                pass
            self._prev_bottom_row = bottom_row

        # 2) 渲染/复用可见区：统一使用“相对行号”，确保位于顶部占位之后
        for i, url in enumerate(urls):
            idx = start_idx + i
            row = (idx // cols) - start_row + 1  # +1：避开顶部占位行
            col = idx % cols

            if idx not in self.active_widgets:
                widget = self.virtual_manager.get_widget()
                widget.url = url
                self.active_widgets[idx] = widget
                # 异步加载图片（托管生命周期）
                loader = ImageLoader(url, idx)
                loader.image_loaded.connect(self._handle_image_loaded)
                loader.error_occurred.connect(lambda msg: self.error_occurred.emit(msg))
                if idx in self.loaders:
                    old_loader = self.loaders[idx]
                    if old_loader.isRunning():
                        old_loader.terminate()
                        old_loader.wait(100)
                self.loaders[idx] = loader
                loader.finished.connect(lambda i=idx: self.loaders.pop(i, None))
                loader.start()

            # 无论是否新建，都重置其在网格中的位置（防止 start_row 变化导致残留旧位置）
            widget = self.active_widgets[idx]
            self.grid_layout.addWidget(widget, row, col)
            widget.show()

        # 3) 回收不在可视范围的widget
        to_remove = []
        visible_set = set(range(start_idx, start_idx + len(urls)))
        for idx, widget in list(self.active_widgets.items()):
            if idx not in visible_set:
                self.virtual_manager.recycle_widget(widget)
                to_remove.append(idx)
        for idx in to_remove:
            del self.active_widgets[idx]



    def _first_render(self):
        """首屏渲染（延后一拍执行，避免布局未稳定导致可视区计算异常）"""
        try:
            v = 0
            h = self.scroll_area.viewport().height()
            start_idx, end_idx, visible_urls = self.virtual_manager.get_visible_range(v, h)
            print(f"[first_render] h={h}, total={len(self.virtual_manager.all_urls)}, "
                  f"range=({start_idx},{end_idx}), visible={len(visible_urls)}", flush=True)
            self.update_visible_widgets(start_idx, visible_urls)
            print(f"[first_render] after update layout_count={self.grid_layout.count()}, "
                  f"active={len(self.active_widgets)}", flush=True)
            try:
                gw = self.grid_layout.parentWidget()
                vp = self.scroll_area.viewport()
                print(f"[geom] grid_widget geom={gw.geometry()} viewport geom={vp.geometry()}", flush=True)
                # 打印前4个可见卡片的相对几何
                for i in range(min(4, len(visible_urls))):
                    idx = start_idx + i
                    w = self.active_widgets.get(idx)
                    if w:
                        print(f"[geom] idx={idx} visible={w.isVisible()} geom={w.geometry()} parent={w.parentWidget().__class__.__name__}", flush=True)
            except Exception as ge:
                print(f"[geom] error: {ge}", flush=True)

        except Exception as e:
            self.error_occurred.emit(f"首屏渲染异常: {e}")

    def _handle_image_loaded(self, index, data):
        """处理图片加载完成"""
        self.image_loaded.emit(index, data)

    def handle_scroll(self, value):
        """处理滚动事件"""
        if not self.keyword:
            return
        print(f"[scroll] value={value}, total={len(self.virtual_manager.all_urls)}, "
              f"h={self.scroll_area.viewport().height()}", flush=True)

        # 获取可视范围
        container_height = self.scroll_area.viewport().height()
        start_idx, end_idx, visible_urls = self.virtual_manager.get_visible_range(
            value, container_height
        )

        # 更新可视区域的widget
        self.update_visible_widgets(start_idx, visible_urls)


        # 检查是否需要加载更多
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.value() >= scrollbar.maximum() - 100:
            self.load_more()