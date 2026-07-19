"""
跨层共享基础类型定义。

所有枚举和数据类均为 Frozen / Immutable，定义在 common/ 中
以供 Design / Construction / Reasoning / Application 四层共同使用。
"""

from enum import Enum


class IntentType(str, Enum):
    """用户意图类型 — 跨 Design、Cognition、Application 层使用。

    原位置:
      - ontology/design/services/qa_ontology_builder.py (10值的超集)
      - cognition/models/cognition_models.py (7值的子集，已废弃)

    迁移到 common/ 以消除重复定义和循环依赖。
    """
    QUERY = "query"             # 信息查询
    UPDATE = "update"           # 数据更新
    CREATE = "create"           # 创建新实体/类型
    ANALYZE = "analyze"         # 数据分析
    UNKNOWN = "unknown"          # 无法识别的意图
    ACTION = "action"            # 执行动作
    EXPLAIN = "explain"          # 请求解释
    RECOMMEND = "recommend"      # 请求推荐
    NAVIGATE = "navigate"        # 知识导航
    COMPARE = "compare"          # 对比分析


class ProcessingStatus(str, Enum):
    """处理状态 — 跨层使用，定义管道处理各阶段的通用状态。

    原位置: ontology/design/models/audit.py
    迁移到 common/ 以消除旧目录结构。
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


__all__ = ["IntentType", "ProcessingStatus"]
