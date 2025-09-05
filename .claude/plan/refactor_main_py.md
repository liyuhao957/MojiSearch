# main.py 重构计划

## 任务概述
将 683 行的 main.py 拆分为 7 个模块文件，提高代码可维护性和可读性。

## 重构方案：组件化架构

### 目标文件结构
```
weibo_emoji/
├── main.py              # 程序入口（~15行）
├── app.py               # MojiApp 应用控制器（~75行）
├── window.py            # MainWindow 主窗口UI（~180行）
├── api.py               # WeiboAPI + SearchCache（~115行）
├── widgets.py           # EmojiWidget 表情组件（~40行）
├── loaders.py           # ImageLoader + CopyLoader（~55行）
├── virtual_scroll.py    # VirtualScrollManager（~50行）
└── search_manager.py    # SearchManager 搜索逻辑管理（~150行）
```

### 执行步骤
1. ✅ 保存执行计划
2. ⏳ 创建 api.py - 移动 API 相关类
3. ⏳ 创建 loaders.py - 移动异步加载器
4. ⏳ 创建 widgets.py - 移动 UI 组件
5. ⏳ 创建 virtual_scroll.py - 移动虚拟滚动管理
6. ⏳ 创建 search_manager.py - 抽取搜索逻辑
7. ⏳ 创建 window.py - 精简版主窗口
8. ⏳ 创建 app.py - 移动应用控制器
9. ⏳ 创建新的 main.py - 程序入口
10. ⏳ 验证和测试

### 设计原则
- KISS: 保持简单，避免过度设计
- DRY: 消除重复代码
- 单一职责: 每个模块职责明确
- 高内聚低耦合: 模块间通过接口通信

### 关键注意事项
- 避免循环导入
- 保持线程安全机制
- 使用 Qt 信号进行模块间通信
- 保持原有功能完整性