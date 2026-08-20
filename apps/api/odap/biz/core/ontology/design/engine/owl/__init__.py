"""OWL 互操作（ADR-077 §4）。

- owl_exporter: 自定义 Schema → OWL/Turtle 导出（owlready2 可用时，否则 rdflib 降级）
- owl_importer: 标准 OWL → Schema 候选（草稿，经 HITL 确认后写回，裁决 2）
"""

from .owl_exporter import OWLExporter
from .owl_importer import OWLImporter

__all__ = ["OWLExporter", "OWLImporter"]
