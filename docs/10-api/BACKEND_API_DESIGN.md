# ODAP 后端接口设计文档

> **版本**: 1.0.0 | **日期**: 2026-05-18
> **状态**: 已发布 | **优先级**: P0

---

## 1. 概述

### 1.1 应用入口

ODAP 后端基于 FastAPI 构建，统一入口为 `app/main.py`，注册了 12 个路由模块。

### 1.2 路由注册表

| 序号 | 路由模块 | 前缀 | 来源文件 | 端点数 |
|------|---------|------|---------|--------|
| 1 | ingest_router | `/api/ontology/ingest` | odap/biz/ontology/api/routes.py | 16 |
| 2 | workspace_router | `/api/workspaces` | odap/biz/workspace/api/routes.py | 20+ |
| 3 | roles_router | `/api/roles` | odap/biz/roles/api/routes.py | 6 |
| 4 | audit_router | - | odap/infra/security/audit_api.py | - |
| 5 | skill_router | `/api/skill` | odap/biz/skill_system/api/routes.py | 8 |
| 6 | hook_router | `/api/hook` | odap/biz/hook_system/api/routes.py | 4 |
| 7 | mcp_router | `/api/mcp` | odap/biz/mcp_adapter/api/routes.py | 6 |
| 8 | event_router | `/api/event-simulator` | odap/biz/event_simulator/api/routes.py | 6 |
| 9 | frontend_router | `/api` | odap/biz/frontend_compat/api/routes.py | 40+ |
| 10 | agent_router | `/api/agent` | odap/biz/openharness_agent/api/routes.py | 5 |
| 11 | business_router | `/api` | odap/biz/business/api/routes.py | 16 |
| 12 | monitoring_router | `/api/v1/monitoring` | - | 2 |

### 1.3 通用响应格式

**成功响应**:
```json
{
  "data": {},
  "message": "success"
}
```

**分页响应**:
```json
{
  "data": [],
  "page": 1,
  "page_size": 10,
  "total": 100,
  "has_more": true
}
```

**错误响应**:
```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数验证失败",
    "details": []
  },
  "request_id": "req-abc123"
}
```

---

## 2. 本体摄入 API

**路由前缀**: `/api/ontology/ingest`
**来源文件**: `odap/biz/ontology/api/routes.py`

### 2.1 通用摄入接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ontology/ingest` | 通用摄入（按 source_type 分发） |

**请求体** (Dict[str, Any]):
```json
{
  "data": "string",
  "data_type": "text|news|manual|json|natural_language|random",
  "scenario_id": "string|null"
}
```

### 2.2 独立摄入端点

| 方法 | 路径 | 说明 | 请求模型 |
|------|------|------|---------|
| POST | `/api/ontology/ingest/news` | 新闻摄入 | NewsIngestRequest |
| POST | `/api/ontology/ingest/manual` | 手动输入 | ManualIngestRequest |
| POST | `/api/ontology/ingest/json` | JSON 摄入 | JsonIngestRequest |
| POST | `/api/ontology/ingest/natural-language` | 自然语言摄入 | NaturalLanguageIngestRequest |
| POST | `/api/ontology/ingest/random` | 随机事件生成 | RandomEventsRequest |
| POST | `/api/ontology/ingest/tavily` | Tavily API 搜索 | TavilyIngestRequest |

**NewsIngestRequest**:
```json
{
  "query": "string|null",
  "url": "string|null",
  "scenario_id": "string|null"
}
```

**ManualIngestRequest**:
```json
{
  "form_data": {
    "title": "string",
    "description": "string"
  },
  "scenario_id": "string|null"
}
```

**JsonIngestRequest**:
```json
{
  "json_data": "string",
  "scenario_id": "string|null"
}
```

**NaturalLanguageIngestRequest**:
```json
{
  "description": "string",
  "scenario_id": "string|null"
}
```

**RandomEventsRequest**:
```json
{
  "parties": ["string"],
  "scenario_context": {},
  "count": 1,
  "scenario_id": "string|null"
}
```

**统一响应** (IngestResponse):
```json
{
  "ingest_id": "string",
  "status": "pending|processing|completed|failed",
  "source_details": {},
  "original_content": "string|null",
  "extracted_data": {
    "source_data": [],
    "document_ids": [],
    "document_count": 0,
    "entities_count": 0,
    "relations_count": 0,
    "events_count": 0
  }
}
```

### 2.3 构建状态 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ontology/ingest/builds/{build_id}` | 获取构建状态 |
| GET | `/api/ontology/ingest/builds` | 构建历史 |
| POST | `/api/ontology/ingest/{ingest_id}/build` | 运行构建管道 |

**查询参数** (构建历史):
- `scenario_id`: string (可选)
- `limit`: integer (可选)

### 2.4 版本管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ontology/ingest/versions/rollback` | 版本回滚 |
| GET | `/api/ontology/ingest/versions` | 版本列表 |

### 2.5 文档与日志 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ontology/ingest/documents/list` | 文档列表 |
| GET | `/api/ontology/ingest/documents/{doc_id}` | 文档详情 |
| GET | `/api/ontology/ingest` | 摄入历史 |
| GET | `/api/ontology/ingest/{ingest_id}` | 摄入状态 |
| GET | `/api/ontology/ingest/{ingest_id}/logs` | 处理日志 |
| GET | `/api/ontology/ingest/{ingest_id}/build-history` | 构建历史 |
| GET | `/api/ontology/ingest/{ingest_id}/full` | 完整摄入记录 |
| GET | `/api/ontology/ingest/random/generators` | 获取生成器类型 |

---

## 3. 工作空间 API

**路由前缀**: `/api/workspaces`
**来源文件**: `odap/biz/workspace/api/routes.py`

### 3.1 工作空间 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/workspaces` | 创建工作空间 |
| GET | `/api/workspaces` | 列出工作空间 |
| GET | `/api/workspaces/{workspace_id}` | 获取工作空间详情 |
| PUT | `/api/workspaces/{workspace_id}` | 更新工作空间 |
| DELETE | `/api/workspaces/{workspace_id}` | 删除工作空间 |

**CreateWorkspaceRequest**:
```json
{
  "name": "string",
  "description": "string|null",
  "type": "default|shared|private|temporary",
  "isolation_strategy": "low|standard|high|strict",
  "owner": "string|null",
  "tags": ["string"]
}
```

**WorkspaceResponse**:
```json
{
  "id": "string",
  "name": "string",
  "description": "string|null",
  "type": "string",
  "status": "string",
  "owner": "string",
  "members": ["string"],
  "config": {},
  "tags": ["string"],
  "created_at": "string",
  "updated_at": "string"
}
```

### 3.2 工作空间操作

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/workspaces/{workspace_id}/activate` | 激活工作空间 |
| POST | `/api/workspaces/{workspace_id}/deactivate` | 停用工作空间 |
| POST | `/api/workspaces/{workspace_id}/members` | 添加成员 |
| DELETE | `/api/workspaces/{workspace_id}/members/{member_id}` | 移除成员 |

### 3.3 隔离策略

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workspaces/{workspace_id}/isolation` | 获取隔离策略 |
| PUT | `/api/workspaces/{workspace_id}/isolation` | 更新隔离策略 |

### 3.4 导入导出

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/workspaces/{workspace_id}/import` | 导入工作空间 |
| POST | `/api/workspaces/{workspace_id}/export` | 导出工作空间 |

### 3.5 场景管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workspaces/{workspace_id}/scenarios` | 列出场景 |
| POST | `/api/workspaces/{workspace_id}/scenarios` | 创建场景 |
| GET | `/api/workspaces/{workspace_id}/scenarios/{scenario_id}` | 获取场景 |
| PUT | `/api/workspaces/{workspace_id}/scenarios/{scenario_id}` | 更新场景 |
| DELETE | `/api/workspaces/{workspace_id}/scenarios/{scenario_id}` | 删除场景 |

### 3.6 版本与冲突

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workspaces/{workspace_id}/versions` | 列出版本 |
| POST | `/api/workspaces/{workspace_id}/conflicts/scan` | 扫描数据冲突 |
| POST | `/api/workspaces/{workspace_id}/conflicts/fix` | 修复数据冲突 |

---

## 4. 业务规则 API

**路由前缀**: `/api`
**来源文件**: `odap/biz/business/api/routes.py`

### 4.1 业务流程

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/business-processes` | 列出流程 |
| POST | `/api/business-processes` | 创建流程 |
| GET | `/api/business-processes/{process_id}` | 获取流程 |
| PUT | `/api/business-processes/{process_id}` | 更新流程 |
| DELETE | `/api/business-processes/{process_id}` | 删除流程 |

### 4.2 业务规则

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/business-rules` | 列出规则 |
| POST | `/api/business-rules` | 创建规则 |
| GET | `/api/business-rules/{rule_id}` | 获取规则 |
| PUT | `/api/business-rules/{rule_id}` | 更新规则 |
| DELETE | `/api/business-rules/{rule_id}` | 删除规则 |

### 4.3 业务逻辑

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/business-logics` | 列出逻辑 |
| POST | `/api/business-logics` | 创建逻辑 |
| GET | `/api/business-logics/{logic_id}` | 获取逻辑 |
| PUT | `/api/business-logics/{logic_id}` | 更新逻辑 |
| DELETE | `/api/business-logics/{logic_id}` | 删除逻辑 |

### 4.4 业务指标

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/business-indicators` | 列出指标 |
| POST | `/api/business-indicators` | 创建指标 |
| GET | `/api/business-indicators/{indicator_id}` | 获取指标 |
| PUT | `/api/business-indicators/{indicator_id}` | 更新指标 |
| DELETE | `/api/business-indicators/{indicator_id}` | 删除指标 |

---

## 5. 角色管理 API

**路由前缀**: `/api/roles`
**来源文件**: `odap/biz/roles/api/routes.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/roles` | 列出角色 |
| POST | `/api/roles` | 创建角色 |
| GET | `/api/roles/{role_id}` | 获取角色 |
| PUT | `/api/roles/{role_id}` | 更新角色 |
| DELETE | `/api/roles/{role_id}` | 删除角色 |
| GET | `/api/roles/permissions` | 列出权限 |

**RoleCreate**:
```json
{
  "name": "string",
  "description": "string|null",
  "role_type": "system_admin|project_owner|team_leader|member|guest",
  "permissions": ["string"]
}
```

---

## 6. 技能系统 API

**路由前缀**: `/api/skill`
**来源文件**: `odap/biz/skill_system/api/routes.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/skill/register` | 注册技能 |
| GET | `/api/skill/{skill_id}` | 获取技能 |
| GET | `/api/skill/list` | 列出技能 |
| POST | `/api/skill/{skill_id}/versions` | 添加版本 |
| POST | `/api/skill/{skill_id}/activate` | 激活技能 |
| POST | `/api/skill/{skill_id}/deactivate` | 停用技能 |
| POST | `/api/skill/{skill_id}/load` | 加载技能 |
| POST | `/api/skill/{skill_id}/unload` | 卸载技能 |
| GET | `/api/skill/loaded` | 已加载技能列表 |

---

## 7. Hook 系统 API

**路由前缀**: `/api/hook`
**来源文件**: `odap/biz/hook_system/api/routes.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/hook/register` | 注册 Hook |
| GET | `/api/hook/{hook_id}` | 获取 Hook |
| POST | `/api/hook/{hook_id}/execute` | 执行 Hook |
| GET | `/api/hook/list` | 列出 Hooks |

---

## 8. MCP 适配器 API

**路由前缀**: `/api/mcp`
**来源文件**: `odap/biz/mcp_adapter/api/routes.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/mcp/servers` | 注册 MCP 服务器 |
| POST | `/api/mcp/servers/{server_id}/connect` | 连接服务器 |
| POST | `/api/mcp/servers/{server_id}/disconnect` | 断开服务器 |
| GET | `/api/mcp/servers` | 列出服务器 |
| GET | `/api/mcp/servers/{server_id}/tools` | 发现工具 |
| GET | `/api/mcp/pool/status` | 连接池状态 |

---

## 9. 工具注册表 API

**路由前缀**: `/api/v1/tools`
**来源文件**: `odap/biz/tool_registry/api/routes.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/tools/register` | 注册工具 |
| GET | `/api/v1/tools/discover` | 发现工具 |
| POST | `/api/v1/tools/execute` | 执行工具 |
| POST | `/api/v1/tools/chains` | 注册工具链 |
| POST | `/api/v1/tools/chains/execute` | 执行工具链 |
| GET | `/api/v1/tools/chains/{chain_id}` | 获取工具链 |
| GET | `/api/v1/tools/chains` | 列出工具链 |
| GET | `/api/v1/tools/health` | 健康报告 |
| GET | `/api/v1/tools/{tool_id}/history` | 执行历史 |
| GET | `/api/v1/tools/{tool_id}` | 工具详情 |

---

## 10. Agent API

**路由前缀**: `/api/agent`
**来源文件**: `odap/biz/openharness_agent/api/routes.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/init` | 初始化 Agent |
| POST | `/api/agent/run` | 运行 Agent 任务 |
| GET | `/api/agent/status` | 获取 Agent 状态 |
| GET | `/api/agent/tools` | 获取工具列表 |
| POST | `/api/agent/chat` | Agent 对话 |

**AgentRunRequest**:
```json
{
  "task": "string",
  "model": "string|null",
  "workspace_id": "string|null"
}
```

**AgentConfigRequest**:
```json
{
  "model": "string|null",
  "workspace_id": "string|null"
}
```

---

## 11. 事件模拟器 API

**路由前缀**: `/api/event-simulator`
**来源文件**: `odap/biz/event_simulator/api/routes.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/event-simulator/templates` | 创建模板 |
| GET | `/api/event-simulator/templates` | 列出模板 |
| POST | `/api/event-simulator/generate` | 生成事件 |
| GET | `/api/event-simulator/events` | 列出事件 |
| POST | `/api/event-simulator/time-control` | 设置时间控制 |
| GET | `/api/event-simulator/time-control` | 获取时间控制 |

---

## 12. 前端兼容层 API

**路由前缀**: `/api`
**来源文件**: `odap/biz/frontend_compat/api/routes.py`

这是最大的路由文件（2031行），包含 40+ 个端点，覆盖以下功能域：

### 12.1 场景管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/scenarios` | 创建场景 |
| GET | `/api/scenarios` | 列出场景 |
| GET | `/api/scenarios/{scenario_id}` | 获取场景 |
| PUT | `/api/scenarios/{scenario_id}` | 更新场景 |
| DELETE | `/api/scenarios/{scenario_id}` | 删除场景 |
| POST | `/api/scenarios/{scenario_id}/sync` | 同步到 Graphiti |
| GET | `/api/scenarios/{scenario_id}/timeline` | 获取时间线 |
| GET | `/api/scenarios/{scenario_id}/entities` | 获取实体 |
| GET | `/api/scenarios/{scenario_id}/relations` | 获取关系 |
| GET | `/api/scenarios/{scenario_id}/export` | 导出场景 |

### 12.2 数据摄入

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ingest/text` | 文本摄入 |
| POST | `/api/ingest/news` | 新闻摄入 |
| POST | `/api/ingest/random` | 随机生成 |
| POST | `/api/ingest/manual` | 手动录入 |
| POST | `/api/ingest/file` | 文件上传 |
| GET | `/api/ingest/status/{task_id}` | 摄入状态 |

### 12.3 版本管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/versions` | 列出版本 |
| GET | `/api/versions/{version_id}` | 获取版本 |
| POST | `/api/versions/{version_id}/rollback` | 回滚版本 |
| GET | `/api/versions/diff` | 版本对比 |

### 12.4 审计日志

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/audit/events` | 审计事件列表 |
| GET | `/api/audit/timeline` | 审计时间线 |
| GET | `/api/audit/stats` | 审计统计 |
| GET | `/api/audit/trace/{trace_id}` | 审计追踪 |

### 12.5 实体查询与图谱

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/entities/{entity_id}` | 获取实体 |
| GET | `/api/entities/{entity_id}/history` | 实体历史 |
| GET | `/api/query/relations` | 查询关系 |
| POST | `/api/graph/generate` | 生成图谱 |
| GET | `/api/graph/progress/{task_id}` | 图谱生成进度 |
| POST | `/api/graph/cancel/{task_id}` | 取消图谱生成 |
| GET | `/api/graph/history` | 图谱历史 |
| GET | `/api/graph/detail/{task_id}` | 图谱详情 |

### 12.6 智能问答

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/qa/ask` | 提问 |
| POST | `/api/qa/stream` | 流式问答 |
| GET | `/api/qa/sessions` | 会话列表 |
| GET | `/api/qa/sessions/{session_id}` | 获取会话 |
| POST | `/api/qa/feedback` | 反馈 |

### 12.7 用户认知引擎

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/cognition/intent` | 意图识别 |
| POST | `/api/cognition/view` | 知识导航 |
| POST | `/api/cognition/navigate` | 导航 |
| POST | `/api/cognition/explain` | 解释 |

### 12.8 闭环反馈

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/feedback/action` | 行动反馈 |
| POST | `/api/feedback/decision` | 决策反馈 |

### 12.9 策略管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/policies` | 列出策略 |
| GET | `/api/policies/{policy_id}` | 获取策略 |
| POST | `/api/policies` | 创建策略 |
| PUT | `/api/policies/{policy_id}` | 更新策略 |
| DELETE | `/api/policies/{policy_id}` | 删除策略 |

### 12.10 系统监控

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/monitoring/metrics` | 系统指标 |
| GET | `/health` | 健康检查 |

### 12.11 本体 Schema

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ontology/schema` | 获取本体 Schema |

---

## 13. WebSocket 端点

| 路径 | 说明 | 来源 |
|------|------|------|
| `/ws/events` | 实时事件流 | odap/web/api/app.py |

---

## 14. 已知问题与改进建议

| 编号 | 问题 | 影响 | 建议 |
|------|------|------|------|
| API-001 | business_router 和 frontend_router 前缀均为 `/api` | 路由冲突 | 为 business_router 分配独立前缀 `/api/business` |
| API-002 | frontend_compat 路由文件 2031 行，40+ 端点 | 难以维护 | 按功能域拆分为独立路由文件 |
| API-003 | 多个端点返回硬编码/空数据（删除不删、回滚不滚） | 功能缺失 | 实现真实业务逻辑 |
| API-004 | 所有端点无认证/授权保护 | 安全风险 | 添加 JWT 认证中间件 |
| API-005 | skill/hook/mcp 路由使用查询参数接收 POST 请求体 | 不符合 RESTful 规范 | 改用请求体 + Pydantic 模型 |
| API-006 | tool_registry 模块目录不存在，导入会失败 | 运行时错误 | 创建模块或移除路由注册 |
| API-007 | 场景查询三层 fallback 模式 | 数据不一致 | 统一为单一数据源 |
| API-008 | ingest 通用端点使用 Dict[str, Any] 绕过验证 | 类型不安全 | 使用 Pydantic 模型 |
| API-009 | log_error 函数体为空 | 错误日志丢失 | 实现错误日志记录 |
| API-010 | Celery 任务失败时仍返回 task_id | 假任务 ID | 检查 Celery 可用性后再返回 |

---

**文档版本历史**:

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2026-05-18 | 初始版本，基于代码分析梳理 |
