# ODAP 无用代码清理清单

> **版本**: 1.0.0 | **日期**: 2026-05-18
> **状态**: 待清理 | **优先级**: P1

---

## 1. 后端无用/问题代码

### 1.1 废弃/Stub 实现

| 编号 | 文件 | 位置 | 问题描述 | 清理建议 | 优先级 |
|------|------|------|---------|---------|--------|
| BE-001 | odap/gateway/api_gateway_v2.py | ServiceProxy.forward | 返回硬编码 `{"status": "ok"}`，forward_ws/forward_sse 均为空实现 | 实现真实代理逻辑或移除 | P1 |
| BE-002 | odap/gateway/api_gateway_v2.py | AuthHandler.logout | 方法体为空（pass） | 实现 logout 逻辑 | P1 |
| BE-003 | odap/gateway/api_gateway_v2.py | RateLimitType.SLIDING_WINDOW | 枚举值定义但从未使用 | 移除 | P2 |
| BE-004 | odap/biz/frontend_compat/api/routes.py | log_error / _log_error_async | 函数体为空（pass），错误日志全部丢失 | 实现错误日志记录 | P0 |
| BE-005 | odap/biz/frontend_compat/api/routes.py | update_scenario | 只查询不更新，直接返回原数据 | 实现更新逻辑 | P0 |
| BE-006 | odap/biz/frontend_compat/api/routes.py | delete_scenario | 只检查存在但不删除，返回假成功 | 实现删除逻辑 | P0 |
| BE-007 | odap/biz/frontend_compat/api/routes.py | ingest_news2 | 硬编码测试端点，返回固定值 | 删除 | P1 |
| BE-008 | odap/biz/frontend_compat/api/routes.py | test_route / test_route2 | 调试端点 | 删除 | P1 |
| BE-009 | odap/biz/frontend_compat/api/routes.py | get_version | 返回硬编码数据 | 对接真实数据源 | P1 |
| BE-010 | odap/biz/frontend_compat/api/routes.py | rollback | 只返回成功但不执行回滚 | 实现回滚逻辑 | P0 |
| BE-011 | odap/biz/frontend_compat/api/routes.py | diff_versions | 返回空 changes | 实现对比逻辑 | P1 |
| BE-012 | odap/biz/frontend_compat/api/routes.py | query_relations | 永远返回空列表 | 实现查询逻辑 | P1 |
| BE-013 | odap/biz/frontend_compat/api/routes.py | get_entity_history | 永远返回空列表 | 实现历史查询 | P1 |
| BE-014 | odap/biz/frontend_compat/api/routes.py | get_graph_progress/cancel/history/detail | 均返回硬编码/空数据 | 实现或移除 | P1 |
| BE-015 | odap/biz/frontend_compat/api/routes.py | get_topic_stats | 返回硬编码模拟数据 | 对接真实统计 | P1 |
| BE-016 | odap/biz/frontend_compat/api/routes.py | get_query_history | 永远返回空列表 | 实现查询历史 | P2 |
| BE-017 | odap/biz/tool_registry/api/routes.py | register_tool | skill/function 类型永远注册失败 | 实现或移除 | P1 |
| BE-018 | odap/biz/tool_registry/api/routes.py | 整个文件 | odap.biz.tool_registry 模块目录不存在，导入会失败 | 创建模块或移除路由 | P0 |

### 1.2 重复代码

| 编号 | 文件 | 问题描述 | 清理建议 | 优先级 |
|------|------|---------|---------|--------|
| BE-019 | odap/web/api/app.py vs frontend_compat | 场景管理端点在两处重复定义 | 统一到 frontend_compat | P1 |
| BE-020 | odap/web/api/app.py vs ontology/routes.py | 摄入端点在两处重复定义 | 统一到 ontology/routes.py | P1 |
| BE-021 | odap/web/api/app.py vs frontend_compat | 版本管理端点在两处重复定义 | 统一到 frontend_compat | P1 |
| BE-022 | odap/biz/workspace/api/routes.py | 场景查询三层 fallback（scenario_service → compat_store → global_store） | 统一为单一数据源 | P1 |
| BE-023 | odap/biz/ontology/api/routes.py | SQLiteIngestStorage 模块级实例与函数内局部实例不一致 | 统一实例管理 | P1 |
| BE-024 | odap/biz/openharness_agent/api/routes.py | run_agent_endpoint 和 chat_with_agent 功能冗余 | 合并为单一端点 | P2 |

### 1.3 代码质量问题

| 编号 | 文件 | 位置 | 问题描述 | 清理建议 | 优先级 |
|------|------|------|---------|---------|--------|
| BE-025 | odap/web/api/app.py | __init__ | storage 参数接收但从未使用 | 移除参数 | P2 |
| BE-026 | odap/web/api/app.py | _ensure_initial_version | 异常被静默吞掉（except Exception: pass） | 添加日志记录 | P1 |
| BE-027 | odap/web/api/app.py | 重复导入 | OntologyDocument 从两个不同模块导入 | 统一导入 | P2 |
| BE-028 | odap/biz/frontend_compat/api/routes.py | 17-23行 | sys.path.append 路径 hack | 移除，使用正确的包结构 | P1 |
| BE-029 | odap/biz/business/storage/sqlite_storage.py | delete_* 方法 | 使用 conn.total_changes 判断删除成功 | 改用 cursor.rowcount | P1 |
| BE-030 | odap/biz/roles/storage/sqlite_role_storage.py | 导入 | 从 api.routes 导入模型，循环依赖风险 | 将模型提取到独立模块 | P1 |
| BE-031 | odap/biz/workspace/storage/sqlite_storage.py | _deserialize_json | 裸 except 吞掉所有异常 | 捕获具体异常 | P2 |
| BE-032 | odap/biz/workspace/storage/sqlite_storage.py | delete_workspace | 不删除关联的 scenarios 记录 | 添加级联删除 | P1 |
| BE-033 | odap/infra/security/audit_logger.py | log_sync | asyncio.run() 在已有事件循环中会抛异常 | 使用 nest_asyncio 或检测事件循环 | P1 |
| BE-034 | app/main.py | @app.on_event("startup") | FastAPI 已弃用此方式 | 改用 lifespan | P2 |
| BE-035 | odap/biz/frontend_compat/api/routes.py | ingest_* | Celery 不可用时仍返回 task_id | 检查可用性后再返回 | P1 |

---

## 2. 前端无用/问题代码

### 2.1 废弃组件

| 编号 | 文件 | 组件 | 问题描述 | 清理建议 | 优先级 |
|------|------|------|---------|---------|--------|
| FE-001 | frontend/src/modules/qa/pages/QAChat.tsx | QAChat | 旧版问答页面，被 QAChatPage 替代，未在路由中使用 | 删除文件 | P1 |
| FE-002 | frontend/src/modules/audit/index.ts | AuditTimeline | 导出但未在路由中使用 | 删除导出或移入内部 | P2 |
| FE-003 | frontend/src/modules/ingest/index.ts | SimulatorConsole | 导出但未在路由中使用 | 删除导出或移入内部 | P2 |
| FE-004 | frontend/src/modules/ontology/index.ts | GraphView | 导出但未在路由中使用 | 删除导出或移入内部 | P2 |
| FE-005 | frontend/src/modules/ontology/index.ts | OntologyBuilder | 导出但未在路由中使用 | 删除导出或移入内部 | P2 |
| FE-006 | frontend/src/modules/ontology/index.ts | GraphCanvas | 导出但未在路由中使用 | 删除导出或移入内部 | P2 |
| FE-007 | frontend/src/modules/ontology/index.ts | OntologyIngestPipeline | 导出但未在路由中使用 | 删除导出或移入内部 | P2 |
| FE-008 | frontend/src/modules/qa/index.ts | QAIProvider | 未在外部使用 | 检查是否内部使用后决定 | P2 |
| FE-009 | frontend/src/modules/qa/index.ts | SessionDrawer | 未在外部使用 | 检查是否内部使用后决定 | P2 |

### 2.2 Mock/硬编码代码

| 编号 | 文件 | 位置 | 问题描述 | 清理建议 | 优先级 |
|------|------|------|---------|---------|--------|
| FE-010 | frontend/src/modules/agent/pages/AgentChat.tsx | handleSend | 使用 setTimeout 模拟回复 | 调用 api.agentChat 真实 API | P0 |
| FE-011 | frontend/src/modules/qa/pages/QAChat.tsx | simulatePipeline | 使用 setTimeout 模拟流水线 | 调用真实构建 API | P1 |
| FE-012 | frontend/src/modules/qa/pages/QAChat.tsx | 统计数据 | 加载失败时使用硬编码 mock 数据 | 显示错误状态 | P1 |
| FE-013 | frontend/src/modules/shared/stores/index.ts | useAppStore.login | 完全是 mock 实现 | 对接真实认证 API | P1 |
| FE-014 | frontend/src/modules/agent/pages/MyAgents.tsx | currentRoleId | 从未设置的 localStorage 键读取 | 实现角色选择逻辑 | P1 |

### 2.3 类型冲突与重复

| 编号 | 文件 | 问题描述 | 清理建议 | 优先级 |
|------|------|---------|---------|--------|
| FE-015 | api.ts vs stores/index.ts | Workspace 接口重复定义且字段不同 | 统一到 shared/types | P1 |
| FE-016 | api.ts vs stores/index.ts | AuditEvent 接口重复定义且字段不同 | 统一到 shared/types | P1 |
| FE-017 | api.ts vs types/index.ts | Relation 与 GraphEdge 功能重叠 | 统一为 GraphEdge | P2 |

### 2.4 代码质量问题

| 编号 | 文件 | 位置 | 问题描述 | 清理建议 | 优先级 |
|------|------|------|---------|---------|--------|
| FE-018 | frontend/src/modules/qa/pages/QAChatPage.tsx | handleDeleteSession | `sessionId === sessionId` 永远为 true | 修复为比较参数与当前活跃 sessionId | P0 |
| FE-019 | frontend/src/modules/qa/pages/QAChatPage.tsx | setSuggestions | 状态被设置但从未读取 | 移除或实现读取逻辑 | P1 |
| FE-020 | frontend/src/modules/agent/pages/MyAgents.tsx | Tag | 使用非标准 size="small" 属性 | 移除 size 属性 | P2 |
| FE-021 | frontend/src/modules/agent/pages/MyAgents.tsx | Card | 使用已废弃的 bodyStyle 属性 | 改用 styles.body | P2 |
| FE-022 | config.ts vs agentApi.ts/businessApi.ts | VITE_API_BASE vs VITE_API_BASE_URL | 环境变量名不一致 | 统一为 VITE_API_BASE | P1 |
| FE-023 | frontend/src/modules/shared/stores/index.ts | useAppStore | App.tsx 未使用，自行管理 workspace | 统一使用 Store | P1 |
| FE-024 | frontend/src/modules/shared/stores/index.ts | useAuditStore | AuditLog.tsx 未使用，自行管理状态 | 统一使用 Store | P1 |
| FE-025 | frontend/src/modules/shared/stores/index.ts | loadWorkspaces | 直接使用 fetch 绕过 api.ts | 使用 api.ts 统一封装 | P1 |
| FE-026 | frontend/src/test/api_integration.test.ts | 整个文件 | 与实际 API 签名严重脱节，无法运行 | 重写测试文件 | P0 |

---

## 3. 归档代码

| 编号 | 文件/目录 | 问题描述 | 清理建议 | 优先级 |
|------|----------|---------|---------|--------|
| AR-001 | docs/11-archive/legacy_code/ | 已归档的旧代码 | 保留归档，不清理 | - |
| AR-002 | odap/biz/hook_system/hook_manager_v2.py | 与 hook_manager.py 并存 | 确认是否替代后删除旧版 | P2 |
| AR-003 | odap/biz/mcp_adapter/mcp_service_v2.py | 与 mcp_service.py 并存 | 确认是否替代后删除旧版 | P2 |
| AR-004 | odap/infra/opa/opa_service_v2.py | 与 opa_service.py 并存 | 确认是否替代后删除旧版 | P2 |
| AR-005 | odap/infra/security/audit_logger_v2.py | 与 audit_logger.py 并存 | 确认是否替代后删除旧版 | P2 |
| AR-006 | odap/tools/base_v2.py | 与 base.py 并存 | 确认是否替代后删除旧版 | P2 |

---

## 4. 清理执行计划

### Phase 1: P0 紧急修复（影响功能正确性）

| 编号 | 任务 | 预计影响 |
|------|------|---------|
| BE-004 | 实现 log_error 错误日志记录 | 日志系统 |
| BE-005 | 实现 update_scenario 更新逻辑 | 场景管理 |
| BE-006 | 实现 delete_scenario 删除逻辑 | 场景管理 |
| BE-010 | 实现 rollback 回滚逻辑 | 版本管理 |
| BE-018 | 修复 tool_registry 导入失败 | 工具注册 |
| FE-010 | AgentChat 对接真实 API | 智能体对话 |
| FE-018 | 修复 handleDeleteSession bug | 问答会话 |
| FE-026 | 重写前端集成测试 | 测试覆盖 |

### Phase 2: P1 重要改进（影响可维护性和安全性）

| 编号 | 任务 | 预计影响 |
|------|------|---------|
| BE-001 | 实现 API 网关代理逻辑 | 网关功能 |
| BE-007-008 | 删除调试/测试端点 | 代码整洁 |
| BE-019-021 | 消除重复路由定义 | 可维护性 |
| BE-022 | 统一场景查询数据源 | 数据一致性 |
| BE-028 | 移除 sys.path hack | 代码规范 |
| BE-029 | 修复删除判断逻辑 | 数据正确性 |
| BE-030 | 消除循环依赖 | 代码规范 |
| BE-035 | 修复假 task_id 返回 | 数据正确性 |
| FE-001 | 删除 QAChat 旧版 | 代码整洁 |
| FE-013 | 实现真实认证 | 安全性 |
| FE-015-016 | 统一类型定义 | 类型安全 |
| FE-022 | 统一环境变量 | 配置一致性 |

### Phase 3: P2 代码优化（提升代码质量）

| 编号 | 任务 | 预计影响 |
|------|------|---------|
| BE-003 | 移除未使用枚举值 | 代码整洁 |
| BE-024 | 合并冗余 Agent 端点 | API 简化 |
| BE-025-027 | 修复小问题 | 代码规范 |
| BE-031-032 | 修复异常处理 | 健壮性 |
| BE-034 | 迁移到 lifespan | 框架兼容 |
| FE-002-009 | 清理未使用导出 | 代码整洁 |
| FE-020-021 | 修复 Ant Design 属性 | UI 一致性 |
| AR-002-006 | 确认 v2 文件替代关系 | 代码整洁 |

---

**文档版本历史**:

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2026-05-18 | 初始版本，基于代码分析梳理 |
