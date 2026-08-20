"""DatalogEngine — pyDatalog 目标化查询执行器 (ADR-075 §4)。

架构约束（spike 数据强制）：
1. 目标化查询（禁全量演绎）
2. 递归规则 ≤ 5 条且仅受限起点（由调用方保证，此处断言）
3. 结论 ≤ 10k 截断标记 truncated: true
4. 单规则 500ms 超时（futures 包裹）→ hybrid 降级
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .rule_loader import RuleLoader, RuleValidationError

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCLUSIONS = 10_000    # 结论数上限
DEFAULT_RULE_TIMEOUT_MS = 500       # 单规则超时
MAX_RECURSIVE_RULES = 5             # 递归规则数上限


@dataclass
class ReasoningResult:
    """推理结果"""
    goal: str
    rows: List[tuple] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "rows": [list(r) for r in self.rows],
            "truncated": self.truncated,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "error": self.error,
            "metadata": self.metadata,
        }


class DatalogEngine:
    """确定性 Datalog 引擎（pyDatalog 0.17.4 封装）"""

    def __init__(
        self,
        rule_loader: Optional[RuleLoader] = None,
        max_conclusions: int = DEFAULT_MAX_CONCLUSIONS,
        rule_timeout_ms: int = DEFAULT_RULE_TIMEOUT_MS,
    ):
        self._rule_loader = rule_loader or RuleLoader()
        self.max_conclusions = max_conclusions
        self.rule_timeout_ms = rule_timeout_ms
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datalog")
        self._loaded_rules: List[str] = []
        self._loaded_facts: List[str] = []

    # ── 生命周期 ──

    def clear(self) -> None:
        """清空 pyDatalog 全局状态与已记录子句"""
        try:
            from pyDatalog import pyDatalog
            pyDatalog.clear()
        except Exception as e:
            logger.debug("pyDatalog clear failed: %s", e)
        self._loaded_rules = []
        self._loaded_facts = []

    def load_rules(self, rules: List[Dict[str, Any]]) -> int:
        """加载规则（白名单编译 + 递归上限断言）"""
        recursive = [r for r in rules if _is_recursive(r.get("rule_text", ""))]
        if len(recursive) > MAX_RECURSIVE_RULES:
            raise RuleValidationError(
                f"递归规则 {len(recursive)} 条超过上限 {MAX_RECURSIVE_RULES}",
                rule_id="batch",
            )
        clauses = self._rule_loader.compile_many(rules)
        self._loaded_rules.extend(clauses)
        return len(clauses)

    def load_facts(self, facts: Sequence[str]) -> int:
        """记录事实子句（实际 assert 在查询线程重放时执行）"""
        if not facts:
            return 0
        for clause in facts:
            # 提前校验子句可解析，避免查询线程运行时才发现
            _parse_fact_clause(clause)
        self._loaded_facts.extend(facts)
        return len(facts)

    def load_fact_objects(self, fact_objects: Sequence[Any]) -> int:
        """加载 Fact 对象列表（来自 fact_loader）"""
        clauses = [f.to_clause() for f in fact_objects]
        return self.load_facts(clauses)

    # ── 查询 ──

    def ask(self, goal: str, timeout_ms: Optional[int] = None) -> ReasoningResult:
        """目标化查询。

        Args:
            goal: Datalog 查询目标，如 `ancestor("a", X)`
            timeout_ms: 单次查询超时（默认 rule_timeout_ms）

        Returns:
            ReasoningResult（含截断/超时标记）
        """
        import time
        start = time.perf_counter()
        timeout = timeout_ms or self.rule_timeout_ms
        future = self._executor.submit(self._ask_sync, goal)
        try:
            rows = future.result(timeout=timeout / 1000.0)
            truncated = len(rows) > self.max_conclusions
            if truncated:
                rows = rows[: self.max_conclusions]
            elapsed = (time.perf_counter() - start) * 1000.0
            return ReasoningResult(
                goal=goal,
                rows=rows,
                truncated=truncated,
                elapsed_ms=elapsed,
            )
        except FuturesTimeout:
            future.cancel()
            elapsed = (time.perf_counter() - start) * 1000.0
            return ReasoningResult(
                goal=goal,
                rows=[],
                truncated=True,
                elapsed_ms=elapsed,
                error=f"timeout (>{timeout}ms)",
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000.0
            return ReasoningResult(
                goal=goal,
                rows=[],
                elapsed_ms=elapsed,
                error=str(e),
            )

    def _ask_sync(self, goal: str) -> List[tuple]:
        """在查询线程内完整重放规则+事实后执行 ask。

        pyDatalog 谓词定义存储在 thread-local，必须与 ask 同线程，
        故每次查询都重建（clear → load rules → assert facts → ask）。
        """
        from pyDatalog import pyDatalog
        pyDatalog.clear()
        for clause in self._loaded_rules:
            pyDatalog.load(clause)
        for clause in self._loaded_facts:
            pred, args = _parse_fact_clause(clause)
            pyDatalog.assert_fact(pred, *args)
        try:
            answer = pyDatalog.ask(goal)
        except AttributeError as e:
            # 目标谓词未定义 → 视为零推导（空结果），非引擎错误
            if "without definition" in str(e):
                return []
            raise
        if answer is None:
            return []
        rows = getattr(answer, "answers", None)
        if rows is None:
            # 单值查询
            return [(getattr(answer, "value", None),)]
        return [tuple(r) for r in rows]

    def close(self) -> None:
        self._executor.shutdown(wait=False)


def _parse_fact_clause(clause: str) -> tuple:
    """解析事实子句 `pred("a", 1, 2.5)` → (pred, ("a", 1, 2.5))"""
    import ast
    # 提取谓词名
    pred, _, rest = clause.partition("(")
    pred = pred.strip()
    if not rest.endswith(")"):
        raise ValueError(f"非法事实子句: {clause}")
    args_text = rest[:-1].strip()
    if not args_text:
        return pred, ()
    # 用 ast 解析参数（引号/数字字面量）
    parsed = ast.literal_eval(f"({args_text},)")
    return pred, tuple(parsed)


def _is_recursive(rule_text: str) -> bool:
    """检测规则是否递归（head 谓词出现在 body）"""
    head = None
    body_start = False
    for token in _split_rule(rule_text):
        if token == "<=":
            body_start = True
            continue
        if head is None and token not in ("<=", "(", ")", ",", "&"):
            head = token
        elif body_start and token == head:
            return True
    return False


def _split_rule(rule_text: str) -> List[str]:
    """简易分词（仅用于递归检测）"""
    import re
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[()<>=&,]", rule_text)


__all__ = [
    "DatalogEngine", "ReasoningResult",
    "DEFAULT_MAX_CONCLUSIONS", "DEFAULT_RULE_TIMEOUT_MS", "MAX_RECURSIVE_RULES",
]
