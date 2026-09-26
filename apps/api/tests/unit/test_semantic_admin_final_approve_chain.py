"""审批工作台终审链回归测试（AGENTS.md 规则 14 要求 6：测试必须执行真实函数体）。

历史缺陷（2026-09-24 修复前）：
  approval_service.py 的 review_level_2 / action_modify / action_final_approve
  三处均用 `CandidateService(candidate_storage=...)` 构造，而真实形参是 `storage=`；
  并给 `promote_to_usl` 传 `overwrite=` / `approver_id=` / `force_writeback=`，
  而真实 kwargs 是 `force_overwrite=` / `admin_id=`（无 force_writeback）。
  这是典型「幻影调用」：TypeError 被外层 `except Exception` 吞成
  {"status": "error"}，路由层再翻成 HTTP 错 —— 看起来只是"写回失败了"。
  但 action_final_approve 在调用 promote **之前**已把 candidate.status 置为
  APPROVED，而入口守卫只接受 ADMIN_PENDING / AUDITOR_APPROVED，于是重试永久
  被拒：候选卡死在「已终审通过但从未写回 USL」，且没有任何接口能再推进它。

  该链路此前**零测试覆盖**（全仓无任何测试触及 action_final_approve /
  review_level_2），名为「2级审批」的测试测的是另一套 CandidateService.approve
  平行实现 —— 这正是幻影 kwargs 能长期"绿"着存在的原因。

本文件的两道防线：
  1. TestCallSiteSignatures — AST 扫描真实源码，锁死三处调用点的 kwargs 必须
     落在被调方真实签名内。不依赖任何 mock，改错形参名立刻变红。
  2. TestFinalApproveFailureIsRetryable — 走真实 action_final_approve +
     真实 CandidateService.promote_to_usl（不 patch 任何待验证逻辑），
     用 TERM_EXISTS_409 制造真实写回失败，断言状态未被推进、可重试。
"""
from __future__ import annotations

import ast
import inspect
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest

from odap.biz.semantic_admin.approval_workflow.services.approval_service import (
    ApprovalService,
)
from odap.biz.semantic_admin.candidate_store.services.candidate_service import (
    CandidateService,
)
from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
    SQLiteCandidateStorage,
)

# 由本文件位置反推仓库根（tests/unit/x.py → parents[4]），不写死绝对路径。
_ROOT = Path(__file__).resolve().parents[4]
_APPROVAL_SERVICE_PY = (
    _ROOT / "apps" / "api" / "odap" / "biz" / "semantic_admin"
    / "approval_workflow" / "services" / "approval_service.py"
)


# ======================================================================
# 防线 1：调用点 kwargs 必须落在真实签名内（反幻影调用）
# ======================================================================

def _collect_call_kwargs(py_path: Path, func_names: set) -> Dict[str, set]:
    """扫描源码，收集对 func_names 中每个函数的所有调用点用到的关键字参数名。

    目录/文件缺失必须报错而不是返回空 dict：返回空会让下面的断言在扫描 0 个
    调用点的情况下"通过"（规则 14：禁止静默降级 / 伪绿灯）。
    """
    assert py_path.is_file(), f"审计目标不存在（布局已变更？）: {py_path}"
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    seen: Dict[str, set] = {name: set() for name in func_names}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = node.func
        name = None
        if isinstance(fname, ast.Name):
            name = fname.id
        elif isinstance(fname, ast.Attribute):
            name = fname.attr
        if name in seen:
            seen[name].update(kw.arg for kw in node.keywords if kw.arg is not None)
    return seen


class TestCallSiteSignatures:
    """三处调用点的形参名必须与被调方真实签名一致。"""

    def test_candidate_service_constructor_kwarg_is_storage(self):
        """CandidateService(candidate_storage=...) 是幻影 —— 真实形参是 storage。"""
        params = set(inspect.signature(CandidateService.__init__).parameters) - {"self"}
        assert "storage" in params
        assert "candidate_storage" not in params, (
            "CandidateService 新增了 candidate_storage 形参？请同步复核本测试"
        )

        used = _collect_call_kwargs(_APPROVAL_SERVICE_PY, {"CandidateService"})
        assert used["CandidateService"], (
            "approval_service.py 里已找不到 CandidateService(...) 调用点 —— "
            "若调用被移除或改名，本用例应显式失败而不是扫描 0 处后通过"
        )
        illegal = used["CandidateService"] - params
        assert not illegal, (
            f"approval_service.py 给 CandidateService 传了不存在的形参 {sorted(illegal)}；"
            f"真实签名是 {sorted(params)}。这类幻影 kwargs 会在运行时抛 TypeError，"
            f"并被外层 except 吞成 {{'status': 'error'}}（规则 14：禁止幻影调用）"
        )

    def test_promote_to_usl_kwargs_are_real(self):
        """promote_to_usl 的真实 kwargs 是 admin_id / force_overwrite / parent_term_id。"""
        params = set(inspect.signature(CandidateService.promote_to_usl).parameters) - {"self"}
        assert {"candidate_id", "admin_id"} <= params
        for phantom in ("overwrite", "approver_id", "force_writeback"):
            assert phantom not in params, (
                f"promote_to_usl 新增了 {phantom} 形参？请同步复核本测试"
            )

        used = _collect_call_kwargs(_APPROVAL_SERVICE_PY, {"promote_to_usl"})
        assert used["promote_to_usl"], (
            "approval_service.py 里已找不到 promote_to_usl(...) 调用点"
        )
        illegal = used["promote_to_usl"] - params
        assert not illegal, (
            f"approval_service.py 给 promote_to_usl 传了不存在的形参 {sorted(illegal)}；"
            f"真实签名是 {sorted(params)}（规则 14：禁止幻影调用）"
        )

    def test_modify_candidate_kwargs_are_real(self):
        """action_modify 走 modify_candidate(candidate_id, patch=, editor_id=)。"""
        params = set(inspect.signature(CandidateService.modify_candidate).parameters) - {"self"}
        used = _collect_call_kwargs(_APPROVAL_SERVICE_PY, {"modify_candidate"})
        assert used["modify_candidate"], (
            "approval_service.py 里已找不到 modify_candidate(...) 调用点"
        )
        illegal = used["modify_candidate"] - params
        assert not illegal, (
            f"approval_service.py 给 modify_candidate 传了不存在的形参 {sorted(illegal)}；"
            f"真实签名是 {sorted(params)}"
        )


# ======================================================================
# 防线 2：真实写回失败时状态不得被推进（一次性门 → 可重试）
# ======================================================================

@pytest.fixture
def cs(tmp_path: Path) -> SQLiteCandidateStorage:
    return SQLiteCandidateStorage(db_path=str(tmp_path / "c.db"))


@pytest.fixture
def usl_on_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """把 USL 库指向 tmp_path。

    action_final_approve 内部自建 CandidateService（不注入 writeback_service），
    于是 promote_to_usl 会惰性构造 SQLiteUslStorage() 并落到 DATA_DIR/usl.db。
    这两个路径是模块级常量，在 __init__ 调用时读取，故 patch 常量即可。
    """
    import odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage as usl_mod

    monkeypatch.setattr(usl_mod, "DEFAULT_USL_DB_DIR", str(tmp_path), raising=True)
    monkeypatch.setattr(
        usl_mod, "DEFAULT_USL_DB_PATH", str(tmp_path / "usl.db"), raising=True
    )


def _seed_candidate(
    cs: SQLiteCandidateStorage, *, canonical: str, status: str, domain_id: str
) -> Dict[str, Any]:
    run = cs.create_pipeline_run(workspace_id="ws-test")
    return cs.bulk_insert_candidates([{
        "id": str(uuid.uuid4()),
        "run_id": run["id"],
        "canonical": canonical,
        "semantic_type": "对象类型",
        "synonyms": ["别名甲"],
        "definition": "测试用定义",
        "confidence": 0.9,
        "status": status,
        "domain_id": domain_id,
        "provenance": {},
    }])[0]


class TestFinalApproveFailureIsRetryable:
    """真实链路：写回失败 → 状态原地不动 → 可重试。

    不 patch action_final_approve / promote_to_usl 的任何一行（规则 14 要求 6）。
    用 USL 中已存在同 domain + canonical 的 Term 触发真实的 TERM_EXISTS_409，
    该分支在 promote_to_usl 的查重步骤就返回，不会触达 Graphiti 双写，
    因此整条路径可离线执行。
    """

    def test_promote_conflict_leaves_status_retryable(
        self,
        cs: SQLiteCandidateStorage,
        usl_on_tmp_path: None,
    ):
        from odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage import (
            SQLiteUslStorage,
        )

        usl = SQLiteUslStorage()
        usl.save_term({
            "domain_id": "dom-conflict",
            "canonical": "势力",
            "semantic_type": "对象类型",
            "synonyms": [],
        })

        cand = _seed_candidate(
            cs, canonical="势力", status="ADMIN_PENDING", domain_id="dom-conflict",
        )
        before = cs.get_candidate(cand["id"])
        assert str(before.get("status") or "").upper() == "ADMIN_PENDING"

        svc = ApprovalService(candidate_storage=cs)
        result = svc.action_final_approve(
            task_id=f"appr-task-{cand['id']}",
            approver_id="admin-1",
            comment="终审",
            auto_promote=True,
            writeback_now=True,
        )

        # 1) 失败必须显式，且带上可定位的错误码与写回详情
        assert result.get("status") == "error", f"写回冲突却报了成功: {result}"
        assert result.get("code") == "PROMOTE_TO_USL_FAILED_502"
        assert "TERM_EXISTS_409" in str(result.get("promote_to_usl_result") or {})

        # 2) 状态必须原地不动 —— 这是「一次性门」是否被拆掉的关键断言
        after = cs.get_candidate(cand["id"])
        assert str(after.get("status") or "").upper() == "ADMIN_PENDING", (
            f"写回失败后状态被推进为 {after.get('status')!r}，入口守卫只接受 "
            f"ADMIN_PENDING/AUDITOR_APPROVED，该候选将永久卡死无法重试"
        )

        # 3) 重试必须真的被接受（守卫不因上一次失败而拒绝）
        retry = svc.action_final_approve(
            task_id=f"appr-task-{cand['id']}",
            approver_id="admin-1",
            comment="重试",
            auto_promote=True,
            writeback_now=True,
        )
        assert retry.get("code") != "STATUS_NOT_ADMIN_PENDING_409", (
            f"重试被状态守卫拒绝，说明第一次失败已把候选推进到不可重试状态: {retry}"
        )

    def test_contradictory_writeback_flags_rejected_explicitly(
        self,
        cs: SQLiteCandidateStorage,
        usl_on_tmp_path: None,
    ):
        """auto_promote=True + writeback_now=False 必须显式拒绝，而不是猜一个。"""
        cand = _seed_candidate(
            cs, canonical="兵种", status="ADMIN_PENDING", domain_id="dom-x",
        )
        svc = ApprovalService(candidate_storage=cs)
        result = svc.action_final_approve(
            task_id=f"appr-task-{cand['id']}",
            approver_id="admin-1",
            auto_promote=True,
            writeback_now=False,
        )
        assert result.get("status") == "error"
        assert result.get("code") == "CONTRADICTORY_WRITEBACK_FLAGS_400"
        after = cs.get_candidate(cand["id"])
        assert str(after.get("status") or "").upper() == "ADMIN_PENDING"

    def test_review_level_2_conflict_leaves_status_retryable(
        self,
        cs: SQLiteCandidateStorage,
        usl_on_tmp_path: None,
    ):
        """review_level_2 同样不得在写回失败时推进状态。"""
        from odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage import (
            SQLiteUslStorage,
        )

        usl = SQLiteUslStorage()
        usl.save_term({
            "domain_id": "dom-l2",
            "canonical": "结义",
            "semantic_type": "过程类型",
            "synonyms": [],
        })
        cand = _seed_candidate(
            cs, canonical="结义", status="PENDING_L2", domain_id="dom-l2",
        )

        svc = ApprovalService(candidate_storage=cs)
        result = svc.review_level_2(
            candidate_id=cand["id"],
            decision="APPROVE",
            reviewer_id="admin-1",
            overwrite=False,
        )

        assert result.get("status") == "error", f"L2 写回冲突却报了成功: {result}"
        assert result.get("code") == "PROMOTE_TO_USL_FAILED_502"
        after = cs.get_candidate(cand["id"])
        assert str(after.get("status") or "").upper() == "PENDING_L2", (
            f"L2 写回失败后状态被推进为 {after.get('status')!r}，"
            f"PENDING_L2 守卫会让重试永久被拒"
        )


class TestActionModifyRealBody:
    """action_modify 走真实 modify_candidate（第三处 storage= 幻影的落点）。"""

    def test_modify_updates_candidate(
        self,
        cs: SQLiteCandidateStorage,
        usl_on_tmp_path: None,
    ):
        cand = _seed_candidate(
            cs, canonical="旧名", status="PENDING_REVIEW", domain_id="dom-m",
        )
        svc = ApprovalService(candidate_storage=cs)
        result = svc.action_modify(
            task_id=f"appr-task-{cand['id']}",
            approver_id="editor-1",
            candidate_patch={"canonical_label": "新名"},
            editor_comment="人工校正",
        )
        assert result.get("status") != "error", f"action_modify 失败: {result}"
        after = cs.get_candidate(cand["id"])
        assert after.get("canonical") == "新名"
