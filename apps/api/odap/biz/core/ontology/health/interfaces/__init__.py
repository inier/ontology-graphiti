"""Data Health - 抽象接口层"""
from .health_rule_repository import HealthRuleRepository
from .health_scanner import HealthScanner

__all__ = ["HealthRuleRepository", "HealthScanner"]
