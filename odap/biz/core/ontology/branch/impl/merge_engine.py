"""
ThreeWayMergeEngine (T355)

3-way merge 基于 RFC 6902 JSON Patch + RFC 6901 JSON Pointer。

算法:
1. 计算 base→ours 的 patch + base→theirs 的 patch
2. 对两个 patch 取交集（同路径且 op 不同 → 冲突）
3. 应用非冲突修改到 base 的深拷贝得到 merged
4. 返回冲突列表（每个 Conflict.path 是 JSON Pointer）
"""
from __future__ import annotations

import copy
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..interfaces import MergeEngine, MergeResult
from ..models import Conflict, ConflictResolution


def _deep_equal(a: Any, b: Any) -> bool:
    """深比较"""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_deep_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_deep_equal(x, y) for x, y in zip(a, b))
    return a == b


def _json_pointer_escape(token: Any) -> str:
    """RFC 6901: '~' → '~0', '/' → '~1'"""
    return str(token).replace("~", "~0").replace("/", "~1")


def _build_path(prefix: str, token: Any) -> str:
    """拼接 JSON Pointer 路径"""
    return f"{prefix}/{_json_pointer_escape(token)}"


def _compute_dict_diff(
    base: Dict[str, Any],
    target: Dict[str, Any],
    path: str = "",
) -> List[Tuple[str, Any, Any]]:
    """
    计算两个 dict 的差异：返回 [(path, base_value, target_value), ...] 列表。
    - 添加/修改：target_value 为新值
    - 删除：target_value = SENTINEL
    """
    diffs: List[Tuple[str, Any, Any]] = []
    SENTINEL = object()

    all_keys = set(base.keys()) | set(target.keys())
    for k in all_keys:
        child_path = _build_path(path, k)
        in_base = k in base
        in_target = k in target
        if in_base and not in_target:
            diffs.append((child_path, base[k], SENTINEL))
        elif not in_base and in_target:
            diffs.append((child_path, SENTINEL, target[k]))
        else:
            bv, tv = base[k], target[k]
            if isinstance(bv, dict) and isinstance(tv, dict):
                diffs.extend(_compute_dict_diff(bv, tv, child_path))
            elif isinstance(bv, list) and isinstance(tv, list):
                # 简化处理 list：递归比较每个 index
                diffs.extend(_compute_list_diff(bv, tv, child_path))
            elif not _deep_equal(bv, tv):
                diffs.append((child_path, bv, tv))
    return diffs


def _compute_list_diff(
    base: List[Any],
    target: List[Any],
    path: str,
) -> List[Tuple[str, Any, Any]]:
    """简化 list diff：按 index 对齐。长度变化标记为整体替换。"""
    SENTINEL = object()
    diffs: List[Tuple[str, Any, Any]] = []

    if len(base) != len(target):
        # 长度不同：标记整条 list 为修改（粗粒度，足够 demo + 测试）
        diffs.append((path, base, target))
        return diffs

    for i, (bv, tv) in enumerate(zip(base, target)):
        idx_path = _build_path(path, i)
        if isinstance(bv, dict) and isinstance(tv, dict):
            diffs.extend(_compute_dict_diff(bv, tv, idx_path))
        elif isinstance(bv, list) and isinstance(tv, list):
            diffs.extend(_compute_list_diff(bv, tv, idx_path))
        elif not _deep_equal(bv, tv):
            diffs.append((idx_path, bv, tv))
    return diffs


def _apply_diff(
    doc: Dict[str, Any],
    diff: Tuple[str, Any, Any],
) -> None:
    """应用单个 diff 到 doc（原地修改）"""
    path, base_value, target_value = diff
    SENTINEL = object()

    if path == "" or path == "/":
        if target_value is SENTINEL:
            return  # 删除根：忽略
        # 整条替换：直接清空
        doc.clear()
        doc.update(target_value)
        return

    tokens = [t for t in path.split("/") if t != ""]
    # 反转义
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in tokens]

    cur = doc
    for tok in tokens[:-1]:
        if isinstance(cur, list):
            cur = cur[int(tok)]
        else:
            cur = cur.setdefault(tok, {})
    last = tokens[-1]
    if target_value is SENTINEL:
        if isinstance(cur, list):
            cur.pop(int(last))
        else:
            cur.pop(last, None)
    else:
        if isinstance(cur, list):
            cur[int(last)] = target_value
        else:
            cur[last] = target_value


class ThreeWayMergeEngine(MergeEngine):
    """3-way merge 引擎实现"""

    def merge(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
        source_meta: Optional[Dict[str, Any]] = None,
        target_meta: Optional[Dict[str, Any]] = None,
    ) -> MergeResult:
        """执行 3-way merge：返回 merged + 冲突列表"""
        conflicts = self.detect_conflicts(base, ours, theirs)
        merged = self._apply_non_conflicting(base, ours, theirs, conflicts)
        return MergeResult(
            merged=merged,
            conflicts=conflicts,
            auto_resolved_count=self._count_non_conflicts(base, ours, theirs) - len(conflicts),
        )

    def detect_conflicts(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
    ) -> List[Conflict]:
        """检测冲突：ours 与 theirs 在 base 之上修改了同一路径为不同值"""
        ours_diffs = _compute_dict_diff(base, ours)
        theirs_diffs = _compute_dict_diff(base, theirs)
        ours_map = {p: (bv, tv) for p, bv, tv in ours_diffs}
        theirs_map = {p: (bv, tv) for p, bv, tv in theirs_diffs}

        SENTINEL = object()
        conflicts: List[Conflict] = []
        # 双方都修改了同一路径且值不同
        all_paths = set(ours_map.keys()) | set(theirs_map.keys())
        for p in all_paths:
            o = ours_map.get(p)
            t = theirs_map.get(p)
            if o is None or t is None:
                # 单方修改：非冲突
                continue
            _, ov = o
            _, tv = t
            if _deep_equal(ov, tv):
                continue
            # 真正的冲突
            base_val = o[0] if o[0] is not SENTINEL else None
            conflicts.append(
                Conflict(
                    id=str(uuid.uuid4()),
                    merge_request_id="",
                    path=p,
                    base_value=base_val,
                    ours_value=ov if ov is not SENTINEL else None,
                    theirs_value=tv if tv is not SENTINEL else None,
                    resolution=ConflictResolution.UNRESOLVED,
                )
            )
        return conflicts

    def _apply_non_conflicting(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
        conflicts: List[Conflict],
    ) -> Dict[str, Any]:
        """应用所有非冲突修改到 base 的深拷贝"""
        merged = copy.deepcopy(base)
        conflict_paths = {c.path for c in conflicts}
        # 先应用 ours（ours 优先于 theirs 的非冲突部分）
        ours_diffs = _compute_dict_diff(base, ours)
        for d in ours_diffs:
            if d[0] not in conflict_paths:
                _apply_diff(merged, d)
        # 再应用 theirs（也排除冲突路径）
        theirs_diffs = _compute_dict_diff(base, theirs)
        for d in theirs_diffs:
            if d[0] not in conflict_paths:
                _apply_diff(merged, d)
        return merged

    def _count_non_conflicts(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
    ) -> int:
        return len(_compute_dict_diff(base, ours)) + len(_compute_dict_diff(base, theirs))
