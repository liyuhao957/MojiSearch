#!/usr/bin/env python3
"""
mojictl - Moji 本地控制工具
用法：
  python mojictl.py open-search [可选的初始关键词]

将一条 OPEN_SEARCH 指令发送到正在运行的 Moji 应用。
将此脚本绑定到 Raycast/Alfred/快捷指令 的全局快捷键，即可实现任意应用内呼出搜索弹窗。
"""

import sys
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtNetwork import QLocalSocket

IPC_NAME = "moji_ipc"


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"open-search", "open_search"}:
        print("用法: python mojictl.py open-search [关键词]")
        return 1

    # 拼接可选的关键词
    query = " ".join(sys.argv[2:]).strip()

    app = QCoreApplication(sys.argv)

    sock = QLocalSocket()
    sock.connectToServer(IPC_NAME)
    if not sock.waitForConnected(400):
        print("Moji 未在运行，请先启动 Moji 再重试。")
        return 2

    msg = "OPEN_SEARCH" + (":" + query if query else "") + "\n"
    sock.write(msg.encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(400)
    # 立即退出即可
    return 0


if __name__ == "__main__":
    sys.exit(main())

