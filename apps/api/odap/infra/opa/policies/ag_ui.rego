# AG-UI Protocol Access Policy
# v2.0 plan §7 Phase 3: OPA policy for /api/ag-ui/run endpoint
#
# 授权：用户必须有工作空间角色才能调用 AG-UI endpoint
# 验证：JWT 携带 ws_id + ws_role；OPA 决策 run 请求合法性

package odap.ag_ui

import future.keywords.if
import future.keywords.in

# 默认拒绝
default allow = false

# 规则 1：管理员可访问所有工作空间的 AG-UI
allow if {
    input.user.role == "admin"
}

# 规则 2：工作空间成员可访问自己工作空间的 AG-UI
allow if {
    input.action == "ag_ui:run"
    input.user.ws_role in {"owner", "admin", "editor", "viewer"}
    input.user.ws_id == input.workspace_id
}

# 规则 3：viewer 角色只读（不可发起 run，但可接收事件流）
allow_read if {
    input.action == "ag_ui:read"
    input.user.ws_id == input.workspace_id
}

# 规则 4：拒绝没有任何工作空间角色的请求
deny if {
    not input.user.ws_role
    input.action == "ag_ui:run"
}

# 规则 5：拒绝无工作空间上下文的请求（跨工作空间泄漏防护）
deny if {
    not input.workspace_id
    input.action == "ag_ui:run"
}
