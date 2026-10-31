"""F7 意图评测集生成器（AC-32）。

产物 `cases.json` 由本脚本确定性生成（无随机、可复现），四类各 ≥100：
    synonym      同义改写      —— 同一指标的不同说法（词典应命中）
    cross_domain 跨域迁移      —— 换业务域表述（含 USL 未覆盖的域词）
    composite    复合意图      —— 一句话含多个意图（主句 + 附加诉求）
    distractor   干扰项        —— 域外问题或域内近似但无术语可命中

标注口径（写死，避免被实现反向污染）：
- `expected_intent` 是**产品语义上正确答案**应得的意图，不由 L1 词典反推；
  跨域用例按"目标域已覆盖时应得的意图"标注 —— 这样才能度量泛化缺口（AC-34）；
  干扰项按"应当澄清"标注为 `unknown`。
- `expected_terms` 是构造该 query 时实际使用的 USL 表面形式（指标 + 可选对象），
  由生成器显式记录，与 IntentRouter 的匹配算法无关。

词表与模板见 `case_templates.py`。用法：
    python apps/api/tests/eval/intent/build_cases.py
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path
from typing import Dict, List

from case_templates import (
    ACTIONS,
    CHANNELS,
    COMPOSITE_TAILS,
    COVERED_CROSS_TEMPLATES,
    CROSS_TEMPLATES,
    DOMAINS,
    METRIC_SURFACES,
    NEAR_MISS,
    OBJECTS,
    OUT_OF_SCOPE,
    PROCESSES,
    PROPERTIES,
    REGIONS,
    RULES,
    SYN_TEMPLATES,
    TIMES,
    UNSEEN_DOMAIN_TERMS,
    make_case,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "cases.json"


# ── 1. 同义改写 ──────────────────────────────────────────────────────────────
def build_synonym(limit: int = 210) -> List[Dict[str, object]]:
    """每个指标表面形式均摊配额，避免整类用例挤在同一个词上（否则指标会虚高）。"""
    out: List[Dict[str, object]] = []
    seen = set()
    per_surface = limit // len(METRIC_SURFACES) + 1
    for _canonical, surf, intent in METRIC_SURFACES:
        made = 0
        for t, r, c, tpl in product(TIMES, REGIONS, CHANNELS, SYN_TEMPLATES):
            query = tpl.format(t=t, r=r, c=c, s=surf)
            if query in seen:
                continue
            seen.add(query)
            out.append(make_case(f"syn-{len(out) + 1:04d}", "synonym", query, intent, [surf]))
            made += 1
            if made >= per_surface:
                break
    return out[:limit]


# ── 2. 跨域迁移 ──────────────────────────────────────────────────────────────
def build_cross_domain(unseen_limit: int = 80,
                       covered_limit: int = 30) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    seen = set()

    per_term = unseen_limit // len(UNSEEN_DOMAIN_TERMS) + 1
    for term, intent in UNSEEN_DOMAIN_TERMS:
        made = 0
        for d, t, tpl in product(DOMAINS, TIMES, CROSS_TEMPLATES):
            query = tpl.format(d=d, t=t, s=term)
            if query in seen:
                continue
            seen.add(query)
            # 该域词是"本应被本体覆盖"的槽位 → 计入 expected_terms，
            # 未命中会体现在 Unmapped-Rate（AC-35，驱动本体补全）
            out.append(make_case(f"xdm-{len(out) + 1:04d}", "cross_domain", query, intent,
                                 [term]))
            made += 1
            if made >= per_term:
                break
    out = out[:unseen_limit]

    covered: List[Dict[str, object]] = []
    per_surface = covered_limit // len(METRIC_SURFACES) + 1
    for _canonical, surf, intent in METRIC_SURFACES:
        made = 0
        for d, t, tpl in product(DOMAINS, TIMES, COVERED_CROSS_TEMPLATES):
            query = tpl.format(d=d, t=t, s=surf, c="")
            if query in seen:
                continue
            seen.add(query)
            covered.append(make_case(f"xdm-{unseen_limit + len(covered) + 1:04d}",
                                     "cross_domain", query, intent, [surf]))
            made += 1
            if made >= per_surface:
                break
    return out + covered[:covered_limit]


# ── 3. 复合意图 ──────────────────────────────────────────────────────────────
def build_composite(limit: int = 110) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    seen = set()
    per_surface = limit // len(METRIC_SURFACES) + 1
    for surf, intent in [(s, i) for _c, s, i in METRIC_SURFACES]:
        made = 0
        for t, (joiner, tail_tpl, is_action) in product(TIMES, COMPOSITE_TAILS):
            _a, a_surfaces = ACTIONS[len(out) % len(ACTIONS)]
            _o, o_surfaces = OBJECTS[len(out) % len(OBJECTS)]
            _p, p_surfaces = PROPERTIES[len(out) % len(PROPERTIES)]
            _pr, pr_surfaces = PROCESSES[len(out) % len(PROCESSES)]
            _ru, ru_surfaces = RULES[len(out) % len(RULES)]
            tail = tail_tpl.format(
                a=a_surfaces[0], o=o_surfaces[0], p=p_surfaces[0],
                pr=pr_surfaces[0], ru=ru_surfaces[0],
            )
            query = f"{t}{surf}是多少，{joiner}{tail}"
            if query in seen:
                continue
            seen.add(query)
            # 主句意图：动作类附加诉求会让 L1 误判为 action_request（这正是要测的）
            terms = [surf] + ([a_surfaces[0]] if is_action else [])
            out.append(make_case(f"cmp-{len(out) + 1:04d}", "composite", query, intent, terms))
            made += 1
            if made >= per_surface:
                break
    return out[:limit]


# ── 4. 干扰项 ────────────────────────────────────────────────────────────────
def build_distractor(limit: int = 110) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    seen = set()
    modifiers = ["", "麻烦问一下，", "请问一下，", "帮我确认下：", "想问下"]
    for base, prefix in product(OUT_OF_SCOPE + NEAR_MISS, modifiers):
        query = f"{prefix}{base}"
        if query in seen:
            continue
        seen.add(query)
        out.append(make_case(f"dis-{len(out) + 1:04d}", "distractor", query, "unknown", []))
        if len(out) >= limit:
            return out
    return out


def build_all() -> Dict[str, object]:
    synonym = build_synonym()
    cross = build_cross_domain()
    composite = build_composite()
    distractor = build_distractor()
    cases = synonym + cross + composite + distractor
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise SystemExit("用例 id 重复，生成器有 bug")
    queries = [c["query"] for c in cases]
    dup = {q for q in queries if queries.count(q) > 1}
    if dup:
        raise SystemExit(f"query 重复 {len(dup)} 条，示例：{sorted(dup)[:3]}")
    return {
        "_comment": "由 build_cases.py 确定性生成，勿手改；改动请改生成器后重跑。",
        "version": "2026-10-17",
        "usl_snapshot": "usl_terms.json",
        "counts": {
            "synonym": len(synonym),
            "cross_domain": len(cross),
            "composite": len(composite),
            "distractor": len(distractor),
            "total": len(cases),
        },
        "cases": cases,
    }


def main() -> int:
    payload = build_all()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = payload["counts"]  # type: ignore[index]
    print(f"[OK] 写出 {OUT}")
    print(f"     同义改写 {counts['synonym']} / 跨域 {counts['cross_domain']} / "
          f"复合 {counts['composite']} / 干扰 {counts['distractor']} / 合计 {counts['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
