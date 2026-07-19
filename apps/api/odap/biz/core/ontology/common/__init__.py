"""
共享类型与常量 — 跨所有四层使用的基础定义。

本模块包含跨 Design / Construction / Reasoning / Application 层
共享的枚举、数据类、常量。不依赖任何具体层的实现。
"""

from .types import IntentType, ProcessingStatus

__all__ = ["IntentType", "ProcessingStatus"]
