# Contract: HEAdapter

**Location**: `odap/biz/data/hyper_extract/impl/he_adapter.py`
**Spec FRs**: FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009

## Description

唯一规范 HE 适配器，封装 Hyper-Extract Python API。合并两套重复实现，修复 API kwarg 名和 get_config import bug，补全缺失方法。

## Interface

```python
class HEAdapter:
    """HE 超结构化抽取适配器 — 封装 hyperextract Python API"""

    def __init__(self):
        """初始化 HE 依赖，尝试导入 hyperextract 包。"""

    def is_available(self) -> bool:
        """HE 包是否已安装且可导入。"""

    def parse(self, text: str, template_config: Dict[str, Any]) -> Dict[str, Any]:
        """使用指定模板从文本抽取知识。

        Args:
            text: 输入文本
            template_config: 模板配置 dict，含 name 或 template_path

        Returns:
            {"entities": [...], "relations": [...]} 或 {"status": "error", "message": "..."}

        Raises:
            RuntimeError: HE 不可用时抛出（禁止静默 fallback）

        Implementation:
            - Template.create(source, language, llm_client=, embedder=)
            - ka.parse(text) → 访问 .nodes/.edges → _normalize_result()
        """

    def parse_batch(self, texts: List[str], template_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """批量抽取，对每个文本独立 parse，单文本失败不阻断其他。"""

    def feed_text(self, ka_instance: Any, new_text: str) -> Dict[str, Any]:
        """增量抽取：在已有 AutoType 实例上追加新文本。

        Args:
            ka_instance: HE BaseAutoType 实例（从 parse 获得）
            new_text: 新增文本

        Returns:
            更新后的结果 dict

        Note:
            HE 原生 API 是 BaseAutoType.feed_text(text)，修改当前实例并返回 self。
            spec 中的 evolve() 修正为 feed_text()（research.md RQ-6 确认）。
        """

    def merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并多个抽取结果。

        Note:
            HE 无原生图合并 API（research.md RQ-1 确认）。
            手工去重：实体按 name 去重（保留首次），关系按 (source, type, target) 三元组去重。
            冲突（name 相同但属性不同）标记到结果 conflicts 字段。
        """

    def trial_extract(self, text: str, template_config: Dict[str, Any], sample_size: int = 1500) -> Dict[str, Any]:
        """试抽取：取文本前 sample_size 字符试抽，返回评分所需指标。

        Returns:
            {
                "entity_count": int,
                "relation_count": int,
                "field_coverage": float,   # 0-1
                "type_diversity": float,   # 0-1
                "types_found": [str],      # 发现的实体类型列表
            }
        """
```

## Dependencies

- `from hyperextract import Template, AutoGraph`
- `from hyperextract.utils.client import create_llm, create_embedder`
- `from odap.infra.config_composer import get_config` (修复 bug)

## Key Corrections from Spec

| Spec 原文 | 修正 |
|-----------|------|
| `evolve()` → `BaseAutoType.evolve()` | `feed_text()` → `BaseAutoType.feed_text()` |
| `dump_dict()` | 不存在，直接访问 `.nodes`/`.edges` |
| "HE 原生合并 API" | HE 无原生图合并，手工去重 |
| `from odap.infra.config import get_config` | `from odap.infra.config_composer import get_config` |
