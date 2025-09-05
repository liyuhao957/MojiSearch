#!/usr/bin/env python3
"""
Moji - 表情包搜索工具
macOS 原生风格 + 性能优化
"""

import sys
import signal
from src.core.app import MojiApp


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    print("\n正在退出...")
    if 'app' in globals():
        app.quit()
    sys.exit(0)


if __name__ == '__main__':
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    app = MojiApp()
    sys.exit(app.run())