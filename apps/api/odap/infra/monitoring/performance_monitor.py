#!/usr/bin/env python3
"""
性能监控模块
"""

import time
import statistics
from collections import deque
from datetime import datetime


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, max_history=1000):
        """初始化性能监控器

        Args:
            max_history: 最大历史记录数
        """
        self.max_history = max_history
        self.metrics = {
            'llm_calls': deque(maxlen=max_history),
            'database_queries': deque(maxlen=max_history),
            'api_requests': deque(maxlen=max_history),
            'tool_executions': deque(maxlen=max_history),
        }
        self.start_times = {}

    def start(self, metric_type, identifier=None):
        """开始监控

        Args:
            metric_type: 指标类型 (llm_calls, database_queries, api_requests, tool_executions)
            identifier: 标识符（可选）
        """
        key = (metric_type, identifier)
        self.start_times[key] = time.time()

    def stop(self, metric_type, identifier=None, additional_data=None):
        """停止监控并记录指标

        Args:
            metric_type: 指标类型 (llm_calls, database_queries, api_requests, tool_executions)
            identifier: 标识符（可选）
            additional_data: 附加数据（可选）
        """
        key = (metric_type, identifier)
        if key in self.start_times:
            duration = time.time() - self.start_times[key]
            del self.start_times[key]
            
            record = {
                'timestamp': datetime.now().isoformat(),
                'duration': duration,
                'identifier': identifier,
                'additional_data': additional_data,
            }
            self.metrics[metric_type].append(record)
            return duration
        return None

    def get_stats(self, metric_type):
        """获取指标统计信息

        Args:
            metric_type: 指标类型

        Returns:
            统计信息字典
        """
        if metric_type not in self.metrics:
            return {}

        records = self.metrics[metric_type]
        if not records:
            return {}

        durations = [r['duration'] for r in records]
        return {
            'count': len(records),
            'mean': statistics.mean(durations) if durations else 0,
            'median': statistics.median(durations) if durations else 0,
            'min': min(durations) if durations else 0,
            'max': max(durations) if durations else 0,
            'p95': self._percentile(durations, 95) if durations else 0,
            'p99': self._percentile(durations, 99) if durations else 0,
        }

    def _percentile(self, data, percentile):
        """计算百分位数

        Args:
            data: 数据列表
            percentile: 百分位数 (0-100)

        Returns:
            百分位数值
        """
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]

    def get_all_stats(self):
        """获取所有指标的统计信息

        Returns:
            所有指标的统计信息字典
        """
        stats = {}
        for metric_type in self.metrics:
            stats[metric_type] = self.get_stats(metric_type)
        return stats

    def reset(self, metric_type=None):
        """重置指标

        Args:
            metric_type: 指标类型（可选，不指定则重置所有）
        """
        if metric_type:
            if metric_type in self.metrics:
                self.metrics[metric_type].clear()
        else:
            for key in self.metrics:
                self.metrics[key].clear()

    def export_metrics(self):
        """导出指标数据

        Returns:
            指标数据字典
        """
        return {
            metric_type: list(records)
            for metric_type, records in self.metrics.items()
        }


# 全局性能监控实例
performance_monitor = PerformanceMonitor()


def monitor_performance(metric_type, identifier=None):
    """性能监控装饰器

    Args:
        metric_type: 指标类型
        identifier: 标识符

    Returns:
        装饰器
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            performance_monitor.start(metric_type, identifier)
            try:
                result = await func(*args, **kwargs)
                performance_monitor.stop(metric_type, identifier)
                return result
            except Exception as e:
                performance_monitor.stop(metric_type, identifier, {'error': str(e)})
                raise
        
        def sync_wrapper(*args, **kwargs):
            performance_monitor.start(metric_type, identifier)
            try:
                result = func(*args, **kwargs)
                performance_monitor.stop(metric_type, identifier)
                return result
            except Exception as e:
                performance_monitor.stop(metric_type, identifier, {'error': str(e)})
                raise
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator
