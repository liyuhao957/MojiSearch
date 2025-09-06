"""
UI 组件定义
"""

from PyQt6.QtWidgets import QLabel, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap


class EmojiWidget(QLabel):
    """表情包组件"""
    clicked = pyqtSignal(str)

    def __init__(self, url=""):
        super().__init__()
        self.url = url
        self._connected = False  # 初始化连接标记
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
            self.clicked.emit(self.url)

    def enterEvent(self, event):
        """鼠标进入：增强阴影，保持元素位置"""
        self.shadow.setBlurRadius(12)
        self.shadow.setOffset(0, 4)

    def leaveEvent(self, event):
        """鼠标离开：恢复阴影"""
        self.shadow.setBlurRadius(8)
        self.shadow.setOffset(0, 2)
    
    def clear(self):
        """清理widget资源，准备重用"""
        # 清空显示
        self.setPixmap(QPixmap())  
        self.url = ""
        
        # 关键：断开信号并重置标记
        try:
            self.clicked.disconnect()
        except:
            pass
        self._connected = False  # 必须重置！