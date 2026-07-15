# Data Model: Hyper-Extract 启用 + 抽取校验完整链路

**Date**: 2026-07-11
**Feature**: 006-he-extraction-chain

## New Entities

### HETemplate (SQLite: he_templates)

Hyper-Extract 模板元数据，记录已沉淀的自定义/本体生成模板供复用。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | UUID |
| ontology_id | TEXT | NOT NULL | 关联本体 ID |
| name | TEXT | NOT NULL | 模板名称 (如 `custom_ecommerce_v1`) |
| description | TEXT | | 模板描述 |
| source | TEXT | NOT NULL | 来源: `preset` / `ontology_generated` / `custom` |
| yaml_path | TEXT | NOT NULL | YAML 文件路径 (如 `data/he_templates/{ontology_id}/{name}.yaml`) |
| preset_name | TEXT | | 基础预设名 (如 `general/base_graph`)，source=preset 时有值 |
| score | REAL | | 试抽评分 (0-1) |
| coverage | TEXT | | 覆盖类别 JSON (如 `["object","relation","action"]`) |
| usage_count | INTEGER | DEFAULT 0 | 复用次数 |
| created_at | TEXT | NOT NULL | ISO 时间戳 (UTC) |
| updated_at | TEXT | NOT NULL | ISO 时间戳 (UTC) |

**约束**: `UNIQUE(ontology_id, name)` — 同一本体下模板名唯一，防止并发生成重复

**索引**: `idx_he_templates_ontology` ON `ontology_id`

### ValidationReport (JSON, 嵌入 ExtractionSession.result_data)

4 维校验报告，抽取完成后生成，嵌入 session 的 result_data 字段。

```python
{
    "schema_conformance": {
        "violations": [
            {"entity": "客户", "field": "age", "issue": "type_mismatch", "expected": "INTEGER", "actual": "str"},
            {"entity": "订单", "field": "amount", "issue": "required_missing"},
        ],
        "passed_count": 12,
        "violated_count": 2,
    },
    "completeness": {
        "fill_rate": 0.85,        # 必填字段填充率
        "empty_rate": 0.15,       # 空值率
        "orphan_count": 3,        # 孤立节点数
        "orphan_entities": ["产品X", "服务Y", "部门Z"],
    },
    "confidence": {
        "threshold": 0.6,
        "scores": [
            {"entity": "客户", "score": 0.92, "components": {"fill": 0.9, "template": 0.95, "llm": 0.9}},
            {"entity": "订单", "score": 0.45, "components": {"fill": 0.5, "template": 0.4, "llm": 0.45}},
        ],
        "needs_review": ["订单"],  # 低于阈值的实体名列表
    },
    "referential_consistency": {
        "dangling_relations": [
            {"source": "客户A", "target": "不存在B", "type": "owns"},
        ],
        "invalid_action_targets": [
            {"action": "发货", "target_type": "未定义类型"},
        ],
        "invalid_rule_references": [],
    },
    "summary": {
        "total_entities": 15,
        "total_relations": 8,
        "needs_review_count": 1,
        "overall_status": "needs_review",  # passed / needs_review / failed
    }
}
```

### TemplateAssessment (JSON, 嵌入 ExtractionSession.result_data)

模板评估结果，记录候选列表、评分、试抽详情。

```python
{
    "sample_size": 1500,           # 试抽样本字符数
    "candidates": [
        {
            "name": "general/base_graph",
            "description": "通用知识图谱",
            "source": "preset",
            "trial_result": {
                "entity_count": 5,
                "relation_count": 3,
                "field_coverage": 0.8,
                "type_diversity": 0.6,
            },
            "score": 0.72,
        },
        # ... more candidates
    ],
    "selected_templates": [         # select_complementary 选出的多模板组合
        {"name": "general/base_graph", "covers": ["object", "relation"]},
        {"name": "industry/operation_flow", "covers": ["action", "process"]},
    ],
    "custom_generated": None,       # 若触发了自定义生成，记录生成详情
    "settled_template_id": None,    # 若复用了已沉淀模板，记录模板 ID
    "degradation_flags": [],        # 降级标记
}
```

## Enhanced Entities

### ExtractionSession (现有, 增强)

现有 ExtractionSession 通过 OntologyService.create_extraction_session 管理，存储在 SQLite。增强字段嵌入 `result_data` JSON:

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| result_data.validation_report | JSON | ValidationReport 对象 |
| result_data.template_assessment | JSON | TemplateAssessment 对象 |
| result_data.degradation_flags | `[str]` | 降级标记列表 (如 `["template_below_threshold"]`) |

**注意**: 不修改 ExtractionSession 表结构，增强字段存储在现有 `result_data` JSON 列中。

### ExtractionProvenance (现有, 增强)

现有 extraction_provenance 表新增字段:

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| source_template | TEXT | 来源模板名 (如 `general/base_graph` 或 `custom_ecommerce_v1`) |

**迁移**: `ALTER TABLE extraction_provenance ADD COLUMN source_template TEXT;`

## SQLite Table DDL

### he_templates (新建)

```sql
CREATE TABLE IF NOT EXISTS he_templates (
    id TEXT PRIMARY KEY,
    ontology_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    source TEXT NOT NULL,          -- preset / ontology_generated / custom
    yaml_path TEXT NOT NULL,
    preset_name TEXT,
    score REAL,
    coverage TEXT,                 -- JSON array
    usage_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(ontology_id, name)
);

CREATE INDEX IF NOT EXISTS idx_he_templates_ontology ON he_templates(ontology_id);
```

### extraction_provenance (增强)

```sql
-- 新增列（迁移时执行）
ALTER TABLE extraction_provenance ADD COLUMN source_template TEXT;
```

## State Transitions

### ExtractionSession 状态机 (现有, 无变化)

```
pending → extracting → reviewing → completed
                    ↘ failed
```

**新增逻辑**: `reviewing` 状态时检查 `validation_report.summary.overall_status`:
- `passed` → 允许直接 confirm
- `needs_review` → 要求用户逐项确认 needs_review 实体后才允许 confirm
- `failed` → 标记错误，仍允许 confirm 但提示"未校验"

### HETemplate 生命周期

```
[试抽评分] → score ≥ 阈值 → settle_template() → [沉淀]
                                              ↓
                                        get_settled_template() → [复用]
                                              ↓
                                        轻量验证 < 阈值80% → [重新评估]
```
