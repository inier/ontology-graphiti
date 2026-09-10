"""Step 1: 实体标准化 — 去重、同义词合并、链接已有实体"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NormalizationResult:
    entities: List[Dict[str, Any]] = field(default_factory=list)
    merge_count: int = 0
    link_count: int = 0
    original_count: int = 0
    decisions: List[Dict[str, Any]] = field(default_factory=list)

    def get_stats(self) -> dict:
        return {
            "original_count": self.original_count,
            "normalized_count": len(self.entities),
            "merge_count": self.merge_count,
            "link_count": self.link_count,
            "dedup_rate": 1 - (len(self.entities) / max(self.original_count, 1)),
        }


class NormalizationStep:
    """实体标准化处理器"""

    async def execute(
        self,
        entities: List[Dict],
        ontology_id: str = "",
        workspace_id: str = "default",
    ) -> NormalizationResult:
        result = NormalizationResult(original_count=len(entities))

        if not entities:
            return result

        # 1. 名称规范化: 去除前后空格、统一全角/半角
        for e in entities:
            name = e.get("name", e.get("entity_name", ""))
            if name:
                e["original_name"] = name
                e["name"] = name.strip().replace("\u3000", " ")

        # 2. 同义词合并: 按名称分组，同名的合并
        name_groups: Dict[str, List[Dict]] = {}
        for e in entities:
            name = e.get("name", "")
            key = name.lower()
            if key not in name_groups:
                name_groups[key] = []
            name_groups[key].append(e)

        merged = []
        for entries in name_groups.values():
            if len(entries) == 1:
                merged.append(entries[0])
            else:
                # 合并同名实体: 保留第一个，合并属性
                primary = entries[0]
                for dup in entries[1:]:
                    # span schema 冻结：merge 阶段是 chunk_id/source_doc_ids 的历史丢失点
                    # （结论文档"质量有点无链"）。必须**先**基于合并前的 primary 计算溯源并集，
                    # 再执行下面的盲 update——否则 primary 的 source_doc_id 会被 dup 覆盖后
                    # 才参与合并，导致 doc 归属永久丢失。source_doc_ids 求并集，其余冻结标量
                    # 取 primary 优先、缺失回退 dup，最后盖在 properties 之上（溯源键胜出）。
                    try:
                        from odap.biz.core.ontology.construction.provenance.provenance_schema import (
                            merge_provenance,
                        )
                        prov = merge_provenance(primary, dup)
                    except Exception as e:  # noqa: BLE001 — 溯源合并失败不阻断标准化
                        prov = {}
                        logger.warning(
                            "Normalization: provenance merge failed for name=%s: %s",
                            primary.get("name", ""), e,
                        )
                    primary.setdefault("properties", {}).update(dup.get("properties", {}))
                    if prov:
                        primary["properties"].update(prov)
                merged.append(primary)
                result.merge_count += len(entries) - 1
                result.decisions.append({
                    "type": "merge",
                    "name": primary.get("name", ""),
                    "count": len(entries),
                })

        result.entities = merged

        # 3. 去重: 基于 id 去重
        seen_ids = set()
        deduped = []
        for e in merged:
            eid = e.get("id", e.get("entity_id", str(id(e))))
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            deduped.append(e)

        result.entities = deduped
        logger.info(
            "Normalization: %d → %d entities (merged=%d, deduped=%d)",
            result.original_count,
            len(result.entities),
            result.merge_count,
            result.original_count - len(deduped),
        )
        return result
