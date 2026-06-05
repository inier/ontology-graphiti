# ODAP API Contracts — Phase 4 (Palantir/OntoFlow 增强)

> **Date**: 2026-06-05 | **Spec**: [spec.md](../../specs/001-odap-platform/spec.md) FR-031..FR-037
> **Plan**: [plan.md](../../specs/001-odap-platform/plan.md) Phase 4

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

## 6. OntoFlow Goal API (FR-036)

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/ontology/goals` | 创建 Goal |
| GET | `/api/ontology/goals` | 列表（按 status / priority） |
| GET | `/api/ontology/goals/{id}` | 详情 |
| PUT | `/api/ontology/goals/{id}` | 更新 |
| POST | `/api/ontology/goals/{id}/achieve` | 标记已达成 |
| GET | `/api/ontology/goals/{id}/impact` | 评估 Goal 影响的实例/规则 |
| GET | `/api/ontology/changes?goal_id={id}` | 按 Goal 反查变更 |

## 7. Object View API (FR-037)

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

## 8. 共用错误响应

| HTTP Code | 含义 | 触发条件 |
|-----------|------|----------|
| 400 | Bad Request | 参数验证失败、继承链循环、属性重名 |
| 401 | Unauthorized | Token 缺失/失效 |
| 403 | Forbidden | OPA 拒绝 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 分支冲突、Mixin 冲突、Goal 已关闭 |
| 422 | Unprocessable Entity | Action Type 校验失败（参数类型不匹配） |
| 500 | Internal Server Error | 平台故障 |
