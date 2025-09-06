"""
轻量搜索弹窗（命令面板样式）
- 无边框、半透明、圆角
- Enter 提交，Esc 关闭
- 发射 submitted(str) 信号
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLineEdit, QLabel, QApplication


class SearchPopup(QDialog):
    submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 弹窗样式：Dialog + 无边框 + 置顶，设为应用模态以确保键盘事件进入
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 保证可聚焦
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 容器与样式
        container = QWidget(self)
        container.setObjectName("popupContainer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

        inner = QVBoxLayout(container)
        inner.setContentsMargins(14, 12, 14, 12)
        inner.setSpacing(8)

        self.prompt = QLabel("搜索表情… (按 Enter 提交，Esc 关闭)")
        self.prompt.setStyleSheet("color: #666; font-size: 12px;")
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入关键词…")

        container.setStyleSheet(
            """
            QWidget#popupContainer {
                background: rgba(255, 255, 255, 0.96);
                border-radius: 12px;
                border: 1px solid rgba(0,0,0,0.12);
            }
            QLineEdit {
                padding: 10px 12px;
                font-size: 15px;
                border: 1px solid rgba(0,0,0,0.10);
                border-radius: 8px;
                background: rgba(255,255,255,0.9);
                color: #2c2c2c;
            }
            QLineEdit:focus {
                border: 1px solid #FF8200;
                background: white;
            }
            """
        )

        inner.addWidget(self.prompt)
        inner.addWidget(self.input)

        # 连接事件
        self.input.returnPressed.connect(self._on_return)

        # 固定大小更稳定
        self.setFixedWidth(380)
        # 高度由布局自适应

    def _on_return(self):
        text = self.input.text().strip()
        # 先关闭再发射，避免主窗显示与弹窗重叠的闪烁
        self.close()
        if text:
            self.submitted.emit(text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def open(self, preset_text: str | None = None):
        """显示弹窗到屏幕上方居中，并聚焦输入框"""
        if preset_text is not None:
            self.input.setText(preset_text)
            if preset_text:
                self.input.selectAll()
        # 根据屏幕居中（稍微下移一点）
        screen = QApplication.primaryScreen().geometry()
        self.adjustSize()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + int(screen.height() * 0.18)
        self.move(max(screen.x(), x), max(screen.y(), y))
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

