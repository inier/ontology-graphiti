"""HITL 审批门 —— 复用既有 OPA 策略 `semantic_admin_approval.rego`（AC-41）。

不另造审批机制：
- 策略真源：`odap/infra/opa/policies/semantic_admin_approval.rego`（既有，Spec 007 Iter3）；
- 判据：`data.semantic_admin_approval.allow`，把「批准一个 QA 高风险动作」映射为
  策略里的 `action="modify"`（写类动作），复用其 `r2_allow_modify` 角色矩阵：
  全局 `admin/schema_auditor/editor` 或 ws_role `term_editor/domain_editor/super_admin`。

失败语义（fail-closed）：
- OPA 不可达 / 策略装载失败 → `503 APPROVAL_SERVICE_UNAVAILABLE`，**绝不**默认放行；
- 策略返回 false → `403 APPROVAL_DENIED`，回传策略消息便于定位缺哪个角色。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from odap.common import api_errors as E
from odap.common.api_errors import ApiError

logger = logging.getLogger(__name__)

PACKAGE = "semantic_admin_approval"
POLICY_ID = "semantic_admin_approval"
POLICY_REF = f"policies/{POLICY_ID}.rego#modify_candidate"

#: 把「QA 高风险动作审批」映射为策略内的写动作
MAPPED_ACTION = "modify"


def policy_path() -> Path:
    """`odap/` 根下的策略文件（与 rule_guard.policy_ref_exists 同口径）。"""
    base = Path(__file__).resolve().parents[5] / "infra" / "opa" / "policies"
    return base / f"{POLICY_ID}.rego"


def policy_ref_exists(policy_ref: str = POLICY_REF) -> bool:
    """AC-37 证据可解析：策略文件与规则名必须真实存在。"""
    path_part, _, rule = policy_ref.partition("#")
    candidate = Path(__file__).resolve().parents[5] / "infra" / "opa" / path_part
    if not candidate.is_file():
        return False
    try:
        content = candidate.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(rule) and (f"{rule} " in content or f"{rule}\n" in content)


class OpaApprovalGate:
    """HITL 审批门插槽实现（可替换，便于测试注入）。"""

    name = "OpaApprovalGate"
    version = "v2.0"
    policy_ref = POLICY_REF

    def __init__(
        self,
        manager_factory: Optional[Callable[[], Any]] = None,
        policy_file: Optional[Path] = None,
    ) -> None:
        self._factory = manager_factory or _default_manager
        self._policy_file = policy_file or policy_path()
        self._loaded = False

    def authorize(self, user_ctx: Dict[str, Any], action: Dict[str, Any]) -> None:
        """校验该用户能否批准这条高风险动作。通过返回 None，否则抛 ApiError。"""
        payload = self._build_input(user_ctx, action)
        try:
            manager = self._factory()
            self._ensure_policy(manager)
            allowed = manager.opa_client.check_package_permission(PACKAGE, payload)
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001 - 审批服务不可用必须 fail-closed
            logger.error(
                "OPA 审批不可用：error_code=%s action_id=%s error_type=%s error=%s",
                E.APPROVAL_SERVICE_UNAVAILABLE, action.get("id"),
                type(exc).__name__, exc,
            )
            raise ApiError(
                E.APPROVAL_SERVICE_UNAVAILABLE,
                f"审批服务不可用，按 fail-closed 拒绝批准动作：{type(exc).__name__}: {exc}",
                status_code=503,
                detail={"action_id": action.get("id"), "policy_ref": self.policy_ref},
            ) from exc
        if not allowed:
            raise ApiError(
                E.APPROVAL_DENIED,
                "审批被拒：需要全局 admin/schema_auditor/editor 或 "
                "ws_role 属于 term_editor/domain_editor/super_admin",
                status_code=403,
                detail={
                    "action_id": action.get("id"),
                    "policy_ref": self.policy_ref,
                    "role": payload.get("role"),
                    "ws_role": payload.get("ws_role"),
                },
            )

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _build_input(self, user_ctx: Dict[str, Any], action: Dict[str, Any]
                     ) -> Dict[str, Any]:
        roles = list(user_ctx.get("roles") or ([] if not user_ctx.get("role")
                                              else [user_ctx["role"]]))
        role = str(user_ctx.get("role") or (roles[0] if roles else "")).lower()
        return {
            "action": MAPPED_ACTION,
            "role": role,
            "ws_role": str(user_ctx.get("ws_role") or "").lower(),
            # 策略里 r2 不读 candidate，但保持 input 形状完整（策略是外部契约）
            "candidate": {
                "current_status": "PENDING_APPROVAL",
                "total_score": 1.0,
                "rejection_reason": "",
                "action_id": action.get("id"),
                "risk_level": action.get("risk_level"),
            },
        }

    def _ensure_policy(self, manager: Any) -> None:
        """把既有 rego 装载进 OPA（幂等）；装载失败抛错由上层转 503。"""
        if self._loaded:
            return
        rego = self._policy_file.read_text(encoding="utf-8")
        manager.opa_client.put_policy(POLICY_ID, rego)
        self._loaded = True


def _default_manager() -> Any:
    from odap.infra.opa.opa_service import OPAManager

    return OPAManager()


__all__ = ["OpaApprovalGate", "POLICY_REF", "PACKAGE", "policy_ref_exists", "policy_path"]
