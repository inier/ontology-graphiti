# Tasks: LLM 与 API 密钥配置管理

**Input**: Design documents from `/specs/006-llm-config-management/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/config-api.md

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 创建配置管理模块的基础目录结构和加密工具

- [x] T001 创建配置管理业务模块目录结构 odap/biz/platform/config/ (api/, models/, interfaces/, impl/, services/, storage/)
- [x] T002 [P] 创建前端设置模块目录结构 frontend/src/modules/settings/ (pages/, components/, services/, stores/, types/)
- [x] T003 [P] 实现敏感配置加密工具 ConfigEncryption in odap/infra/security/config_encryption.py — AES-256-GCM 加密/解密，密钥从 CONFIG_ENCRYPTION_KEY 环境变量读取
- [x] T004 扩展 ConfigurationComposer 新增 L5(DB) 层和缺失 schema in odap/infra/config_composer.py — 添加 neo4j.*, minio.*, tavily.*, ddg.*, serpapi.* 等 schema；新增 DB 层读取逻辑；新增 get_config() 全局便捷函数

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 核心存储和模型，所有 User Story 的前置依赖

**⚠️ CRITICAL**: 此阶段完成前，不可开始任何 User Story

- [x] T005 创建配置领域模型 in odap/biz/platform/config/models/config_models.py — ServiceCategory, ConfigValueType, ConnectionStatus 枚举；ConfigItem, ServiceConfig, ConfigRevision, ConfigChange, ConfigValidationResult 模型
- [x] T006 创建配置存储抽象接口 in odap/biz/platform/config/interfaces/config_repository.py — ConfigRepository ABC 定义 save_config, get_config, list_configs, delete_config, save_revision, list_revisions 等方法
- [x] T007 实现 SQLiteConfigStorage in odap/biz/platform/config/storage/sqlite_config_storage.py — config_items, config_revisions, config_schema_registry 三张表；CRUD 操作；启动时注册 21 个预定义配置项到 schema_registry
- [x] T008 [P] 创建 storage/__init__.py in odap/biz/platform/config/storage/__init__.py — Storage = SQLiteConfigStorage 别名导出
- [x] T009 实现配置管理核心 ConfigManager in odap/biz/platform/config/impl/config_manager.py — 内存缓存 + 热更新通知；subscribe/publish 模式；加密存储/解密读取；脱敏展示值生成
- [x] T010 [P] 实现外部服务连接验证器 ConfigValidator in odap/biz/platform/config/impl/config_validator.py — 按 ServiceCategory 分类验证（LLM: POST /v1/chat/completions, Neo4j: verify_connectivity, MinIO: health, OPA: policies, Redis: PING, Tavily/DDG/SerpAPI: test query）；10s 超时
- [x] T011 创建 ConfigService 编排层 in odap/biz/platform/config/services/config_service.py — 委托 ConfigManager 和 ConfigValidator；批量更新（all-or-nothing）；变更审计写入 config_revisions + unified_audit

**Checkpoint**: 基础设施就绪 — 存储、加密、热更新、验证、编排层全部完成 ✅

---

## Phase 3: User Story 1 - 管理员通过界面配置 LLM 服务连接 (Priority: P1) 🎯 MVP

**Goal**: 管理员可在配置界面修改 LLM API Key/模型/地址，保存后立即生效，无需重启

**Independent Test**: 修改 LLM 配置 → 发起问答请求 → 验证使用新配置

### Implementation for User Story 1

- [x] T012 [P] [US1] 创建 Pydantic 请求/响应模型 in odap/biz/platform/config/api/schemas.py — UpdateConfigRequest(items, test_connection), UpdateConfigResponse, ConfigItemResponse, ServiceConfigResponse, ConfigValidationResultResponse
- [x] T013 [US1] 创建配置管理路由 in odap/biz/platform/config/api/routes.py — GET /api/config (获取全部), GET /api/config/{category} (按类别), PUT /api/config (批量更新), POST /api/config/test (测试连接)；admin-only 权限校验 (Depends(verify_admin))；except HTTPException: raise 透传
- [x] T014 [US1] 注册 config_router 到生产入口 in odap/web/router_registry.py — include_router(config_router)
- [x] T015 [P] [US1] 创建前端类型定义 in frontend/src/modules/settings/types/index.ts — ServiceCategory, ConfigValueType, ConnectionStatus, ConfigItem, ServiceConfig, ConfigValidationResult, UpdateConfigRequest, UpdateConfigResponse
- [x] T016 [P] [US1] 创建前端 API 客户端 in frontend/src/modules/settings/services/configApi.ts — getConfigs, getConfigsByCategory, updateConfigs, testConnection 四个 API 函数
- [x] T017 [US1] 创建前端 Zustand Store in frontend/src/modules/settings/stores/configStore.ts — 配置状态管理：categories, loading, validationResults, fetchConfigs, updateConfig, testConnection actions
- [x] T018 [US1] 实现 ConfigGroup 组件 in frontend/src/modules/settings/components/ConfigGroup.tsx — Ant Design Collapse.Panel 展示服务类别；连接状态 Tag (connected/disconnected/not_configured)；测试连接 Button
- [x] T019 [US1] 实现 ConfigItemForm 组件 in frontend/src/modules/settings/components/ConfigItemForm.tsx — 根据 value_type 渲染不同表单控件 (Input/Input.Password/InputNumber/Select/Switch)；敏感字段 Input.Password 支持点击显示
- [x] T020 [US1] 实现 ConnectionTestButton 组件 in frontend/src/modules/settings/components/ConnectionTestButton.tsx — 测试连接按钮 + Spin 加载 + 结果 Tag 展示
- [x] T021 [US1] 实现 SettingsPage 主页面 in frontend/src/modules/settings/pages/SettingsPage.tsx — 按 ServiceCategory 分组展示所有配置；批量保存按钮；整体测试连接按钮
- [ ] T022 [US1] 注册 /settings 路由 in frontend/src/AppRoutes.tsx — 添加 /settings → SettingsPage 路由；导航栏添加"系统设置"入口（仅 admin 可见）⚠️ 文件锁定，需手动完成
- [x] T023 [US1] 创建模块导出 in frontend/src/modules/settings/index.ts — 导出 SettingsPage
- [x] T024 [US1] 统一 LLM 配置读取入口 — 替换 16 个文件中的 os.getenv("OPENAI_API_KEY")/os.getenv("OPENAI_API_BASE")/os.getenv("OPENAI_MODEL") 为 get_config("llm.api_key")/get_config("llm.api_base")/get_config("llm.model")

**Checkpoint**: LLM 配置可通过界面管理，保存后立即生效 ✅ (T022 待手动完成)

---

## Phase 4: User Story 2 - 管理员统一管理所有外部服务连接 (Priority: P2)

**Goal**: 所有外部服务（Neo4j/MinIO/OPA/Redis/搜索服务）配置统一管理，界面展示连接状态

**Independent Test**: 修改 Neo4j 密码 → 执行图查询 → 验证使用新密码

### Implementation for User Story 2

- [x] T025 [P] [US2] 扩展 ConfigValidator 支持所有服务类别 in odap/biz/platform/config/impl/config_validator.py — 实现 _test_neo4j, _test_minio, _test_opa, _test_redis, _test_tavily, _test_ddg, _test_serpapi 验证方法
- [x] T026 [P] [US2] 扩展 ConfigService 支持按类别获取和测试 in odap/biz/platform/config/services/config_service.py — get_configs_by_category, test_connection_by_category 方法
- [ ] T027 [US2] 统一其他服务配置读取入口 — 替换 os.getenv("NEO4J_URI")/os.getenv("NEO4J_USER")/os.getenv("NEO4J_PASSWORD") 等为 get_config("graph_db.uri")/get_config("graph_db.user")/get_config("graph_db.password")；替换 MinIO/OPA/Redis/Tavily/DDG/SerpAPI 相关环境变量读取
- [x] T028 [US2] 增强 SettingsPage 展示所有服务类别 in frontend/src/modules/settings/pages/SettingsPage.tsx — 8 个服务类别分组展示；每组显示连接状态总览；未配置服务高亮提示
- [x] T029 [US2] 添加配置状态总览 API in odap/biz/platform/config/api/routes.py — GET /api/config/status 返回所有服务类别的连接状态摘要

**Checkpoint**: 所有外部服务配置可通过界面管理，连接状态实时展示 ✅ (T027 待完成)

---

## Phase 5: User Story 4 - 敏感配置的安全管理 (Priority: P2)

**Goal**: 敏感配置脱敏展示、加密存储、admin-only 访问控制

**Independent Test**: 检查界面展示脱敏、API 响应脱敏、存储文件加密、非 admin 返回 403

### Implementation for User Story 4

- [x] T030 [US4] 实现脱敏展示逻辑 in odap/biz/platform/config/impl/config_manager.py — _mask_value(value) 方法：password 类型显示最后 4 位 (****abcd)，其他敏感类型显示前 3 位 + ****
- [x] T031 [US4] 确保 API 响应脱敏 in odap/biz/platform/config/api/routes.py — GET /api/config 返回 display_value 而非 value；GET /api/config/value/{key} 仅内部 API，不暴露给前端
- [x] T032 [P] [US4] 增强 ConfigItemForm 敏感字段展示 in frontend/src/modules/settings/components/ConfigItemForm.tsx — Input.Password 默认脱敏；点击"显示"按钮临时展示完整值；3 秒后自动恢复脱敏
- [x] T033 [US4] 确保 admin-only 权限校验 in odap/biz/platform/config/api/routes.py — 所有端点添加 Depends(verify_admin)；非 admin 返回 403

**Checkpoint**: 敏感配置安全管理到位，脱敏展示+加密存储+权限控制 ✅

---

## Phase 6: User Story 3 - 管理员查看配置变更历史与回滚 (Priority: P3)

**Goal**: 配置变更有完整审计记录，支持回滚到历史版本

**Independent Test**: 修改配置 → 查看变更历史 → 回滚 → 验证配置恢复

### Implementation for User Story 3

- [x] T034 [US3] 实现变更历史查询 in odap/biz/platform/config/services/config_service.py — list_revisions(category, limit, offset) 方法；从 config_revisions 表查询
- [x] T035 [US3] 实现配置回滚 in odap/biz/platform/config/services/config_service.py — rollback_to_revision(revision_number) 方法；从 config_revisions 读取历史值；重新应用并创建新 revision
- [x] T036 [US3] 添加变更历史和回滚 API in odap/biz/platform/config/api/routes.py — GET /api/config/history (查询历史), POST /api/config/rollback (回滚)
- [x] T037 [P] [US3] 实现 ConfigHistoryDrawer 组件 in frontend/src/modules/settings/components/ConfigHistoryDrawer.tsx — Ant Design Drawer + Timeline 展示变更记录；按类别/时间筛选；回滚按钮
- [x] T038 [US3] 集成变更历史到 SettingsPage in frontend/src/modules/settings/pages/SettingsPage.tsx — 页面右上角"变更历史"按钮；点击打开 ConfigHistoryDrawer

**Checkpoint**: 配置变更可追溯，支持回滚 ✅

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 导入导出、测试、代码质量

- [x] T039 [P] 实现配置导入导出 API in odap/biz/platform/config/api/routes.py — GET /api/config/export (导出，敏感字段替换为 ***REDACTED***), POST /api/config/import (导入，跳过 REDACTED 字段)
- [x] T040 [P] 实现 ConfigImportExport 组件 in frontend/src/modules/settings/components/ConfigImportExport.tsx — 导出按钮下载 JSON；导入按钮上传 JSON
- [ ] T041 [P] 编写后端单元测试 in tests/unit/test_config_storage.py — SQLiteConfigStorage CRUD 测试（使用 tmp_path 真实 DB）；加密/解密测试；schema 注册测试
- [ ] T042 [P] 编写后端服务层测试 in tests/unit/test_config_manager.py — ConfigManager 热更新测试；脱敏展示测试；订阅通知测试
- [ ] T043 [P] 编写后端路由测试 in tests/unit/test_config_routes.py — HTTP 状态码映射；admin-only 403 测试；批量更新 all-or-nothing 测试
- [ ] T044 [P] 编写连接验证测试 in tests/unit/test_config_validator.py — 各服务类别验证逻辑测试（mock 外部连接）
- [ ] T045 运行 lint 和类型检查 — ruff check odap/biz/platform/config/ && cd frontend && npm run lint && npm run typecheck
- [ ] T046 运行 quickstart.md 验证 — 按 quickstart.md 步骤端到端验证配置管理功能

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately ✅
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user stories ✅
- **US1 (Phase 3)**: Depends on Phase 2 - MVP ✅ (T022 pending)
- **US2 (Phase 4)**: Depends on Phase 2 ✅ (T027 pending)
- **US4 (Phase 5)**: Depends on Phase 2 ✅
- **US3 (Phase 6)**: Depends on Phase 2 ✅
- **Polish (Phase 7)**: Depends on all user stories (tests pending)

### Pending Tasks

1. **T022**: 注册 /settings 路由到 AppRoutes.tsx（文件锁定，需手动完成）
2. **T027**: 统一其他服务配置读取入口（Neo4j/MinIO/OPA/Redis/搜索服务）
3. **T041-T044**: 后端单元测试
4. **T045-T046**: 代码质量检查和端到端验证

---

## Notes

- T024 (统一 LLM 配置读取) 已完成，16 个文件已替换
- T003 (加密工具) 使用 cryptography 库的 AESGCM，已是项目间接依赖
- T004 (扩展 ConfigurationComposer) 已完成，新增 L5(DB) 层 + get_config() 全局函数
- 前端组件遵循 Ant Design 6 设计规范，与项目现有 UI 风格一致
- 所有路由遵循 AGENTS.md 规则：except HTTPException: raise 透传
