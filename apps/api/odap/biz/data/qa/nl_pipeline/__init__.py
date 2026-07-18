"""
NL Pipeline (Iter 1 迁移)

本目录由 Spec 007 Iter 1 迁移动作创建，原文件位于：
  odap/biz/core/ontology/design/schema/semantic_layer/

迁移后的模块：
  - intent_parser: 自然语言意图解析
  - query_planner: 结构化查询任务规划
  - disambiguator: 术语消歧与扩展
"""

from .intent_parser import IntentParser, StructuredQuery
from .query_planner import QueryPlanner
from .disambiguator import Disambiguator

__all__ = [
    "IntentParser",
    "StructuredQuery",
    "QueryPlanner",
    "Disambiguator",
]
