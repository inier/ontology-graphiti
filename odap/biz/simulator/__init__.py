"""模拟推演模块 - 沙盘推演引擎，用于验证方案可行性，辅助决策

与 test_data 的区别:
  - test_data: 为构建本体场景生成测试数据（数据准备）
  - simulator: 对选定方案进行推演验证（决策辅助）
"""
from .engine import SimulatorEngine

__all__ = ['SimulatorEngine']
