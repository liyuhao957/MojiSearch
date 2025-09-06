"""
错误聚合 - 避免刷屏，提供有意义的错误信息
"""
from collections import defaultdict
import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

class ErrorAggregator(QObject):
    """错误聚合器"""
    
    # 聚合后的错误信号
    errors_aggregated = pyqtSignal(dict)  # {error_type: {count, indices, message}}
    
    def __init__(self, report_interval=2000):  # 2秒汇报一次
        super().__init__()
        self.errors = defaultdict(lambda: {
            'count': 0, 
            'indices': set(), 
            'first_time': None,
            'last_time': None
        })
        self.report_interval = report_interval
        
        # 定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.flush_errors)
        self.timer.start(report_interval)
        
    def add_error(self, index, code, message):
        """添加错误"""
        now = time.time()
        error = self.errors[code]
        
        error['count'] += 1
        error['indices'].add(index)
        error['message'] = message
        
        if error['first_time'] is None:
            error['first_time'] = now
        error['last_time'] = now
        
        # 严重错误立即上报
        if code in ['CONNECTION', 'TIMEOUT'] and error['count'] == 1:
            self.flush_errors()
    
    def flush_errors(self):
        """汇报错误"""
        if not self.errors:
            return
            
        # 准备汇总数据
        summary = {}
        for code, data in self.errors.items():
            summary[code] = {
                'count': data['count'],
                'indices': list(data['indices'])[:5],  # 只显示前5个
                'message': data['message'],
                'duration': data['last_time'] - data['first_time'] if data['first_time'] else 0
            }
        
        # 发送信号
        self.errors_aggregated.emit(summary)
        
        # 清空
        self.errors.clear()
    
    def reset(self):
        """重置错误统计"""
        self.errors.clear()