"""L5 模式归纳（基数估计 + 不相交草图，纯统计，零新依赖）。

只在 relation_candidates 上「打标 provenance」，不新增/删除候选行，
保证后续 pipeline 流程对 L5 完全是透明的。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


class RuleBasedPatternInferrer:
    """基于统计的模式归纳器（Approach A 精简版，<=200 LOC）。

    对每个关系候选 provenance 注入：
      - L5_cardinality_estimate: {rel_type, min_card, max_card}
      - L5_disjoint_draft_candidates: List[关系对 canonical_key]
    """

    def infer(
        self,
        *,
        relation_candidates: List[Dict[str, Any]],
        entity_candidates: Optional[List[Dict[str, Any]]] = None,
        **_: Any,
    ) -> List[Dict[str, Any]]:
        """返回修改后的 relation_candidates（不丢原 list；in-place 注入。"""
        # 1. 按 (subject, relation_phrase) 聚合 objects
        #    注意：用 provenance 里的 subject/object/phrase，避免 canonical key 被拼接影响
        sp_objs: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        #    额外保留 key: relation canonical -> 聚合 group 的 (s, p) 映射
        rel_to_group: Dict[str, Tuple[str, str]] = {}
        #    subject -> List[(p, canonical_key)] 集合（用于 disjoint 检测）
        subj_rel_pairs: Dict[str, List[Tuple[str, str, Set[str]]]] = defaultdict(list)

        for rc in relation_candidates or []:
            prov = rc.get("provenance") or {}
            s = str(prov.get("subject_canonical") or "")
            p = str(prov.get("relation_phrase") or "")
            o = str(prov.get("object_canonical") or "")
            if not s or not p or not o:
                continue
            sp_objs[(s, p)].add(o)
            key = str(rc.get("canonical") or f"{s}_{p}_{o}")
            rel_to_group[key] = (s, p)

        # 构造 (s, p) -> (canonical_keys 列表, objs 集合)
        sp_to_info: Dict[Tuple[str, str], Tuple[List[str], Set[str]]] = defaultdict(
            lambda: ([], set())
        )
        for rc in relation_candidates or []:
            key = str(rc.get("canonical") or "")
            grp = rel_to_group.get(key)
            if not grp:
                continue
            s, p = grp
            sp_to_info[grp][0].append(key)
            objs = sp_to_info[grp][1]
            objs.update(sp_objs[grp])

        # 2. 计算 cardinality estimate（组级 -> 拷贝到该组每条关系）
        cardinality_map: Dict[str, Dict[str, Any]] = {}
        for (s, p), (keys, objs) in sp_to_info.items():
            n = len(set(objs))
            if n == 0:
                card: Dict[str, Any] = {
                    "rel_type": "1:1", "min_card": 0, "max_card": 1,
                }
            elif n == 1:
                card = {"rel_type": "1:1", "min_card": 1, "max_card": 1}
            elif 1 < n <= 5:
                card = {"rel_type": "1:N", "min_card": 1, "max_card": n}
            else:
                card = {"rel_type": "1:N", "min_card": 1, "max_card": None}
            card["distinct_object_count"] = n
            for k in keys:
                cardinality_map[k] = card

        # 3. 同 subject 下的两两关系做不相交草图（objects 完全不相交）
        #    先按 subject 聚合关系
        subj_groups: Dict[str, List[Tuple[str, str, Set[str]]]] = defaultdict(list)
        for (s, p), (keys, objs) in sp_to_info.items():
            # 取该组第一个 canonical_key 作为代表（避免同一 (s,p) 下多条自比较）
            if keys:
                subj_groups[s].append((p, keys[0], objs))

        disjoint_pairs: Dict[str, Set[str]] = defaultdict(set)
        for _subj, rels in subj_groups.items():
            for i in range(len(rels)):
                _, ki, obji = rels[i]
                for j in range(i + 1, len(rels)):
                    _, kj, objj = rels[j]
                    if not obji or not objj:
                        continue
                    if obji.isdisjoint(objj):
                        disjoint_pairs[ki].add(kj)
                        disjoint_pairs[kj].add(ki)

        # 4. 注入 provenance（in-place 修改）
        for rc in relation_candidates or []:
            key = str(rc.get("canonical") or "")
            prov = rc.get("provenance")
            if not isinstance(prov, dict):
                prov = {}
                rc["provenance"] = prov
            card = cardinality_map.get(key)
            if card:
                prov["L5_cardinality_estimate"] = card
            dj = sorted(disjoint_pairs.get(key, ()))
            if dj:
                prov["L5_disjoint_draft_candidates"] = dj

        return relation_candidates if relation_candidates is not None else []
