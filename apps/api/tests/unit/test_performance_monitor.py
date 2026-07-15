import pytest
import sys
import os
import asyncio
import time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.infra.monitoring.performance_monitor import (
    PerformanceMonitor,
    monitor_performance,
    performance_monitor,
)


class TestPerformanceMonitor:

    @pytest.fixture
    def monitor(self):
        return PerformanceMonitor(max_history=1000)

    def test_start_stop_basic(self, monitor):
        monitor.start('llm_calls', 'test-1')
        duration = monitor.stop('llm_calls', 'test-1')
        assert duration is not None
        assert duration >= 0
        assert len(monitor.metrics['llm_calls']) == 1
        record = monitor.metrics['llm_calls'][0]
        assert record['identifier'] == 'test-1'
        assert record['duration'] >= 0
        assert record['timestamp'] is not None

    def test_start_stop_without_identifier(self, monitor):
        monitor.start('api_requests')
        duration = monitor.stop('api_requests')
        assert duration is not None
        assert len(monitor.metrics['api_requests']) == 1
        record = monitor.metrics['api_requests'][0]
        assert record['identifier'] is None

    def test_stop_without_start(self, monitor):
        duration = monitor.stop('llm_calls', 'nonexistent')
        assert duration is None

    def test_stop_cleans_start_time(self, monitor):
        monitor.start('llm_calls', 'test-1')
        monitor.stop('llm_calls', 'test-1')
        assert ('llm_calls', 'test-1') not in monitor.start_times

    def test_stop_with_additional_data(self, monitor):
        monitor.start('llm_calls', 'test-1')
        monitor.stop('llm_calls', 'test-1', additional_data={'model': 'gpt-4'})
        record = monitor.metrics['llm_calls'][0]
        assert record['additional_data'] == {'model': 'gpt-4'}

    def test_get_stats_empty(self, monitor):
        stats = monitor.get_stats('llm_calls')
        assert stats == {}

    def test_get_stats_unknown_metric(self, monitor):
        stats = monitor.get_stats('nonexistent')
        assert stats == {}

    def test_get_stats_with_records(self, monitor):
        for i in range(5):
            monitor.metrics['llm_calls'].append({
                'timestamp': '2026-01-01T00:00:00',
                'duration': float(i + 1),
                'identifier': None,
                'additional_data': None,
            })
        stats = monitor.get_stats('llm_calls')
        assert stats['count'] == 5
        assert stats['mean'] == 3.0
        assert stats['median'] == 3.0
        assert stats['min'] == 1.0
        assert stats['max'] == 5.0
        assert 'p95' in stats
        assert 'p99' in stats

    def test_get_stats_single_record(self, monitor):
        monitor.metrics['database_queries'].append({
            'timestamp': '2026-01-01T00:00:00',
            'duration': 0.5,
            'identifier': None,
            'additional_data': None,
        })
        stats = monitor.get_stats('database_queries')
        assert stats['count'] == 1
        assert stats['mean'] == 0.5
        assert stats['median'] == 0.5
        assert stats['min'] == 0.5
        assert stats['max'] == 0.5
        assert stats['p95'] == 0.5
        assert stats['p99'] == 0.5

    def test_get_all_stats(self, monitor):
        monitor.metrics['llm_calls'].append({
            'timestamp': '2026-01-01T00:00:00',
            'duration': 1.0,
            'identifier': None,
            'additional_data': None,
        })
        monitor.metrics['api_requests'].append({
            'timestamp': '2026-01-01T00:00:00',
            'duration': 2.0,
            'identifier': None,
            'additional_data': None,
        })
        all_stats = monitor.get_all_stats()
        assert 'llm_calls' in all_stats
        assert 'database_queries' in all_stats
        assert 'api_requests' in all_stats
        assert 'tool_executions' in all_stats
        assert all_stats['llm_calls']['count'] == 1
        assert all_stats['api_requests']['count'] == 1
        assert all_stats['database_queries'] == {}
        assert all_stats['tool_executions'] == {}

    def test_reset_single_metric(self, monitor):
        monitor.metrics['llm_calls'].append({
            'timestamp': '2026-01-01T00:00:00',
            'duration': 1.0,
            'identifier': None,
            'additional_data': None,
        })
        monitor.metrics['api_requests'].append({
            'timestamp': '2026-01-01T00:00:00',
            'duration': 2.0,
            'identifier': None,
            'additional_data': None,
        })
        monitor.reset('llm_calls')
        assert len(monitor.metrics['llm_calls']) == 0
        assert len(monitor.metrics['api_requests']) == 1

    def test_reset_all(self, monitor):
        for metric_type in monitor.metrics:
            monitor.metrics[metric_type].append({
                'timestamp': '2026-01-01T00:00:00',
                'duration': 1.0,
                'identifier': None,
                'additional_data': None,
            })
        monitor.reset()
        for metric_type in monitor.metrics:
            assert len(monitor.metrics[metric_type]) == 0

    def test_reset_unknown_metric(self, monitor):
        monitor.reset('nonexistent')

    def test_export_metrics(self, monitor):
        monitor.metrics['llm_calls'].append({
            'timestamp': '2026-01-01T00:00:00',
            'duration': 1.0,
            'identifier': 'call-1',
            'additional_data': None,
        })
        exported = monitor.export_metrics()
        assert 'llm_calls' in exported
        assert len(exported['llm_calls']) == 1
        assert exported['llm_calls'][0]['duration'] == 1.0
        assert exported['llm_calls'][0]['identifier'] == 'call-1'
        assert isinstance(exported['llm_calls'], list)

    def test_max_history_deque_overflow(self):
        small_monitor = PerformanceMonitor(max_history=3)
        for i in range(5):
            small_monitor.metrics['llm_calls'].append({
                'timestamp': '2026-01-01T00:00:00',
                'duration': float(i),
                'identifier': None,
                'additional_data': None,
            })
        assert len(small_monitor.metrics['llm_calls']) == 3
        durations = [r['duration'] for r in small_monitor.metrics['llm_calls']]
        assert durations == [2.0, 3.0, 4.0]

    def test_percentile_empty(self, monitor):
        result = monitor._percentile([], 95)
        assert result == 0

    def test_percentile_calculation(self, monitor):
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        p95 = monitor._percentile(data, 95)
        p99 = monitor._percentile(data, 99)
        assert p95 == 10.0
        assert p99 == 10.0

    def test_percentile_single_value(self, monitor):
        result = monitor._percentile([5.0], 50)
        assert result == 5.0

    def test_start_stop_measures_real_time(self, monitor):
        monitor.start('llm_calls', 'delay-test')
        time.sleep(0.05)
        duration = monitor.stop('llm_calls', 'delay-test')
        assert duration >= 0.04


class TestMonitorPerformanceDecorator:

    @pytest.fixture(autouse=True)
    def reset_global_monitor(self):
        performance_monitor.reset()
        yield
        performance_monitor.reset()

    def test_sync_function(self):
        @monitor_performance('tool_executions', 'sync-fn')
        def sync_work():
            return 42

        result = sync_work()
        assert result == 42
        assert len(performance_monitor.metrics['tool_executions']) == 1
        record = performance_monitor.metrics['tool_executions'][0]
        assert record['identifier'] == 'sync-fn'
        assert record['duration'] >= 0
        assert record['additional_data'] is None

    def test_sync_function_without_identifier(self):
        @monitor_performance('api_requests')
        def sync_work():
            return 'ok'

        result = sync_work()
        assert result == 'ok'
        record = performance_monitor.metrics['api_requests'][0]
        assert record['identifier'] is None

    def test_sync_function_exception(self):
        @monitor_performance('llm_calls', 'failing')
        def failing_work():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            failing_work()

        assert len(performance_monitor.metrics['llm_calls']) == 1
        record = performance_monitor.metrics['llm_calls'][0]
        assert record['additional_data'] is not None
        assert record['additional_data']['error'] == 'boom'

    def test_async_function(self):
        @monitor_performance('database_queries', 'async-fn')
        async def async_work():
            return 'async-result'

        result = asyncio.run(async_work())
        assert result == 'async-result'
        assert len(performance_monitor.metrics['database_queries']) == 1
        record = performance_monitor.metrics['database_queries'][0]
        assert record['identifier'] == 'async-fn'
        assert record['duration'] >= 0
        assert record['additional_data'] is None

    def test_async_function_exception(self):
        @monitor_performance('llm_calls', 'async-failing')
        async def async_failing():
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError, match="async boom"):
            asyncio.run(async_failing())

        assert len(performance_monitor.metrics['llm_calls']) == 1
        record = performance_monitor.metrics['llm_calls'][0]
        assert record['additional_data'] is not None
        assert record['additional_data']['error'] == 'async boom'

    def test_decorator_multiple_calls(self):
        @monitor_performance('tool_executions', 'multi')
        def work():
            return 1

        work()
        work()
        work()
        assert len(performance_monitor.metrics['tool_executions']) == 3
