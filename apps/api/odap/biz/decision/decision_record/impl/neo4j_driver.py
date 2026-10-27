"""决策存储专用 Graphiti Neo4jDriver 单例

独立成模块的原因：读写两侧（`neo4j_decision_store` / `neo4j_decision_query`
/ `neo4j_decision_migration`）都要用它，放在任一实现文件里都会形成循环 import。
"""

import logging
from typing import Any, Dict

from odap.infra.security import security_config

logger = logging.getLogger(__name__)

try:
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.nodes import EntityNode

    GRAPHITI_AVAILABLE = True
except ImportError:  # pragma: no cover
    Neo4jDriver = None
    EntityNode = None
    GRAPHITI_AVAILABLE = False

_driver = None


def get_decision_driver():
    """决策存储专用 Graphiti Neo4jDriver（模块级单例）。

    注意（0.29.2 已核验）：EntityNode.save() 要求 graphiti 包装 driver
    （访问 graph_operations_interface 属性），不能传裸 neo4j AsyncDriver。
    execute_query(cypher, **kwargs) 与裸 driver 用法兼容（kwargs 即查询参数）。
    """
    global _driver
    if _driver is None:
        if not GRAPHITI_AVAILABLE:
            raise RuntimeError("graphiti-core 未安装")
        _driver = Neo4jDriver(
            uri=security_config.NEO4J_URI,
            user=security_config.NEO4J_USER,
            password=security_config.get_neo4j_password(),
        )
    return _driver


def node_props(record: Any) -> Dict[str, Any]:
    """neo4j Node/record 属性转普通 dict（datetime 等类型的兜底在模型层处理）。"""
    return {k: v for k, v in dict(record).items()}
