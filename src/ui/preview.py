"""
预览浮层：在悬停图片时展示更大的预览（支持 GIF 播放）
"""

from PyQt6.QtCore import Qt, QPoint, QBuffer, QSize, QRect
from PyQt6.QtGui import QMovie, QPixmap, QPainter, QColor, QPen, QBrush, QImageReader
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect


class PreviewOverlay(QWidget):
    """悬停预览浮层
    - 顶层无边框、圆角阴影
    - 支持静态图与 GIF
    - 按最长边限制解码/播放尺寸，避免内存超限
    """

    def __init__(self, parent=None, max_side: int = 320):
        # 使用顶层无边框工具窗口，保证跨平台可见性
        super().__init__(parent, flags=Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(False)

        self.max_side = max(64, min(640, max_side))

        # 内容容器
        self.container = QWidget(self)
        self.container.setObjectName("previewContainer")
        self.container.setStyleSheet(
            """
            QWidget#previewContainer {
                background: rgba(255, 255, 255, 0.98);
                border-radius: 10px;
            }
            """
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        self.label = QLabel(self.container)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self._movie: QMovie | None = None
        self._gif_buffer: QBuffer | None = None

        # 初始隐藏
        self.hide()

    # --------- 内部辅助 ---------
    def _cleanup(self):
        if self._movie:
            try:
                self._movie.stop()
            except Exception:
                pass
            self._movie = None
        if self._gif_buffer:
            try:
                self._gif_buffer.close()
            except Exception:
                pass
            self._gif_buffer = None
        self.label.clear()

    def _fit_and_move(self, global_pos: QPoint):
        # 以 label 的 size hint 为准，给容器外边距
        hint = self.label.sizeHint()
        w = min(self.max_side + 20, max(100, hint.width() + 20))
        h = min(self.max_side + 20, max(100, hint.height() + 20))
        self.container.resize(w, h)
        self.resize(w, h)

        # 在鼠标右下方展示，避免越界（简单防溢出）
        offset = QPoint(12, 12)
        pos = global_pos + offset
        screen = self.screen().geometry() if self.screen() else QRect(0, 0, 1920, 1080)
        if pos.x() + w > screen.right() - 8:
            pos.setX(max(8, screen.right() - w - 8))
        if pos.y() + h > screen.bottom() - 8:
            pos.setY(max(8, screen.bottom() - h - 8))
        self.move(pos)

    # --------- 对外 API ---------
    def show_preview(self, data: bytes, is_gif: bool, global_pos: QPoint):

        self._cleanup()
        if not data:

            return

        if is_gif:
            # GIF 使用 QMovie + QBuffer，并按 max_side 限制播放尺寸
            self._gif_buffer = QBuffer(self)
            self._gif_buffer.setData(data)
            if not self._gif_buffer.open(QBuffer.OpenModeFlag.ReadOnly):
                return
            self._movie = QMovie(self)
            self._movie.setDevice(self._gif_buffer)
            self._movie.setCacheMode(QMovie.CacheMode.CacheAll)
            self._movie.setScaledSize(QSize(self.max_side, self.max_side))
            self.label.setMovie(self._movie)
            self._movie.start()
        else:
            # 静态图：用 QImageReader 按最长边解码
            try:
                buf = QBuffer()
                buf.setData(data)
                if not buf.open(QBuffer.OpenModeFlag.ReadOnly):
                    return
                reader = QImageReader(buf)
                reader.setAutoTransform(True)
                size = reader.size()
                if size.isValid() and size.width() > 0 and size.height() > 0:
                    if size.width() >= size.height():
                        w = self.max_side
                        h = max(1, int(size.height() * w / size.width()))
                    else:
                        h = self.max_side
                        w = max(1, int(size.width() * h / size.height()))
                    reader.setScaledSize(QSize(w, h))
                image = reader.read()
                buf.close()
                if not image.isNull():
                    self.label.setPixmap(QPixmap.fromImage(image))
                else:
                    return
            except Exception:
                return

        self._fit_and_move(global_pos)
        self.show()


    def hide_preview(self):

        self._cleanup()
        self.hide()

