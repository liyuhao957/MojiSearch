# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**Moji** - macOS 表情包搜索工具
- **技术栈**: Python 3 + PyQt6
- **核心功能**: 搜索微博表情包并复制到剪贴板
- **架构模式**: 模块化架构，8个独立模块，每个模块职责单一

## 常用命令

### 环境设置
```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install PyQt6 requests
```

### 运行应用
```bash
# 直接运行
python3 main.py

# 调试运行（查看 API 响应）
python3 -u main.py
```

### 打包发布
```bash
# 安装打包工具
pip install pyinstaller

# 打包为 macOS App
pyinstaller --onefile --windowed --name=Moji main.py
```

## 架构设计

### 模块化文件结构

```
weibo_emoji/
├── main.py                 # 程序入口 - 应用启动点
├── src/
│   ├── core/              # 核心业务逻辑
│   │   ├── app.py         # MojiApp - 应用控制器，管理托盘和窗口生命周期
│   │   └── api.py         # WeiboAPI + SearchCache - API通信和缓存
│   ├── ui/                # UI 界面层
│   │   ├── window.py      # MainWindow - UI主窗口，协调界面交互
│   │   └── widgets.py     # EmojiWidget - UI组件定义
│   ├── managers/          # 业务管理器
│   │   ├── search.py      # SearchManager - 搜索逻辑管理，处理数据流
│   │   └── virtual_scroll.py # VirtualScrollManager - 虚拟滚动管理
│   └── utils/             # 工具类
│       └── loaders.py     # ImageLoader + CopyLoader - 异步加载器
└── resources/             # 资源文件
    └── icon.png           # 应用图标
```

### 核心模块职责

1. **app.py - MojiApp** - 应用主控制器
   - 管理系统托盘图标和菜单
   - 控制窗口显示/隐藏
   - 处理应用生命周期
   - 与 window.py 协作管理 UI

2. **window.py - MainWindow** - 主窗口界面
   - UI 布局和样式管理
   - 搜索框输入处理（500ms 防抖）
   - 与 SearchManager 通过信号通信
   - 处理复制操作和用户反馈

3. **search_manager.py - SearchManager** - 搜索业务逻辑
   - 管理搜索流程和分页
   - 协调虚拟滚动更新
   - 处理图片加载调度
   - 维护 widget 池和活动 widget

4. **api.py - WeiboAPI + SearchCache** - 数据层
   - 封装微博 API 调用
   - 实现自动重试机制（432 状态码处理）
   - LRU 缓存管理（5分钟过期）
   - 图片数据提取

5. **loaders.py - 异步加载器**
   - ImageLoader：后台图片加载线程
   - CopyLoader：后台图片复制线程
   - get_large_url()：统一的 URL 转换函数

6. **virtual_scroll.py - VirtualScrollManager** - 性能优化
   - 虚拟列表实现
   - Widget 池化管理
   - 可视区域计算

7. **widgets.py - EmojiWidget** - UI 组件
   - 表情包卡片组件
   - 鼠标交互处理
   - 视觉效果管理

### 关键设计原则

1. **模块间通信**
   - MainWindow ← → SearchManager：通过 Qt 信号机制
   - SearchManager → loaders：创建线程实例
   - 所有模块 → api.py：直接调用类方法

2. **线程安全**
   - 图片加载线程仅传递 bytes 数据
   - UI 线程负责 QPixmap 转换和缩放
   - 避免跨线程 GUI 操作

3. **性能优化**
   - 虚拟滚动：Widget 池化复用
   - 搜索缓存：减少重复 API 请求
   - 懒加载：仅加载可视区域图片

4. **错误处理**
   - API 432 状态码：指数退避重试
   - 网络超时：友好提示，自动隐藏
   - 图片加载失败：静默处理

## 微博 API 规范

### 核心配置（禁止硬编码）

```python
# 必须使用的 API 配置
BASE_URL = "https://m.weibo.cn/api/container/getIndex"

# 搜索容器 ID 格式
containerid = f'100103type={type_code}&q={quote(keyword)}&t='
# 注意：t 参数必须为空字符串，不要添加时间戳

# 推荐使用的 type_code
TYPE_IMAGE = 63  # 图片频道，表情包密度最高
TYPE_GENERAL = 1  # 综合频道
```

### 请求头要求
```python
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
    'Referer': 'https://m.weibo.cn/'
}
# User-Agent 必须是移动端格式
```

### 图片 URL 处理
```python
# 图片尺寸转换（从小到大）
thumb_url = "https://wx3.sinaimg.cn/orj360/xxx.jpg"
large_url = thumb_url.replace('/orj360/', '/large/')  # 高清图
original_url = thumb_url.replace('/orj360/', '/original/')  # 原图

# 推荐使用 large 尺寸，平衡质量和速度
```

### 错误处理规范
```python
# 432 状态码处理（反爬虫）
if response.status_code == 432:
    wait_time = 2 * (retry_count + 1)  # 指数退避
    time.sleep(wait_time)
    # 最多重试 3 次

# 请求频率控制
time.sleep(1)  # 分页请求间隔至少 1 秒
```

## 开发规范

### 测试文件管理规范

**重要**：所有测试和临时文件必须在测试完成后立即删除，保持代码库清洁。

**需要立即删除的文件类型：**
- 测试报告文件（*test*.md, *测试*.md）
- API 测试文件（api_test_*, test_*.py）
- 临时备份文件（*_old.py, *.bak）
- 设计文档草稿（*_design.md, *_draft.md）
- 调试日志文件（*.log, debug_*）
- 问题分析文档（*_issue.md, *_analysis.md）

**清理命令示例：**
```bash
# 删除所有测试相关文件
rm -f *test*.* *_old.py *_analysis.md *_design*.md

# 清理 Python 缓存
rm -rf __pycache__/
```

**注意**：创建测试文件时应使用明确的测试前缀（如 test_），便于后续批量清理。

### 严禁代码占位符和硬编码

**重要**：绝对不允许在代码实现中使用占位符或硬编码值。所有代码必须是可直接运行的完整实现。

❌ **严禁的代码占位符示例**：
```python
# 占位符 - 绝对禁止
api_key = "YOUR_API_KEY_HERE"  
url = "TODO: 添加实际URL"
username = "PLACEHOLDER_USERNAME"

# 硬编码 URL - 禁止
url = "https://example.com/api/endpoint"  

# 硬编码配置 - 禁止
MAX_PAGES = 10  # 写死的页数限制
CACHE_TIME = 300  # 写死的缓存时间
```

✅ **必须的实现方式**：
```python
# 使用明确的常量定义
class WeiboAPI:
    BASE_URL = "https://m.weibo.cn/api/container/getIndex"  # 真实 API 地址
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
        'Referer': 'https://m.weibo.cn/'
    }
    
# 从用户输入获取动态值
keyword = self.search_input.text().strip()  # 从实际输入获取

# 使用可配置参数
def __init__(self, max_age=300, max_size=50):  # 提供默认值但可配置
    self.max_age = max_age
    self.max_size = max_size

# UI 文字提示是允许的（这不是占位符）
self.search_input.setPlaceholderText("搜点什么...")  # 这是 UI 提示，允许使用
```

### 代码完整性要求

1. **所有 URL 必须是真实可用的**
   - 微博 API：`https://m.weibo.cn/api/container/getIndex`
   - 图片 CDN：`https://wx3.sinaimg.cn/`

2. **所有配置必须有合理默认值**
   ```python
   # 正确：提供实际可用的默认值
   class SearchCache:
       def __init__(self, max_age=300):  # 5分钟缓存
           self.max_age = max_age
           self.max_size = 50  # 最多缓存50个结果
   ```

3. **测试数据必须使用真实示例**
   ```python
   # 正确：使用真实的测试关键词
   if __name__ == "__main__":
       # 使用实际的搜索词进行测试
       test_keywords = ["猫猫表情包", "狗狗表情包", "可爱表情"]
   ```

### UI 实现要求

1. **macOS 原生风格**
   - 毛玻璃效果：`rgba(248, 248, 248, 0.95)`
   - 圆角：窗口 12px，卡片 8px
   - 微博橙点缀：`#FF8200`（仅用于交互反馈）

2. **窗口规格**
   - 固定尺寸：380x520px
   - 位置：屏幕右上角，距离右边缘 20px
   - 行为：ESC 键隐藏，点击托盘图标显示

3. **交互细节**
   - 搜索延迟：500ms（防止过度请求）
   - 错误提示：3 秒自动消失
   - 复制反馈：橙色闪烁 150ms

### 调试技巧

**快速定位模块问题：**
```bash
# 测试 API 模块独立运行
python3 -c "from api import WeiboAPI; print(WeiboAPI.search('猫猫表情包')[:3])"

# 检查模块导入依赖
python3 -c "import app, window, search_manager, api, loaders, widgets, virtual_scroll"
```

### 测试要点

1. **API 测试**
   - 验证 type=63（图片频道）返回大量图片
   - 确认 432 状态码重试机制工作
   - 检查搜索缓存是否生效

2. **UI 测试**
   - 虚拟滚动流畅性
   - 内存占用（Widget 池化）
   - 图片加载不阻塞主线程

3. **边界情况**
   - 空搜索结果处理
   - 网络断开恢复
   - 快速切换搜索词

## 已验证的 API 数据

基于 2025 年 1 月测试：
- 搜索"猫猫表情包"（type=63）：单页 37 个卡片，230 张图片
- 搜索"表情包"（type=1）：单页 26 个卡片，图片较少
- API 成功率 > 95%
- 最大结果数：1000（API 限制）

## 注意事项

1. **版权问题**：图片仅供个人使用，不要添加商业化功能
2. **API 稳定性**：非官方接口，需要容错处理
3. **内存管理**：及时回收不可见的 Widget
4. **线程清理**：确保图片加载线程正确结束
5. **缓存大小**：限制缓存最多 50 个搜索结果