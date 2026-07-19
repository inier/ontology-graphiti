# ADR-071: BuildResultContract —— L2 Construction 层构建产物契约

## Status
Proposed

## Context

ADR-068 将本体模块重组为 3+1 分层架构，新增 L2 Construction 层负责数据摄入、信息抽取、构建流水线和质量验证。该层需要对外暴露构建产物（实体实例、关系实例、质量报告、构建状态），供 +AI Reasoning 和 L3 Application 层消费。

若不定义契约，上层模块会直接导入 Construction 内部实现：
- L3 Application 的 OMS/运行时/查询需要读取构建产物，但不应关心 ingestion 内部存储细节
- +AI Reasoning 的一致性校验需要跨层比对 Design schema 与 Construction 实例，但不应耦合到 pipeline 实现
- Construction 的写入操作（ingestion/pipeline）需走独立桥接路径，不应与只读视图混用

遵循 ADR-068 的「所有 Contract 返回 Frozen Dataclass Views，禁止直接引用内部实现类」原则。

## Decision

### 1. Frozen Dataclass Views

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class EntityInstanceView:
    """已构建的实体实例（只读视图）。"""
    instance_id: str
    entity_type_id: str
    workspace_id: str
    properties: Dict[str, Any]          # 实例属性键值对
    source_tracing: Dict[str, str]      # 来源追溯: {source_id, record_id, ingestion_run_id}
    confidence_score: float             # 抽取置信度 0.0-1.0
    created_at: datetime
    updated_at: datetime
    quality_flags: Dict[str, bool] = field(default_factory=dict)  # e.g. {"passed_validation": True}

@dataclass(frozen=True)
class RelationInstanceView:
    """已构建的关系实例（只读视图）。"""
    relation_id: str
    relation_type_id: str
    source_entity_instance_id: str
    target_entity_instance_id: str
    properties: Dict[str, Any]
    confidence_score: float
    source_tracing: Dict[str, str]
    created_at: datetime

@dataclass(frozen=True)
class BuildStatusView:
    """构建流水线当前状态。"""
    pipeline_run_id: str
    workspace_id: str
    status: str                         # "pending" | "running" | "completed" | "failed"
    stages: Dict[str, str]              # stage_name → status
    progress_pct: float                 # 0.0-100.0
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    errors: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class QualityReportView:
    """质量验证报告（只读视图）。"""
    pipeline_run_id: str
    total_entities: int
    passed_entities: int
    failed_entities: int
    anomaly_counts: Dict[str, int]      # 异常类型 → 计数
    entity_details: Dict[str, str]      # instance_id → "pass"|"fail"
    generated_at: datetime

@dataclass(frozen=True)
class IngestionSourceView:
    """数据摄入源元数据。"""
    source_id: str
    workspace_id: str
    source_type: str                    # "pdf"|"word"|"news"|"crawler"|"db"|"file_upload"
    display_name: str
    last_run_at: Optional[datetime]
    last_record_count: int
    status: str                         # "active"|"paused"|"error"
    config_metadata: Dict[str, Any] = field(default_factory=dict)
```

### 2. BuildResultContract 抽象合约

```python
class BuildResultContract:
    """
    L2 Construction 层对外契约（只读）。

    +AI Reasoning 和 L3 Application 通过此契约读取构建产物，
    禁止直接引用 construction/ 内部实现类。

    写入操作（ingestion/pipeline）通过桥接模式走 construction 内部服务，
    不走此契约。
    """

    # ---------- 实体实例 ----------
    def list_entity_instances(
        self, entity_type_id: str, limit: int = 100, offset: int = 0
    ) -> List[EntityInstanceView]:
        """按实体类型分页列出已构建的实例。"""
        raise NotImplementedError

    def get_entity_instance(self, instance_id: str) -> EntityInstanceView:
        """按 ID 获取单个实体实例。"""
        raise NotImplementedError

    # ---------- 关系实例 ----------
    def list_relation_instances(
        self, source_entity_id: str, relation_type: Optional[str] = None
    ) -> List[RelationInstanceView]:
        """列出指定源实体的关系，可按关系类型过滤。"""
        raise NotImplementedError

    # ---------- 构建状态 ----------
    def get_build_status(self, pipeline_run_id: str) -> BuildStatusView:
        """获取指定流水线运行的当前状态。"""
        raise NotImplementedError

    # ---------- 质量报告 ----------
    def get_quality_report(self, pipeline_run_id: str) -> QualityReportView:
        """获取指定流水线运行的质量验证报告。"""
        raise NotImplementedError

    # ---------- 摄入源 ----------
    def list_ingestion_sources(self, workspace_id: str) -> List[IngestionSourceView]:
        """列出工作空间下所有数据摄入源。"""
        raise NotImplementedError
```

### 3. 写入操作走桥接模式

与 ADR-068 中 L1 DesignContract 一致，Construction 的写入操作不通过此契约暴露。Ingestion 触发、Pipeline 执行等变更操作通过桥接模式（`construction/contract/bridge.py`）调用 Construction 内部服务：

```
Caller (Application/API)
  → BuildResultContract              # 只读查询
  → ConstructionBridge.trigger_*()   # 写入操作，委托给内部 IngestService / PipelineService
```

## Consequences

### 变得更容易
- +AI Reasoning 层通过 `get_entity_instance` + `get_quality_report` 做跨层一致性校验，无需导入 Construction 内部
- L3 Application 的 OMS 通过 `list_entity_instances` 构建只读缓存，与 Design schema 版本解耦
- 摄入源变更不影响上层，仅 `IngestionSourceView.config_metadata` 字段通过字典灵活承载

### 变得困难/需注意
- View 对象的字段变更需同时更新契约和内部映射逻辑，属有意为之的设计约束
- `confidence_score` 和 `quality_flags` 需 Construction 层在构建时填充，增加了 Pipeline 的输出规范要求
- 关系查询当前仅支持按源实体遍历，后续可能需扩展按目标实体/类型搜索

### 风险与缓解
| 风险 | 等级 | 缓解 |
|------|------|------|
| 内部模型与 View 映射遗漏字段 | 中 | 实现 Bridge 时编写字段级映射测试 |
| 大规模 Instances 分页性能 | 低 | limit/offset 分页，后续可用游标分页替代 |
| `source_tracing` 结构不稳定 | 低 | 通过 `Dict[str, str]` 保持灵活性 |

---

> **父决策**: [ADR-068 本体模块四层分层架构](ADR-068_本体模块四层分层架构.md)
