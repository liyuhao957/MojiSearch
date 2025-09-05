"""
应用主控制器
"""

import sys
import os
import signal
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer
from src.ui.window import MainWindow


class MojiApp:
    """应用主类"""
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # 设置应用实例引用，用于信号处理
        self.app.setApplicationName("Moji")
        
        # 创建定时器来处理 Python 信号
        self.signal_timer = QTimer()
        self.signal_timer.timeout.connect(lambda: None)  # 空操作，仅为了让事件循环处理信号
        self.signal_timer.start(500)  # 每500ms触发一次
        
        # 主窗口
        self.window = MainWindow()
        
        # 系统托盘
        self.tray = QSystemTrayIcon()
        # 尝试加载自定义图标，如果失败则使用默认图标
        from src.utils.paths import get_icon_path
        icon_path = get_icon_path()
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        else:
            self.tray.setIcon(self.app.style().standardIcon(self.app.style().StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("Moji - 表情包搜索")
        
        # 托盘菜单
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #f0f0f0;
            }
        """)
        
        show_action = QAction("打开 Moji", None)
        show_action.triggered.connect(self.show_window)
        quit_action = QAction("退出", None)
        quit_action.triggered.connect(self.quit)
        
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()
        
    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()
            
    def show_window(self):
        # 定位到屏幕右上角
        screen = self.app.primaryScreen().geometry()
        # 右侧预留 20px 边距，适配 380 宽度
        self.window.move(screen.width() - self.window.width() - 20, 40)
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        self.window.search_input.setFocus()
        
    def quit(self):
        """安全退出应用"""
        # 停止定时器
        if hasattr(self, 'signal_timer'):
            self.signal_timer.stop()
        
        # 清理窗口资源
        if hasattr(self, 'window'):
            self.window.cleanup()
            self.window.close()
        
        # 隐藏托盘图标
        if hasattr(self, 'tray'):
            self.tray.hide()
        
        # 退出应用
        self.app.quit()
        
    def run(self):
        return self.app.exec()