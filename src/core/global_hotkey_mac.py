"""
macOS 全局快捷键监听（Command+Shift+K 默认）
- 基于 Quartz.CGEventTap（需“辅助功能”权限）
- 无依赖时优雅降级（不崩溃）
"""
from __future__ import annotations

import sys
import threading
from typing import Iterable, Optional

from PyQt6.QtCore import QObject, pyqtSignal

try:
    import Quartz
except Exception:  # 未安装 pyobjc 或环境不支持
    Quartz = None  # type: ignore


# 部分常用键码（ANSI US 键盘）；K=40 较稳定
VK_MAP = {
    "SPACE": 49,
    "K": 40,
}

# 修饰键掩码映射
MOD_MAP = {
    "cmd": getattr(Quartz, "kCGEventFlagMaskCommand", 1 << 20) if Quartz else (1 << 20),
    "shift": getattr(Quartz, "kCGEventFlagMaskShift", 1 << 17) if Quartz else (1 << 17),
    "option": getattr(Quartz, "kCGEventFlagMaskAlternate", 1 << 19) if Quartz else (1 << 19),
    "ctrl": getattr(Quartz, "kCGEventFlagMaskControl", 1 << 18) if Quartz else (1 << 18),
}


class GlobalHotkeyListener(QObject):
    hotkeyPressed = pyqtSignal()

    def __init__(self, mods: Iterable[str] = ("cmd", "shift"), key: str = "K"):
        super().__init__()
        self._mods = tuple(m.lower() for m in mods)
        self._key = key.upper()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tap = None
        self._source = None

    def start(self) -> bool:
        """启动监听；返回是否成功启用。未在 macOS 或无 Quartz 时返回 False。"""
        if sys.platform != "darwin" or Quartz is None:
            return False
        if self._running:
            return True

        keycode = VK_MAP.get(self._key)
        if keycode is None:
            # 仅支持定义的键；可按需扩展
            return False

        want_flags = 0
        for m in self._mods:
            want_flags |= MOD_MAP.get(m, 0)

        def tap_callback(proxy, type_, event, refcon):  # noqa: N802 (C 接口)
            try:
                if type_ == Quartz.kCGEventKeyDown:
                    code = Quartz.CGEventGetIntegerValueField(
                        event, Quartz.kCGKeyboardEventKeycode
                    )
                    flags = Quartz.CGEventGetFlags(event)
                    # 仅匹配需要的修饰键全部按下（忽略其它系统位）
                    if code == keycode and (flags & want_flags) == want_flags:
                        # 跨线程安全：PyQt 信号可从任意线程发射（排队连接）
                        self.hotkeyPressed.emit()
            except Exception:
                pass
            return event

        # 先尝试创建 tap（若失败，立即返回 False）
        mask = 1 << Quartz.kCGEventKeyDown
        self._tap_callback = tap_callback  # 保持回调不被 GC
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            self._tap_callback,
            None,
        )
        if not self._tap:
            return False

        def worker():
            try:
                self._source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
                loop = Quartz.CFRunLoopGetCurrent()
                Quartz.CFRunLoopAddSource(loop, self._source, Quartz.kCFRunLoopCommonModes)
                Quartz.CGEventTapEnable(self._tap, True)
                Quartz.CFRunLoopRun()
            except Exception:
                pass
            finally:
                self._running = False

        self._running = True
        self._thread = threading.Thread(target=worker, name="MojiGlobalHotkey", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if not self._running:
            return
        try:
            if Quartz and self._source:
                Quartz.CFRunLoopStop(Quartz.CFRunLoopGetCurrent())
        except Exception:
            pass
        self._running = False

    def isRunning(self) -> bool:
        return self._running

