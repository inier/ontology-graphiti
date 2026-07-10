# ODAP API Contracts — Phase 4 (Palantir/OntoFlow 增强)

> **Date**: 2026-06-05 | **Spec**: [spec.md](../../../specs/001-odap-platform/spec.md) FR-031..FR-037
> **Plan**: [plan.md](../../../specs/001-odap-platform/plan.md) Phase 4

本契约文件覆盖 Phase 4 新增的 35+ 端点，与现有 contracts/core-ontology.md 互补。

## 1. Data Health API (FR-031)

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/ontology/health/rules` | 创建健康规则 |
| GET | `/api/ontology/health/rules` | 规则列表（按 target_type / severity 过滤） |
| GET | `/api/ontology/health/rules/{id}` | 规则详情 |
| PUT | `/api/ontology/health/rules/{id}` | 更新规则 |
| DELETE | `/api/ontology/health/rules/{id}` | 删除规则 |
| POST | `/api/ontology/health/scan` | 触发扫描（rule_id 可选，缺省全量） |
| GET | `/api/ontology/health/scan/{scan_id}/status` | 扫描进度 |
| GET | `/api/ontology/health/reports` | 报告列表（按 rule_id / status 过滤） |
| GET | `/api/ontology/health/reports/{id}` | 报告详情 |
| POST | `/api/ontology/health/reports/{id}/resolve` | 标记已修复 |
| GET | `/api/ontology/health/summary` | 总体健康摘要（pass/warn/fail 计数） |

### 1.1 请求/响应样例

**创建规则**:
```json
POST /api/ontology/health/rules
{
  "target_type_id": "equipment-type-uuid",
  "rule_name": "Equipment must have currentLocation",
  "check_expression": "type: completeness\ntarget: Equipment\nwhen: status == 'ACTIVE'\ncheck: currentLocation IS NOT NULL",
  "severity": "error",
  "schedule": "0 */6 * * *",
  "notification_channel": {
    "webhook": "https://hooks.example.com/odap-alerts"
  }
}
```

**响应**:
```json
{
  "id": "rule-uuid",
  "status": "created",
  "next_scan_at": "2026-06-05T18:00:00Z"
}
```

## 2. Branch & Merge API (FR-032)

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/ontology/branches` | 创建分支 |
| GET | `/api/ontology/branches` | 分支列表（按 ontology_id） |
| GET | `/api/ontology/branches/{id}` | 分支详情 |
| PUT | `/api/ontology/branches/{id}/protect` | 保护/取消保护分支 |
| DELETE | `/api/ontology/branches/{id}` | 删除分支 |
| POST | `/api/ontology/merge-requests` | 创建 MR |
| GET | `/api/ontology/merge-requests` | MR 列表（按 status 过滤） |
| GET | `/api/ontology/merge-requests/{id}` | MR 详情（含 diff + conflicts） |
| POST | `/api/ontology/merge-requests/{id}/approve` | 批准 MR |
| POST | `/api/ontology/merge-requests/{id}/reject` | 拒绝 MR |
| POST | `/api/ontology/merge-requests/{id}/resolve-conflict` | 解决冲突 |
| POST | `/api/ontology/merge-requests/{id}/merge` | 合并（after conflicts resolved） |

### 2.1 创建分支

```json
POST /api/ontology/branches
{
  "ontology_id": "ontology-uuid",
  "name": "feature/add-vehicle-type",
  "base_version_id": "v1.2.3",
  "merge_strategy": "3-way"
}
```

### 2.2 创建 MR

```json
POST /api/ontology/merge-requests
{
  "source_branch_id": "branch-uuid",
  "target_branch_id": "main-branch-uuid",
  "title": "Add Vehicle object type",
  "description": "支持 Vehicle 类型及其子类",
  "goal_id": "goal-uuid"   // FR-036 关联
}
```

## 3. Object Type Inheritance API (FR-033)

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/ontology/model/entity-types` | 创建（含 inherits / mixins 字段） |
| GET | `/api/ontology/model/entity-types/{id}/effective-properties` | 解析后的完整属性 |
| GET | `/api/ontology/model/entity-types/{id}/inheritance-graph` | 继承关系图 |
| POST | `/api/ontology/model/validate-inheritance` | 验证继承链（不写入） |
| POST | `/api/ontology/model/mixins` | 创建 Mixin |
| GET | `/api/ontology/model/mixins` | Mixin 列表 |
| GET | `/api/ontology/model/mixins/{id}` | Mixin 详情 |

### 3.1 创建继承的 EntityType

```json
POST /api/ontology/model/entity-types
{
  "name": "Truck",
  "inherits": ["vehicle-uuid"],
  "mixins": ["auditable-mixin-uuid", "localizable-mixin-uuid"],
  "properties": [
    {"name": "payload_kg", "data_type": "number", "required": true},
    {"name": "axle_count", "data_type": "integer"}
  ],
  "actions": ["assign-mission"]
}
```

## 4. Action Type API (FR-034)

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/ontology/action-types` | 创建 Action Type |
| GET | `/api/ontology/action-types` | 列表（按 target_entity_type_id） |
| GET | `/api/ontology/action-types/{id}` | 详情 |
| PUT | `/api/ontology/action-types/{id}` | 更新 |
| DELETE | `/api/ontology/action-types/{id}` | 删除 |
| POST | `/api/ontology/action-types/{id}/execute` | Agent 调用 |
| GET | `/api/ontology/action-types/{id}/executions` | 执行历史 |
| POST | `/api/skill/bind-action` | 绑定 Skill 到 Action |

### 4.1 Action 执行流程

```
1. POST /api/ontology/action-types/{id}/execute
   { arguments: {...} }

2. 平台校验
   - Action 是否存在且启用
   - 参数按 ObjectType 强类型校验
   - OPA 二次校验 (preconditions)

3. 加载 implementation (List[SkillBinding])
4. 按 step 顺序执行 Skills
5. 任一失败 → 调用 rollback_skill → 标记 rolled_back
6. 写 action_executions 表
7. 返回结果
```

### 4.2 执行响应

```json
{
  "execution_id": "exec-uuid",
  "status": "success",
  "skill_results": [
    {"skill_id": "validate", "status": "success", "duration_ms": 12},
    {"skill_id": "persist", "status": "success", "duration_ms": 23}
  ],
  "duration_ms": 35
}
```

## 5. Computed Property + Materialized View API (FR-035)

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/ontology/materialization/views` | 创建物化视图 |
| GET | `/api/ontology/materialization/views` | 列表 |
| GET | `/api/ontology/materialization/views/{id}` | 详情 |
| PUT | `/api/ontology/materialization/views/{id}` | 更新 |
| DELETE | `/api/ontology/materialization/views/{id}` | 删除 |
| POST | `/api/ontology/materialization/views/{id}/recompute` | 触发重算（同步/异步） |
| GET | `/api/ontology/materialization/views/{id}/status` | 视图状态 |
| GET | `/api/ontology/computed/resolve` | 查询计算属性 |

## 6. OntoFlow Goal API (FR-037)

> **重要说明**：本节对应 **FR-037 OntoFlow Goal**。原契约文档中此处误标为 FR-036，已根据 Phase 11 最终决策修正（Object View 实际对应 FR-036，见 §7）。

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/ontology/goals` | 创建 Goal |
| GET | `/api/ontology/goals` | 列表（按 workspace_id 必填 / status 可选 / 分页） |
| GET | `/api/ontology/goals/{id}` | 详情 |
| PUT | `/api/ontology/goals/{id}` | 更新 |
| DELETE | `/api/ontology/goals/{id}` | 删除 |
| POST | `/api/ontology/goals/{id}/transition` | 状态机转换 (body: `{"new_status": "approved"}`) |
| POST | `/api/ontology/goals/{id}/propose-change` | 创建 ChangeProposal + 自动 ImpactAnalysis |
| GET | `/api/ontology/goals/{id}/proposals` | 列出该 Goal 的所有 Proposal |
| POST | `/api/ontology/goals/proposals/{id}/review` | 审批 (body: `{"decision": "approve", "reviewer_notes": "..."}`) |
| GET | `/api/ontology/goals/{id}/lineage` | 获取 Goal 血缘树（祖先 + 子 + 关联 Proposal） |

### 6.1 Goal 状态机

```
proposed ──→ approved ──→ in-progress ──→ achieved
   │            │              │
   ↓            ↓              ↓
rejected    (rejected)     abandoned
```

非法转换（如 `proposed → achieved`）返回 400。

## 7. Object View API (FR-036)

> **重要说明**：本节对应 **FR-036 Object View**（视图与角色权限）。原契约文档中此处误标为 FR-037，已修正。

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/ontology/views` | 创建 View |
| GET | `/api/ontology/views` | 列表（按 target_type_id） |
| GET | `/api/ontology/views/{id}` | 详情 |
| PUT | `/api/ontology/views/{id}` | 更新 |
| DELETE | `/api/ontology/views/{id}` | 删除 |
| GET | `/api/ontology/views/{id}/resolve` | 解析用户可见属性 |
| POST | `/api/ontology/views/{id}/bind-role` | 绑定角色 |

### 7.1 View 解析流程

```
GET /api/ontology/views/commander-view/resolve?entity_id=eq-uuid&user_id=user-uuid

→ ViewResolver:
  1. 加载 View (commander-view)
  2. 应用 included_properties 白名单
  3. 应用 redaction_rules 脱敏
  4. OPA 二次校验 (FR-007)
  5. 写 view_resolution_cache (Redis TTL 5min)
  6. 返回最终可见属性
```

## 8. OntoFlow Goal API 详细规范（FR-037，补充）

本节为 Phase 11 M4 实施后对 §6 的进一步补充，包含请求/响应模型与示例。

### 8.1 创建 Goal 请求/响应

**请求**:
```json
POST /api/ontology/goals
Content-Type: application/json
Authorization: Bearer <token>

{
  "title": "提升装备完好率",
  "description": "Q3 末将一线部队装备完好率从 75% 提升至 90%",
  "business_objective": "通过预防性维护 + 备件补充，提高一线装备可用性",
  "workspace_id": "ws-prod-001",
  "created_by": "commander.zhang",
  "parent_goal_id": null,
  "tags": ["Q3", "maintenance", "readiness"],
  "auto_rationale": true
}
```

**响应** (201 Created):
```json
{
  "id": "goal-uuid",
  "title": "提升装备完好率",
  "description": "Q3 末将一线部队装备完好率从 75% 提升至 90%",
  "business_objective": "通过预防性维护 + 备件补充...",
  "rationale": "LLM 生成的业务合理性说明...",
  "status": "proposed",
  "parent_goal_id": null,
  "workspace_id": "ws-prod-001",
  "created_by": "commander.zhang",
  "created_at": "2026-06-06T10:00:00Z",
  "updated_at": "2026-06-06T10:00:00Z",
  "tags": ["Q3", "maintenance", "readiness"],
  "metadata": {}
}
```

### 8.2 状态机转换请求

**请求**:
```json
POST /api/ontology/goals/{goal_id}/transition
Content-Type: application/json
Authorization: Bearer <token>

{
  "new_status": "approved"
}
```

**合法转换**:
- `proposed` → `approved` / `rejected`
- `approved` → `in-progress`
- `in-progress` → `achieved` / `abandoned`

**非法转换** → 400：`{"detail": "invalid transition: proposed -> achieved"}`

### 8.3 提案 + 影响分析

**请求**:
```json
POST /api/ontology/goals/{goal_id}/propose-change
Content-Type: application/json
Authorization: Bearer <token>

{
  "title": "新增 'droneStatus' 属性到 Equipment",
  "description": "用于跟踪无人机的在线/离线状态",
  "changes": [
    {
      "op": "add",
      "path": "/object_types/Equipment/properties/droneStatus",
      "value": {"type": "string", "enum": ["online", "offline", "maintenance"]}
    }
  ],
  "proposed_by": "designer.li",
  "estimated_benefit": "提升无人机作战可用性 20%",
  "estimated_cost": "2 人天"
}
```

**响应** (201 Created):
```json
{
  "proposal": {
    "id": "proposal-uuid",
    "goal_id": "goal-uuid",
    "title": "新增 'droneStatus' 属性到 Equipment",
    "description": "...",
    "changes": [...],
    "impact_analysis_id": "impact-uuid",
    "estimated_benefit": "...",
    "status": "draft",
    "proposed_by": "designer.li",
    "created_at": "2026-06-06T10:05:00Z"
  },
  "impact": {
    "id": "impact-uuid",
    "proposal_id": "proposal-uuid",
    "affected_object_types": ["Equipment"],
    "affected_action_types": [],
    "affected_instances_count": 142,
    "breaking_changes": [],
    "estimated_migration_cost": "low",
    "risk_level": "low",
    "analysis_metadata": {},
    "created_at": "2026-06-06T10:05:00Z"
  }
}
```

### 8.4 血缘查询

**请求**:
```
GET /api/ontology/goals/{goal_id}/lineage
Authorization: Bearer <token>
```

**响应** (200 OK):
```json
{
  "goal": {"id": "goal-uuid", "title": "提升装备完好率", ...},
  "ancestors": [
    {"id": "parent-uuid", "title": "2026 年度战备目标", ...}
  ],
  "children": [
    {"id": "child-uuid-1", "title": "3 个月内完成 X 装备大修", ...},
    {"id": "child-uuid-2", "title": "采购 Y 备件", ...}
  ],
  "proposals": [
    {"id": "proposal-uuid", "title": "...", "status": "approved", ...}
  ]
}
```

## 9. 错误码表（完整版）

> 本节扩展原 §8 的错误码表，覆盖所有 Phase 4 接口。

| HTTP Code | 错误名 | 触发条件 | 典型场景 |
|-----------|--------|----------|----------|
| 400 | BAD_REQUEST | 参数验证失败 | Goal 状态机非法转换、JSON Patch 格式错误、ActionType 缺少 linked_skill_id、Health rule 规则类型不支持 |
| 401 | UNAUTHORIZED | Token 缺失/失效 | JWT 过期、Token 签名错误 |
| 403 | FORBIDDEN | OPA 拒绝 | Action Type 写权限不足、View 读权限被 OPA 拒绝、跨工作空间访问 |
| 404 | NOT_FOUND | 资源不存在 | goal_id / proposal_id / branch_id / view_id 不存在 |
| 409 | CONFLICT | 资源冲突 | 分支合并冲突、Impact 阻断（CRITICAL risk 强制拦截）、Goal 已有同名子 Goal |
| 422 | UNPROCESSABLE | 业务校验失败 | Action Type 参数类型不匹配、Impact risk=CRITICAL 强制拦截、Inheritance 深度 > 5、循环继承 |
| 500 | INTERNAL | 平台故障 | DB 故障、LLM 不可用（但已降级为 warning）、Neo4j 不可达 |

### 9.1 错误响应统一格式

所有错误响应遵循：
```json
{
  "detail": "human-readable error message"
}
```

对于复杂错误（多个 validation 错误、conflict 列表），`detail` 字段是字符串，复杂结构放在 `errors` / `conflicts` 字段：

```json
{
  "detail": "validation failed",
  "errors": [
    "depth exceeds 5: Truck -> Vehicle -> ...",
    "circular inheritance detected: A -> B -> A"
  ]
}
```

### 9.2 各模块特有错误

| 模块 | 错误码 | 错误消息示例 |
|------|--------|--------------|
| Health | 400 | `unknown rule_type: invalid_type` / `name is required` |
| Branch | 400 | `source and target must differ` / `conflict not resolved` |
| Inheritance | 400 | `circular inheritance detected` / `depth > 5` |
| Action | 400 | `name is required` / `linked_skill_id cannot be empty` |
|  | 422 | `parameter validation failed: expected string, got integer` |
| Computed | 400 | `unsafe expression: attribute access not allowed` |
| View | 400 | `unknown redaction rule: foo` |
| Goal | 400 | `invalid transition: proposed -> achieved` / `parent goal not found` |
|  | 404 | `goal not found: {goal_id}` |
| Proposal | 400 | `changes[0] missing required field 'op'` |

## 10. 完整 curl 示例

> 所有示例假设 API base URL 为 `http://localhost:8000`，使用 JWT Token 认证。

### 10.1 创建 Goal

```bash
curl -X POST http://localhost:8000/api/ontology/goals \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "title": "提升装备完好率",
    "description": "Q3 末将一线部队装备完好率从 75% 提升至 90%",
    "business_objective": "通过预防性维护 + 备件补充，提高一线装备可用性",
    "workspace_id": "ws-prod-001",
    "created_by": "commander.zhang",
    "tags": ["Q3", "maintenance"],
    "auto_rationale": true
  }'
```

**预期响应** (201 Created):
```json
{
  "id": "9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab",
  "title": "提升装备完好率",
  "business_objective": "通过预防性维护 + 备件补充...",
  "rationale": "该目标对齐 2026 年度战备规划...",
  "status": "proposed",
  "workspace_id": "ws-prod-001",
  "created_by": "commander.zhang",
  "created_at": "2026-06-06T10:00:00.123456",
  "updated_at": "2026-06-06T10:00:00.123456",
  "tags": ["Q3", "maintenance"],
  "metadata": {}
}
```

### 10.2 创建 ChangeProposal + 自动 ImpactAnalysis

```bash
curl -X POST http://localhost:8000/api/ontology/goals/9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab/propose-change \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "title": "新增 droneStatus 属性到 Equipment",
    "description": "用于跟踪无人机的在线/离线状态",
    "changes": [
      {
        "op": "add",
        "path": "/object_types/Equipment/properties/droneStatus",
        "value": {"type": "string", "enum": ["online", "offline", "maintenance"]}
      }
    ],
    "proposed_by": "designer.li",
    "estimated_benefit": "提升无人机作战可用性 20%",
    "estimated_cost": "2 人天"
  }'
```

**预期响应** (201 Created):
```json
{
  "proposal": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "goal_id": "9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab",
    "title": "新增 droneStatus 属性到 Equipment",
    "changes": [...],
    "impact_analysis_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "status": "draft",
    "proposed_by": "designer.li",
    "created_at": "2026-06-06T10:05:00.123456"
  },
  "impact": {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "proposal_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "affected_object_types": ["Equipment"],
    "affected_action_types": [],
    "affected_instances_count": 142,
    "breaking_changes": [],
    "estimated_migration_cost": "low",
    "risk_level": "low",
    "created_at": "2026-06-06T10:05:00.123456"
  }
}
```

### 10.3 状态机转换

```bash
# proposed → approved
curl -X POST http://localhost:8000/api/ontology/goals/9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab/transition \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"new_status": "approved"}'
```

**预期响应** (200 OK):
```json
{
  "id": "9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab",
  "title": "提升装备完好率",
  "status": "approved",
  "updated_at": "2026-06-06T10:10:00.123456",
  ...
}
```

**非法转换示例** (400 Bad Request):
```bash
# approved → achieved (跳过 in-progress)
curl -X POST http://localhost:8000/api/ontology/goals/9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab/transition \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"new_status": "achieved"}'
# {"detail": "invalid transition: approved -> achieved"}
```

### 10.4 获取 Goal 血缘树

```bash
curl -X GET "http://localhost:8000/api/ontology/goals/9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab/lineage" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**预期响应** (200 OK):
```json
{
  "goal": {
    "id": "9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab",
    "title": "提升装备完好率",
    "status": "approved",
    "parent_goal_id": "parent-uuid",
    "workspace_id": "ws-prod-001",
    "created_at": "2026-06-06T10:00:00.123456",
    "updated_at": "2026-06-06T10:10:00.123456"
  },
  "ancestors": [
    {
      "id": "parent-uuid",
      "title": "2026 年度战备目标",
      "status": "in-progress",
      "parent_goal_id": null,
      "workspace_id": "ws-prod-001",
      "created_at": "2026-01-15T09:00:00.000000",
      "updated_at": "2026-05-20T14:30:00.000000"
    }
  ],
  "children": [
    {
      "id": "child-uuid-1",
      "title": "3 个月内完成 X 装备大修",
      "status": "proposed",
      "parent_goal_id": "9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab",
      "workspace_id": "ws-prod-001",
      "created_at": "2026-06-06T11:00:00.000000",
      "updated_at": "2026-06-06T11:00:00.000000"
    },
    {
      "id": "child-uuid-2",
      "title": "采购 Y 备件",
      "status": "proposed",
      "parent_goal_id": "9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab",
      "workspace_id": "ws-prod-001",
      "created_at": "2026-06-06T11:05:00.000000",
      "updated_at": "2026-06-06T11:05:00.000000"
    }
  ],
  "proposals": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "goal_id": "9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab",
      "title": "新增 droneStatus 属性到 Equipment",
      "status": "draft",
      "proposed_by": "designer.li",
      "created_at": "2026-06-06T10:05:00.123456"
    }
  ]
}
```

**错误响应** (404 Not Found):
```json
{"detail": "goal not found: 9b8e4f3a-7c1d-4e2a-b5f6-1234567890ab"}
```

## 11. 共用错误响应（保留旧版作为参考）

| HTTP Code | 含义 | 触发条件 |
|-----------|------|----------|
| 400 | Bad Request | 参数验证失败、继承链循环、属性重名 |
| 401 | Unauthorized | Token 缺失/失效 |
| 403 | Forbidden | OPA 拒绝 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 分支冲突、Mixin 冲突、Goal 已关闭 |
| 422 | Unprocessable Entity | Action Type 校验失败（参数类型不匹配） |
| 500 | Internal Server Error | 平台故障 |

> **版本说明**：本节与 §9 重复，保留以兼容老引用。新代码请使用 §9 的扩展错误码表。