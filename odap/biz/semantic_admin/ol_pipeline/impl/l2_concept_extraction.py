"""L2 概念归并实现。

Protocol: L2ConceptExtractor.merge()

责任：
  1. 相同 surface 合并（frequency 累加，保留高置信度）
  2. 包含性归并：如 "孙悟空三打" 内含 "悟空"，如果前者已提，则后者若 frequency<前者1/3，归为同义词（避免"孙悟空/悟空/孙行者"被分裂成3个独立候选）
  3. 与 existing_usl_terms 去重：已在 USL 中的规范术语+同义词直接跳过，不重复产出
  4. 低置信度过滤：< min_confidence 的丢弃
  5. canonical 选择：出现频率最高的 surface（作为规范术语）
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple


class ConceptMergeEngine:
    """L2 归并引擎。实现 Protocol L2ConceptExtractor。"""

    def merge(
        self,
        tokens,  # List[RawToken]
        *,
        existing_usl_terms: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):  # -> List[ConceptCandidate]
        cfg = config or {}
        min_confidence = float(cfg.get("min_confidence", 0.15))
        syn_similarity_threshold = float(cfg.get("syn_similarity", 0.88))  # difflib ratio
        max_syn_per_canonical = int(cfg.get("max_syn_per_canonical", 12))

        # Step 0: 过滤低置信 + 归一
        tokens = [
            t for t in tokens
            if float(t.get("confidence") or 0.0) >= min_confidence
        ]
        tokens.sort(key=lambda t: t.get("frequency", 0), reverse=True)

        # Step 1: 去重 existing USL 术语（surface命中 规范术语或同义词之一就不产出）
        if existing_usl_terms:
            usl_surfaces: set = set()
            for t in existing_usl_terms:
                canon = (t.get("canonical") or "").strip()
                if canon:
                    usl_surfaces.add(canon)
                for s in (t.get("synonyms") or []):
                    usl_surfaces.add(s.strip())
            tokens = [t for t in tokens if t["surface"] not in usl_surfaces]

        # Step 2: 相同 surface 合频
        merged_map: Dict[str, Dict[str, Any]] = {}
        for t in tokens:
            surf = t["surface"]
            if surf in merged_map:
                merged_map[surf]["frequency"] += int(t.get("frequency") or 1)
                merged_map[surf]["confidence"] = max(
                    merged_map[surf]["confidence"], float(t.get("confidence") or 0.0)
                )
                # 追加示例上下文（去重）
                ctx = t.get("provenance") or {}
                for s in ctx.get("sample_contexts", []):
                    if s not in merged_map[surf]["_contexts"]:
                        merged_map[surf]["_contexts"].append(s)
            else:
                merged_map[surf] = {
                    "surface": surf,
                    "frequency": int(t.get("frequency") or 1),
                    "confidence": float(t.get("confidence") or 0.0),
                    "source_text": t.get("source_text") or "",
                    "_contexts": list((t.get("provenance") or {}).get("sample_contexts", [])),
                }

        # Step 3: 包含+相似度归并
        items = sorted(
            merged_map.values(),
            key=lambda x: (-x["frequency"], -len(x["surface"]), x["surface"]),
        )

        results: List[Dict[str, Any]] = []  # canonical -> {synonyms, near_synonyms, ...}
        used: set = set()
        for base in items:
            canon = base["surface"]
            if canon in used:
                continue
            used.add(canon)
            synonyms: List[str] = []
            near_synonyms: List[str] = []
            freq_sum = int(base["frequency"])
            conf_max = float(base["confidence"])
            sample_ctx = list(base["_contexts"])

            for other in items:
                surf2 = other["surface"]
                if surf2 == canon or surf2 in used:
                    continue
                is_sub = (canon in surf2) or (surf2 in canon)
                if is_sub:
                    # 包含：作为 near_synonyms（避免"刘备之墓"/"刘备"强合为同义词）
                    if int(other["frequency"]) >= 1:
                        near_synonyms.append(surf2)
                        used.add(surf2)
                        freq_sum += int(other["frequency"])
                        conf_max = max(conf_max, float(other["confidence"]))
                        for s in other["_contexts"]:
                            if s not in sample_ctx:
                                sample_ctx.append(s)
                    continue
                # 字符串相似度（difflib）
                ratio = SequenceMatcher(None, canon, surf2).ratio()
                if ratio >= syn_similarity_threshold:
                    synonyms.append(surf2)
                    used.add(surf2)
                    freq_sum += int(other["frequency"])
                    conf_max = max(conf_max, float(other["confidence"]))
                    for s in other["_contexts"]:
                        if s not in sample_ctx:
                            sample_ctx.append(s)
                elif ratio >= syn_similarity_threshold - 0.08:
                    near_synonyms.append(surf2)

            if len(synonyms) > max_syn_per_canonical:
                # 保留频率最高的前 N 个（先按频率近似排序，没有就不管）
                synonyms = synonyms[:max_syn_per_canonical]
            if len(near_synonyms) > max_syn_per_canonical:
                near_synonyms = near_synonyms[:max_syn_per_canonical]

            # 综合置信度：conf_max * len_boost * 频数占比对数衰减
            total_ref = max(sum(x["frequency"] for x in items), 1)
            freq_boost = min(1.0, 0.5 + 0.5 * (freq_sum / max(total_ref * 0.01, 1)))
            final_conf = round(min(conf_max * (0.8 + 0.2 * freq_boost), 0.995), 4)
            results.append({
                "canonical": canon,
                "synonyms": sorted(set(synonyms)),
                "near_synonyms": sorted(set(near_synonyms)),
                "aliases": [],
                "frequency": freq_sum,
                "confidence": final_conf,
                "source_text": base["source_text"],
                "provenance": {
                    "sample_contexts": sample_ctx[:8],
                    "l2_merge_strategy": "include + difflib",
                },
            })

        results.sort(key=lambda c: (-c["frequency"], -c["confidence"]))
        return results
