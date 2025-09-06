"""
应用主控制器
"""

import sys
import os
import signal
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer
from PyQt6.QtNetwork import QLocalServer
from src.ui.search_popup import SearchPopup

from src.ui.window import MainWindow


class MojiApp:
    """应用主类"""
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # 设置应用实例引用，用于信号处理
        self.app.setApplicationName("Moji")

        # macOS: 隐藏 Dock 中的 Python 图标（作为菜单栏/托盘应用运行）
        if sys.platform == "darwin":
            try:
                from AppKit import NSApp, NSApplicationActivationPolicyAccessory
                # 设为 Accessory：不显示 Dock 图标，但保留托盘/窗口能力
                NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            except Exception:
                # 若未安装 pyobjc 或失败，则忽略（仍可正常运行，只是会显示图标）
                pass


        # 创建定时器来处理 Python 信号
        self.signal_timer = QTimer()
        self.signal_timer.timeout.connect(lambda: None)  # 空操作，仅为了让事件循环处理信号
        self.signal_timer.start(500)  # 每500ms触发一次

        # 轻量搜索弹窗（命令面板样式）
        self.search_popup = SearchPopup()
        self.search_popup.submitted.connect(self._on_search_submitted)

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

        # 本地 IPC：监听唤起指令
        self._setup_ipc_server()


        # macOS 全局快捷键（Command+Shift+K 搜索；Command+Shift+E 退出）：尝试启用；失败时提示依赖/权限
        try:
            from src.core.global_hotkey_mac import GlobalHotkeyListener
            if sys.platform == "darwin":
                # 打开搜索：Cmd+Shift+K
                self.global_hotkey = GlobalHotkeyListener(mods=("cmd", "shift"), key="K")
                try:
                    self.global_hotkey.hotkeyPressed.connect(lambda: self.open_search_popup())
                except Exception:
                    pass
                ok = self.global_hotkey.start()

                # 退出应用：Cmd+Shift+E（避免与系统的 Cmd+Shift+Q“注销”冲突）
                self.quit_hotkey = GlobalHotkeyListener(mods=("cmd", "shift"), key="E")
                try:
                    self.quit_hotkey.hotkeyPressed.connect(self.quit)
                except Exception:
                    pass
                ok_quit = self.quit_hotkey.start()

                if not (ok and ok_quit):
                    try:
                        self.tray.showMessage(
                            "Moji",
                            "全局快捷键未启用：请安装 pyobjc 并在 系统设置-隐私与安全性-辅助功能 中授权",
                            QSystemTrayIcon.MessageIcon.Information,
                            5000,
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        
        try:
            if sys.platform == "darwin":
                self._hotkey_watchdog = QTimer()
                self._hotkey_watchdog.setInterval(5000)
                def _ensure():
                    try:
                        if hasattr(self, "global_hotkey") and not self.global_hotkey.isRunning():
                            self.global_hotkey.start()
                        if hasattr(self, "quit_hotkey") and not self.quit_hotkey.isRunning():
                            self.quit_hotkey.start()
                    except Exception:
                        pass
                self._hotkey_watchdog.timeout.connect(_ensure)
                self._hotkey_watchdog.start()
        except Exception:
            pass



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

    def _activate_app(self):
        """在 macOS 下将应用提到前台，确保可以接收键盘事件"""
        try:
            if sys.platform == "darwin":
                try:
                    from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
                    NSRunningApplication.currentApplication().activateWithOptions_(
                        NSApplicationActivateIgnoringOtherApps
                    )
                except Exception:
                    # 退化到 Qt 的方式
                    self.app.setActiveWindow(self.window)
                    self.window.raise_()
                    self.app.processEvents()
            else:
                self.app.setActiveWindow(self.window)
                self.window.raise_()
                self.app.processEvents()
        except Exception:
            pass


    def open_search_popup(self, preset_text: str | None = None):
        """外部唤起：打开轻量搜索弹窗"""
        # 先把应用提到前台，确保键盘事件进来
        self._activate_app()
        try:
            self.search_popup.open(preset_text)
        except Exception:
            # 兜底：若弹窗异常，则直接显示主窗口
            self.show_window()

    def _on_search_submitted(self, query: str):
        """弹窗提交后，显示主窗口并执行搜索"""
        self.show_window()
        try:
            self.window.search_input.setText(query)
            self.window.do_search()
        except Exception:
            # 兜底：直接调用搜索管理器
            try:
                self.window.search_manager.do_search(query)
            except Exception:
                pass

    def _setup_ipc_server(self):
        """启动本地 IPC 服务器，接收外部唤起命令"""
        self._ipc_name = "moji_ipc"
        try:
            # 清理可能的陈旧 socket
            QLocalServer.removeServer(self._ipc_name)
        except Exception:
            pass
        self._ipc_server = QLocalServer()
        if not self._ipc_server.listen(self._ipc_name):
            # 已有实例在监听，当前实例不重复监听
            return
        self._ipc_server.newConnection.connect(self._on_ipc_new_connection)

    def _on_ipc_new_connection(self):
        conn = self._ipc_server.nextPendingConnection()
        if not conn:
            return

        def _read():
            try:
                data = bytes(conn.readAll()).decode("utf-8", errors="ignore").strip()
                if not data:
                    return
                # 支持 OPEN_SEARCH[:query]
                if data.startswith("OPEN_SEARCH"):
                    query = None
                    sep_idx = data.find(":")
                    if sep_idx != -1 and sep_idx + 1 < len(data):
                        query = data[sep_idx + 1 :].strip()
                    self.open_search_popup(query or None)
            finally:
                try:
                    conn.disconnectFromServer()
                except Exception:
                    pass
        conn.readyRead.connect(_read)
        # 尝试立即读取一次，避免极端情况下未触发 readyRead
        _read()


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