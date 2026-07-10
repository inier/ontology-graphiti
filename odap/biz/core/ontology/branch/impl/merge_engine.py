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
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from odap.infra.security.audit_helper import storage_audit

from ..interfaces import MergeEngine, MergeResult
from ..models import Conflict, ConflictResolution

logger = logging.getLogger(__name__)

_AUDIT_SERVICE = "ontology_design"


def _audit_success(action: str, resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="success",
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


def _audit_failure(action: str, msg: str = "", resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="failure",
            result_message=(msg or "")[:200],
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


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
            return
        doc.clear()
        doc.update(target_value)
        return

    tokens = [t for t in path.split("/") if t != ""]
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
        """执行 3-way merge：返回 merged + 冲突列表（start_merge + finalize_merge 合并流程）"""
        action = "merge_engine.merge"
        try:
            conflicts = self.detect_conflicts(base, ours, theirs)
            merged = self._apply_non_conflicting(base, ours, theirs, conflicts)
            auto_count = self._count_non_conflicts(base, ours, theirs) - len(conflicts)
            _audit_success(action,
                           details={"base_size": len(base or {}),
                                    "ours_size": len(ours or {}),
                                    "theirs_size": len(theirs or {}),
                                    "conflict_count": len(conflicts),
                                    "auto_resolved_count": auto_count})
            return MergeResult(
                merged=merged,
                conflicts=conflicts,
                auto_resolved_count=auto_count,
            )
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"base_size": len(base or {}),
                                    "ours_size": len(ours or {}),
                                    "theirs_size": len(theirs or {})})
            raise

    def start_merge(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
    ) -> MergeResult:
        """开始合并：检测冲突 + 生成 merged 初稿"""
        return self.merge(base, ours, theirs)

    def detect_conflicts(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
    ) -> List[Conflict]:
        """检测冲突：ours 与 theirs 在 base 之上修改了同一路径为不同值"""
        action = "merge_engine.detect_conflicts"
        try:
            ours_diffs = _compute_dict_diff(base, ours)
            theirs_diffs = _compute_dict_diff(base, theirs)
            ours_map = {p: (bv, tv) for p, bv, tv in ours_diffs}
            theirs_map = {p: (bv, tv) for p, bv, tv in theirs_diffs}

            SENTINEL = object()
            conflicts: List[Conflict] = []
            all_paths = set(ours_map.keys()) | set(theirs_map.keys())
            for p in all_paths:
                o = ours_map.get(p)
                t = theirs_map.get(p)
                if o is None or t is None:
                    continue
                _, ov = o
                _, tv = t
                if _deep_equal(ov, tv):
                    continue
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
            _audit_success(action,
                           details={"ours_diff_count": len(ours_diffs),
                                    "theirs_diff_count": len(theirs_diffs),
                                    "conflict_count": len(conflicts)})
            return conflicts
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            raise

    def resolve_conflict(
        self,
        conflict: Conflict,
        resolution: ConflictResolution,
        resolved_value: Any = None,
    ) -> Conflict:
        """解决单条冲突：更新 conflict 对象的 resolution/resolved_value"""
        action = "merge_engine.resolve_conflict"
        resource = conflict.id or "unknown"
        try:
            if resolution == ConflictResolution.UNRESOLVED:
                raise ValueError("resolution cannot be UNRESOLVED")
            conflict.resolution = resolution
            if resolution == ConflictResolution.USE_OURS:
                conflict.resolved_value = conflict.ours_value
            elif resolution == ConflictResolution.USE_THEIRS:
                conflict.resolved_value = conflict.theirs_value
            elif resolution == ConflictResolution.USE_BASE:
                conflict.resolved_value = conflict.base_value
            elif resolved_value is not None:
                conflict.resolved_value = resolved_value
            _audit_success(action, resource=resource,
                           details={"conflict_id": conflict.id,
                                    "resolution": resolution.value,
                                    "path_len": len(conflict.path or "")})
            return conflict
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=resource,
                           details={"conflict_id": conflict.id,
                                    "resolution": resolution.value if hasattr(resolution, "value") else str(resolution)})
            raise

    def finalize_merge(
        self,
        base: Dict[str, Any],
        ours: Dict[str, Any],
        theirs: Dict[str, Any],
        resolved_conflicts: List[Conflict],
    ) -> MergeResult:
        """完成合并：在已解决冲突基础上生成最终 merged"""
        action = "merge_engine.finalize_merge"
        try:
            resolved_ours = copy.deepcopy(ours)
            for c in resolved_conflicts:
                if c.resolution != ConflictResolution.UNRESOLVED and c.resolved_value is not None:
                    _apply_pointer_inplace(resolved_ours, c.path, c.resolved_value)

            unresolved = [c for c in resolved_conflicts if c.resolution == ConflictResolution.UNRESOLVED]
            merged = self._apply_non_conflicting(base, resolved_ours, theirs, unresolved)
            auto_count = self._count_non_conflicts(base, resolved_ours, theirs) - len(unresolved)
            _audit_success(action,
                           details={"resolved_count": len(resolved_conflicts) - len(unresolved),
                                    "unresolved_count": len(unresolved),
                                    "auto_resolved_count": auto_count})
            return MergeResult(
                merged=merged,
                conflicts=list(unresolved),
                auto_resolved_count=auto_count,
            )
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"resolved_conflicts_count": len(resolved_conflicts)})
            raise

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
        ours_diffs = _compute_dict_diff(base, ours)
        for d in ours_diffs:
            if d[0] not in conflict_paths:
                _apply_diff(merged, d)
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


def _apply_pointer_inplace(doc: Any, path: str, value: Any) -> None:
    """原地把 value 写回 doc 的 JSON Pointer 路径"""
    if not path or path in ("", "/"):
        return
    tokens = [t for t in path.split("/") if t != ""]
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in tokens]
    cur = doc
    for tok in tokens[:-1]:
        if isinstance(cur, list):
            cur = cur[int(tok)]
        else:
            cur = cur.setdefault(tok, {})
    last = tokens[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value
