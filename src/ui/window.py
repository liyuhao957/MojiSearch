"""
主窗口界面
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, 
                           QGridLayout, QLabel, QGraphicsDropShadowEffect, QApplication,
                           QToolButton)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QColor, QCursor
from src.managers.search import SearchManager
from src.utils.loaders import CopyLoader


class MainWindow(QWidget):
    """主窗口 - macOS 原生风格"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setup_search_manager()
        
    def init_ui(self):
        # 窗口设置
        self.setWindowTitle("Moji")
        self.setFixedSize(380, 520)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                           Qt.WindowType.WindowStaysOnTopHint)
        
        # macOS 毛玻璃效果
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget#mainWidget {
                background: rgba(248, 248, 248, 0.95);
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)
        
        # 创建主容器
        self.main_widget = QWidget()
        self.main_widget.setObjectName("mainWidget")
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.main_widget)
        
        layout = QVBoxLayout(self.main_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 搜索容器（包含搜索框和按钮）
        search_container = QWidget()
        search_container.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.9);
                border-radius: 10px;
            }
            QWidget:focus-within {
                background: white;
            }
        """)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜点什么...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 16px;
                padding-right: 40px;  /* 为按钮留出空间 */
                font-size: 15px;
                border: none;
                background: transparent;
                color: #2c2c2c;
            }
            QLineEdit::placeholder {
                color: #999;
            }
        """)
        
        # 搜索按钮
        self.search_button = QToolButton()
        self.search_button.setText("🔍")
        self.search_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.search_button.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                font-size: 16px;
                padding: 8px 12px;
                color: #999;
            }
            QToolButton:hover {
                color: #666;
                background: rgba(0, 0, 0, 0.05);
                border-radius: 6px;
            }
            QToolButton:pressed {
                color: #FF8200;
            }
        """)
        
        # 组装搜索容器
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        
        # 连接信号
        self.search_input.returnPressed.connect(self.do_search)
        self.search_button.clicked.connect(self.do_search)
        
        # 错误提示标签
        self.error_label = QLabel()
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet("""
            QLabel {
                color: #a33;
                background: #fdecee;
                border: 1px solid #f9d3d7;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
        """)
        self.error_label.hide()
        
        # macOS 风格滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 0.3);
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        
        # 图片网格容器
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(8)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_widget.setLayout(self.grid_layout)
        self.scroll_area.setWidget(self.grid_widget)
        
        # 加载提示
        self.loading_label = QLabel("加载更多内容...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 12px;
                padding: 8px;
            }
        """)
        self.loading_label.hide()
        
        # 组装布局
        layout.addWidget(search_container)
        layout.addWidget(self.error_label)  # 错误提示
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.loading_label)
        
        # 窗口阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 2)
        self.main_widget.setGraphicsEffect(shadow)
        
    def setup_search_manager(self):
        """设置搜索管理器"""
        self.search_manager = SearchManager(self.grid_layout, self.scroll_area)
        
        # 连接信号
        self.search_manager.error_occurred.connect(self.show_error)
        self.search_manager.loading_status_changed.connect(self.update_loading_status)
        self.search_manager.image_loaded.connect(self.update_image)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.search_manager.handle_scroll)
        
    def show_error(self, message):
        """显示错误提示"""
        self.error_label.setText(f"⚠ {message}")
        self.error_label.show()
        
        # 3秒后自动隐藏
        QTimer.singleShot(3000, self.error_label.hide)
        
    def update_loading_status(self, loading, message):
        """更新加载状态"""
        if loading or message:
            self.loading_label.setText(message)
            self.loading_label.show()
        else:
            self.loading_label.hide()
            
            
    def do_search(self):
        """执行搜索"""
        keyword = self.search_input.text().strip()
        if keyword:
            self.search_manager.do_search(keyword)
            
    def update_image(self, index, data):
        """更新图片显示 - 使用UniqueConnection"""
        if index in self.search_manager.active_widgets:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            scaled = pixmap.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            widget = self.search_manager.active_widgets[index]
            widget.setPixmap(scaled)
            
            # 使用UniqueConnection避免重复连接
            if not widget._connected:
                widget.clicked.connect(
                    self.copy_image,
                    Qt.ConnectionType.UniqueConnection  # 关键！
                )
                widget._connected = True
            
    def copy_image(self, url):
        """复制图片到剪贴板（后台下载，避免UI阻塞）"""
        self.copy_loader = CopyLoader(url)
        self.copy_loader.done.connect(self._after_copy_done)
        self.copy_loader.start()
        
    def _after_copy_done(self, data: bytes, err: str):
        """复制完成回调（干净实现）"""
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            QApplication.clipboard().setPixmap(pixmap)
            # 复制成功反馈 - 橙色闪烁
            self.main_widget.setStyleSheet(
                """
                QWidget#mainWidget {
                    background: rgba(255, 130, 0, 0.08);
                    border-radius: 12px;
                    border: 1px solid rgba(255, 130, 0, 0.3);
                }
                """
            )
            QTimer.singleShot(
                150,
                lambda: self.main_widget.setStyleSheet(
                    """
                    QWidget#mainWidget {
                        background: rgba(248, 248, 248, 0.95);
                        border-radius: 12px;
                        border: 1px solid rgba(0, 0, 0, 0.1);
                    }
                    """
                ),
            )
        else:
            self.show_error("复制失败: " + (err or "网络错误"))
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
    
    def cleanup(self):
        """清理资源 - 使用优雅停止"""
        # 清理搜索管理器中的线程
        if hasattr(self, 'search_manager'):
            # 使用优雅停止机制
            for loader in self.search_manager.loaders.values():
                loader.request_stop()
            
            # 等待线程自然退出
            for loader in self.search_manager.loaders.values():
                if not loader.wait(100):  # 等待100ms
                    if loader.isRunning():
                        loader.terminate()
                        loader.wait(50)
            self.search_manager.loaders.clear()
        
        # 清理复制加载器
        if hasattr(self, 'copy_loader') and self.copy_loader:
            if self.copy_loader.isRunning():
                self.copy_loader.terminate()
                self.copy_loader.wait(100)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.cleanup()
        event.accept()