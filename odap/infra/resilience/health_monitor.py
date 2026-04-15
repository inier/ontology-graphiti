"""
健康监控器模块
实现 Swarm 系统和 Agent 的健康监控、指标收集和告警

Phase 2 扩展: 故障恢复与状态管理
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("health_monitor")


@dataclass
class HealthMetric:
    """健康指标"""
    name: str
    value: float
    unit: str
    threshold_warning: float
    threshold_critical: float
    timestamp: datetime = field(default_factory=datetime.now)


class HealthMonitor:
    """健康监控器"""

    _instance: Optional['HealthMonitor'] = None

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.metrics_history: Dict[str, List[HealthMetric]] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.monitoring_tasks: List[asyncio.Task] = []
        self._running = False

    @classmethod
    def get_instance(cls, check_interval: int = 60) -> 'HealthMonitor':
        if cls._instance is None:
            cls._instance = HealthMonitor(check_interval)
        return cls._instance

    async def start_monitoring(self):
        """启动健康监控"""
        if self._running:
            logger.warning("健康监控已在运行")
            return

        logger.info("启动 Swarm 健康监控...")
        self._running = True

        tasks = [
            self._monitor_swarm_health(),
        ]

        self.monitoring_tasks = [asyncio.create_task(task) for task in tasks]
        logger.info(f"已启动 {len(self.monitoring_tasks)} 个监控任务")

    async def stop_monitoring(self):
        """停止健康监控"""
        logger.info("停止 Swarm 健康监控...")
        self._running = False

        for task in self.monitoring_tasks:
            task.cancel()

        try:
            await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        self.monitoring_tasks.clear()
        logger.info("Swarm 健康监控已停止")

    async def _monitor_swarm_health(self):
        """监控 Swarm 系统健康状态"""
        while self._running:
            try:
                await self._check_swarm_components()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f" Swarm 健康监控异常: {e}")
                await asyncio.sleep(10)

    async def _check_swarm_components(self):
        """检查 Swarm 各组件健康状态"""
        from odap.biz.agent.swarm_orchestrator import BattlefieldSwarm
        from odap.infra.resilience.fault_tolerance import FaultRecoveryManager

        swarm = BattlefieldSwarm()
        fault_manager = FaultRecoveryManager.get_instance()

        for agent_type, agent in swarm.agents.items():
            agent_id = agent_type.value

            state = fault_manager.get_agent_state(agent_id)
            metric = HealthMetric(
                name=f"agent_{agent_id}_state",
                value=1.0 if state.value == "idle" else 0.5 if state.value == "running" else 0.0,
                unit="score",
                threshold_warning=0.3,
                threshold_critical=0.1,
            )
            await self._record_metric(metric)

            if state.value in ["failed", "degraded"]:
                await self._generate_alert(
                    level="warning" if state.value == "degraded" else "critical",
                    component=agent_id,
                    metric="agent_state",
                    value=state.value,
                    message=f"Agent {agent_id} 状态异常: {state.value}"
                )

        mission_count = len(swarm.active_missions)
        metric = HealthMetric(
            name="swarm_active_missions",
            value=float(mission_count),
            unit="count",
            threshold_warning=10,
            threshold_critical=20,
        )
        await self._record_metric(metric)

    async def _record_metric(self, metric: HealthMetric):
        """记录指标"""
        if metric.name not in self.metrics_history:
            self.metrics_history[metric.name] = []

        self.metrics_history[metric.name].append(metric)

        if len(self.metrics_history[metric.name]) > 1000:
            self.metrics_history[metric.name] = self.metrics_history[metric.name][-1000:]

        if metric.value >= metric.threshold_critical:
            await self._generate_alert(
                level="critical",
                metric_name=metric.name,
                value=metric.value,
                threshold=metric.threshold_critical,
                message=f"指标 {metric.name} 达到严重阈值: {metric.value}{metric.unit}"
            )
        elif metric.value >= metric.threshold_warning:
            await self._generate_alert(
                level="warning",
                metric_name=metric.name,
                value=metric.value,
                threshold=metric.threshold_warning,
                message=f"指标 {metric.name} 达到警告阈值: {metric.value}{metric.unit}"
            )

    async def _generate_alert(self, level: str, **kwargs):
        """生成告警"""
        alert = {
            "level": level,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }

        self.alerts.append(alert)

        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

        logger.log(
            logging.WARNING if level == "warning" else logging.ERROR,
            f"告警: {alert['message']}"
        )

    async def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {},
            "alerts_count": len(self.alerts),
            "recent_alerts": self.alerts[-10:],
            "recommendations": []
        }

        for metric_name, metrics in self.metrics_history.items():
            if not metrics:
                continue

            latest = metrics[-1]
            if latest.value >= latest.threshold_critical:
                report["overall_status"] = "critical"
                report["recommendations"].append(f"立即处理: {metric_name} 超过严重阈值")
            elif latest.value >= latest.threshold_warning and report["overall_status"] != "critical":
                report["overall_status"] = "degraded"

        return report

    def get_recent_metrics(self, metric_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的指标数据"""
        metrics = self.metrics_history.get(metric_name, [])
        return [
            {
                "name": m.name,
                "value": m.value,
                "unit": m.unit,
                "timestamp": m.timestamp.isoformat()
            }
            for m in metrics[-limit:]
        ]

    def clear_alerts(self):
        """清除告警历史"""
        cleared = len(self.alerts)
        self.alerts.clear()
        logger.info(f"已清除 {cleared} 条告警记录")