"""
BranchService 编排层 (T356)

服务层规范（AGENTS.md 规则 2）：
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum→.value, datetime→.isoformat(), BaseModel→扁平 dict

业务职责:
- create_branch / get_branch / list_branches / delete_branch
- create_merge_request / detect_conflicts / resolve_conflict / execute_merge
- get_lineage: 父子链
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..impl import BranchRepositoryImpl, ThreeWayMergeEngine
from ..interfaces import MergeEngine, MergeResult
from ..models import (
    Branch,
    BranchStatus,
    Conflict,
    ConflictResolution,
    MergeRequest,
    MergeRequestStatus,
)


class BranchService:
    """分支与合并编排服务"""

    def __init__(
        self,
        repository: Optional[BranchRepositoryImpl] = None,
        engine: Optional[MergeEngine] = None,
    ):
        self._repo = repository or BranchRepositoryImpl()
        self._engine = engine or ThreeWayMergeEngine()

    # ============== Branch ==============

    def create_branch(
        self,
        name: str,
        ontology_id: str,
        base_version_id: str,
        description: str = "",
        created_by: str = "system",
        head_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建分支"""
        if not name or not ontology_id or not base_version_id:
            return {"status": "error", "message": "name/ontology_id/base_version_id required"}

        branch = Branch(
            name=name,
            ontology_id=ontology_id,
            base_version_id=base_version_id,
            head_version_id=head_version_id or base_version_id,
            description=description,
            created_by=created_by,
        )
        saved = self._repo.save(branch)
        return self._branch_to_dict(saved)

    def get_branch(self, branch_id: str) -> Dict[str, Any]:
        b = self._repo.get(branch_id)
        if not b:
            return {"status": "error", "message": f"branch {branch_id} not found"}
        return self._branch_to_dict(b)

    def list_branches(
        self, ontology_id: Optional[str] = None
    ) -> Dict[str, Any]:
        branches = (
            self._repo.list_by_ontology(ontology_id) if ontology_id else self._repo.list()
        )
        return {
            "branches": [self._branch_to_dict(b) for b in branches],
            "count": len(branches),
        }

    def delete_branch(self, branch_id: str) -> Dict[str, Any]:
        ok = self._repo.delete(branch_id)
        if not ok:
            return {"status": "error", "message": f"branch {branch_id} not found"}
        return {"deleted": True, "branch_id": branch_id}

    def get_lineage(self, branch_id: str) -> Dict[str, Any]:
        """获取分支父子链（基于 base_version_id 链）"""
        chain: List[Dict[str, Any]] = []
        seen = set()
        cur_id: Optional[str] = branch_id
        while cur_id and cur_id not in seen:
            seen.add(cur_id)
            b = self._repo.get(cur_id)
            if not b:
                break
            chain.append(self._branch_to_dict(b))
            # 通过同名 ontology_id 寻找 base 引用本分支 head 的子分支
            siblings = self._repo.list_by_ontology(b.ontology_id)
            children = [s for s in siblings if s.base_version_id == b.head_version_id and s.id != b.id]
            cur_id = children[0].id if children else None
        return {"lineage": chain, "count": len(chain)}

    # ============== MergeRequest ==============

    def create_merge_request(
        self,
        source_branch_id: str,
        target_branch_id: str,
        title: str,
        description: str = "",
        base_snapshot: Optional[Dict[str, Any]] = None,
        ours_snapshot: Optional[Dict[str, Any]] = None,
        theirs_snapshot: Optional[Dict[str, Any]] = None,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        """创建合并请求"""
        if not source_branch_id or not target_branch_id or not title:
            return {"status": "error", "message": "source/target/title required"}
        if source_branch_id == target_branch_id:
            return {"status": "error", "message": "source and target must differ"}

        mr = MergeRequest(
            source_branch_id=source_branch_id,
            target_branch_id=target_branch_id,
            title=title,
            description=description,
            base_snapshot=base_snapshot or {},
            ours_snapshot=ours_snapshot or {},
            theirs_snapshot=theirs_snapshot or {},
            created_by=created_by,
        )
        saved = self._repo.save_merge_request(mr)
        return self._mr_to_dict(saved)

    def list_merge_requests(
        self,
        branch_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        mrs = self._repo.list_merge_requests(branch_id=branch_id, status=status)
        return {
            "merge_requests": [self._mr_to_dict(m) for m in mrs],
            "count": len(mrs),
        }

    def get_merge_request(self, mr_id: str) -> Dict[str, Any]:
        mr = self._repo.get_merge_request(mr_id)
        if not mr:
            return {"status": "error", "message": f"merge_request {mr_id} not found"}
        return self._mr_to_dict(mr)

    # ============== Conflict ==============

    def detect_conflicts(self, mr_id: str) -> Dict[str, Any]:
        mr = self._repo.get_merge_request(mr_id)
        if not mr:
            return {"status": "error", "message": f"merge_request {mr_id} not found"}

        conflicts = self._engine.detect_conflicts(
            mr.base_snapshot, mr.ours_snapshot, mr.theirs_snapshot
        )
        # 绑定 mr_id
        for c in conflicts:
            c.merge_request_id = mr_id
        self._repo.save_conflicts(mr_id, conflicts)

        new_status = (
            MergeRequestStatus.CONFLICT if conflicts
            else MergeRequestStatus.APPROVED
        )
        mr.status = new_status
        mr.updated_at = datetime.now()
        self._repo.save_merge_request(mr)

        return {
            "merge_request_id": mr_id,
            "conflicts": [self._conflict_to_dict(c) for c in conflicts],
            "count": len(conflicts),
            "status": new_status.value,
        }

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        resolved_value: Any = None,
        resolved_by: str = "system",
    ) -> Dict[str, Any]:
        """解决单条冲突"""
        try:
            res_enum = ConflictResolution(resolution)
        except ValueError:
            return {"status": "error", "message": f"unknown resolution: {resolution}"}

        if res_enum == ConflictResolution.UNRESOLVED:
            return {"status": "error", "message": "resolution cannot be unresolved"}

        located = self._find_conflict_in_mrs(conflict_id)
        if located is None:
            return {"status": "error", "message": f"conflict {conflict_id} not found"}
        c, mr = located

        if resolved_value is None:
            resolved_value = self._derive_value_from_resolution(c, res_enum)

        updated = self._repo.update_conflict_resolution(
            conflict_id, res_enum, resolved_value, resolved_by
        )
        new_status = self._reevaluate_mr_status(mr.id)
        return {
            "conflict": self._conflict_to_dict(updated),
            "merge_request_status": new_status.value,
        }

    def _derive_value_from_resolution(
        self, c: Conflict, res_enum: ConflictResolution
    ) -> Any:
        """根据解决策略自动推导 resolved_value（未显式传入时）"""
        if res_enum == ConflictResolution.USE_OURS:
            return c.ours_value
        if res_enum == ConflictResolution.USE_THEIRS:
            return c.theirs_value
        if res_enum == ConflictResolution.USE_BASE:
            return c.base_value
        return None  # MANUAL: 由调用方提供

    def _reevaluate_mr_status(self, mr_id: str) -> MergeRequestStatus:
        """重新评估 MR 状态：所有冲突 resolved → APPROVED，否则 CONFLICT"""
        mr = self._repo.get_merge_request(mr_id)
        if not mr:
            return MergeRequestStatus.OPEN
        all_conflicts = self._repo.list_conflicts(mr_id)
        if all(c.resolution != ConflictResolution.UNRESOLVED for c in all_conflicts):
            mr.status = MergeRequestStatus.APPROVED
        else:
            mr.status = MergeRequestStatus.CONFLICT
        mr.updated_at = datetime.now()
        self._repo.save_merge_request(mr)
        return mr.status

    def execute_merge(self, mr_id: str) -> Dict[str, Any]:
        """执行合并：所有冲突必须已解决，否则返回错误"""
        mr = self._repo.get_merge_request(mr_id)
        if not mr:
            return {"status": "error", "message": f"merge_request {mr_id} not found"}

        conflicts = self._repo.list_conflicts(mr_id)
        unresolved = [c for c in conflicts if c.resolution == ConflictResolution.UNRESOLVED]
        if unresolved:
            return {
                "status": "error",
                "message": f"{len(unresolved)} conflicts unresolved",
                "unresolved_paths": [c.path for c in unresolved],
            }

        ours = self._apply_resolved_to_ours(mr, conflicts)
        result: MergeResult = self._engine.merge(
            mr.base_snapshot, ours, mr.theirs_snapshot
        )
        self._mark_branches_merged(mr)
        self._mark_mr_merged(mr)

        return {
            "merge_request_id": mr_id,
            "status": mr.status.value,
            "merged": result.merged,
            "auto_resolved_count": result.auto_resolved_count,
            "remaining_conflicts": [self._conflict_to_dict(c) for c in result.conflicts],
        }

    @staticmethod
    def _apply_resolved_to_ours(
        mr: MergeRequest, conflicts: List[Conflict]
    ) -> Dict[str, Any]:
        """将已解决冲突的 resolved_value 写回 ours 快照的深拷贝"""
        ours = copy.deepcopy(mr.ours_snapshot)
        for c in conflicts:
            _apply_pointer(ours, c.path, c.resolved_value)
        return ours

    def _mark_branches_merged(self, mr: MergeRequest) -> None:
        """合并完成后：更新 target head + 标记 source 为 MERGED"""
        target = self._repo.get(mr.target_branch_id)
        if target:
            target.head_version_id = f"merged-{mr.id}-{uuid.uuid4().hex[:8]}"
            target.updated_at = datetime.now()
            self._repo.save(target)
        source = self._repo.get(mr.source_branch_id)
        if source:
            source.status = BranchStatus.MERGED
            source.merged_at = datetime.now()
            source.merge_target_branch_id = mr.target_branch_id
            source.updated_at = datetime.now()
            self._repo.save(source)

    def _mark_mr_merged(self, mr: MergeRequest) -> None:
        """标记 MR 为 MERGED"""
        mr.status = MergeRequestStatus.MERGED
        mr.merged_at = datetime.now()
        mr.updated_at = datetime.now()
        self._repo.save_merge_request(mr)

    # ============== helpers ==============

    def _find_conflict_in_mrs(self, conflict_id: str):
        """通过遍历所有 MR 找到包含指定 conflict_id 的 (Conflict, MR) 元组"""
        # 因为 storage 没有直接按 conflict_id 查的接口，走 MR 列表
        for mr in self._repo.list_merge_requests():
            for c in self._repo.list_conflicts(mr.id):
                if c.id == conflict_id:
                    return c, mr
        return None

    @staticmethod
    def _branch_to_dict(b: Branch) -> Dict[str, Any]:
        return {
            "id": b.id,
            "name": b.name,
            "ontology_id": b.ontology_id,
            "base_version_id": b.base_version_id,
            "head_version_id": b.head_version_id,
            "status": b.status.value,
            "description": b.description,
            "created_by": b.created_by,
            "created_at": b.created_at.isoformat(),
            "updated_at": b.updated_at.isoformat(),
            "merged_at": b.merged_at.isoformat() if b.merged_at else None,
            "merge_target_branch_id": b.merge_target_branch_id,
        }

    @staticmethod
    def _mr_to_dict(mr: MergeRequest) -> Dict[str, Any]:
        return {
            "id": mr.id,
            "source_branch_id": mr.source_branch_id,
            "target_branch_id": mr.target_branch_id,
            "title": mr.title,
            "description": mr.description,
            "conflicts": mr.conflicts,
            "status": mr.status.value,
            "base_snapshot": mr.base_snapshot,
            "ours_snapshot": mr.ours_snapshot,
            "theirs_snapshot": mr.theirs_snapshot,
            "created_by": mr.created_by,
            "created_at": mr.created_at.isoformat(),
            "updated_at": mr.updated_at.isoformat(),
            "merged_at": mr.merged_at.isoformat() if mr.merged_at else None,
        }

    @staticmethod
    def _conflict_to_dict(c: Conflict) -> Dict[str, Any]:
        return {
            "id": c.id,
            "merge_request_id": c.merge_request_id,
            "path": c.path,
            "base_value": c.base_value,
            "ours_value": c.ours_value,
            "theirs_value": c.theirs_value,
            "resolution": c.resolution.value,
            "resolved_value": c.resolved_value,
            "resolved_by": c.resolved_by,
            "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        }


def _apply_pointer(doc: Any, path: str, value: Any) -> None:
    """将 resolved_value 写回 doc 对应 JSON Pointer 路径"""
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
