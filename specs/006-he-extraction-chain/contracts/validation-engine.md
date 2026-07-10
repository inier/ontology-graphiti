# Contract: ValidationEngine

**Location**: `odap/biz/data/hyper_extract/services/validation_engine.py`
**Spec FRs**: FR-024, FR-025, FR-026, FR-027, FR-028, FR-029

## Description

4 维校验引擎：Schema 一致性、完整性、置信度评分、引用一致性。

## Interface

```python
class ValidationEngine:
    def __init__(self, confidence_threshold: float = 0.6):
        self._confidence_threshold = confidence_threshold

    def validate(self, result: Dict[str, Any], ontology_schema: Dict[str, Any],
                 template_scores: Dict[str, float]) -> Dict[str, Any]:
        """执行 4 维校验，返回完整校验报告。

        Args:
            result: 抽取结果 (含 object_types, link_types, action_types, rule_types, process_types, entities, relations)
            ontology_schema: 本体 Schema 定义 (含各 type 的 properties 定义)
            template_scores: 各来源模板的评分 (用于置信度的 template_match 维度)

        Returns:
            ValidationReport dict (见 data-model.md)
        """
        return {
            "schema_conformance": self._validate_schema(result, ontology_schema),
            "completeness": self._validate_completeness(result),
            "confidence": self._score_confidence(result, template_scores),
            "referential_consistency": self._validate_references(result, ontology_schema),
            "summary": { ... },
        }

    def _validate_schema(self, result: Dict, schema: Dict) -> Dict:
        """Schema 一致性校验。

        检查:
        - 类型匹配: 实体字段类型 vs ObjectType 定义 (STRING/INTEGER/BOOLEAN/...)
        - 必填字段已填
        - 无未定义字段 (实体有但 ObjectType 没有的字段)

        Returns:
            {"violations": [...], "passed_count": int, "violated_count": int}
        """

    def _validate_completeness(self, result: Dict) -> Dict:
        """完整性评估。

        检查:
        - fill_rate: 必填字段填充率 (已填/应填)
        - empty_rate: 空值率 (空值/总字段)
        - orphan_count: 孤立节点数 (无任何关系的实体)

        Returns:
            {"fill_rate": float, "empty_rate": float, "orphan_count": int, "orphan_entities": [...]}
        """

    def _score_confidence(self, result: Dict, template_scores: Dict) -> Dict:
        """置信度评分。

        每个实体/关系 0-1 分:
        - 字段填充率 0.4 (已填字段数/总字段数)
        - 模板匹配度 0.3 (来源模板的 trial_extract score)
        - LLM 一致性 0.3 (实体名/描述是否与文本语义一致，简化为字段非空率)

        低于阈值(默认0.6)列入 needs_review。

        Returns:
            {"threshold": float, "scores": [...], "needs_review": [...]}
        """

    def _validate_references(self, result: Dict, schema: Dict) -> Dict:
        """引用一致性检查。

        检查:
        - dangling_relations: 关系的 source/target 实体不存在
        - invalid_action_targets: 动作目标类型未在 ObjectType 定义
        - invalid_rule_references: 规则引用的对象未定义

        Returns:
            {"dangling_relations": [...], "invalid_action_targets": [...], "invalid_rule_references": [...]}
        """
```

## Configuration

- `he.confidence_threshold`: 置信度阈值，默认 0.6
- 校验失败不阻断抽取流程（EC-018），结果标记 "validation_skipped"

## Dependencies

- 无外部依赖（纯逻辑）
- 输入: 抽取结果 + 本体 Schema + 模板评分
