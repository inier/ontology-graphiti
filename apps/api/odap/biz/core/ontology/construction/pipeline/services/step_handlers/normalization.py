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
                    primary.setdefault("properties", {}).update(dup.get("properties", {}))
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
