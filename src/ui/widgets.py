"""
UI 组件定义
"""

from PyQt6.QtWidgets import QLabel, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal, QBuffer, QSize, QTimer
from PyQt6.QtGui import QColor, QPixmap, QMovie, QImageReader
from collections import deque


def is_gif_data(data: bytes) -> bool:
    """检测是否为 GIF 格式

    GIF 文件头识别：
    - GIF87a: 47 49 46 38 37 61
    - GIF89a: 47 49 46 38 39 61
    """
    if len(data) < 6:
        return False
    header = data[:6]
    return header in (b'GIF87a', b'GIF89a')


class GifPlaybackManager:
    """全局 GIF 播放管理器 - 限制同时播放数量"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.playing_widgets = deque(maxlen=3)  # 最多同时播放 3 个
            cls._instance.pending_widget = None  # 待播放的 widget
            cls._instance.hover_timer = None  # 悬停延迟定时器
        return cls._instance

    def request_play(self, widget):
        """请求播放 GIF"""
        # 如果已经在播放列表中，移到最前面
        if widget in self.playing_widgets:
            self.playing_widgets.remove(widget)
            self.playing_widgets.append(widget)
            return True

        # 如果达到上限，停止最早的一个
        if len(self.playing_widgets) >= 3:
            oldest = self.playing_widgets.popleft()
            if oldest and oldest.movie:
                oldest.movie.stop()
                oldest.setMovie(None)
                if oldest.static_pixmap:
                    oldest.setPixmap(oldest.static_pixmap)

        # 添加到播放列表
        self.playing_widgets.append(widget)
        return True

    def stop_playing(self, widget):
        """停止播放 GIF"""
        if widget in self.playing_widgets:
            self.playing_widgets.remove(widget)

    def clear_all(self):
        """清理所有播放"""
        for widget in self.playing_widgets:
            if widget and widget.movie:
                widget.movie.stop()
                widget.setMovie(None)
                if widget.static_pixmap:
                    widget.setPixmap(widget.static_pixmap)
        self.playing_widgets.clear()


class EmojiWidget(QLabel):
    """增强版表情包组件 - 支持 GIF 动画"""
    clicked = pyqtSignal(str)  # 保持向后兼容
    clicked_with_data = pyqtSignal(str, bytes, bool)  # url, data, is_gif
    preview_requested = pyqtSignal(str, bytes, bool)  # url, data, is_gif
    preview_close = pyqtSignal()  # 关闭预览

    def __init__(self, url=""):
        super().__init__()
        # 现有属性
        self.url = url
        self._connected = False  # 初始化连接标记

        # 新增 GIF 支持
        self.movie = None           # QMovie 对象
        self.is_gif = False        # 是否为 GIF
        self.static_pixmap = None  # 静态显示帧
        self.gif_badge = None      # GIF 标识标签
        self.original_data = None  # 原始图片数据（用于复制）
        self._gif_buffer = None    # GIF 数据缓冲区

        # 性能优化：播放管理器和延迟定时器
        self.playback_manager = GifPlaybackManager()
        self.hover_timer = None
        self.preview_timer = None
        self._want_preview_when_ready = False

        self.setFixedSize(72, 72)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: none;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.8);
                padding: 4px;
            }
            QLabel:hover {
                background: rgba(255, 130, 0, 0.1);
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 阴影
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(8)
        self.shadow.setColor(QColor(0, 0, 0, 30))
        self.shadow.setOffset(0, 1)
        self.setGraphicsEffect(self.shadow)

    def mousePressEvent(self, event):
        if self.url and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.url)  # 保持向后兼容
            # 如果有原始数据，发送完整信息
            if self.original_data:
                self.clicked_with_data.emit(self.url, self.original_data, self.is_gif)

    def enterEvent(self, event):
        """鼠标进入：增强阴影，延迟播放 GIF + 触发预览"""
        # 原有的阴影效果
        self.shadow.setBlurRadius(12)
        self.shadow.setOffset(0, 4)

        # 进入日志


        # 触发预览（100ms 延迟，避免快速掠过）
        if self.original_data:
            if self.preview_timer:
                self.preview_timer.stop()

            self.preview_timer = QTimer()
            self.preview_timer.setSingleShot(True)
            self.preview_timer.timeout.connect(self._emit_preview)
            self.preview_timer.start(100)
        else:
            # 数据尚未就绪，等待 set_image_data 后触发
            self._want_preview_when_ready = True


    def _emit_preview(self):
        self.preview_requested.emit(self.url, self.original_data, self.is_gif)


        # 设置延迟播放 GIF（100ms 延迟，避免快速掠过触发）
        if self.is_gif and self.movie and self.original_data:
            # 取消之前的定时器
            if self.hover_timer:
                self.hover_timer.stop()

            # 创建新的延迟定时器
            self.hover_timer = QTimer()
            self.hover_timer.setSingleShot(True)
            self.hover_timer.timeout.connect(self._start_gif_playback)
            self.hover_timer.start(100)  # 100ms 延迟

    def leaveEvent(self, event):
        """鼠标离开：恢复阴影，停止 GIF + 关闭预览"""
        # 恢复阴影
        self.shadow.setBlurRadius(8)
        self.shadow.setOffset(0, 2)

        # 取消延迟定时器
        if self.hover_timer:
            self.hover_timer.stop()
            self.hover_timer = None
        if self.preview_timer:
            self.preview_timer.stop()
            self.preview_timer = None
        # 取消等待标记
        self._want_preview_when_ready = False

        # 停止播放并还原首帧
        if self.is_gif and self.movie:
            self.movie.stop()
            self.setMovie(None)
            if self.static_pixmap:
                self.setPixmap(self.static_pixmap)
            # 从播放管理器中移除
            self.playback_manager.stop_playing(self)

        # 关闭预览

        self.preview_close.emit()

    def set_image_data(self, data: bytes, url: str):
        """智能设置图片数据（保持 QBuffer 生命周期，避免崩溃）"""
        #  
        self._cleanup_resources()
        self.url = url
        self.original_data = data

        # when data ready

        if self._want_preview_when_ready and self.underMouse():
            QTimer.singleShot(10, self._emit_preview)
        self._want_preview_when_ready = False

        if is_gif_data(data):
            self.is_gif = True
            self._setup_gif_display(data)
            self._create_gif_badge()
        else:
            self.is_gif = False
            self._setup_static_display(data)

    def _setup_gif_display(self, data: bytes):
        """准备 GIF 显示但默认不播放；提取首帧作为静态显示"""
        # 关键：QBuffer 必须保存为实例属性，确保生命周期覆盖 QMovie
        self._gif_buffer = QBuffer(self)
        self._gif_buffer.setData(data)
        self._gif_buffer.open(QBuffer.OpenModeFlag.ReadOnly)

        self.movie = QMovie(self)
        self.movie.setDevice(self._gif_buffer)

        # 性能优化：根据文件大小选择缓存模式
        file_size = len(data) / 1024 / 1024  # MB
        if file_size <= 1:
            self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
        elif file_size <= 5:
            self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
        else:
            self.movie.setCacheMode(QMovie.CacheMode.CacheNone)

        # 直接按目标尺寸解码，减少每帧缩放开销
        self.movie.setScaledSize(QSize(64, 64))  # 留出 padding 空间

        # 提取第一帧作为静态图
        self.movie.jumpToFrame(0)
        first = self.movie.currentPixmap()
        if not first.isNull():
            self.static_pixmap = first
            self.setPixmap(self.static_pixmap)
        else:
            # GIF 解码失败，降级处理
            self._setup_static_display(data)
            self.is_gif = False

    def _setup_static_display(self, data: bytes):
        """设置静态图片显示（使用 QImageReader 按目标尺寸解码，避免超大图触发 256MB 限制）"""
        try:
            buf = QBuffer()
            buf.setData(data)
            if not buf.open(QBuffer.OpenModeFlag.ReadOnly):
                return

            reader = QImageReader(buf)
            reader.setAutoTransform(True)

            # 目标边长（与现有 UI 保持一致）
            target = 64
            # 读取原始尺寸（只解析头，不会解码整图）
            size = reader.size()
            if size.isValid() and size.width() > 0 and size.height() > 0:
                if size.width() >= size.height():
                    w = target
                    h = max(1, int(size.height() * target / size.width()))
                else:
                    h = target
                    w = max(1, int(size.width() * target / size.height()))
                reader.setScaledSize(QSize(w, h))
            else:
                # 如果读不到尺寸，退化为直接目标尺寸（可能会拉伸，但能避免超限）
                reader.setScaledSize(QSize(target, target))

            image = reader.read()
            buf.close()
            if not image.isNull():
                self.static_pixmap = QPixmap.fromImage(image)
                self.setPixmap(self.static_pixmap)
        except Exception:
            # 忽略个别格式异常，保持不显示（避免白块）
            pass

    def _create_gif_badge(self):
        """创建 GIF 标识角标 - 支持 HiDPI"""
        if self.gif_badge:
            return  # 避免重复创建

        self.gif_badge = QLabel("GIF", self)

        # 相对尺寸计算（基于 Widget 高度）
        widget_height = self.height()
        font_size = max(9, min(12, int(widget_height * 0.14)))
        badge_height = int(widget_height * 0.18)
        border_radius = int(badge_height * 0.2)
        margin = int(widget_height * 0.06)

        self.gif_badge.setStyleSheet(f"""
            QLabel {{
                background: rgba(0, 0, 0, 0.6);
                color: white;
                border-radius: {border_radius}px;
                padding: 1px 3px;
                font-size: {font_size}px;
                font-weight: bold;
            }}
        """)

        # 调整角标大小并定位在右上角
        self.gif_badge.adjustSize()
        self.gif_badge.move(
            self.width() - self.gif_badge.width() - margin,
            margin
        )
        self.gif_badge.show()

    def _start_gif_playback(self):
        """开始播放 GIF（延迟触发）"""
        if self.is_gif and self.movie and self.original_data:
            # 检查 movie 是否有效
            if self.movie.isValid():
                # 请求播放权限
                if self.playback_manager.request_play(self):
                    self.setMovie(self.movie)
                    self.movie.start()  # 默认循环播放

    def _cleanup_resources(self):
        """释放资源，避免内存泄漏/悬挂指针"""
        # 停止定时器
        if self.hover_timer:
            self.hover_timer.stop()
            self.hover_timer = None

        # 从播放管理器中移除
        if self.is_gif:
            self.playback_manager.stop_playing(self)

        try:
            if self.movie:
                self.movie.stop()
                self.setMovie(None)  # 断开与 QLabel 的连接
                self.movie.deleteLater()
        except Exception:
            pass
        self.movie = None

        # 断开并移除角标
        if self.gif_badge:
            self.gif_badge.deleteLater()
            self.gif_badge = None

        # 关闭并清空缓冲区
        if self._gif_buffer:
            try:
                self._gif_buffer.close()
            except Exception:
                pass
        self._gif_buffer = None

        # 清空数据引用
        self.original_data = None
        self.static_pixmap = None
        self.is_gif = False

    def clear(self):
        """清理widget资源，准备重用"""
        # 清理 GIF 相关资源
        self._cleanup_resources()

        # 清空显示
        self.setPixmap(QPixmap())
        self.url = ""

        # 关键：断开信号并重置标记
        for sig in (self.clicked, self.clicked_with_data, self.preview_requested, self.preview_close):
            try:
                sig.disconnect()
            except Exception:
                pass
        self._connected = False  # 必须重置！