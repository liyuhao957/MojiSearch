"""
路径工具模块
"""

import os

def get_resource_path(filename):
    """获取资源文件的绝对路径"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, 'resources', filename)

def get_icon_path():
    """获取应用图标路径"""
    return get_resource_path('icon.png')