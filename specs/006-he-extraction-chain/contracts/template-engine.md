# Contract: TemplateEngine

> ## ⚠️ 版块清理说明（2026-08-07）
>
> 以下方法已**删除**，HE kb 持久化与复用由 009 spec FR-003 `he feed` 增量演化承担：
> - `settle_template()` — 已删除（原 FR-017）
> - `get_settled_template()` — 已删除（原 FR-018）
> - `SqliteTemplateStorage` 依赖 — 已删除（HE kb 原生管理）
>
> `__init__` 不再接收 `storage: SqliteTemplateStorage` 参数。模板评估时 HE kb 内部已有的知识由 `he feed` 自动复用。
> 详见 `specs/REFACTORING-NOTES.md`。

**Location**: `odap/biz/data/hyper_extract/services/template_engine.py`
**Spec FRs**: FR-011, FR-012, FR-013, FR-014, FR-015, FR-016（~~FR-017, FR-018, FR-019 已删除~~）

## Description

模板引擎：动态枚举预设、试抽评分、贪心集合覆盖选择、自定义生成。**不沉淀**——模板持久化由 009 HE kb `he feed` 承担。

## Interface

```python
class TemplateEngine:
    def __init__(self, he_adapter: HEAdapter, embedder=None):
        self._adapter = he_adapter
        self._embedder = embedder

    def list_presets(self) -> List[Dict[str, Any]]:
        """动态枚举 HE 全部预设模板（30+），禁止硬编码。

        Returns:
            [{"name": "general/base_graph", "description": "通用知识图谱", "type": "graph", "tags": [...], "language": "zh"}, ...]

        Implementation:
            Template.list(filter_by_language="zh") → Dict[str, TemplateCfg]
        """

    def assess(self, text: str, ontology_id: str) -> Dict[str, Any]:
        """模板评估：收集候选 → 预筛选 → 试抽评分 → 排序。

        Returns:
            {
                "candidates": [{"name", "description", "source", "trial_result", "score"}, ...],
                "best_score": float,
                "threshold": 0.5,
                "needs_custom": bool,  # best_score < threshold
            }

        Steps:
            1. list_presets() → embedder 余弦相似度预筛选 top-k=5
            2. 对 top-k 候选 trial_extract 试抽
            3. 按评分公式打分排序

        Note: ~~get_settled_template 短路复用~~ 已删除（Iter 2.1 ADR-074），HE kb 内部知识由 `he feed` 自动复用。
        """

    def select_complementary(self, scored_candidates: List[Dict], ontology_schema: Dict) -> List[Dict]:
        """贪心集合覆盖算法选择多模板组合，覆盖 ODAP 5 类产出。

        Returns:
            [{"name", "covers": ["object", "relation"], "score": float}, ...]

        Algorithm:
            1. 从最高分模板开始
            2. 逐步加入覆盖缺失类别且分数最高的模板
            3. 直到 5 类全覆盖或候选耗尽
        """

    def generate_custom(self, text: str, ontology_schema: Dict, gaps: List[str]) -> Optional[Dict[str, Any]]:
        """LLM 生成自定义 HE YAML 模板。

        Args:
            gaps: 缺失的产出类别列表 (如 ["action", "rule"])

        Returns:
            {"name": "custom_...", "yaml_path": "...", "score": float} 或 None

        Implementation:
            - LLM prompt 包含: 输入文本摘要 + 本体 Schema + 缺失类别 + HE YAML 模板规范
            - 生成后试抽验证质量
            - 失败重试最多 2 次 (FR-016)
        """

    # ~~settle_template()~~ 已删除（原 FR-017，HE kb `he feed` 承担）
    # ~~get_settled_template()~~ 已删除（原 FR-018，HE kb 内部复用）
```

## Scoring Formula (FR-013)

```
score = 0.3 * normalize(entity_count) + 0.3 * normalize(relation_count) + 0.2 * field_coverage + 0.2 * type_diversity
```

- `normalize(count)`: 归一化到 0-1（除以候选中最大 count）
- 阈值默认 0.5，可通过 `he.template_score_threshold` 配置

## Dependencies

- HEAdapter (trial_extract, _create_embedder, _Template.list)
- LLM client (generate_custom)
- Embedder (预筛选余弦相似度)
- ~~SqliteTemplateStorage~~ 已删除（HE kb 原生管理）
