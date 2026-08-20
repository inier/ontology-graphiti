"""SHACL 本体治理（ADR-077 §2）。

- shape_generator: 自定义 Schema → SHACL Shape 实时生成（不持久化，防漂移）
- validator:      实例 JSON → RDF 临时图 → pySHACL 校验
"""

from .shape_generator import ShapeGenerator
from .validator import SHACLValidator

__all__ = ["ShapeGenerator", "SHACLValidator"]
