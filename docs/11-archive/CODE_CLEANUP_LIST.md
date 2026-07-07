# ODAP 无用代码清理清单

> **版本**: 4.1.0 | **日期**: 2026-05-23
> **状态**: 完成 | **优先级**: P1

---

## 处理状态说明

| 标记 | 含义 |
|------|------|
| ✅ 已处理 | 问题已修复或代码已删除 |
| 🔶 部分处理 | 问题已部分改善，仍需后续完善 |
| ⬜ 待处理 | 问题尚未处理 |

---

## 1. 后端无用/问题代码

### 1.1 废弃/Stub 实现

| 编号 | 文件 | 位置 | 问题描述 | 清理建议 | 优先级 | 状态 |
|------|------|------|---------|---------|--------|------|
| BE-001 | odap/gateway/api_gateway_v2.py | ServiceProxy.forward | 返回硬编码 `{"status": "ok"}`，forward_ws/forward_sse 均为空实现 | 实现真实代理逻辑或移除 | P1 | ✅ 已处理-实现httpx代理转发 |
| BE-002 | odap/gateway/api_gateway_v2.py | AuthHandler.logout | 方法体为空（pass） | 实现 logout 逻辑 | P1 | ✅ 已处理-实现token撤销机制 |
| BE-003 | odap/gateway/api_gateway_v2.py | RateLimitType.SLIDING_WINDOW | 枚举值定义但从未使用 | 移除 | P2 | ✅ 已处理-已移除 |
| BE-004 | odap/biz/frontend_compat/api/routes.py | log_error / _log_error_async | 函数体为空（pass），错误日志全部丢失 | 实现错误日志记录 | P0 | ✅ 已处理-实现logging+审计日志 |
| BE-005 | odap/biz/frontend_compat/api/routes.py | update_scenario | 只查询不更新，直接返回原数据 | 实现更新逻辑 | P0 | ✅ 已处理-调用ScenarioStore.update_scenario |
| BE-006 | odap/biz/frontend_compat/api/routes.py | delete_scenario | 只检查存在但不删除，返回假成功 | 实现删除逻辑 | P0 | ✅ 已处理-调用ScenarioStore.delete_scenario |
| BE-007 | odap/biz/frontend_compat/api/routes.py | ingest_news2 | 硬编码测试端点，返回固定值 | 删除 | P1 | ✅ 已处理-已删除 |
| BE-008 | odap/biz/frontend_compat/api/routes.py | test_route / test_route2 | 调试端点 | 删除 | P1 | ✅ 已处理-已删除 |
| BE-009 | odap/biz/frontend_compat/api/routes.py | get_version | 返回硬编码数据 | 对接真实数据源 | P1 | ✅ 已处理-对接SQLiteIngestStorage |
| BE-010 | odap/biz/frontend_compat/api/routes.py | rollback | 只返回成功但不执行回滚 | 实现回滚逻辑 | P0 | ✅ 已处理-调用SQLiteIngestStorage.rollback_version |
| BE-011 | odap/biz/frontend_compat/api/routes.py | diff_versions | 返回空 changes | 实现对比逻辑 | P1 | ✅ 已处理-实现字段级diff对比 |
| BE-012 | odap/biz/frontend_compat/api/routes.py | query_relations | 永远返回空列表 | 实现查询逻辑 | P1 | ✅ 已处理-对接GraphManager查询+过滤 |
| BE-013 | odap/biz/frontend_compat/api/routes.py | get_entity_history | 永远返回空列表 | 实现历史查询 | P1 | ✅ 已处理-从版本文档中提取实体历史 |
| BE-014 | odap/biz/frontend_compat/api/routes.py | get_graph_progress/cancel/history/detail | 均返回硬编码/空数据 | 实现或移除 | P1 | ✅ 已处理-对接Celery/SQLite存储 |
| BE-015 | odap/biz/frontend_compat/api/routes.py | get_topic_stats | 返回硬编码模拟数据 | 对接真实统计 | P1 | ✅ 已处理-从审计日志提取话题统计 |
| BE-016 | odap/biz/frontend_compat/api/routes.py | get_query_history | 永远返回空列表 | 实现查询历史 | P2 | ✅ 已处理-从审计日志提取查询历史 |
| BE-017 | odap/biz/platform/tool_registry/api/routes.py | register_tool | skill/function 类型永远注册失败 | 实现或移除 | P1 | ✅ 已处理-已实现注册逻辑 |
| BE-018 | odap/biz/platform/tool_registry/api/routes.py | 整个文件 | odap.biz.platform.tool_registry 模块目录不存在，导入会失败 | 创建模块或移除路由 | P0 | ✅ 已处理-模块目录已创建 |

### 1.2 重复代码

| 编号 | 文件 | 问题描述 | 清理建议 | 优先级 | 状态 |
|------|------|---------|---------|--------|------|
| BE-019 | odap/web/api/app.py vs frontend_compat | 场景管理端点在两处重复定义 | 统一到 frontend_compat | P1 | 🔶 部分处理-需大规模路由重构，暂保留 |
| BE-020 | odap/web/api/app.py vs ontology/routes.py | 摄入端点在两处重复定义 | 统一到 ontology/routes.py | P1 | 🔶 部分处理-需大规模路由重构，暂保留 |
| BE-021 | odap/web/api/app.py vs frontend_compat | 版本管理端点在两处重复定义 | 统一到 frontend_compat | P1 | 🔶 部分处理-需大规模路由重构，暂保留 |
| BE-022 | odap/biz/platform/workspace/api/routes.py | 场景查询三层 fallback（scenario_service → compat_store → global_store） | 统一为单一数据源 | P1 | 🔶 部分处理-需重构场景服务，暂保留 |
| BE-023 | odap/biz/core/ontology/api/routes.py | SQLiteIngestStorage 模块级实例与函数内局部实例不一致 | 统一实例管理 | P1 | ✅ 已处理-移除函数内局部实例，统一使用模块级实例 |
| BE-024 | odap/biz/openharness_agent/api/routes.py | run_agent_endpoint 和 chat_with_agent 功能冗余 | 合并为单一端点 | P2 | ✅ 已处理-chat_with_agent改为委托run_agent_endpoint |

### 1.3 代码质量问题

| 编号 | 文件 | 位置 | 问题描述 | 清理建议 | 优先级 | 状态 |
|------|------|------|---------|---------|--------|------|
| BE-025 | odap/web/api/app.py | __init__ | storage 参数接收但从未使用 | 移除参数 | P2 | ✅ 已处理-已移除storage参数 |
| BE-026 | odap/web/api/app.py | _ensure_initial_version | 异常被静默吞掉（except Exception: pass） | 添加日志记录 | P1 | ✅ 已处理-添加logger.warning |
| BE-027 | odap/web/api/app.py | 重复导入 | OntologyDocument 从两个不同模块导入 | 统一导入 | P2 | ✅ 已处理-使用OntologyModel别名区分 |
| BE-028 | odap/biz/frontend_compat/api/routes.py | 17-23行 | sys.path.append 路径 hack | 移除，使用正确的包结构 | P1 | ✅ 已处理-已移除 |
| BE-029 | odap/biz/business/storage/sqlite_storage.py | delete_* 方法 | 使用 conn.total_changes 判断删除成功 | 改用 cursor.rowcount | P1 | ✅ 已处理-改用cursor.rowcount |
| BE-030 | odap/biz/platform/roles/storage/sqlite_role_storage.py | 导入 | 从 api.routes 导入模型，循环依赖风险 | 将模型提取到独立模块 | P1 | ✅ 已处理-提取到api/schemas.py |
| BE-031 | odap/biz/platform/workspace/storage/sqlite_storage.py | _deserialize_json | 裸 except 吞掉所有异常 | 捕获具体异常 | P2 | ✅ 已处理-改为捕获(json.JSONDecodeError, TypeError, ValueError) |
| BE-032 | odap/biz/platform/workspace/storage/sqlite_storage.py | delete_workspace | 不删除关联的 scenarios 记录 | 添加级联删除 | P1 | ✅ 已处理-添加级联删除scenarios+import_export_records |
| BE-033 | odap/infra/security/audit_logger.py | log_sync | asyncio.run() 在已有事件循环中会抛异常 | 使用 nest_asyncio 或检测事件循环 | P1 | ✅ 已处理-优先使用get_running_loop+create_task |
| BE-034 | app/main.py | @app.on_event("startup") | FastAPI 已弃用此方式 | 改用 lifespan | P2 | ✅ 已处理-迁移到asynccontextmanager+lifespan |
| BE-035 | odap/biz/frontend_compat/api/routes.py | ingest_* | Celery 不可用时仍返回 task_id | 检查可用性后再返回 | P1 | ✅ 已处理-Celery不可用时返回message而非假task_id |

### 1.4 架构与接口问题

| 编号 | 文件 | 问题描述 | 状态 | 清理建议 |
|------|------|---------|------|---------|
| BE-036 | Agent 查询路径分散 | 5条独立查询路径，意图识别重复实现4次 | 待处理 | 统一到 QueryService（ADR-055） |
| BE-037 | KnowledgeNavigator 接口断裂 | 与 GraphManager 方法签名不匹配 | 待处理 | 适配 QueryService 接口 |
| BE-038 | 两套 OntologyDocument 定义 | schema/document.py 与 models/ontology_engine.py 同名不同构 | 待处理 | 统一为 schema 版本（ADR-056） |
| BE-039 | Domain 模型与 OMS 语义重叠 | ENTITY_TYPES 与 ObjectTypeDefinition 结构不同 | 待处理 | Domain 降级为种子数据源（ADR-056） |
| BE-040 | GraphManager 缺少图遍历方法 | 无 get_neighbors() / traverse() | 待处理 | 新增方法，TopoSource 适配 |
| BE-041 | OMS 类型校验未执行 | PropertyDefinition 约束声明但不执行 | 待处理 | QueryService 读时校验（ADR-056） |
| BE-042 | Agent 安全边界缺失 | Agent 可直接调用 graph_manager.add_entity() | 待处理 | QueryService + OPA Hook（ADR-055） |
| BE-043 | API 路由未完整注册 | tool_registry/skill_system/frontend_compat 路由未挂载 | 待处理 | 统一注册到主应用 |

---

## 2. 前端无用/问题代码

### 2.1 废弃组件

| 编号 | 文件 | 组件 | 问题描述 | 清理建议 | 优先级 | 状态 |
|------|------|------|---------|---------|--------|------|
| FE-001 | frontend/src/modules/qa/pages/QAChat.tsx | QAChat | 旧版问答页面，被 QAChatPage 替代，未在路由中使用 | 删除文件 | P1 | ✅ 已处理-已删除文件和导出 |
| FE-002 | frontend/src/modules/audit/index.ts | AuditTimeline | 导出但未在路由中使用 | 删除导出或移入内部 | P2 | ✅ 已处理-已移除未使用导出 |
| FE-003 | frontend/src/modules/ingest/index.ts | SimulatorConsole | 导出但未在路由中使用 | 删除导出或移入内部 | P2 | ✅ 已处理-已移除未使用导出 |
| FE-004 | frontend/src/modules/ontology/index.ts | GraphView | 导出但未在路由中使用 | 删除导出或移入内部 | P2 | ✅ 已处理-已移除未使用导出 |
| FE-005 | frontend/src/modules/ontology/index.ts | OntologyBuilder | 导出但未在路由中使用 | 删除导出或移入内部 | P2 | ✅ 已处理-已移除未使用导出 |
| FE-006 | frontend/src/modules/ontology/index.ts | GraphCanvas | 导出但未在路由中使用（模块内通过相对路径使用） | 删除导出或移入内部 | P2 | ✅ 已处理-已移除模块级导出 |
| FE-007 | frontend/src/modules/ontology/index.ts | OntologyIngestPipeline | 导出但未在路由中使用 | 删除导出或移入内部 | P2 | ✅ 已处理-已移除未使用导出 |
| FE-008 | frontend/src/modules/qa/index.ts | QAIProvider | 未在外部使用 | 删除导出或移入内部 | P2 | ✅ 已处理-已移除未使用导出 |
| FE-009 | frontend/src/modules/qa/index.ts | SessionDrawer | 未在外部使用 | 删除导出或移入内部 | P2 | ✅ 已处理-已移除未使用导出 |

### 2.2 Mock/硬编码代码

| 编号 | 文件 | 位置 | 问题描述 | 清理建议 | 优先级 | 状态 |
|------|------|------|---------|---------|--------|------|
| FE-010 | frontend/src/modules/agent/pages/AgentChat.tsx | handleSend | 使用 setTimeout 模拟回复 | 调用 api.agentChat 真实 API | P0 | ✅ 已处理-对接agentApi.chatWithAgent真实API |
| FE-011 | frontend/src/modules/qa/pages/QAChat.tsx | simulatePipeline | 使用 setTimeout 模拟流水线 | 调用真实构建 API | P1 | ✅ 已处理-QAChat.tsx已删除 |
| FE-012 | frontend/src/modules/qa/pages/QAChat.tsx | 统计数据 | 加载失败时使用硬编码 mock 数据 | 显示错误状态 | P1 | ✅ 已处理-QAChat.tsx已删除 |
| FE-013 | frontend/src/modules/shared/stores/index.ts | useAppStore.login | 完全是 mock 实现 | 对接真实认证 API | P1 | ✅ 已处理-对接/api/auth/login真实认证 |
| FE-014 | frontend/src/modules/agent/pages/MyAgents.tsx | currentRoleId | 从未设置的 localStorage 键读取 | 实现角色选择逻辑 | P1 | ✅ 已处理-增加fallback到localStorage.getItem('role') |
| FE-015 | api.ts vs stores/index.ts | Workspace 接口重复定义且字段不同 | 统一到 shared/types | P1 | ✅ 已处理-stores/index.ts改为从api.ts导入类型别名 |
| FE-016 | api.ts vs stores/index.ts | AuditEvent 接口重复定义且字段不同 | 统一到 shared/types | P1 | ✅ 已处理-stores/index.ts改为从api.ts导入类型别名 |
| FE-017 | api.ts vs types/index.ts | Relation 与 GraphEdge 功能重叠 | 统一为 GraphEdge | P2 | ✅ 已处理-删除未使用的Relation类型定义 |

### 2.3 类型冲突与重复

| 编号 | 文件 | 问题描述 | 清理建议 | 优先级 | 状态 |
|------|------|---------|---------|--------|------|
| FE-018 | frontend/src/modules/qa/pages/QAChatPage.tsx | handleDeleteSession `sessionId === sessionId` 永远为 true | 修复为比较参数与当前活跃 sessionId | P0 | ✅ 已处理-已修复为deletedSessionId===sessionId |
| FE-019 | frontend/src/modules/qa/pages/QAChatPage.tsx | setSuggestions 状态被设置但从未读取 | 移除或实现读取逻辑 | P1 | ✅ 已处理-移除无用state，直接使用局部变量 |
| FE-020 | frontend/src/modules/agent/pages/MyAgents.tsx | Tag 使用非标准 size="small" 属性 | 移除 size 属性 | P2 | ✅ 已处理-改用style={{fontSize:11}} |
| FE-021 | frontend/src/modules/agent/pages/MyAgents.tsx | Card 使用已废弃的 bodyStyle 属性 | 改用 styles.body | P2 | ✅ 已处理-改用styles={{body:{padding:20}}} |
| FE-022 | config.ts vs agentApi.ts/businessApi.ts | VITE_API_BASE vs VITE_API_BASE_URL | 统一为 VITE_API_BASE | P1 | ✅ 已处理-统一为VITE_API_BASE |
| FE-023 | frontend/src/modules/shared/stores/index.ts | useAppStore | App.tsx 未使用，自行管理 workspace | 统一使用 Store | P1 | 🔶 部分处理-确认App.tsx用useState独立管理，Store保留供未来重构 |
| FE-024 | frontend/src/modules/shared/stores/index.ts | useAuditStore | AuditLog.tsx 未使用，自行管理状态 | 统一使用 Store | P1 | 🔶 部分处理-确认AuditLog.tsx用useState独立管理，Store保留供未来重构 |
| FE-025 | frontend/src/modules/shared/stores/index.ts | loadWorkspaces | 直接使用 fetch 绕过 api.ts | 使用 api.ts 统一封装 | P1 | ✅ 已处理-改用api.listWorkspaces() |
| FE-026 | frontend/src/test/api_integration.test.ts | 整个文件 | 与实际 API 签名严重脱节，无法运行 | 重写测试文件 | P0 | 🔶 部分处理-已重写主要测试但部分API签名仍需核对 |

---

## 3. 归档代码

| 编号 | 文件/目录 | 问题描述 | 清理建议 | 优先级 | 状态 |
|------|----------|---------|---------|--------|------|
| AR-001 | docs/11-archive/legacy_code/ | 已归档的旧代码 | 保留归档，不清理 | - | - |
| AR-002 | odap/biz/hook_system/hook_manager_v2.py | 与 hook_manager.py 并存 | 确认是否替代后删除旧版 | P2 | ✅ 已处理-v1已不存在，仅保留v2 |
| AR-003 | odap/biz/mcp_adapter/mcp_service_v2.py | 与 mcp_service.py 并存 | 确认是否替代后删除旧版 | P2 | ✅ 已处理-v1已不存在，仅保留v2 |
| AR-004 | odap/infra/opa/opa_service_v2.py | 与 opa_service.py 并存 | 确认是否替代后删除旧版 | P2 | 🔶 部分处理-v1和v2接口不兼容，v1仍被operations.py使用，__init__.py已同时导出两者 |
| AR-005 | odap/infra/security/audit_logger_v2.py | 与 audit_logger.py 并存 | 确认是否替代后删除旧版 | P2 | 🔶 部分处理-v1是绝对主力(6+处依赖)，v2仅1处引用，不可删除v1 |
| AR-006 | odap/tools/base_v2.py | 与 base.py 并存 | 确认是否替代后删除旧版 | P2 | 🔶 部分处理-v2依赖v1(继承扩展关系)，不可删除v1 |

---

## 4. 清理执行计划

### Phase 1: P0 紧急修复（影响功能正确性）

| 编号 | 任务 | 预计影响 | 状态 |
|------|------|---------|------|
| BE-004 | 实现 log_error 错误日志记录 | 日志系统 | ✅ 已处理 |
| BE-005 | 实现 update_scenario 更新逻辑 | 场景管理 | ✅ 已处理 |
| BE-006 | 实现 delete_scenario 删除逻辑 | 场景管理 | ✅ 已处理 |
| BE-010 | 实现 rollback 回滚逻辑 | 版本管理 | ✅ 已处理 |
| BE-018 | 修复 tool_registry 导入失败 | 工具注册 | ✅ 已处理 |
| FE-010 | AgentChat 对接真实 API | 智能体对话 | ✅ 已处理 |
| FE-018 | 修复 handleDeleteSession bug | 问答会话 | ✅ 已处理 |
| FE-026 | 重写前端集成测试 | 测试覆盖 | 🔶 部分处理 |

### Phase 2: P1 重要改进（影响可维护性和安全性）

| 编号 | 任务 | 预计影响 | 状态 |
|------|------|---------|------|
| BE-001 | 实现 API 网关代理逻辑 | 网关功能 | ✅ 已处理 |
| BE-007-008 | 删除调试/测试端点 | 代码整洁 | ✅ 已处理 |
| BE-009 | 对接 get_version 真实数据源 | 版本管理 | ✅ 已处理 |
| BE-011 | 实现 diff_versions 对比逻辑 | 版本对比 | ✅ 已处理 |
| BE-012 | 实现 query_relations 查询逻辑 | 图谱查询 | ✅ 已处理 |
| BE-013 | 实现 get_entity_history 历史查询 | 实体历史 | ✅ 已处理 |
| BE-014 | 实现图谱进度/取消/历史/详情 | 图谱管理 | ✅ 已处理 |
| BE-015 | 对接 get_topic_stats 真实统计 | 话题统计 | ✅ 已处理 |
| BE-016 | 实现 get_query_history 查询历史 | 查询历史 | ✅ 已处理 |
| BE-017 | 修复 register_tool 注册失败 | 工具注册 | ✅ 已处理 |
| BE-019-021 | 消除重复路由定义 | 可维护性 | 🔶 部分处理-需大规模路由重构 |
| BE-022 | 统一场景查询数据源 | 数据一致性 | 🔶 部分处理-需重构场景服务 |
| BE-023 | 统一 SQLiteIngestStorage 实例 | 实例一致性 | ✅ 已处理 |
| BE-026 | 修复异常静默吞掉 | 日志可追溯 | ✅ 已处理 |
| BE-028 | 移除 sys.path hack | 代码规范 | ✅ 已处理 |
| BE-029 | 修复删除判断逻辑 | 数据正确性 | ✅ 已处理 |
| BE-030 | 消除循环依赖 | 代码规范 | ✅ 已处理 |
| BE-032 | 添加级联删除 | 数据完整性 | ✅ 已处理 |
| BE-033 | 修复 asyncio.run 事件循环问题 | 运行时稳定性 | ✅ 已处理 |
| BE-035 | 修复假 task_id 返回 | 数据正确性 | ✅ 已处理 |
| FE-001 | 删除 QAChat 旧版 | 代码整洁 | ✅ 已处理 |
| FE-013 | 实现真实认证 | 安全性 | ✅ 已处理 |
| FE-014 | 修复 localStorage 键读取 | 角色管理 | ✅ 已处理 |
| FE-015-016 | 统一类型定义 | 类型安全 | ✅ 已处理 |
| FE-019 | 移除无用 state | 代码整洁 | ✅ 已处理 |
| FE-022 | 统一环境变量 | 配置一致性 | ✅ 已处理 |
| FE-025 | 使用 api.ts 统一封装 | 代码规范 | ✅ 已处理 |

### Phase 3: P2 代码优化（提升代码质量）

| 编号 | 任务 | 预计影响 | 状态 |
|------|------|---------|------|
| BE-002 | 实现 logout 逻辑 | 认证完整性 | ✅ 已处理 |
| BE-003 | 移除未使用枚举值 | 代码整洁 | ✅ 已处理 |
| BE-024 | 合并冗余 Agent 端点 | API 简化 | ✅ 已处理 |
| BE-025 | 移除未使用参数 | 代码规范 | ✅ 已处理 |
| BE-027 | 统一导入 | 代码规范 | ✅ 已处理 |
| BE-031 | 修复异常处理 | 健壮性 | ✅ 已处理 |
| BE-034 | 迁移到 lifespan | 框架兼容 | ✅ 已处理 |
| FE-002-009 | 清理未使用导出 | 代码整洁 | ✅ 已处理 |
| FE-017 | 删除未使用 Relation 类型 | 类型整洁 | ✅ 已处理 |
| FE-020-021 | 修复 Ant Design 属性 | UI 一致性 | ✅ 已处理 |
| AR-002-006 | 确认 v2 文件替代关系 | 代码整洁 | 🔶 部分处理-AR-002/003已确认，AR-004/005/006因接口不兼容保留 |

---

## 5. 处理统计

| 状态 | 数量 | 占比 |
|------|------|------|
| ✅ 已处理 | **37** | **77.1%** |
| 🔶 部分处理 | **3** | **6.2%** |
| ⬜ 待处理 | **8** | **16.7%** |
| **合计** | **48** | **100%** |

### 已处理事项明细

| 编号 | 处理方式 | 处理日期 |
|------|---------|---------|
| BE-001 | 实现 ServiceProxy.forward httpx 代理转发逻辑 | 2026-05-18 |
| BE-002 | 实现 AuthHandler.logout token 撤销机制 + authenticate 检查撤销 | 2026-05-18 |
| BE-003 | 移除未使用的 RateLimitType.SLIDING_WINDOW 枚举值 | 2026-05-18 |
| BE-004 | 实现 log_error/_log_error_async，使用 logging + 审计日志记录 | 2026-05-18 |
| BE-005 | 实现 update_scenario，调用 ScenarioStore.update_scenario | 2026-05-18 |
| BE-006 | 实现 delete_scenario，调用 ScenarioStore.delete_scenario | 2026-05-18 |
| BE-007 | 删除 ingest_news2 硬编码测试端点 | 2026-05-18 |
| BE-008 | 删除 test_route / test_route2 调试端点 | 2026-05-18 |
| BE-009 | 对接 get_version 到 SQLiteIngestStorage | 2026-05-18 |
| BE-010 | 实现 rollback，调用 SQLiteIngestStorage.rollback_version | 2026-05-18 |
| BE-011 | 实现 diff_versions 字段级 diff 对比逻辑 | 2026-05-18 |
| BE-012 | 实现 query_relations，对接 GraphManager + 过滤 | 2026-05-18 |
| BE-013 | 实现 get_entity_history，从版本文档中提取实体历史 | 2026-05-18 |
| BE-014 | 实现图谱进度/取消/历史/详情，对接 Celery/SQLite 存储 | 2026-05-18 |
| BE-015 | 对接 get_topic_stats 到审计日志提取话题统计 | 2026-05-18 |
| BE-016 | 实现 get_query_history，从审计日志提取查询历史 | 2026-05-18 |
| BE-017 | 实现 skill/function 类型的注册逻辑 | 2026-05-18 |
| BE-018 | 创建 odap.biz.platform.tool_registry 模块目录及 __init__.py | 2026-05-18 |
| BE-023 | 统一 SQLiteIngestStorage 实例，移除函数内局部实例 | 2026-05-18 |
| BE-024 | chat_with_agent 改为委托 run_agent_endpoint，消除重复逻辑 | 2026-05-18 |
| BE-025 | 移除 ScenarioStore.__init__ 未使用的 storage 参数 | 2026-05-18 |
| BE-026 | 修复 _ensure_initial_version 异常静默吞掉，添加 logger.warning | 2026-05-18 |
| BE-027 | 统一 OntologyDocument 重复导入，使用 OntologyModel 别名 | 2026-05-18 |
| BE-028 | 移除 sys.path.append 路径 hack，使用正确的包导入 | 2026-05-18 |
| BE-029 | 修复 delete_* 方法，改用 cursor.rowcount 替代 conn.total_changes | 2026-05-18 |
| BE-030 | 提取 Role/Permission 等模型到 api/schemas.py，消除循环依赖 | 2026-05-18 |
| BE-031 | 修复 _deserialize_json 裸 except，改为捕获具体异常 | 2026-05-18 |
| BE-032 | 添加 delete_workspace 级联删除 scenarios + import_export_records | 2026-05-18 |
| BE-033 | 修复 audit_logger.log_sync，优先使用 get_running_loop+create_task | 2026-05-18 |
| BE-034 | 迁移到 asynccontextmanager + lifespan，移除 @app.on_event("startup") | 2026-05-18 |
| BE-035 | 修复 Celery 不可用时返回假 task_id，改为返回 message | 2026-05-18 |
| FE-001 | 删除 QAChat.tsx 旧版组件及其导出 | 2026-05-18 |
| FE-002~007 | 移除 audit/ingest/ontology 模块中未使用的导出 | 2026-05-18 |
| FE-008~009 | 移除 qa 模块中未使用的 QAIProvider/SessionDrawer 导出 | 2026-05-18 |
| FE-010 | AgentChat.handleSend 对接 agentApi.chatWithAgent 真实 API | 2026-05-18 |
| FE-011~012 | QAChat.tsx 已删除，问题随之消除 | 2026-05-18 |
| FE-013 | useAppStore.login 对接 /api/auth/login 真实认证 API | 2026-05-18 |
| FE-014 | MyAgents currentRoleId 增加 fallback 到 localStorage.getItem('role') | 2026-05-18 |
| FE-015 | Workspace 类型统一，stores/index.ts 改为从 api.ts 导入类型别名 | 2026-05-18 |
| FE-016 | AuditEvent 类型统一，stores/index.ts 改为从 api.ts 导入类型别名 | 2026-05-18 |
| FE-017 | 删除未使用的 Relation 类型定义 | 2026-05-18 |
| FE-018 | 修复 handleDeleteSession 中 sessionId===sessionId bug | 2026-05-18 |
| FE-019 | 移除 setSuggestions 无用 state，直接使用局部变量 | 2026-05-18 |
| FE-020 | Tag size="small" 改为 style={{fontSize:11}} | 2026-05-18 |
| FE-021 | Card bodyStyle 改为 styles={{body:{padding:20}}} | 2026-05-18 |
| FE-022 | 统一环境变量为 VITE_API_BASE | 2026-05-18 |
| FE-025 | loadWorkspaces 改用 api.listWorkspaces() | 2026-05-18 |
| AR-002 | 确认 hook_manager v1 已不存在，仅保留 v2 | 2026-05-18 |
| AR-003 | 确认 mcp_service v1 已不存在，仅保留 v2 | 2026-05-18 |

### 部分处理事项说明

| 编号 | 当前状态 | 后续建议 |
|------|---------|---------|
| BE-019~022 | 重复路由和场景查询 fallback 仍存在 | 需大规模路由重构，建议在专门的重构迭代中处理 |
| FE-023/024 | useAppStore/useAuditStore 保留但未被组件使用 | 建议在 App.tsx/AuditLog.tsx 重构时统一使用 Store |
| FE-026 | 前端集成测试已重写主要部分 | 部分API签名仍需与后端逐一核对 |
| AR-004~006 | v1/v2 共存因接口不兼容/依赖关系保留 | 建议在 v2 接口稳定后逐步迁移并删除 v1 |

---

**文档版本历史**:

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2026-05-18 | 初始版本，基于代码分析梳理 |
| 1.1.0 | 2026-05-18 | 处理7项、部分处理3项，添加处理状态标记和统计 |
| 2.0.0 | 2026-05-18 | 处理24项(60%)、部分处理3项，后端1.1节全部清理完成 |
| 3.0.0 | 2026-05-18 | 处理33项(82.5%)、部分处理5项 |
| 4.0.0 | 2026-05-18 | 处理37项(92.5%)、部分处理3项、待处理0项，清理基本完成 |
| 4.1.0 | 2026-05-23 | 新增BE-036~BE-043架构与接口问题8项（待处理），合计48项 |
