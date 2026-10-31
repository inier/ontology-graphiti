"""F7 意图评测入口（SPEC-v2 AC-32 ~ AC-35）。

指标口径（写死，避免"调数据好看"）：
- `Intent-Acc@1`     = 意图预测正确的用例占比（全体）
- `Slot-F1`          = 期望术语集 vs L1 命中术语集的 micro-F1
                       （分类标签是"应被 ground 的槽位"，未命中即 fn；干扰项多命中即 fp）
- `Gen-Gap`          = Acc@1(同义改写) − Acc@1(跨域迁移)；跨域用例按"目标域已覆盖时应得的
                       意图"标注，因此 L1 词典未覆盖的域词会真实体现在这个差值上（AC-34）
- `Clarify-Rate`     = 返回 `unknown`（走澄清）的占比
- `Unmapped-Rate`    = 期望术语中未被命中的占比，用于驱动本体补全（AC-35）

门禁模式：
- `baseline`（默认，CI 回归用）：任一指标准劣于基线超过 `--tolerance` 即失败；
- `acceptance`（验收用）：`--min-acc/--min-slot-f1/--max-gen-gap` 绝对阈值，AC-33/34 原文口径。

用法：
    python scripts/eval_intent.py                      # 回归模式
    python scripts/eval_intent.py --mode acceptance    # 对照 AC-33/AC-34
    python scripts/eval_intent.py --update-baseline    # 重写基线（需代码评审说明原因）
    python scripts/eval_intent.py --json out.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "apps" / "api" / "tests" / "eval" / "intent"
DEFAULT_CASES = EVAL_DIR / "cases.json"
DEFAULT_TERMS = EVAL_DIR / "usl_terms.json"
DEFAULT_BASELINE = EVAL_DIR / "baseline.json"

#: 基线回归比较的容差（指标单位均为 0~1）
DEFAULT_TOLERANCE = 0.02
_LOWER_IS_BETTER = {"gen_gap", "unmapped_rate"}


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"[ERROR] 文件不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _build_router(terms_path: Path, layer: str = "full"):
    from odap.biz.core.ontology.orchestration.impl.intent_router import (
        L1IntentRouter,
        UslDictionary,
    )

    terms = _load_json(terms_path).get("terms", [])
    return L1IntentRouter(dictionary=UslDictionary(loader=lambda: list(terms)), layers=layer)


async def _predict(router, cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    predictions = []
    for case in cases:
        frame = await router.route(case["query"], {"sub": "eval-runner"}, "ws-eval")
        predictions.append({
            "id": case["id"],
            "intent_type": frame.intent_type,
            "confidence": frame.confidence,
            "terms": list(frame.slots.get("terms") or []),
        })
    return predictions


def _slot_scores(cases: List[Dict[str, Any]],
                 predictions: List[Dict[str, Any]]) -> Tuple[float, float, float, float]:
    """返回 (precision, recall, f1, unmapped_rate)，micro 口径。"""
    tp = fp = fn = 0
    for case, pred in zip(cases, predictions):
        expected = set(case.get("expected_terms") or [])
        actual = set(pred["terms"])
        hit = expected & actual
        tp += len(hit)
        fp += len(actual - expected)
        fn += len(expected - actual)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    unmapped = fn / (tp + fn) if (tp + fn) else 0.0
    return precision, recall, f1, unmapped


def compute_metrics(cases: List[Dict[str, Any]],
                    predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(cases)
    per_category: Dict[str, Dict[str, int]] = {}
    clarify = 0
    correct = 0
    for case, pred in zip(cases, predictions):
        category = case["category"]
        bucket = per_category.setdefault(category, {"total": 0, "correct": 0})
        bucket["total"] += 1
        if pred["intent_type"] == "unknown":
            clarify += 1
        if pred["intent_type"] == case["expected_intent"]:
            bucket["correct"] += 1
            correct += 1
    precision, recall, f1, unmapped = _slot_scores(cases, predictions)
    acc_by_category = {
        name: (bucket["correct"] / bucket["total"] if bucket["total"] else 0.0)
        for name, bucket in per_category.items()
    }
    return {
        "total": total,
        "intent_acc_at_1": correct / total if total else 0.0,
        "slot_precision": precision,
        "slot_recall": recall,
        "slot_f1": f1,
        "gen_gap": acc_by_category.get("synonym", 0.0) - acc_by_category.get("cross_domain", 0.0),
        "clarify_rate": clarify / total if total else 0.0,
        "unmapped_rate": unmapped,
        "acc_by_category": acc_by_category,
    }


def _check_baseline(metrics: Dict[str, Any], baseline: Dict[str, Any],
                    tolerance: float) -> List[str]:
    failures: List[str] = []
    for key, base_value in baseline.items():
        if key not in metrics:
            continue
        current = float(metrics[key])
        base = float(base_value)
        worse = (current > base + tolerance) if key in _LOWER_IS_BETTER \
            else (current < base - tolerance)
        if worse:
            direction = "高于" if key in _LOWER_IS_BETTER else "低于"
            failures.append(
                f"{key} {direction}基线：当前 {current:.4f} vs 基线 {base:.4f}"
                f"（容差 {tolerance}）"
            )
    return failures


def _check_acceptance(metrics: Dict[str, Any], args: argparse.Namespace) -> List[str]:
    failures: List[str] = []
    if metrics["intent_acc_at_1"] < args.min_acc:
        failures.append(
            f"AC-33 未达标：Intent-Acc@1 {metrics['intent_acc_at_1']:.4f} < {args.min_acc}"
        )
    if metrics["slot_f1"] < args.min_slot_f1:
        failures.append(
            f"AC-33 未达标：Slot-F1 {metrics['slot_f1']:.4f} < {args.min_slot_f1}"
        )
    if metrics["gen_gap"] > args.max_gen_gap:
        failures.append(
            f"AC-34 未达标：Gen-Gap {metrics['gen_gap']:.4f} > {args.max_gen_gap}"
        )
    return failures


def _print_report(metrics: Dict[str, Any], counts: Dict[str, int], layer: str) -> None:
    layer_label = {
        "l1": "L1 词典精确匹配",
        "l2": "L1 词典 + L2 语义召回（形态/模糊）",
        "full": "L1 + L2 + L3 受限消歧（完整漏斗）",
    }.get(layer, layer)
    print("─" * 62)
    print(f"F7 意图评测（{layer_label}）")
    print("─" * 62)
    print(f"用例：合计 {metrics['total']}  "
          f"(同义 {counts.get('synonym', 0)} / 跨域 {counts.get('cross_domain', 0)} / "
          f"复合 {counts.get('composite', 0)} / 干扰 {counts.get('distractor', 0)})")
    print()
    print(f"Intent-Acc@1   {metrics['intent_acc_at_1']:.4f}   (AC-33 目标 ≥ 0.90)")
    print(f"Slot-F1        {metrics['slot_f1']:.4f}   "
          f"(P {metrics['slot_precision']:.4f} / R {metrics['slot_recall']:.4f} / AC-33 目标 ≥ 0.85)")
    print(f"Gen-Gap        {metrics['gen_gap']:.4f}   (AC-34 目标 ≤ 0.10)")
    print(f"Clarify-Rate   {metrics['clarify_rate']:.4f}")
    print(f"Unmapped-Rate  {metrics['unmapped_rate']:.4f}   (AC-35，驱动本体补全)")
    print()
    print("分类准确率：")
    for name, value in sorted(metrics["acc_by_category"].items()):
        print(f"  {name:<14} {value:.4f}")
    print("─" * 62)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="F7 意图评测集运行器（AC-32~AC-35）")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--terms", default=str(DEFAULT_TERMS))
    parser.add_argument("--mode", choices=["baseline", "acceptance"], default="baseline")
    parser.add_argument("--layer", choices=["l1", "l2", "full"], default="full",
                        help="分层度量：l1 只跑词典、l2 加语义召回、full 含 L3 与模糊兜底")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--min-acc", type=float, default=0.90)
    parser.add_argument("--min-slot-f1", type=float, default=0.85)
    parser.add_argument("--max-gen-gap", type=float, default=0.10)
    parser.add_argument("--json", default=None, help="把完整结果写入指定 JSON 文件")
    args = parser.parse_args(argv)

    payload = _load_json(Path(args.cases))
    cases = payload.get("cases") or []
    counts = payload.get("counts") or {}
    if not cases:
        print(f"[ERROR] 用例集为空：{args.cases}")
        return 2

    router = _build_router(Path(args.terms), layer=args.layer)
    predictions = asyncio.run(_predict(router, cases))
    metrics = compute_metrics(cases, predictions)

    _print_report(metrics, counts, args.layer)

    failures: List[str] = []
    if args.update_baseline:
        baseline_values = {k: metrics[k] for k in _LOWER_IS_BETTER | {"intent_acc_at_1", "slot_f1"}}
        Path(args.baseline).write_text(
            json.dumps(baseline_values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"[OK] 基线已更新：{args.baseline}")
    elif args.mode == "acceptance":
        failures = _check_acceptance(metrics, args)
    else:
        baseline_path = Path(args.baseline)
        if not baseline_path.is_file():
            print(f"[WARN] 基线文件不存在（{baseline_path}），跳过回归门禁；"
                  f"用 --update-baseline 生成。")
        else:
            failures = _check_baseline(metrics, _load_json(baseline_path), args.tolerance)

    if args.json:
        Path(args.json).write_text(
            json.dumps({"counts": counts, "metrics": metrics,
                        "mode": args.mode, "failures": failures},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[OK] 结果已写入：{args.json}")

    if failures:
        print()
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print(f"[PASS] 门禁通过（mode={args.mode}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
