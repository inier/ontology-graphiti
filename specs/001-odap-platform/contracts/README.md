# ODAP API Contracts

本目录包含 ODAP 平台各模块的 API 契约定义，按业务领域组织。

## 契约文件索引

| 文件 | 领域 | 端点数 | 说明 |
|------|------|--------|------|
| core-ontology.md | core/ontology | ~120 | 本体管理全链路（摄入/版本/模型/引擎/运行时/蓝图/服务化） |
| core-cognition.md | core/cognition | 16 | 认知引擎+思维图 |
| core-agent.md | core/agent | 8 | Agent 编排+决策 |
| platform-workspace.md | platform/workspace | 38 | 工作空间+场景+隔离+导入导出 |
| platform-roles.md | platform/roles | 6 | 角色权限管理 |
| platform-skills.md | platform/skill_system | 22 | 技能系统 |
| platform-tools.md | platform/tool_registry | 5 | 工具注册表 |
| platform-session-memory.md | platform/session_memory | 13 | 会话记忆管理 |
| platform-ontology-memory.md | platform/ontology_memory | 25 | 本体记忆+图谱同步+共享工作空间 |
| platform-i18n.md | platform/i18n | 5 | 国际化 |
| integration-openharness.md | integration/openharness_agent | 8 | OpenHarness Agent |
| integration-mcp.md | integration/mcp_adapter | 9 | MCP 协议适配 |
| integration-hooks.md | integration/hook_system | 5 | Hook 系统 |
| integration-frontend-compat.md | integration/frontend_compat | 40+ | 前端兼容层 |
| decision.md | decision | 10 | 决策管道+动作+推荐 |
| data.md | data | 25 | 知识库+问答+语义地图+数据仓库+感知 |
| simulation.md | simulation | 30 | 事件模拟+沙箱+推演+反馈 |
| management.md | management | 26 | Agent 管理+业务管理 |
| infra-security.md | infra/security | 15 | 认证+审计+数据分级 |
| infra-opa.md | infra/opa | 13 | OPA 策略+Markdown+ABAC |
| infra-query.md | infra/query | 5 | 统一查询服务 |

## 契约格式

每个契约文件遵循以下格式：

```markdown
# [模块名] API Contract

## Base URL
`/api/{module}`

## Authentication
所有端点需要 `Authorization: Bearer <token>` 头，除非标注为 Public。

## Endpoints

### [HTTP Method] [Path]
**描述**: [端点说明]
**认证**: Required / Optional / Public
**请求体**: [Schema 引用或内联定义]
**响应**: [Schema 引用或内联定义]
**状态码**: 200 / 400 / 401 / 403 / 404 / 500
```

## Schema 定义位置

- 后端 Pydantic Schema: `odap/biz/{domain}/{module}/api/schemas.py`
- 后端领域模型: `odap/biz/{domain}/{module}/models/`
- 前端 TypeScript 类型: `frontend/src/modules/{module}/types/`

## 总计

- **端点总数**: ~320+
- **WebSocket 端点**: 2
- **Pydantic Schema 类**: ~180+