# semantic_admin — 最小骨架策略（Spec 007 Iter 1）
#
# 说明：
#   Iter 1 仅提供可被 OPA 成功加载的最小 allow 骨架，避免未安装/未挂载
#   OPA 环境或上游策略未就绪时产生加载错误。Iter 3 将在此文件或同目录
#   下补全 16 条基于 JWT role/ws_role + 写分类（创建/更新/删除/审批/发布）
#   的完整 RBAC/ABAC 规则。
#
#   在 Iter 1~Iter 2 阶段，后端 Depends 钩子（verify_schema_auditor）
#   以代码写死方式校验，不调用本策略。从 Iter 3 起切换到本策略驱动。
package semantic_admin

default allow = false

# 最小骨架：仅允许全局 admin 进行语义管理员级操作。
# Iter 3 会扩展为：
#   - allow { input.role == "admin" }
#   - allow { input.ws_role == "schema_auditor"; input.action == "audit" }
#   - allow { input.ws_role == "schema_auditor"; input.action == "approve" }
#   - allow { input.ws_role == "schema_auditor"; input.action == "write" }
#   - 以及基于 workspace_id / resource_type 的精细化分类。
allow {
    input.role == "admin"
}
