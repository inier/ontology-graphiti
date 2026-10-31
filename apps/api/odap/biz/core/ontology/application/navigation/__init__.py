"""
L3 Application Knowledge Navigation (Phase 2 桥接, 从 cognition/ 迁移).

注：`navigate_knowledge` 已重构为 `KnowledgeNavigator` 的方法，模块级函数不再存在；
此前仍按旧符号 re-export，导致本包在 import 期就抛 ImportError。
"""

from odap.biz.core.cognition.impl.knowledge_navigator import KnowledgeNavigator

__all__ = ["KnowledgeNavigator"]
