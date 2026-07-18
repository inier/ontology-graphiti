# semantic_admin_approval — 2 级审批 + OPA 5 规则权限策略（Spec 007 §Iter3）
#
# 替代 Iter 1 的最小骨架 semantic_admin_min_iter1.rego，包含：
#   规则 1：audit_candidate       — L1 schema_auditor / ws_role=reviewer 可审核
#   规则 2：modify_candidate      — ws_role ∈ {term_editor, domain_editor} / 全局 admin/schema_auditor 可编辑
#   规则 3：reject_candidate      — 同 audit；必须带 rejection_reason
#   规则 4：final_approve_candidate — L2 全局 admin / ws_role=super_admin 可终审
#   规则 5：auto_skip_admin         — total_score≥0.9 且 L1 AUDITOR_APPROVED → 自动跳过 L2 直接 APPROVED
#
# 用法：
#   opa eval -d semantic_admin_approval.rego \
#     --input input.json 'data.semantic_admin_approval.allow'
#
# input JSON 结构：
#   { "action": "audit" | "modify" | "reject" | "final_approve" | "auto_skip",
#     "role":   "admin" | "schema_auditor" | "editor" | "viewer" | ...,
#     "ws_role": "viewer" | "term_editor" | "domain_editor" | "reviewer" | "super_admin",
#     "candidate": { "total_score": 0.92, "current_status": "AUDITOR_APPROVED",
#                    "rejection_reason": "..."  # reject 时必填
#     } }
package semantic_admin_approval

import future.keywords.if
import future.keywords.in
import future.keywords.contains

# ======================================================================
# FAIL-CLOSED: 未被任何规则允许的请求一律拒绝（default deny 安全兜底）
# ======================================================================
default allow := false

# ======================================================================
# 常量
# ======================================================================

# 全局角色合法集
global_roles_administrative := {"admin", "schema_auditor"}
global_roles_editable       := {"admin", "schema_auditor", "editor"}
ws_roles_viewers            := {"viewer", "term_editor", "domain_editor", "reviewer", "super_admin"}
ws_roles_editable           := {"term_editor", "domain_editor", "super_admin"}
ws_roles_l1_auditor         := {"reviewer", "super_admin"}
ws_roles_l2_admin           := {"super_admin"}

# 阈值：total_score ≥ THR 可 Auto-Skip L2
AUTO_SKIP_THRESHOLD := 0.90

# ======================================================================
# 工具函数
# ======================================================================

has_global_auditor_role if { input.role in global_roles_administrative }
has_global_editor_role  if { input.role in global_roles_editable }
has_ws_editor_role      if { input.ws_role in ws_roles_editable }
has_ws_l1_auditor_role  if { input.ws_role in ws_roles_l1_auditor }
has_ws_l2_admin_role    if { input.ws_role in ws_roles_l2_admin }

current_status := object.get(object.get(input, "candidate", {}), "current_status", "")
total_score    := to_number(object.get(object.get(input, "candidate", {}), "total_score", 0.0))
reject_reason  := object.get(object.get(input, "candidate", {}), "rejection_reason", "")

# ======================================================================
# 规则 1：audit_candidate — L1 审核
# ======================================================================

r1_allow_audit contains msg if {
  input.action == "audit"
  has_global_auditor_role
  msg := "rule1 audit PASS: global role schema_auditor/admin"
}

r1_allow_audit contains msg if {
  input.action == "audit"
  has_ws_l1_auditor_role
  msg := "rule1 audit PASS: ws_role in {reviewer, super_admin}"
}

deny_audit contains msg if {
  input.action == "audit"
  count(r1_allow_audit) == 0
  msg := "rule1 audit DENY: 需全局 schema_auditor/admin 或 ws_role reviewer/super_admin"
}

# ======================================================================
# 规则 2：modify_candidate — 修改 candidate canonical/synonyms/parents
# ======================================================================

r2_allow_modify contains msg if {
  input.action == "modify"
  has_global_editor_role
  msg := "rule2 modify PASS: global role admin/schema_auditor/editor"
}

r2_allow_modify contains msg if {
  input.action == "modify"
  has_ws_editor_role
  msg := "rule2 modify PASS: ws_role in {term_editor, domain_editor, super_admin}"
}

deny_modify contains msg if {
  input.action == "modify"
  count(r2_allow_modify) == 0
  msg := "rule2 modify DENY: 需全局 editor+ 或 ws_role term_editor/domain_editor"
}

# ======================================================================
# 规则 3：reject_candidate — 驳回（必须带 rejection_reason）
# ======================================================================

r3_allow_reject contains msg if {
  input.action == "reject"
  has_global_auditor_role
  reject_reason != ""
  msg := "rule3 reject PASS: global role + reason present"
}

r3_allow_reject contains msg if {
  input.action == "reject"
  has_ws_l1_auditor_role
  reject_reason != ""
  msg := "rule3 reject PASS: ws_role reviewer+ + reason present"
}

deny_reject contains msg if {
  input.action == "reject"
  reject_reason == ""
  msg := "rule3 reject DENY: rejection_reason 必填，禁止无原因驳回"
}

deny_reject contains msg if {
  input.action == "reject"
  reject_reason != ""
  count(r3_allow_reject) == 0
  msg := "rule3 reject DENY: 需 L1 审核员权限"
}

# ======================================================================
# 规则 4：final_approve_candidate — L2 Admin 终审
# ======================================================================

r4_allow_final contains msg if {
  input.action == "final_approve"
  input.role == "admin"
  msg := "rule4 final_approve PASS: global role admin"
}

r4_allow_final contains msg if {
  input.action == "final_approve"
  has_ws_l2_admin_role
  msg := "rule4 final_approve PASS: ws_role=super_admin"
}

deny_final contains msg if {
  input.action == "final_approve"
  count(r4_allow_final) == 0
  msg := "rule4 final_approve DENY: 需全局 admin 或 ws_role super_admin"
}

# ======================================================================
# 规则 5：auto_skip_admin — 总分 ≥ 0.9 + L1 已通过 → 跳过 L2 直接 APPROVED
# ======================================================================

r5_allow_auto_skip contains msg if {
  input.action == "auto_skip"
  total_score >= AUTO_SKIP_THRESHOLD
  current_status == "AUDITOR_APPROVED"
  msg := sprintf("rule5 auto_skip PASS: total_score=%.3f ≥ %.2f + status=%s",
                 [total_score, AUTO_SKIP_THRESHOLD, current_status])
}

deny_auto_skip contains msg if {
  input.action == "auto_skip"
  total_score < AUTO_SKIP_THRESHOLD
  msg := sprintf("rule5 auto_skip DENY: 总分 %.3f < 阈值 %.2f", [total_score, AUTO_SKIP_THRESHOLD])
}

deny_auto_skip contains msg if {
  input.action == "auto_skip"
  current_status != "AUDITOR_APPROVED"
  msg := sprintf("rule5 auto_skip DENY: 前置状态应为 AUDITOR_APPROVED，实为 '%s'", [current_status])
}

# ======================================================================
# 聚合 allow / deny 汇总
# ======================================================================

all_allows := r1_allow_audit | r2_allow_modify | r3_allow_reject | r4_allow_final | r5_allow_auto_skip

all_denials := deny_audit | deny_modify | deny_reject | deny_final | deny_auto_skip

allow_messages := all_allows
deny_messages  := all_denials

# 顶级 allow：动作至少匹配 1 条 allow，且无 deny
allow if {
  count(all_allows) > 0
  count(all_denials) == 0
}

# 顶级默认：不满足任何 allow → deny
deny_default contains msg if {
  count(all_allows) == 0
  msg := sprintf("no rules matched for action='%s'", [input.action])
}
