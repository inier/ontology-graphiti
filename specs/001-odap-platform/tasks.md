# Implementation Tasks: ODAP 本体驱动分析决策平台

**Branch**: `001-odap-platform` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Total Tasks**: 434 | **Phases**: 11 | **User Stories**: 6 + 7 增强 FR (FR-031..FR-037)

---

## Phase 1: Setup — 项目基础设施

> 预计工期: 1-2 周 | 无前置依赖 | 可并行执行

- [x] T001 [P] MinIO Docker Compose 配置 — `docker/docker-compose.yml` 新增 minio 服务（端口 9000/9001，healthcheck，volume minio_data） [completed: 2026-06-06]
- [x] T002 [P] MinIO 环境变量配置 — `.env.example` 新增 MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY / MINIO_SECURE - [x] T003 [P] MinIO Python SDK 安装 — `requirem- [x] T004 MinIO 客户端封装 — `odap/infra/storage/minio_client.py` 实现 MinIOClient 单例（upload_object / download_object / get_presigned_url / delete_object / ensure_bucket） - [x] T005 [TDD] [REVIEW] MinIO 客户端单元测试 — `tests/unit/test_minio_client.py` 覆盖上传/下载/预签名URL/桶管理 - [x] T006 [P] [REVIEW] [SUBAGENT] 前端 UIAdapter 抽象接口定义 — `frontend/src/modules/shared/components/adapter/UIAdapter.ts` 定义 getButton / getInput / getTable / getModal / getForm / getSelect / getTag / getTooltip / getMessage / getNotification 接口 [completed: 2026-06-06]Form / getSelect / getTag / getTooltip / getMessage / getNotification 接口 - [x] T007 [P] [SUBAGENT] 前端 AntDesignAdapter 实现 — `fron- [x] T008 [P] [SUBAGENT] 前端 adapter 导出 — `frontend/src/modules/shared/components/adapter/index.ts` 导出当前 Adapter 实例 - [x] T009 [P] [SUBAGENT] 前端 L1 Atoms 原子组件创建 — `frontend/src/modules/shared/components/atoms/` 创建 Button / Input / Badge / Tooltip / Icon 组件 + `index.ts` 统一导出 - [x] T010 [P] [SUBAGENT] 前端 L2 Molecules 分子组件创建 — `frontend/src/modules/shared/components/molecules/` 创建 FormField / SearchBar / Card / Modal 组件 + `index.ts` 统一导出 - [x] T011 [P] [SUBAGENT] 前端 L3 Organisms 组织组件创建 — `frontend/src/modules/shared/components/organisms/` 创建 DataTable / FormPanel / GraphView / ChatPanel 组件 + `index.ts` 统一导出 - [x] T012 [P] [SUBAGENT] 前端 L4 Templates 模板组件创建 — `frontend/src/modules/shared/components/templates/` 创建 MasterDetail / SplitView / FullScreen 组件 + `index.ts` 统一导出 - [x] T013 [P] 前端响应式断点常量 — `frontend/src/modules/shared/styles/breakpoints.ts` 定义 6 断点常量（xs/sm/md/lg/xl/xxl）+ CSS 媒体查询 mixin - [x] T014 [P] 前端 useResponsive Hook — `frontend/src/modules/shared/hooks/useResponsive.ts` 返回当前断点信息 + 设备类型判断 - [x] T015 [P] 前端 i18n 基础设施 — `frontend/src/modules/shared/stores/i18nStore.ts` 配置 i18next 实例 + react-i18next 集成 + 按模块命名空间加载 - [x] T016 [P] 前端共享翻译文件 — `frontend/src/modules/shared/locales/zh-CN/common.json` + `frontend/src/modules/shared/locales/en-US/common.json` 共享翻译条目 - [x] T017 [P] 前端 useI18n Hook — `frontend/src/modules/shared/hooks/useI18n.ts` 封装 useTranslation + 语言切换方法 - [x] T018 [P] OpenHarness v2 适配层扩展 — `odap/infra/openharness/v2_adapter.py` 增强 OpenHarnessIntegration 单例，支持 lifespan 初始化 - [x] T019 [P] OpenHarness Swarm 适配器 — `odap/infra/openharness/swarm_adapter.py` 封装 OpenHarness Swarm 进程内调用 - [x] T020 [P] OpenHarness Skill 适配器 — `odap/infra/openharness/skill_adapter.py` 封装 OpenHarness Skill 注册/发现 - [x] T021 [P] OpenHarness Memory 适配器 — `odap/infra/openharness/memory_adapter.py` 封装 OpenHarness Memory Plugin - [x] T022 [P] OpenHarness Hook 适配器 — `odap/infra/openharness/hook_adapter.py` 封装 OpenHarness 生命周期钩子 - [x] T023 [P] OpenHarness Tool 适配器增强 — `odap/infra/openharness/tool_adapter.py` 增强 GraphitiToolAdapter，支持统一工具注册 - [x] T024 [TDD] OpenHarness 适配层单元测试 — `tests/unit/test_openharness_adapters.py` 覆盖各适配器初始化和接口调用 - [x] T025 [REVIEW] FastAPI lifespan 集成 OpenHarness — `odap/web/app.py` 在 lifespan 中初始化 OpenHarness（v1 + v2） [completed: 2026-06-06] Memory 适配器 — `odap/infra/openharness/memory_adapter.py` 封装 OpenHarness Memory Plugin - [x] T022 [P] OpenHarness Hook 适配器 — `odap/infra/openharness/hook_adapter.py` 封装 OpenHarness 生命周期钩子 - [x] T023 [P] OpenHarness Tool 适配器增强 — `odap/infra/openharness/tool_adapter.py` 增强 GraphitiToolAdapter，支持统一工具注册 - [x] T024 [TDD] OpenHarness 适配层单元测试 — `tests/unit/test_openharness_adapters.py` 覆盖各适配器初始化和接口调用 - [x] T025 [REVIEW] FastAPI lifespan 集成 OpenHarness — `odap/web/app.py` 在 lifespan 中初始化 OpenHarness（v1 + v2） [completed: 2026-06-06]harness_adapters.py` 覆盖各适配器初始化和接口调用
- [x] T025 [REVIEW]- [x] T026 本体模型层目录结构创建 — `odap/biz/core/ontology/model/` 创建 api/ models/ interfaces/ impl/ services/ storage/ 子目录 + `__init__.py` - [x] T027 本体管理引擎目录结构创建 — `odap/biz/core/ontology/engine/` 创建 api/ models/ interfaces/ impl/ services/ storage/ 子目录 + `__init__.py` - [x] T028 本体数据摄入目录结构创建 — `odap/biz/core/ontology/ingestion/` 创建 api/ impl/ services/ storage/ 子目录 + `__init__.py` - [x] T029 EntityType 领域模型定义 — `odap/biz/core/ontology/model/models/entity_type.py` EntityType(BaseModel) 含 name / properties / primary_key / constraints / classification_level - [x] T030 Property 领域模型定义 — `odap/biz/core/ontology/model/models/property.py` Property(BaseModel) 含 name / data_type / required / default_value / classification_level / constraints - [x] T031 Relation 领域模型定义 — `odap/biz/core/ontology/model/models/relation.py` Relation(Bas- [x] T035 [TDD] 本体模型层模型单元测试 — `tests/unit/test_ontology_model.py` 覆盖 EntityType / Property / Relation / Constraint / OntologyDocument 必填字段验证、默认值、容器字段 default_factory、Enum 值 [completed: 2026-06-06]aseModel) 含 constraint_type / expression / error_message - [x] T033 OntologyDocument 领域模型定义 — `odap/biz/core/ontology/model/models/ontology_document.py` OntologyDocument(BaseModel) 含 id / name / version / object_types / action_types / relations / metadata，对齐 Palantir AIP - [x] T034 本体模型层模型导出 — `odap/biz/core/ontology/model/models/__init__.py` 统一导出所有模型类 - [x] T035 [TDD] 本体模型层模型单元测试 — `tests/unit/test_ontology_model.py` 覆盖 EntityType / Property / Relation / Constraint / OntologyDocument 必填字段验证、默认值、容器字段 default_factory、Enum - [x] T040 [TDD] 本体管理引擎模型单元测试 — `tests/unit/test_ontology_engine.py` 覆盖 Version / Audit / Validation 模型验证 [completed: 2026-06-06]) 含 version_number / changelog / status / valid_time / transaction_time - [x] T037 Audit 领域模型定义 — `odap/biz/core/ontology/engine/models/audit.py` AuditRecord(BaseModel) 含 source / process_steps / transform_rules / timestamp - [x] T038 Validation 领域模型定义 — `odap/biz/core/ontology/engine/models/validation.py` ValidationResult(BaseModel) 含 is_valid / errors / warnings - [x] T039 本体管理引擎模型导出 — `odap/biz/core/ontology/engine/models/__init__.py` 统一导出 - [x] T040 [TDD] 本体管理引擎模型单元测试 — `tests/unit/test_ontology_engine.py` 覆盖 Version / Audit / Validation 模型验证 - [x] T041 [REVIEW] ModelRepository 抽象接口定义 — `odap/biz/core/ontology/model/interfaces/model_repository.py` ABC 定义 save_entity_type / get_entity_type / list_entity_types / delete_entity_type / save_instance / get_instance / list_instances / delete_instance - [x] T042 [REVIEW] VersionManager 抽象接口定义 — `odap/biz/core/ontology/engine/interfaces/version_manager.py` ABC 定义 create_version / get_version / rollback_version / comp- [x] T046 [TDD] SQLite Model Storage 单元测试 — `tests/unit/test_ontology_model.py` 新增 TestSQLiteModelStorage 类覆盖 CRUD 全流程、get 不存在返回 None、JSON 字段序列化/反序列化 [completed: 2026-06-06]it / get_audit / list_audits - [x] T044 [REVIEW] ValidationEngine 抽象接口定义 — `odap/biz/core/ontology/engine/interfaces/validation_engine.py` ABC 定义 validate_p- [x] T048 [TDD] SQLite Engine Storage 单元测试 — `tests/unit/test_ontology_engine.py` 新增 TestSQLiteEngineStorage 类覆盖版本 CRUD、审计记录 CRUD - [x] T049 Graphiti 双时态基础设施增强 — `odap/infra/graph/graph_service.py` 增强 query_temporal() 方法，正确区分 valid_time 和 transaction_time（reference_time 对应 valid_time，created_at 对应 transaction_time） - [x] T050 [TDD] Graphiti 双时态单元测试 — `tests/unit/test_graph_service_temporal.py` 覆盖双时态查询、历史查询、时间点快照 - [x] T051 DataClassification 枚举定义 — `odap/infra/security/data_classification.py` DataClassification(str, Enum) 四级分类 TS/S/C/U + 数据写入时自动标记分类级别逻辑 - [x] T052 Encryption 模块实现 — `odap/infra/security/encryption.py` 实现 TLS 1.3 强制配置 + AES-256-GCM 加密/解密函数（TS/S 级数据加密存储） - [x] T053 [TDD] 数据分类与加密单元测试 — `tests/unit/test_data_classification.py` 覆盖分类枚举值、加密/解密流程、分类级别判定 [completed: 2026-06-06]/unit/test_ontology_engine.py` 新增 TestSQLiteEngineStorage 类覆盖版本 CRUD、审计记录 CRUD - [x] T049 Graphiti 双时态基础设施增强 — `odap/infra/graph/graph_service.py` 增强 query_temporal() 方法，正确区分 valid_time 和 transaction_time（reference_time 对应 valid_time，created_at 对应 transaction_time） - [x] T050 [TDD] Graphiti 双时态单元测试 — `tests/unit/test_graph_service_temporal.py` 覆盖双时态查询、历史查询、时间点快照 - [x] T051 DataClassification 枚举定义 — `odap/infra/security/data_classification.py` DataClassification(str, Enum) 四级分类 TS/S/C/U + 数据写入时自动标记分类级别逻辑 - [x] T052 Encryption 模块实现 — `odap/infra/security/encryption.py` 实现 TLS 1.3 强制配置 + AES-256-GCM 加密/解密函数（TS/S 级数据加密存储） - [x] T053 [TDD] 数据分类与加密单元测试 — `tests/unit/test_data_classification.py` 覆盖分类枚举值、加密/解密流程、分类级别判定 [completed: 2026-06-06]录 CRUD - [x] T049 Graphiti 双时态基础设施增强 — `odap/infra/graph/graph_service.py` 增强 query_tempor- [x] T054 [REVIEW] ModelRepositoryImpl 实现- [x] T058 [REVIEW] 本体模型层路由注册 — `odap/web/app.py` include_router(ontology_model_router) - [x] T059 [TDD] 本体模型层服务单元测试 — `tests/unit/test_ontology_model.py` 新增 TestModelService 类覆盖成功返回扁平 dict、错误返回 {"status": "error"}、类型转换 - [x] T060 [TDD] 本体模型层路由单元测试 — `tests/unit/test_ontology_model.py` 新增 TestModelRoutes 类覆盖 HTTP 状态码映射、404/400/500 场景 [completed: 2026-06-06]vices/model_service.py` 编排层，返回 Dict[str, Any]，Enum→.value / datetime→.isoformat 类型转换 - [x] T056 本体模型层 schemas 定义 — - [x] T062 [SUBAGENT] 前端实体类型编辑组件 — `frontend/src/modules/ontology/components/EntityTypeEditor.tsx` L3 组织组件，属性列表编辑 + 主键选择 + 约束配置 [completed: 2026-06-06]stanceRequest / InstanceResponse 等 Pydantic 模型 - [x] T057 [REVIEW] 本体模型层路由实现 — `odap/biz/core/ontology/- [x] T064 前端本体模块 API 服务 — `frontend/src/modules/ontology/services/ontologyApi.ts` 封装 /api/ontology/model/* 接口调用 - [x] T065 前端本体模块 Store — `frontend/src/modules/ontology/stores/ontologyStore.ts` Zustand store 管理实体类型/实例状态 - [x] T066 前端本体模块翻译文件 — `frontend/src/modules/ontology/locales/zh-CN/ontology.json` + `frontend/src/modules/ontology/locales/en-US/ontology.json` - [x] T067 前端本体模块路由更新 — `frontend/src/AppRoutes.tsx` 更新 /ontology 路由指向 OntologyModelDesigner [completed: 2026-06-06]y_model.py` 新增 TestModelRoutes 类覆盖 HTTP 状态码映射、404/400/500 场景 [completed: 2026-06-06]EntityTypeEditor.tsx` L3 组织组件，属性列表编辑 + 主键选择 + 约束配置 [completed: 2026-06-06]stanceRequest / InstanceResponse 等 Pydant- [x] T062 [SUBAGENT] 前端实体类型编辑组件 — `frontend/src/modules/ontology/components/EntityTypeEditor.tsx` L3 组织组件，属性列表编辑 + 主键选择 + 约束配置 [completed: 2026-06-06]s/ontologyApi.ts` 封装 /api/ontology/model/* 接口调用 - [x] T065 前端本体模块 Store — `frontend/src/modules/ontolog- [x] T064 前端本体模块 API 服务 — `frontend/src/modules/ontology/services/ontologyApi.ts` 封装 /api/ontology/model/* 接口调用 - [x] T065 前端本体模块 Store — `frontend/src/modules/ontology/stores/ontologyStore.ts` Zustand store 管理实体类型/实例状态 - [x] T066 前端本体模块翻译文件 — `frontend/src/modules/ontology/locales/zh-CN/ontology.json` + `frontend/src/modules/ontology/locales/en-US/ontology.json` - [x] T067 前端本体模块路由更新 — `frontend/src/AppRoutes.tsx` 更新 - [x] T074 [REVIEW] 本体管理引擎路由注册 — `odap/web/app.py` include_router(ontology_engine_router) - [x] T075 [TDD] 版本管理服务单元测试 — `tests/unit/test_ontology_engine.py` 新增 TestVersionManager 类覆盖版本创建/查询/回滚/对比/时序查询 - [x] T076 [TDD] 验证引擎单元测试 — `tests/unit/test_ontology_engine.py` 新增 TestValidationEngine 类覆盖属性完整性/一致性/约束校验 - [x] T077 [SUBAGENT] 前端版本管理面板 — `frontend/src/modules/ontology/components/VersionPanel.tsx` L3 组织组件，版本时间线 + 变更对比 + 一键回滚 [completed: 2026-06-06]y` 实现数据摄入审计记录 [completed: 2026-06-06]/ontology/services/ontologyApi.ts` 封装 /api/ontology/model/* 接口调用 - [x] T065 前端本体模块 Store — `frontend/src/modules/ontology/stores/ontologyStore.ts` Zustand store 管理实体类型/实例状态 - [x] T066 前端本体模块翻译文件 — `frontend/src/modules/ontology/locales/zh-CN- [x] T072 本体管理引擎 schemas 定义 — `odap/biz/core/ontology/engine/api/schemas.py` CreateVersionRequest / VersionResponse / RollbackRequest / CompareResponse / ValidateRequest / AuditResponse 等 - [x] T073 [REVIEW] 本体管理引擎路由实现 — `odap/biz/core/ontology/engine/api/routes.py` APIRouter(prefix="/api/ontology/engine") 版本管理 + 验证 + 审计路由 - [x] T074 [REVIEW] 本体管理引擎路由注册 — `odap/web/app.py` include_router(ontology_engine_router) - [x] T075 [TDD] 版本管理服务单元测试- [x] T084 [REVIEW] 数据摄入路由注册 — `odap/web/app.py` include_router(ontology_ingestion_router) - [x] T085 [TDD] 批量导入单元测试 — `tests/unit/test_ontology_model.py` 新增 TestBatchImporter 类覆盖 CSV/JSON 导入、无效数据处理、结果摘要 - [x] T086 [SUBAGENT] 前端批量导入组件 — `frontend/src/modules/ingest/components/BatchImporter.tsx` L3 组织组件，文件上传 + 格式选择 + 导入进度 + 结果摘要展示 [completed: 2026-06-06] L3 组织组件，版本时间线 + 变更对比 + 一键回滚 [completed: 2026-06-06]` Zustand store 管理版本状态 [completed: 2026-06-06]re/ontology/engine/services/engine_service.p- [x] T079 前端版本模块 Store — `frontend/src/modules/version/stores/versionStore.ts` Zustand store 管理版本状态 [completed: 2026-06-06]eateVers- [x] T080 批量导入处理器实现 — `odap/biz/core/ontology/ingestion/impl/batch_importer.py` BatchImporter 支持 CSV/JSON 批量导入，自动验证属性完整性，无效数据标记跳过，返回导入结果摘要 - [x] T081 IngestService 实现 — `odap/biz/core/ontology/ingestion/services/ingest_service.py` 编排层，协调批量导入和验证 - [x] T082 数据摄入 schemas 定义 — `odap/biz/core/ontology/ingestion/api/schemas.py` BatchImportRequest / BatchImportResponse 等 [completed: 2026-06-06]_router) - [x] T075 [TDD] 版本管理服务单元测试- [x] T084 [REVIEW] 数据摄入路由注册 — `odap/web/app.py` include_router(ontology_ingestion_router) - [x] T085 [TDD] 批量导入单元测试 — `tests/unit/test_ontology_model.py` 新增 TestBatchImporter 类覆盖 CSV/JSON 导入、无效数据处理、结果摘要 - [x] T086 [SUBAGENT] 前端批量导入组件 — `frontend/src/modules/ingest/components/BatchImporter.tsx` L3 组织组件，文件上传 + 格式选择 + 导入进度 +- [x] T086 [SUBAGENT] 前端批量导入组件 — `frontend/src/modules/ingest/components/BatchImporter.tsx` L3 组织组件，文件上传 + 格式选择 + 导入进度 + 结果摘要展示 [completed: 2026-06-06]ponents/VersionCompare.tsx` L3 组织组件，双版本差异高亮展示 - [x] T079 前端版本模块 Store — `frontend/src/modules/version/stores/versionStore.ts` Zustand store 管理版本状态 [completed: 2026-06-06]` L3 组织组件，双版本差异高亮展示
- [x] T079 前端版本模块 Store — `frontend/src/modules/version/stores/versionStore.ts` Zustand store 管理版本状态 [completed: 2026-06-07]

### FR-003: 本体实例 CRUD + 批量导入

- [x] T080 批量导入处理器实现 — `odap/biz/core/ontology/ingestion/impl/batch_importer.py` BatchImporter 支持 CSV/JSON 批量导入，自动验证属性完整性，无效数据标记跳过，返回导入结果摘要 [completed: 2026-06-07]
- [x] T081 IngestService 实现 — `odap/biz/core/ontology/ingestion/services/ingest_service.py` 编排层，协调批量导入和验证 [completed: 2026-06-07]
- [x] T082 数据摄入 schemas 定义 — `odap/biz/core/ontology/ingestion/api/schemas.py` BatchImportRequest / BatchImportResponse 等 [completed: 2026-06-07]
-- [x] T092 多模态处理器集成 — `odap/infra/data_pipeline/multimodal_processor.py` 整合 PDF/Word/OCR 处理器，统一文件上传→MinIO 存储→文本/OCR 提取→LLM 实体抽取→本体实例更新流程 - [x] T093 [TDD] 多模态处理单元测试 — `tests/unit/test_ontology_model.py` 新增 TestMultimodalProcessor 类覆盖 PDF/W- [x] T086 [SUBAGENT] 前端批量导入组件 — `frontend/src/modules/ingest/components/BatchImporter.tsx` L3 组织组件，文件上传 + 格式选择 + 导入进度 + 结果摘要展示 [completed: 2026-06-06]N 导入、无效数据处理、结果摘要
- [x] T086 [SUBAGENT] 前端批量导入组件 — `frontend/src/modules/ingest/components/BatchImporter.tsx` L3 组织组件，文件上传 + 格式选择 + 导入进度 + 结果摘要展示 [completed: 2026-06-07]
- [ ] T- [x] T096 Workspace 隔离级别增强 — `odap/biz/platform/workspace/models/` 新增 IsolationLevel(str, Enum) — low/standard/high/strict - [x] T097 Workspace 4 级隔离实现 — `odap/biz/platform/workspace/impl/` SQLite workspace_id 过滤 + Neo4j workspace_id 标签隔离 + Redis workspace_id 前缀隔离 + MinIO 按工作空间分桶 - [x] T098 Workspace 导入导出 — `odap/biz/platform/workspace/impl/` 实现 JSON 格式完整工作空间导出和导入 - [x] T099 Workspace API 增强 — `odap/biz/platform/workspace/api/routes.py` 新增 POST /api/workspace/{id}/export + POST /api/workspace/{id}/impo- [x] T097 Workspace 4 级隔离实现 — `odap/biz/platform/workspace/impl/` SQLite workspace_id 过滤 + Neo4j workspace_id 标签隔离 + Redis workspace_id 前缀隔离 + MinIO 按工作空间分桶 [completed: 2026-06-06]c/modules/workspace/pages/WorkspaceManager.tsx` L5 页面，隔离级别选择 + 导入导出操作 - [x] T102 前端工作空间 Store — `frontend/src/modules/workspace/stores/workspaceStore.ts` Zustand store 增强隔离级别管理 [completed: 2026-06- [x] T103 [REVIEW] 场景切换服务增强 — `od- [x] T100 [TDD] Workspace 单元测试 — `tests/unit/t- [x] T112 [TDD] 审计记录单元测试 — `tests/unit/test_ontology_engine.py` 新增 TestAuditRecorder 类覆盖数据来源/处理过程/转换规则记录 - [x] T113 [SUBAGENT] 前端审计时间线组件 — `frontend/src/modules/audit/components/AuditTimeline.tsx` L3 组织组件，审计记录时间线展示 + 详情查看 [completed: 2026-06-06]re — `frontend/src/modules/workspace/stores/workspaceStore.ts` Zustand store 增强隔离级别管理 [completed: 2026-06- [x] T103 [REVIEW] 场景切换服务增强 — `odap/biz/platform/workspace/services/scenario_service.py` 场景切换时自动加载关联本体列表/技能配置/OPA 策略/Agent 配置，切换事件通过 Hook 系统广播 - [x] T104 场景本体 N:M 关联 — `odap/biz/platform/workspace/impl/` 场景与本体 N:M 关联，解绑需检查依赖 - [x] T105 场景 API 路由 — `odap/biz/platform/workspace/api/routes.py` 新增 POST /api/workspace/{ws_id}/scenarios + POST /api/workspace/{ws_id}/scenarios/{id}/activate + POST /api/workspace/{ws_id}/scenarios/{id}/ontologies - [x] T106 [TDD] 场景切换单元测试 — `tests/uni- [x] T117 [TDD] OntologyDocument 单元测试 — `tests/unit/test_ontology_model.py` 新增 TestOntologyDocument 类覆盖格式转换、导入导出、Palantir/OWL 对齐 - [x] T118 [SUBAGENT] 前端 OntologyDocument 导入导出组件 — `frontend/src/modules/ontology/components/DocumentImporter.tsx` L3 组织组件，OntologyDocument JSON 导入 + 多格式导出 [completed: 2026-06-06]ores/scenarioStore.ts` Zustand store 管理场景状态 [completed: 2026-06-0- [x] T109 数据摄入审计记录增强 — `odap/biz/core/ontology/engine/impl/audit_recorder_impl.py` 增强记录数据来源（上传文件/批量导入/API 调用/Agent 操作）、处理过程、转换规则 - [x] T110 审计统一通道集成 — `odap/infra/security/unified_audit.py` 集成本体管理引擎审计- [x] T121 [REVIEW] 传输加密 FastAPI HTTPS 配置 — `odap/web/app.py` 强制 TLS 1.3 配置 - [x] T122 数据分类 API — `odap/infra/security/` 新增 GET /api/security/classification-levels 路由 - [x] T123 [TDD] 数据分类单元测试 — `tests/unit/test_data_classification.py` 新增 TestClassificationMarking 类覆盖自动标记、分类级别查询 [completed: 2026-0- [x] T124 后端 i18n 模块创建 — `odap/biz/platform/i18n/` 创建 api/ models/ services/ storage/ 子目录 - [x] T125 Translation 领域模型定义 — `odap/biz/platform/i18n/models/translation.py` Translation(BaseModel) 含 key / module / locale / value - [x] T126 SQLite i18n Storage 实现 — `odap/biz/platform/i18n/storage/sqlite_i18n_storage.py` SQLiteI18nStorage 翻译条目 CRUD + `__init__.py` 别名导出 - [x] T127 I18nService 实现 — `odap/biz/platform/i18n/services/i18n_service.py` 翻译管理 + LLM 翻译调用（调用 OpenAI API 批量翻译未翻译条目） - [x] T128 i18n schemas 定义 — `odap/biz/platform/i18n/api/schemas.py` TranslationRequest / TranslationResponse / AutoTranslateRequest 等 - [x] T129 [REVIEW] i18n 路由实现 — `odap/biz/platform/i18n/api/routes.py` APIRouter(prefix="/api/i18n") 翻译 CRUD + LLM 自动翻译 + 模块/语言列表 - [x] T130 [REVIEW] i18n 路由注册 — `odap/web/app.py` include_router(i18n_router) - [x] T131 [TDD] i18n 单元测试 — `tests/unit/test_i18n.py` 覆盖翻译 CRUD、LLM 翻译调用、模块/语言列表 - [x] T132 [SUBAGENT] 前端 i18n 管理页面 — `frontend/src/modules/i18n-admin/pages/I18nAdminPage.tsx` L5 页面，翻译条目列表 + 在线编辑 + LLM 自动翻译按钮 + 人工审核 - [x] T133 前端 i18n API 服务 — `frontend/src/modules/i18n-admin/services/i18nApi.ts` 封装 /api/i18n/* 接口调用 [completed: 2026-06-06]ENT] 前端 OntologyDocument 导入导出组件 — `frontend/src/modules/ontology/components/DocumentImporter.tsx` L3 组织组件，OntologyDocument JSON 导入 + 多格式导出 [completed: 2026-06-06]models/ services/ storage/ 子目录 - [x] T125 Translation 领域模型定义 — `odap/biz/platform/i18n/models/translation.py` Translation(BaseModel) 含 key / module / locale / value - [x] T126 SQLite i18n Storage 实现 — `odap/biz/platform/i18n/storage/sqlite_i18n_storage.py` SQLiteI18nStorage 翻译条目 CRUD + `__- [x] T121 [REVIEW] 传输加密 FastAPI HTTPS 配置 — `odap/web/app.py` 强制 T- [x] T137 OODA Loop 实现增强 — `odap/biz/core/agent/impl/ooda_loop.py` OODA 各阶段与 OpenHarness 对齐：Observe→Tool 调用、Orient→Hook 后处理、Decide→QueryEngine、Act→Tool 执行 - [x] T138 Agent 角色模型定义 — `odap/biz/core/agent/models/` AgentRole(str, Enum) — Commander/Intelligence/Operations（可扩展）+ AgentConfig(BaseModel) - [x] T139 Agent schemas 定义 — `odap/biz/core/agent/api/schemas.py` DispatchRequest / DispatchResponse / TaskStatusResponse / SwarmConfigRequest 等 - [x] T140 [REVIEW] Agent 路由实现 — `odap/biz/core/agent/api/routes.py` APIRouter(prefix="/api/agent") 意图分发 + 任务状态 + 决策链路 + Swarm 配置 - [x] T141 [REVIEW] Agent 路由注册 — `odap/web/app.py` include_router(agent_router) - [x] T142 [TDD] Agent 服务单元测试 — `tests/unit/test_agent.py` 覆盖 DomainSwarm OODA 循环、IntentRouter 混合路由、SubAgentPlanner 任务分解 - [x] T143 [SUBAGENT] 前端 Agent 聊天页面增强 — `frontend/src/modules/agent/pages/AgentChat.tsx` L5 页面，自然语言输入 + 意图识别展示 + Agent 响应 - [x] T144 [SUBAGENT] 前端 Agent 列表页面 — `frontend/src/modules/agent/pages/MyAgents.tsx` L5 页面，Agent 角色配置 + Swarm 配置 - [x] T145 前端 Agent Store — `frontend/src/modules/agent/stores/agentStore.ts` Zustand store 管理 Agent 状态 - [x] T146 前端 Agent API 服务 — `frontend/src/modules/agent/services/agentApi.ts` 封装 /api/agent/* 接口调用 - [x] T147 前端 Agent 翻译文件 — `frontend/src/modules/agent/locales/zh-CN/agent.json` + `frontend/src/modules/agent/locales/en-US/agent.json` [completed: 2026-06-06]py` 覆- [x] T148 DecisionChain 数据结构定义 — `odap/biz/core/agent/models/` DecisionChain(BaseModel) 含 steps（OODA 各阶段）/ reasoning（推理过程）/ evidence（依据） [completed: 2026-06-06]线编辑 + LLM 自动翻译按钮 + 人工审核 - [x] T133 前端 i18n API 服务 — `frontend/src/modules/i18n-admin- [x] T150 决策过程 API 路由 — `odap/biz/core/agent/api/routes.py` 新增 GET /api/agent/decisions/{decision_id} + GET /api/agent/decisions/{decision_id}/chain - [x] T151 决策过程 WebSocket 推送 — `odap/web/ws/event_bus.py` 新增 WS /ws/agent/decisions 实时推送决策过程 - [x] T152 [TDD] 决策过程单元测试 — `tests/unit/test_agent.py` 新增 TestDecisionChain 类覆盖决策链路记录和查询 - [x] T153 [SUBAGENT] 前端决策链路时间线组件 — `frontend/src/modules/agent/components/DecisionTimeline.tsx` L3 组织组件，按时间顺序展示决策步骤 - [x] T154 [SUBAGENT] 前端思维链视图组件 — `frontend/src/modules/agent/components/ReasoningChain.tsx` L3 组织组件，展示推理过程和依据，点击步骤查看详情 [completed: 2026-06-06]n- [x] T155 Skill 热插拔实现 — `odap/biz/platform/skill_system/impl/hotplug.py` register_skill(skill_def) / unregister_skill(skill_id) / discover_skills(query)，通过 OpenHarness Skill 管理功能注册和发现 - [x] T156 Skill 生命周期管理 — `odap/biz/platform/skill_system/models/` SkillStatus(str, Enum) — draft/active/deprecated/archived + SkillDefinition(BaseModel) - [x] T157 现有技能包迁移 — `odap/tools/` 下 9 个技能包迁移为 OpenHarness Skill 格式 - [x] T158 Skill API 路由 — `odap/biz/platform/skill_system/api/routes.py` 新增 POST /api/skill/register + DELETE /api/skill/{id} + GET /api/skill/discover + GET /api/skill/{id}/status - [x] T159 [REVIEW] Skill 路由注册 — `odap/web/app.py` include_router(skill_router) - [x] T160 [TDD] Skill 热插拔单元测试 — `tests/unit/test_skill_system.py` 覆盖注册/注销/发现/生命周期状态转换 - [x] T161 [SUBAGENT] 前端技能管理页面增强 — `frontend/src/modules/system/pages/SkillManagement.tsx` L5 页面，Skill 注册/注销/发现/状态管理 - [x] T162 前端技能 Store — `frontend/src/modules/system/stores/skillStore.ts` Zustand store 管理 Skill 状态 [completed: 2026-06-06]nit/test_agent.py` 覆盖 DomainSwarm OODA 循环、IntentRouter 混合路由、SubAgentPlanner 任务分解 - [x] T143 [SUBAGENT] 前端 Agent 聊天页面- [x] T163 [REVIEW] Markdown→Rego 编译器实现 — `odap/infra/opa/markdown_compiler.py` 解析 Markdown DSL 标题→Rego 规则名、当/且→条件组合、时允许/拒绝→规则体、编译验证、fail-close 机制 - [x] T164 [REVIEW] OPA 策略版本管理 — `odap/infra/opa/opa_service.py` 增加 SQLite 策略版本历史存储，支持回滚 - [x] T165 [REVIEW] OPA 策略热更新增强 — `odap/infra/opa/opa_service.py` 增强 hot_update_bundle()，编译后通过 OPA API 加载策略，30 秒内生效，编译失败保持旧策略 - [x] T166 [REVIEW] OPA 策略 schemas 定义 — `odap/infra/opa/routes.py` 新增 MarkdownPolicyRequest / MarkdownPolicyResponse / CompileStatusResponse 等 - [x] T167 [REVIEW] OPA 策略 API 路由 — `odap/infra/opa/routes.py` 新增 POST /api/policy/markdown + GET /api/policy/markdown/{id} + PUT /api/policy/markdown/{id} + POST /api/policy/markdown/{id}/compile + GET /api/policy/markdown/{id}/status - [x] T168 [TDD] [REVIEW] OPA 策略单元测试 — `tests/unit/test_opa.py` 覆盖 Markdown→Rego 编译、编译失败 fail-close、热更新、版本回滚 - [x] T169 [SUBAGENT] 前端策略编辑器 — `frontend/src/modules/config/components/PolicyEditor.tsx` L3 组织组件，Markdown 编辑 + 预览 + 编译状态展示 - [x] T170 [SUBAGENT] 前端策略管理页面 — `frontend/src/modules/config/pages/PolicyManager.tsx` L5 页面，策略列表 + 编辑 + 编译 + 热更新 [completed: 2026-06-06] GET /ap- [x] T171 [REVIEW] ABAC 四维模型实现 — `odap/infra/opa/opa_service.py` 增强 check_permission(subject, action, resource, env)，OPA 策略校验返回 allow/deny + 原因 [completed: 2026-06-06]DD] 决策过程单元测试 — `tests/unit/test_agent.py` 新增 TestDecisionChain 类覆盖决策链路记录和查询 - [x] T153 [SUBAGENT] 前端决策链路时间线组件 — `fron- [x] T173 审计日志增强 — `odap/infra/security/unified_audit.py` 增加写操作审计记录 actor/action/resource/result/timestamp，写入 SQLite + Graphiti 审计通道 - [x] T174 审计 API 增强 — `odap/infra/security/audit_api.py` 新增 GET /api/audit/logs（分页+过滤）+ GET /api/audit/timeline（资源审计时间线） - [x] T175 [TDD] [REVIEW] ABAC + 审计单元测试 — `tests/unit/test_opa.py` 新增 TestABAC 类覆盖四维权限校验、数据分类级别控制、审计日志记录 [completed: 2026-06-06]ll_def) / unregister_skill(skill_id) / discover_skills(query)，通过 OpenHarness Skill 管理功能注册和- [x] T177 前端审计 Store — `frontend/src/modules/audit/stores/auditStore.ts` Zustand store 管理审计日志状态 [completed: 2026-06-06]raft/active/- [x] T178 [REVIEW] OAuth2/OIDC Provider 集成 — `odap/infra/security/oauth2_providers.py` 支持企业 SSO（Keycloak/Auth0/Okta），Authorization Code Flow + PKCE，Token 交换 OAuth2→JWT [completed: 2026-06-06]system/api/routes.py` 新增 POST /api/skill/register + DELETE /api/skill/{id} + GET /api/skill/discover + GET /api/skill/{id}/status - [x] T159 [- [x] T180 [REVIEW] 认证 API 路由增强 — `odap/infra/security/auth_routes.py` 新增 POST /api/auth/login + POST /api/auth/sso/{provider} + POST /api/auth/refresh + POST /api/auth/logout - [x] T181 [TDD] [REVIEW] 认证单元测试 — `tests/unit/test_auth.py` 覆盖本地账号登录、SSO 登录、Token 刷新、登出 - [x] T182 [SUBAGENT] 前端登录页增强 — `frontend/src/modules/shared/pages/LoginPage.tsx` 增加 SSO 登录按钮 + 本地账号密码表单 - [x] T183 [REVIEW] 前端 authStore 增强 — `frontend/src/modules/shared/stores/authStore.ts` 增加 SSO 登录流程 + Token 刷新逻辑 [completed: 2026-06-06]) [completed: 2026-06-06]on/resource/result/timestamp，写入 SQLite + Graphiti 审计通道 - [x] T174 审计 API 增强 — `odap/infra/security/audit_api.py` 新增 GET /api/audit/logs（分页+过滤）+ GET /api/audit/timeline（资源审计时间线） - [x] T175 [TDD] [REVIEW] ABAC + 审计单元测试 — `tests/unit/test_opa.py` 新增 TestABAC 类覆盖四维权限校验、数据分类级别控制、审计日志记录 [completed: 2026-06-06]ll_def) / unregister_skill(skill_id) / discover_skills(query)，通过 OpenHarness Skill 管理功能注册和- [x] T177 前端审计 Store — `frontend/src/modules/audit/stores/auditStore.ts` Zustand store 管理审计日志状态 [completed: 2026-06-06]raft/active/- [x] T178 [REVIEW] OAuth2/OIDC Provider 集成 — `odap/infra/security/oauth2_providers.py` 支持企业 SSO（Keycloak/Auth0/Okta），Authorization Code Flow + PKCE，Token- [x] T159 [- [x] T180 [REVIEW] 认证 API 路由增强 — `odap/infra/security/auth_routes.py` 新增 POST /api/auth/login + POST /api/auth/sso/{provider} + POST /api/auth/refresh + POST /api/auth/logout - [x] T181 [TDD] [REVIEW] 认证单元测试 — `tests/unit/test_auth.py` 覆盖本地账号登录、SSO 登录、Token 刷新、登出 - [x] T182 [SUBAGENT] 前端登录页增强 — `frontend/src/modules/shared/pages/LoginPage.tsx` 增加 SSO 登录按钮 + 本地账号密码表单 - [x] T183 [REVIEW] 前端 authStore 增强 — `frontend/src/modules/shared/stores/authStore.ts` 增加 SSO 登录流程 + Token 刷新逻辑 [completed: 2026-06-06]) [completed: 2026-06-06]ge.tsx` 增加 SSO 登录按钮 + 本地账号密码表单 - [x] T183 [REVIEW] 前端 authStore 增强 — `frontend/src/modules/shared/stores/authStore.ts` 增加 SSO 登录流程 + Token 刷新逻辑 [completed: 2026-06-06])

> 预计工期: 3-4 周 | 依赖 Phase 3 | US3: 策略治理与权限控制 | 可与 Phase 4 并行

### FR-007: OPA 策略 Mar- [x] T184 意图识别器实现 — `odap/biz/core/cognition/impl/intent_recognizer.py` 基于 LLM + 本体事实的意图分类，支持角色上下文，输出 intent_type + confidence + parameters - [x] T185 知识导航器实现 — `odap/biz/core/cognition/impl/knowledge_navigator.py` 基于本体的知识图谱导航，推理路径可视化（高亮路径+逐步回溯） - [x] T186 解释引擎实现 — `odap/biz/core/cognition/impl/explanation_engine.py` AI 决策过程可解释性，推理链路展示（"为什么"问题的回答） - [x] T187 角色视图管理器实现 — `odap/biz/core/cognition/impl/role_view_manager.py` 不同角色（Commander/Intelligence/Operations）定制化视图，角色切换后界面自动适配 - [x] T188 认知引擎领域模型定义 — `odap/biz/core/cognition/models/` IntentResult / NavigationPath / Explanation / RoleViewConfig 等 BaseModel - [x] T189 CognitionService 实现 — `odap/biz/core/cognition/services/cognition_service.py` 编排层，协调意图识别/知识导航/解释引擎/角色视图 - [x] T190 认知引擎 schemas 定义 — `odap/biz/core/cognition/api/schemas.py` RecognizeIntentRequest / NavigateRequest / ExplainRequest / RoleViewResponse 等 - [x] T191 [REVIEW] 认知引擎路由实现 — `odap/biz/core/cognition/api/routes.py` APIRouter(prefix="/api/cognition") 意图识别 + 知识导航 + 解释 + 角色视图 - [x] T192 [REVIEW] 认知引擎路由注册 — `odap/web/app.py` include_router(cognition_router) - [x] T193 [TDD] 认知引擎单元测试 — `tests/unit/test_cognition.py` 覆盖意图识别、知识导航、解释引擎、角色视图管理 - [x] T194 [SUBAGENT] 前端认知引擎集成 — `frontend/src/modules/agent/components/CognitionPanel.tsx` L3 组织组件，意图识别结果展示 + 推理链路可视化 + 角色视图切换 - [x] T195 [SUBAGENT] 前端推理路径可视化组件 — `frontend/src/modules/agent/components/ReasoningPath.tsx` L3 组织组件，基于 G6 的推理路径高亮 + 逐步回溯 - [x] T196 前端认知 Store — `frontend/src/modules/ag- [x] T180 [REVIEW] 认证 API 路由增强 — `odap/infra/security/auth_routes.py` 新增 POST /api/auth/login + POST /api/auth/sso/{provider} + POST /api/auth/refresh +- [x] T208 会话记忆 API 路由 — `odap/biz/platform/session_memory/api/routes.py` GET /api/memory/session/{session_id} + POST /api/memory/session/{session_id}/clear + GET /api/memory/long-term - [x] T209 [REVIEW] 会话记忆路由注册 — `odap/web/app.py` include_router(memory_router) - [x] T210 [TDD] 会话记忆单元测试 — `tests/unit/test_session_memory.py` 覆盖短期/工作/长期记忆 CRUD、TTL 过期、语义检索 - [x] T211 [SUBAGENT] 前端会话记忆组件 — `frontend/src/modules/agent/components/SessionMemory.tsx` L3 组织组件，会话上下文展示 + 记忆管理 [completed: 2026-06-06]se 5 | US6: 用户认知引擎 [completed: 2026-06-0- [x] T184 意图识别器实现 — `odap/biz/core/cognition/impl/intent_recognizer.py` 基于 LLM + 本体事实的意图分类，支持角色上下文，输出 intent_type + confidence + parameters - [x] T185 知识导航器实现 — `odap/biz/core/cognition/impl/knowledge_navigator.py` 基于本体的知识图谱导航，推理路径可视化（高亮路径+逐步回溯） - [x] T186 解释引- [x] T214 工具注册表领域模型 — `odap/biz/platform/tool_registry/models/` ToolDefinition(BaseModel) 含 id / name / category / description / input_schema / permissions - [x] T215 工具注册表 API 路由 — `odap/biz/platform/tool_registry/api/routes.py` POST /api/tools/register + DELETE /api/tools/{id} + POST /api/tools/{id}/invoke + GET /api/tools + POST /api/tools/discover - [x] T216 [REVIEW] 工具注册表路由注册 — `odap/web/app.py` include_router(tool_registry_router) - [x] T217 [TDD] 工具注册表单元测试 — `tests/unit/test_tool_registry.py` 覆盖注册/注销/调用/列表/语义发现 - [x] T218 [SUBAGENT] 前端工具管理组件 — `frontend/src/modules/system/components/ToolRegistry.tsx` L3 组织组件，工具列表 + 注册/注销 + 语义发现 [completed: 2026-06-0- [x] T219 意图解析器实现 — `odap/biz/core/ontology/` 新增 semantic_layer/ 目录，`intent_parser.py` 自然语言意图解析为 StructuredQuery [completed: 2026-06-06]core/cognition/api/routes.py` APIRouter(prefix="/api/cognition") 意图识别 + 知识导航 + 解释 + 角色视图 - [x] T192 [REVIEW] 认知引擎路由注册 — `odap/web/app.py` include_router(cognition_router) - [x] T193 [TDD] 认知引擎单元测试 — `tests/unit/test_cognition.py` 覆盖意图识别、知识导航、解释引擎、角色视图管理 - [x] T194 [SUBAGENT] 前端认知引擎集成 — `frontend/src/modules/agent/components/CognitionPanel.tsx` L3 组织组件，意图识别结果展示 + 推理链路可视化 + 角色视图切换 - [x] T195 [SUBAGENT] 前端推理路径可视化组件 — `frontend/src/modules/agent/components/Reasonin- [x] T223 [REVIEW] 语义层路由注册 — `odap/web/app.py` include_router(semantic_router) - [x] T224 [TDD] 语义层单元测试 — `tests/unit/test_semantic_layer.py` 覆盖意图解析、任务规划、同义词映射、扩写规则 - [x] T225 [SUBAGENT] 前端语义层配置组件 — `frontend/src/modules/ontology/components/SemanticConfig.tsx` L3 组织组件，同义词/近似词映射配置 + 扩写规则配置 [completed: 2026-06-06- [x] T226 [REVIEW] HookManager 实现 — `odap/biz/integration/hook_system/impl/hook_manager.py` Pre-Hook（OPA 策略注入、参数校验）+ Post-Hook（审计日志、性能监控）+ Hook 注册表（管理优先级和依赖），基于 OpenHarness 生命周期钩子 - [x] T227 Hook 领域模型定义 — `odap/biz/integration/hook_system/models/` HookDefinition(BaseModel) 含 id / type(pre/post) / priority / handler / enabled - [x] T228 Hook API 路由 — `odap/biz/integration/hook_system/api/routes.py` POST /api/hooks/register + DELETE /api/hooks/{id} + GET /api/hooks + POST /api/hooks/{id}/enable + POST /api/hooks/{id}/disable - [x] T229 [REVIEW] Hook 路由注册 — `odap/web/app.py` include_router(hook_router) - [x] T230 [TDD] [REVIEW] Hook 系统单元测试 — `tests/unit/test_hook_system.py` 覆盖 Pre/Post Hook 注册/执行、优先级排序、OPA 策略注入、审计日志记录 - [x] T231 [SUBAGENT] 前端 Hook 管理组件 — `frontend/src/modules/system/components/HookManager.tsx` L3 组织组件，Hook 列表 + 注册/注销 + 启用/禁用 [completed: 2026-06-06]/query/validate - [x] T203 [TDD] 统一查询单元测试 — `tests/unit/test_query.py` 覆盖 4 种查询源、Agent Safe 只读模式、架构守卫（验证 Agent 代码无直接 graph_manager 写调用） - [x] T204 [SUBAGENT] 前端查询服务组件 — - [x] T195 [SUBAGENT] 前端推理路径可视化组件 — `frontend/src/mod- [x] T206 工作记忆实现 — `odap/biz/platform/session_memory/impl/workin- [x] T236 反馈 API 路由 — `odap/biz/simulation/feedback/api/routes.py` POST /api/feedback/collect + GET /api/feedback/analysis/{task_id} + GET /api/feedback/aggregate + POST /api/feedback/close-loop - [x] T237 [REVIEW] 反馈路由注册 — `odap/web/app.py` include_router(feedback_router) - [x] T238 [TDD] 反馈机制单元测试 — `tests/unit/test_feedback.py` 覆盖收集/分析/聚合/闭环触发/Graphiti 写入 - [x] T239 [SUBAGENT] 前端反馈展示组件 — `frontend/src/modules/simulation/components/FeedbackPanel.tsx` L3 组织组件，反馈分析展示 + 经验聚合可视化 [completed: 2026-06-06]pp.py` include_router(memory_router) - [x] T210 [TDD] 会话记忆单元测试 — `tests/unit/test_- [x] T240 SandboxManager 实现 — `odap/biz/simulation/simulation_sandbox/impl/sandbox_manager.py` create_sandbox / run_simulation / get_sandbox_status / destroy_sandbox，基于 OpenHarness 沙箱机制进程级隔离 - [x] T241 沙箱资源限制 — `odap/biz/simulation/simulation_sandbox/impl/sandbox_manager.py` 内存/时间超限自动终止，返回部分结果和超时提示 - [x] T242 沙箱结果导出 — `odap/biz/simulation/simulation_sandbox/impl/sandbox_manager.py` 推演结果可导出到生产环境（需审批） - [x] T243 沙箱 API 路由 — `odap/biz/simulation/simulation_sandbox/api/routes.py` POST /api/simulation/sandbox + POST /api/simulation/sandbox/{id}/run + GET /api/simulation/sandbox/{id}/status + GET /api/simulation/sandbox/{id}/results + DELETE /api/simulation/sandbox/{id} - [x] T244 [REVIEW] 沙箱路由注册 — `odap/web/app.py` include_router(sandbox_router) [completed: 2026-06-06]工具注册表 API 路由 — `odap/biz/platform/tool_registry/api/routes.p- [x] T246 [SUBAGENT] 前端沙箱管理页面 — `frontend/src/modules/simulation/pages/SandboxManager.tsx` L5 页面，沙箱创建/运行/监控/销毁 [completed: 2026-06-06]/tools/di- [x] T247 ParallelRunner 实现 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` run_parallel(scenarios) 最多 10 个方案并行 + run_what_if(base_scenario, param_variations) 参数敏感性分析 - [x] T248 推演结果对比 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` 结果以并排对比视图展示，高亮关键指标差异 - [x] T249 推演进度 WebSocket 推送 — `odap/web/ws/event_bus.py` 新增 WS /ws/simulation/progress 实时推送推演进度 - [x] T250 推演历史双时态存储 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` 推演结果附带 valid_time + transaction_time，基于 Graphiti 双时态 - [x] T251 并行推演 API 路由 — `odap/biz/simulation/simulation_sandbox/api/routes.py` 新增 POST /api/simulation/parallel + POST /api/simulation/what-if + GET /api/simulation/comparison [completed: 2026-06-06]uator.py` 同义词/近似词映射 + 扩写规则（用户可配置） - [x] T222 语义层 API 路由 — `odap/biz/core/ontology/s- [x] T253 [SUBAGENT] 前端并行推演组件 — `frontend/src/modules/simulation/components/ParallelComparison.tsx` L3 组织组件，多方案并排对比 + 关键指标差异高亮 - [x] T254 [SUBAGENT] 前端 What-if 参数面板 — `frontend/src/modules/simulation/components/WhatIfPanel.tsx` L3 组织组件，参数敏感性分析配置 + 结果展示 - [x] T255 [SUBAGENT] 前端推演进度组件 — `frontend/src/modules/simulation/components/SimulationProgress.tsx` L2 分子组件，WebSocket 实时推演进度展示 [completed: 2026-06-- [x] T256 EventGenerator 实现 — `odap/biz/simulation/event_simulator/impl/event_generator.py` 按剧本/模板自动生成事件序列，事件必须基于当前工作空间的本体定义展开 - [x] T257 TimelineEngine 实现 — `odap/biz/simulation/event_simulator/impl/timeline_engine.py` 模拟时钟独立控制（加速/减速/暂停），事件按时间线顺序注入 - [x] T258 ScenarioTemplate 实现 — `odap/biz/simulation/event_simulator/impl/scenario_template.py` 预定义事件模板库 + 支持自定义模板 - [x] T259 事件手动注入 — `odap/biz/simulation/event_simulator/impl/event_generator.py` 手动注入关键事件，事件注入驱动本体状态演化 - [x] T260 事件模拟器 API 路由 — `odap/biz/simulation/event_simulator/api/routes.py` POST /api/event-simulator/generate + POST /api/event-simulator/inject + GET /api/event-simulator/timeline/{id} + POST /api/event-simulator/clock/control + GET /api/event-simulator/templates - [x] T261 [REVIEW] 事件模拟器路由注册 — `odap/web/app.py` include_router(event_simulator_router) - [x] T262 [TDD] 事件模拟器单元测试 — `tests/unit/test_event_simulator.py` 覆盖事件生成/注入/时间线/时钟控制/模板管理 [completed: 2026-06-06]ap/web/app.py` include_router(hook_router) [completed: 2026-06-06]raphiti 双时态 - [x] T251 并行推演 API 路由 — `odap/biz/simulation/simulation_sandbox/api/routes.py` 新增 POST /api/simulation/parallel + POST /api/simulation/what-if + GET /api/simulation/comparison [completed: 2026-06-06]uator.py` 同义词/近似词映射 + 扩写规则（用户可配置） - [x] T222 语义层 API 路- [x] T232 Feedback Collector 实现 — `odap/biz/simulation/feedback/impl/collector.py` 执行结果收集（感知层输入），作为 OpenHarness 外层封装 [completed: 2026-06-06]parison.tsx` L3 组织组件，多方案并排对比 + 关键指标差异高亮 - [x] T254 [SUBAGENT] 前端 What-if 参数面板 — `frontend/src/modules/simulation/components/WhatIfPanel.tsx` L3 组织组件，参数敏感性分析配置 + 结果展示 - [x] T255 [SUBAGENT] 前端推演进度组件 — `frontend/src/modules/simulation/components/SimulationProgress.tsx` L2 分子组件，WebSocket 实时推演进度展示 [completed: 2026-06-- [x] T256 EventGenerator 实现 — `odap/biz/simulation/event_simulator/impl/e- [x] T236 反馈 API 路由 — `odap/biz/simulation/feedback/api/routes.py` POST /api/feedback/collect + GET - [x] T270 QA API 路由 — `odap/biz/data/qa/api/routes.py` POST /api/qa/ask + POST /api/qa/ask/temporal + GET /api/qa/sessions/{id} + POST /api/qa/chart - [x] T271 [REVIEW] QA 路由注册 — `odap/web/app.py` include_router(qa_router) [completed: 2026-06-06] — `tests/unit/test_feedback.py` 覆盖收集/分析/聚合/闭环触发/G- [x] T273 [SUBAGENT] 前端问答页面增强 — `frontend/src/modules/qa/pages/QAPage.tsx` L5 页面，自然语言输入 + 多轮对话 + 图表展示 + 一键添加视图上下文 - [x] T274 [SUBAGENT] 前端图表渲染组件 — `frontend/src/modules/qa/components/ChartRenderer.tsx` L3 组织组件，8 种以上图表类型渲染（ECharts + G6 + Leaflet） - [x] T275 前端 QA Store — `frontend/src/modules/qa/stores/qaStore.ts` Zustand store 管理问答会话状态 [completed: 2026-06-06]- [x] T276 MCP ServerManager 实现 — `odap/biz/integration/mcp_adapter/impl/server_manager.py` register_server / unregister_server / call_tool，基于 OpenHarness 实现 MCP v1.0 协议 - [x] T277 MCP 连接池实现 — `odap/biz/integration/mcp_adapter/impl/connection_pool.py` MCP Server 连接池管理，MCP Server 在独立沙箱进程中运行 - [x] T278 MCP Tool 注册 — `odap/biz/integration/mcp_adapter/impl/server_manager.py` MCP Server 通过统一工具注册表注册为 Tool - [x] T279 MCP 领域模型定义 — `odap/biz/integration/mcp_adapter/models/` MCPServerConfig(BaseModel) 含 id / name / endpoint / tools / status - [x] T280 MCP API 路由 — `odap/biz/integration/mcp_adapter/api/routes.py` POST /api/mcp/servers + DELETE /api/mcp/servers/{id} + GET /api/mcp/servers + POST /api/mcp/servers/{id}/tools/{tool_name} + GET /api/mcp/servers/{id}/status - [x] T281 [REVIEW] MCP 路由注册 — `odap/web/app.py` include_router(mcp_router) - [x] T282 [TDD] MCP 单元测试 — `tests/unit/test_mcp_adapter.py` 覆盖 Server 注册/注销/工具调用/连接池/沙箱隔离 - [x] T283 [SUBAGENT] 前端 MCP 管理组件 — `frontend/src/modules/system/components/MCPManager.tsx` L3 组织组件，MCP Server 列表 + 注册/注销 + 状态监控 + 工具调用 [completed: 2026-06-06]010: 多方案并行推演 + What-if [- [x] T247 ParallelRunner 实现 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` run_parallel(scenarios) 最多 10 个方案并行 + run_what_if(base_scenario, param_variations) 参数敏感性分析 - [x] T248 推演结果对比 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` 结果以并排对比视图展示，高亮关键指标差异 - [x] T249 推演进度 WebSocket 推送 — `odap/web/ws/event_bus.py` 新增 WS /ws/simulation/progress 实时推送推演进度 - [x] T250 推演历史双时态存储 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` 推演结果附带 valid_time + transaction_time，基于 Graphiti 双时态 - [x] T251 并行推演 API 路由 — `odap/biz/simulation/simulation_sandbox/api/routes- [x] T288 决策推荐 API 路由 — `odap/biz/decision/decision_recommendation/api/routes.py` POST /api/decision/recommend + POST /api/decision/risk-assessment + GET /api/decision/recommendations/{id}/explain + GET /api/decision/history - [x] T289 [REVIEW] 决策推荐路由注册 — `odap/web/app.py` include_router(decision_router) - [x] T290 [TDD] 决策推荐单元测试 — `tests/unit/test_decision_recommendation.py` 覆盖方案推荐/风险评估/排序/可解释性/RAG 增强 - [x] T291 [SUBAGENT] 前端决策推荐组件 — `frontend/src/modules/simulation/components/RecommendationPanel.tsx` L3 组织组件，方案推荐展示 + 风险评估 + 决策理由解释 [completed: 2026-06-06] T255 [SUBAGENT] 前端推演进度组件 — `frontend/src/modules/simulation/components/SimulationProgress.tsx` L2 分子组件，WebSocket 实时推演进度展示 [completed: 2026-06-- [x] T256 EventGenerator 实现 — `odap/biz/simulation/event_simulator/impl/event_- [x] T293 集成测试补全 — `tests/integration/` 补全 test_ontology_graphiti.py / test_agent_openharness.py / test_opa_integration.py / test_mcp_integration.py - [x] T294 E2E 测试补全 — `tests/e2e/` 补全 test_ontology_workflow.py / test_agent_workflow.py / test_simulation_workflow.py（Playwright） [completed: 2026-06-06]template.py` 预定义事件模板库 + 支持自定义模板 - [x] T259 事件手动注入 — `odap/biz/simulation/event_simulator/impl/event_generator.py` 手动注入关键事件，事件注入驱动本体状态演化 - [x] T260 事件模拟器 API 路由 — `odap/biz/simulation/event_simulator/api/routes.py` POST /api/event-simulator/generate + POST /api/event-simulator/inject + GET /api/event-simulator/timeline/{id} + POST /api/event-simulator/clock/control + GET /api/event-simulator/templates - [x] T261 [REVIEW] 事件模拟器路由注册 — `odap/web/app.py` include_router(event_simulator_router) - [x] T262 [TDD] 事件模拟器单元测试 — `tests/unit/test_event_simulator.py` 覆盖事件生成/注入/时间线/时钟控制/模板管理 [completed: 2026-06-06]WebSocket 推送 — `odap/web/ws/event_bus.py` 新增 WS /ws/simulation/progress 实时推送推演进度 - [x] T250 推演历史双时态存储 —- [x] T264 [SUBAGENT] 前端时间线组件 — `frontend/src/modules/simulation/components/TimelineView.tsx` L3 组织组件，事件时间线可视化 + 时钟控制面板 [completed: 2026-06-06]- [ ] T251 并行推演 API 路由 — `odap/biz/simulation/simulation_sandbox/api/routes- [x] T288 决策推荐 API 路由 — `odap- [x] T265 QA Engine 增强 — `odap/biz/data/qa/impl/qa_engine.py` 融合本体知识 + 图谱检索 + LLM 生成，多轮对话上下文理解（基于会话记忆） - [x] T266 TemporalReasoner 实现 — `odap/biz/data/qa/impl/temporal_reasoner.py` 基于 Graphiti valid_time 的时序查询，支持三类时序问答（"当时发生了什么"/"什么时候变成这样"/"某时间点综合状态"） - [x] T267 ChartRenderer 实现 — `odap/biz/data/qa/impl/chart_renderer.py` 混合渲染模式：轻量交互型前端渲染（G6+- [x] T308 现有页面迁移到 5 级组件体系 — `frontend/src/modules/` 逐步迁移现有页面到 L5 级别，使用 L1-L4 组件重构 - [x] T309 前端全局样式统一 — `frontend/src/modules/shared/styles/global.css` 统一 CSS Variables + Ant Design Token 系统 + 移动优先响应式 - [x] T310 Graphiti 双时态查询性能优化 — `odap/infra/graph/graph_service.py` 建立时间索引 + 缓存常用查询结果 [completed: 2026-06-06]equest / SessionResponse 等 - [x] T270 QA API 路由 — `odap/biz/data/qa/api/routes.py` POST /api/qa/ask + POST /api/qa/ask/temporal + GET /api/qa/sessions/{id} + POST /api/qa/chart - [x] T271 [REVIEW] QA 路由注册 — `odap/web/app.py` include_router(qa_router) [completed: 2026-06-06]gy_graphiti.py / test_agent_openharness.py / test_- [x] T273 [SUBAGENT] 前端问答页面增强 — `frontend/src/modules/qa/pages/QAPage.tsx` L5 页面，自然语言输入 + 多轮对话 + 图表展示 + 一键添加视图上下文 - [x] T274 [SUBAGENT] 前端图表渲染组件 — `frontend/src/modules/qa/components/ChartRenderer.tsx` L3 组织组件，8 种以上图表类型渲染（ECharts + G6 + Leaflet） - [x] T275 前端 QA Store — `frontend/src/modules/qa/stores/qaStore.ts` Zustand store 管理问答会话状态 [completed: 2026-06-06]- [x] T276 MCP ServerManager 实现 — `odap/biz/integration/mcp_adapter/impl/server_manager.py` register_server / unregister_server / call_tool，基于 OpenHarness 实现 MCP v1.0 协议 - [x] T277 MCP 连接池实现 — `odap/biz/integration/mcp_adapter/impl/connection_pool.py` MCP Server 连接池管理，MCP Server 在独立沙箱进程中运行 - [x] T278 MCP Tool 注册 — `odap/biz/integration/mcp_adapter/impl/server_manager.py` MCP Server 通过统一工具注册表注册为 Tool - [x] T279 MCP 领域模型定义 — `odap/biz/integration/mcp_adapter/models/` MCPServerConfig(BaseModel) 含 id / name / endpoint / tools / status - [x] T280 MCP API 路由 — `odap/biz/integration/mcp_adapter/api/routes.py` POST /api/mcp/servers + DELETE /api/mcp/servers/{id} + GET /api/mcp/servers + POST /api/mcp/servers/{id}/tools/{tool_name} + GET /api/mcp/servers/{id}/status - [x] T281 [REVIEW] MCP 路由注册 — `odap/web/app.- [x] T320 [SUBAGENT] 前端冲突解决组件 — `frontend/src/modules/ontology/components/ConflictResolver.tsx` L3 组织组件，候选值对比 + 策略选择 + LLM 判断按钮 [completed: 2026-06-06]T283 [SUBAGENT] 前端 MCP 管理组件 — `frontend/src/modules/system/components/MCPManager.tsx` L3 组织组件，MCP Server 列表 + 注册/注销 + 状态监控 + 工具调用 [completed: 2026-06-06]] T266 TemporalReasoner 实现 — `odap/biz/data/qa/impl/temporal_reasoner.py` 基于 Graphiti valid_time 的时序查询，支持三类时序问答（"当时发生了什么"/"什么时候变成这样"/"某时间点综合状态"） - [x] T267 ChartRenderer 实现 — `odap/biz/data/qa/impl/chart_renderer.py` 混合渲染模式：轻量交互型前端渲染（G6+- [x] T308 现有页面迁移到 5 级组件体系 — `frontend/src/modules/` 逐步迁移现有页面到 L5 级别，使用 L1-L4 组件重构 - [x] T309 前端全局样式统一 — `frontend/src/modules/shared/styles/global.css` 统一 CSS Variables + Ant Design Token 系统 + 移动优先响应式 - [x] T310 Graph- [x] T287 决策推荐 schemas 定义 — `odap/biz/decision/decision_recommendation/api/schemas.py` RecommendRequest / RecommendationResponse / RiskAssessmentResponse / ExplainResponse 等 - [x] T288 决策推荐 API 路由 — `odap/biz/decision/decision_recommendation/api/routes.py` POST /api/decision/recommend + POST /api/decision/risk-assessment + GET /api/decision/recommendations/{id}/explain + GET /api/decision/history - [x] T289 [REVIEW] 决策推荐路由注册 — `odap/web/app.py` include_router(decision_router) - [x] T290 [TDD] 决策推荐单元测试 — `tests/unit/test_decision_recommendation.py` 覆盖方案推荐/风险评估/排序/可解释性/RAG 增强 - [x] T291 [SUBAGENT] 前端决策推荐组件 — `frontend/src/modules/simulation/components/RecommendationPanel.tsx` L3 组织组件，方案推荐展示 + 风险评估 + 决策理由解释 [completed: 2026-06-06]` L3 组织组件，8 种以上图表类型渲染（ECharts + G6 + Leaflet） - [x] T275 前端 QA Store — `frontend/src/modules/qa/stores/qaStore.ts` Zustand store 管理问答会话状态 [completed: 2026-06-06]- [x] T276 MCP ServerManager 实现 — `odap/biz/integration/mcp_a- [x] T293 集成测试补全 — `tests/integration/` 补全 test_ontology_graphiti.py / test_agent_openharness.py / test_opa_integration.py / test_mcp_integration.py - [x] T294 E2E 测试补全 — `tests/e2e/` 补全 test_ontology_workflow.py / test_agent_workflow.py / test_simulation_workflow.py（Playwright） [completed: 2026-06-06]odap/biz/integration/mcp_adapter/impl/server_manager.py` MCP Server 通过统一工具注册表注册为 Tool - [x] T279 MCP 领域模型定义 — `odap/biz/integration/mcp_adapter/models/` MCPServerConfig(BaseModel) 含 id / name / endpoint / tools / status - [x] T280 MCP API 路由 — `odap/biz/integration/mcp_adapter/api/routes.py` POST /api/mcp/servers + DELETE /api/mcp/servers/{id} + GET /api/mcp/servers + POST /api/mcp/servers/{id}/tools/{tool_name} + GET /api/mcp/servers/{id}/status - [x] T281 [REVIEW] MCP 路由注册 — `odap/web/app.- [x] T320 [SUBAGENT] 前端冲突解决组件 — `frontend/src/modules/ontology/components/ConflictResolver.tsx` L3 组织组件，候选值对比 + 策略选择 + LLM 判断按钮 [completed: 2026-06-06]T283 [SUBAGENT] 前端 MCP 管理组件 — `frontend/src/modules/system/components/MCPManager.tsx` L3 组织组件，MCP Server 列表 + 注册/注销 + 状态监控 + 工具调用 [completed: 2026-06-06]{id}/tools/{tool_name} + GET /api/mcp/servers/{id}/status
- [x] T281 [REVIEW] MCP 路由注册 — `odap/web/app. [completed: 2026-06-07]

### FR-019: 决策推荐引擎

- [x] T284 RecommendationEngine 增强 — `odap/biz/de [completed: 2026-06-07]

### FR-028: 测试金字塔 + 质量门禁

- [x] T292 质量门禁脚本 — `scripts/quality-gate.sh` 统一质量门禁脚本：后端 ruff check + pytest --cov-fail-under=80，前端 lint + typecheck + test [completed: 2026-06-07]
- [x] T293 集成测试补全 — `tests/integration/` 补全 test_ontology_graphiti.py / test_agent_openharness.py / test_opa_integration.py / test_mcp_integration.py [completed: 2026-06-07]
- [x] T294 E2E 测试补全 — `tests/e2e/` 补全 t [completed: 2026-06-07]

- [x] T296 [REVIEW] ADR-030 状态修正 — `docs/07-adr/ADR-030.md` 状态从 Accepted 修正为 Superseded（OpenHarness 立即集成覆盖推迟决策） [completed: 2026-06-07]
- [x] T297 [REVIEW] ADR-036 补充严格对齐说明 — `docs/07-adr/ADR-036.md` 补充"严格对齐 Palantir AIP 本体模型"说明 [completed: 2026-06-07]
- [x] T298 [REVIEW] ADR-037 补充完整 i18n 实现 — `docs/07-adr/ADR-037.md` 补充完整 i18n 实现（后台管理+LLM 翻译） [completed: 2026-06-07]
- [x] T299 [REVIEW] ADR-038 补充本体拆分说明 — `docs/07-adr/ADR-038.md` 补充本体模型层+本体管理引擎拆分说明 [completed: 2026-06-07]
- [x] T300 [REVIEW] ADR-043 补充混合路由策 [completed: 2026-06-07]
- - [x] T308 现有页面迁移到 5 级组件体系 — `frontend/src/modules/` 逐步迁移现有页面到 L5 级别，使用 L1-L4 组件重构 - [x] T309 前端全局样式统一 — `frontend/src/modules/shared/styles/global.css` 统一 CSS Variables + Ant Design Token 系统 + 移动优先响应式 - [x] T310 Graphiti 双时态查询性能优化 — `odap/infra/graph/graph_service.py` 建立时间索引 + 缓存常用查询结果 [completed: 2026-06-06]P 依赖 — `docs/07-adr/ADR-026.md` 补充基于 OpenHarness 实现 - [x] T312 bootstep.py MinIO 服务集成 — `bootstep.py` 新增 MinIO 容器启动/停止/状态检查支持 [completed: 2026-06-06]ADR-027.md` 补充基于 OpenHarness 生命周期钩子的依赖说明
- [x] T306 [REVIEW] ADR-051 补充 OpenHarness 外层封装 — `docs/07-adr/ADR-051.md` 补充基于 OpenHarness 外层封装的依赖说明 [completed: 2026-06-07]
- [x] T307 [REVIEW] ADR-029 补充统一工具注册表 — `docs/07-adr/ADR-029.md` 补充统一工具注册表基于 OpenHarness Tool 接口 [completed: 2026-06-07]

### 前端组件迁移 + 性能优化

- [x] T308 现有页面迁移到 5 级组件体系 — `frontend/src/modules/` 逐步迁移现有页面到 L5 级别，使用 L1-L4 组件重构 [completed: 2026-06-07]
- [x] T309 前端全局样式统一 — `frontend/src/modules/shared/styles/global.css` 统一 CSS Variables + Ant Design Token 系统 + 移动优先响应式 [completed: 2026-06-07]
- [x] T310 Graphiti 双时态查询性能优化 — `odap/infra/graph/graph_service.py` 建立时间索引 + 缓存常用查询结果 [completed: 2026-06-07]
- [x] T311 API P95 性能优化 — 后端 API P95 < 500ms 优化，QA P95 < 3s 优化，推演 < 30s 优化 [completed: 2026-06-07]
- [x] T312 bootstep.py MinIO 服务集成 — `bootstep.py` 新增 MinIO 容器启动/停止/状态检查支持 [completed: 2026-06-07]

---

## Phase 10: Brainstorm 边缘场景补全（2026-05-31 brainstorm 增量）

> 预计工期: 4-5 周 | 依赖 Phase 9 | 聚焦 6 个 brainstorm 边缘场景 | 任务编号 T313-T330

### SC-01: 多源冲突解决（OntoFlow 范式强化）

- [x] T313 [P] 冲突解决策略领域模型 — `odap/biz/core/ontology/conflict/models/conflict_resolution.py` `ConflictResolution(str, Enum)` 含 FIRST_WINS / LAST_WINS / LLM_JUDGE / MANUAL 四种策略 + `ConflictRecord(BaseModel)` 含 entity_id / conflict_type / candidates / chosen ✅ 2026-06-05
- [x] T314 [P] [REVIEW] 冲突解决器抽象接口 — `odap/biz/core/ontology/conflict/interfaces/conflict_resolver.py` `ConflictResolver(ABC)` 定义 resolve(conflict) / detect_conflicts(sources) ✅ 2026-06-05
- [x] T315 ConflictResolverIm- [x] T320 [SUBAGENT] 前端冲突解决组件 — `frontend/src/modules/ontology/components/ConflictResolver.tsx` L3 组织组件，候选值对比 + 策略选择 + LLM 判断按钮 [completed: 2026-06-06]LLM 判断）、MANUAL（标记待人工处理）✅ 2026-06-05
- [x] T316 ConflictService 编排层 — `odap/biz/core/ontology/conflict/services/conflict_service.py` 返回 Dict[str, Any]，集成到数据摄入流程 ✅ 2026-06-05
- [x] T317 冲突解决 API 路由 — `odap/biz/core/ontology/conflict/api/routes.py` `APIRouter(prefix="/api/ontology/conflict")` POST `/detect` + POST `/resolve/{conflict_id}` + GET `/conflicts?status=pending` ✅ 2026-06-05
- [x] T318 [REVIEW] 冲突解决路由注册 — `odap/web/app.py` `include_router(conflict_router)` ✅ 2026-06-05
- [x] T319 [TDD] 冲突解决单元测试 — `tests/unit/test_conflict_resolver.py` 覆盖 4 种策略、检测逻辑、人工处理流程（21 用例全部通过）✅ 2026-06-05
- [x] T320 [SUBAGENT] 前端冲突解决组件 — `frontend/src/modules/ontology/components/ConflictResolver.tsx` L3 组织组件，候选值对比 + 策略选择 + LLM 判断按钮 [completed: 2026-06-07]

### SC-02: 冷启动数据稀疏

- [x] T321 冷启动引导服务 — `odap/biz/core/ontology/cold_start/impl/bootstrap.py` 当新工作空间无数据时，从模板库加载示例本体（金融/医疗/制造三个行业模板）✅ 2026-06-05
- [x] T322 [TDD] 冷启动单元测试 — `tests/unit/test_cold_start.py` 覆盖模板加载、数据稀疏检测、引导流程（21 用例全部通过）✅ 2026-06-05
- [x] T323 行业模板库 — `odap/biz/core/ontology/cold_start/templates/` 三个 YAML 模板（finance.yaml / healthcare.yaml / manufacturing.yaml）✅ 2026-06-05

### SC-03: 大规模本体分片

- [x] T324 本体分片器 — `odap/biz/core/ontology/sharding/impl/sharder.py` 当 ObjectType > 10000 实例时按主键 hash 自动分片，查询时并行扫描并合并 ✅ 2026-06-06
- [x] T325 [TDD] 分片单元测试 — `tests/unit/test_sharding.py` 覆盖分片策略、并行查询、结果合并（23 用例全部通过）✅ 2026-06-06

### SC-04: 多租户隔离强化

- [x] T326 [REVIEW] 租户隔离中间件 — `odap/infra/security/tenant_isolation.py` 所有 API 自动注入 ws_id 过滤条件，越权访问返回 403（不泄漏存在性）✅ 2026-06-06
- [x] T327 [TDD] 租户隔离单元测试 — `tests/unit/test_tenant_isolation.py` 覆盖跨租户访问拦截、403 响应、审计日志（18 用例全部通过）✅ 2026-06-06

### SC-05: 审计日志保留策略

- [x] T328 审计保留策略 — `odap/infra/security/audit_retention.py` 默认 90 天保留，支持按 workspace / classification 自定义保留期，过期自动归档到 MinIO ✅ 2026-06-06
- [x] T329 [TDD] 审计保留单元测试 — `tests/unit/test_audit_retention.py` 覆盖保留期计算、过期归档、查询历史归档（41 用例全部通过）✅ 2026-06-06

### SC-06: 错误降级与熔断

- [x] T330 [REVIEW] 熔断器中间件 — `odap/infra/resilience/circuit_breaker.py` 对外部服务（LLM/Neo4j/OPA）实现熔断（错误率 > 50% 持续 30s 触发），半开探测恢复（46 用例全部通过）✅ 2026-06-06

---

## Phase 11: Palantir/OntoFlow 增强层（2026-06-05 brainstorm 增量）

> 预计工期: 12-15 周（4 个里程碑 M1-M4）| 依赖 Phase 3（FR-001/002/029）| 部分可并行
> 设计原则：零结构破坏（叠加于 FR-001）、职责分离（OPA vs Data Health）、Action-Skill 分层、Goal-driven 演化
> **本- [x] T346 [SUBAGENT] 前端 Health 报告页面 — `frontend/src/modules/ontology/pages/HealthDashboard.tsx` L5 页面，规则列表 + 扫描触发 + 报告可视化（饼图+表格） [completed: 2026-06-06]1 [P] [SUBAGENT] Health 模块目录结构创建 — `odap/biz/core/ontology/health/` 创建 `api/` `models/` `interfaces/` `impl/` `services/` `storage/` 子目录 + `__init__.py` ✅ 2026-06-06
- [x] T332 [P] HealthRule 领域模型定义 — `odap/biz/core/ontology/health/models/rule.py` `HealthRule(BaseModel)` 含 `target_type_id`、`check_expression` (JSON/YAML)、`severity` (info/warning/error/critical)、`schedule` (cron)、`notification_channel` (JSON) ✅ 2026-06-06
- [x] T333 [P] HealthReport 领域模型定义 — `odap/biz/core/ontology/health/models/report.py` `HealthReport(BaseModel)` 含 `instance_id`、`rule_id`、`status` (pass/warn/fail)、`details`、`scanned_at` ✅ 2026-06-06
- [x] T334 [P] [REVIEW] HealthRuleRepository 抽象接口 — `odap/biz/core/ontology/health/interfaces/health_rule_repository.py` ABC 定义 CRUD + `list_by_target_type` + `list_by_severity` ✅ 2026-06-06
- [x] T335 [P] [REVIEW] HealthScanner 抽象接口 — `odap/biz/core/ontology/health/interfaces/health_scanner.py` ABC 定义 `scan(rule_id: Optional[str]) -> List[HealthReport]` ✅ 2026-06-06
- [x] T336 SQLite Health Storage — `odap/biz/core/ontology/health/storage/sqlite_health_storage.py` 实现 `health_rules` / `health_reports` 表 CRUD + `__init__.py` 别名导出 ✅ 2026-06-06
- [x] T337 [REVIEW] HealthRuleRepositoryImpl — `odap/biz/core/ontology/health/impl/health_rule_repository_impl.py` 实现接口 ✅ 2026-06-06
- [x] T338 HealthScannerImpl — `odap/biz/core/ontology/health/impl/health_scanner_impl.py` 支持 5 种规则：not_null / unique / regex / range / referential_integrity，使用 JSONLogic 引擎求值 ✅ 2026-06-06
- [x] T339 NotificationDispatcher — `odap/biz/core/ontology/health/impl/notification_dispatcher.py` 支持 email / webhook / im 三种通道，异步发送（asyncio.create_task）✅ 2026-06-06
- [x] T340 Health Service 编排层 — `odap/biz/core/ontology/health/services/health_service.py` 返回 Dict[str, Any] ✅ 2026-06-06
- [x] T341 Heal- [x] T373 [SUBAGENT] 前端继承关系可视化 — `frontend/src/modules/ontology/components/InheritanceGraph.tsx` L3 组件，G6 渲染继承树 [completed: 2026-06-06]s CRUD + scan + reports 查询）✅ 2026-06-06
- [x] T342 Health schemas 定义 — `odap/biz/core/ontology/health/api/schemas.py` CreateHealthRuleRequest / HealthRuleResponse / ScanRequest / HealthReportResponse ✅ 2026-06-06
- [x] T343 [REVIEW] Health 路由注册 — `odap/web/app.py` `include_router(health_router)` ✅ 2026-06-06
- [x] T344 [TDD] Health 单元测试 — `tests/unit/test_health.py` 覆盖 5 种规则、CRUD、扫描调度、通知发送（97 用例全部通过）✅ 2026-06-06
- [x] T345 [SUBAGENT] 前端 Health 规则编辑器 — `frontend/src/modules/ontology/components/HealthRuleEditor.tsx` L3 组件，YAML 编辑 + 表达式实时校验 + 严重程度选择 [completed: 2026-06-07]
- [x] T346 [SUBAGENT] 前端 Health 报告页面 — `frontend/src/modules/ontology/pages/HealthDashboard.tsx` L5 页面，规则列表 + 扫描触发 + 报告可视化（饼图+表格） [completed: 2026-06-07]

#### FR-032: 本体 Branch & Merge

- [x] T347 [P] [SUBAGENT] Branch 模块目录结构创建 — `odap/biz/core/ontology/branch/` 创建 `api/` `models/` `interfaces/` `impl/` `services/` `storage/` 子目录 ✅ 2026-06-06
- [x] T348 [P] Branch 领域模型定义 — `odap/biz/core/ontology/branch/models/branch.py` `Branch(BaseModel)` 含 `id` / `name` / `ontology_id` / `base_version_id` / `head_version_id` / `status` (active/merged/abandoned) ✅ 2026-06-06
- [x] T349 [P] MergeRequest 领域模型 — `odap/biz/core/ontology/branch/models/merge_request.py` `MergeRequest(BaseModel)` 含 `source_branch_id` / `target_branch_id` / `conflicts` (JSON) / `status` (open/approved/merged/conflict) ✅ 2026-06-06
- [x] T350 [P] Conflict 领域模型 — `odap/biz/core/ontology/branch/models/conflict.py` `Conflict(BaseModel)` 含 `path` (JSON Pointer) / `base_value` / `ours_value` / `theirs_value` / `resolution` ✅ 2026-06-06
- [x] T351 [REVIEW] BranchRepository 抽象接口 — `odap/biz/core/ontology/branch/interfaces/branch_repository.py` ABC 定义 CRUD + `list_by_ontology` + `get_active` ✅ 2026-06-06
- [x] T352 [REVIEW] MergeEngine 抽象接口 — `odap/biz/core/ontology/branch/interfaces/merge_engine.py` ABC 定义 `merge(source, target) -> MergeResult` / `detect_conflicts(base, ours, theirs) -> List[Conflict]` ✅ 2026-06-06
- [x] T353 SQLite Branch Storage — `odap/biz/core/ontology/branch/storage/sqlite_branch_storage.py` 实现 `branches` / `merge_requests` / `conflicts` 表 CRUD ✅ 2026-06-06
- [x] T354 [REVIEW] BranchRepositoryImpl — `odap/biz/core/ontology/branch/impl/branch_repository_impl.py` ✅ 2026-06-06
- [x] T355 ThreeWayMergeEngine — `odap/biz/core/ontology/branch/impl/merge_engine.py` 基于 RFC 6902 JSON Patch 实现 3-way merge，自动合并无冲突字段，冲突字段返回由用户解决 ✅ 2026-06-06
- [x] T356 Branch Service 编排层 — `odap/biz/core/ontology/branch/services/branch_service.py` 集成 OntologyVersion 与 MergeEngine ✅ 2026-06-06
- [x] T357 Bran- [x] T390 [P] [SUBAGENT] ComputedProperty 模块目录创建 — `odap/biz/core/ontology/computed/` 标准分层 - [x] T391 [P] ComputedProperty 领域模型 — `odap/biz/core/ontology/computed/models/property.py` `ComputedProperty(BaseModel)` 含 `id` / `name` / `target_type_id` / `expression` (DSL) / `dependencies` (List[str]) / `materialization` (none/full/incremental) - [x] T392 [P] MaterializationJob 领域模型 — `odap/biz/core/ontology/computed/models/job.py` `MaterializationJob(BaseModel)` 含 `id` / `property_id` / `status` (pending/running/done/failed) / `started_at` / `finished_at` - [x] T393 DependencyTracker — `odap/biz/core/ontology/computed/impl/dependency_tracker.py` 解析表达式依赖（基于 AST 遍历），构建 DAG - [x] T394 [REVIEW] ExpressionEvaluator — `odap/biz/core/ontology/computed/impl/evaluator.py` 安全沙箱执行（RestrictedPython），支持数学/字符串/日期/聚合函数 - [x] T395 IncrementalComputer — `odap/biz/core/ontology/computed/impl/incremental.py` 当依赖属性变化时，仅重算受影响对象（DAG 反向传播） - [x] T396 SQLite Computed Storage — `odap/biz/core/ontology/computed/storage/sqlite_computed_storage.py` 实现 `computed_properties` / `materialization_jobs` / `materialized_values` 表 - [x] T397 ComputedService 编排层 — `odap/biz/core/ontology/computed/services/computed_service.py` - [x] T398 Computed API 路由 — `odap/biz/core/ontology/computed/api/routes.py` 端点：CRUD + POST `/recompute/{property_id}` + GET `/jobs/{id}/status` - [x] T399 [TDD] [REVIEW] Computed 单元测试 — `tests/unit/test_computed.py` 覆盖表达式求值、依赖追踪、增量重算、沙箱安全 [completed: 2026-06-06]z/core/ontology/inheritance/models/inheritance.py` `InheritanceEdge(BaseModel)` 含 `child_type_id` / `parent_type_id` / `depth` / `discriminator` (JSON) ✅ 2026-06-06
- [x] T366 [P] Mixin 领域模型 — `odap/biz/core/ontology/inheritance/models/mixin.py` `Mixin(BaseModel)` 含 `id` - [x] T402 [P] [SUBAGENT] ObjectView 模块目录创建 — `odap/biz/core/ontology/view/` 标准分层 - [x] T403 [P] ObjectView 领域模型 — `odap/biz/core/ontology/view/models/view.py` `ObjectView(BaseModel)` 含 `id` / `name` / `base_type_id` / `role` / `projected_properties` (List[str]) / `filters` (JSON) / `row_limit` / `sort_order` - [x] T404 [P] ViewPermission 领域模型 — `odap/biz/core/ontology/view/models/permission.py` `ViewPermission(BaseModel)` 含 `view_id` / `role` / `can_export` / `can_share` / `redaction_rules` (JSON) - [x] T405 [REVIEW] ViewRepository 抽象接口 — `odap/biz/core/ontology/view/interfaces/view_repository.py` - [x] T406 [REVIEW] ViewQueryEngine 抽象接口 — `odap/biz/core/ontology/view/interfaces/view_query_engine.py` 定义 `query(view_id, user_context) -> List[Dict]` - [x] T407 SQLite View Storage — `odap/biz/core/ontology/view/storage/sqlite_view_storage.py` 实现 `object_views` / `view_permissions` 表 - [x] T408 [REVIEW] ViewRepositoryImpl — `odap/biz/core/ontology/view/impl/view_repository_impl.py` - [x] T409 [REVIEW] ViewQueryEngineImpl — `odap/biz/core/ontology/view/impl/view_query_engine_impl.py` 集成 OPA（读取时权限校验）+ 字段脱敏（redaction_rules） - [x] T410 ViewService 编排层 — `odap/biz/core/ontology/view/services/view_service.py` - [x] T411 View API 路由 — `odap/biz/core/ontology/view/api/route- [x] T390 [P] [SUBAGENT] ComputedProperty 模块目录创建 — `odap/biz/core/ontology/computed/` 标准分层 - [x] T391 [P] ComputedProperty 领域模型 — `odap/biz/core/ontology/computed/models/property.py` `ComputedProperty(BaseModel)` 含 `id` / `name` / `target_type_id` / `expression` (DSL) / `dependencies` (List[str]) / `materialization` (none/full/incremental) - [x] T392 [P] MaterializationJob 领域模型 — `odap/biz/core/ontology/computed/models/job.py` `MaterializationJob(BaseModel)` 含 `id` / `property_id` / `status` (pending/running/done/failed) / `started_at` / `finished_at` - [x] T393 DependencyTracker — `odap/biz/core/ontology/computed/impl/dependency_tracker.py` 解析表达式依赖（基于 AST 遍历），构建 DAG - [x] T394 [REVIEW] ExpressionEvaluator — `odap/biz/core/ontology/computed/impl/evaluator.py` 安全沙箱执行（RestrictedPython），支持数学/字符串/日期/聚合函数 - [x] T395 IncrementalComputer — `odap/biz/core/ontology/computed/impl/incremental.py` 当依赖属性变化时，仅重算受影响对象（DAG 反向传播） - [x] T396 SQLite Computed Storage — `odap/biz/core/ontology/computed/storage/sqlite_computed_storage.py` 实现 `computed_properties` / `materialization_jobs` / `materialized_values` 表 - [x] T397 ComputedService 编排层 — `odap/biz/core/ontology/computed/services/computed_service.py` - [x] T398 Computed API 路由 — `odap/biz/core/ontology/computed/api/routes.py` 端点：CRUD + POST `/recompute/{property_id}` + GET `/jobs/{id}/status` - [x] T399 [TDD] [REVIEW] Computed 单元测试 — `tests/unit/test_computed.py` 覆盖表达式求值、依赖追踪、增量重算、沙箱安全 [completed: 2026-06-06]y` 实现 `action_types` / `action_executions` 表 ✅ 2026-06-06
- [x] T381 [REVIEW] ActionTypeRepositoryImpl — `odap/biz/core/ontology/action/impl/action_type_repository_impl.py` ✅ 2026-06-06
- [x] T382 SkillBackedExecutor — `odap/biz/core/ontology/action/impl/skill_executor.py- [x] T402 [P] [SUBAGENT] ObjectView 模块目录创建 — `odap/biz/core/ontology/view/` 标准分层 - [x] T403 [P] ObjectView 领域模型 — `odap/biz/core/ontology/view/models/view.py` `ObjectView(BaseModel)` 含 `id` / `name` / `base_type_id` / `role` / `projected_properties` (List[str]) / `filters` (JSON) / `row_limit` / `sort_order` - [x] T404 [P] ViewPermission 领域模型 — `odap/biz/core/ontology/view/models/permission.py` `ViewPermission(BaseModel)` 含 `view_id` / `role` / `can_export` / `can_share` / `redaction_rules` (JSON) - [x] T405 [REVIEW] ViewRepository 抽象接口 — `odap/biz/core/ontology/view/interfaces/view_repository.py` - [x] T406 [REVIEW] ViewQueryEngine 抽象接口 — `odap/biz/core/ontology/view/interfaces/view_query_engine.py` 定义 `query(view_id, user_context) -> List- [x] T391 [P] ComputedProperty 领域模型 — `odap/biz/core/ontology/computed/models/property.py` `ComputedProperty(BaseModel)` 含 `id` / `name` / `target_type_id` / `expression` (DSL) / `dependencies` (List[str]) / `materialization` (none/full/incremental) - [x] T392 [P] MaterializationJob 领域模型 — `odap/biz/core/ontology/computed/models/job.py` `MaterializationJob(BaseModel)` 含 `id` / `property_id` / `status` (pending/running/done/failed) / `started_at` / `finished_at` - [x] T393 DependencyTracker — `odap/biz/core/ontology/computed/impl/dependency_tracker.py` 解析表达式依赖（基于 AST 遍历），构建 DAG - [x] T394 [REVIEW] ExpressionEvaluator — `odap/biz/core/ontology/computed/impl/evaluator.py` 安全沙箱执行（RestrictedPython），支持数学/字符串/日期/聚合函数 - [x] T395 IncrementalComputer — `odap/biz/core/ontology/computed/impl/incremental.py` 当依赖属性变化时，仅重算受影响对象（DAG 反向传播） - [x] T396 SQLite Computed Storage — `odap/biz/core/ontology/computed/storage/sqlite_computed_storage.py` 实现 `computed_properties` / `materialization_jobs` / `materialized_values` 表 - [x] T397 ComputedService 编排层 — `odap/biz/core/ontology/computed/services/computed_service.py` - [x] T398 Computed API 路由 — `odap/biz/core/ontology/computed/api/routes.py` 端点：CRUD + POST `/recompute/{property_id}` + GET `/jobs/{id}/status` - [x] T399 [TDD] [REVIEW] Computed 单元测试 — `tests/unit/test_computed.py` 覆盖表达式求值、依赖追踪、增量重算、沙箱安全 [completed: 2026-06-06]nning/done/failed) / `started_at` / `finished_at`
- [x] T393 DependencyTracker — `odap/biz/core/ontology/computed/impl/dependency_tracker.py` 解析表达式依赖（基于 AST 遍历），构建 DAG [completed: 2026-06-07]
- [x] T394 [REVIEW] ExpressionEvaluator — `odap/biz/core/ontology/computed/impl/evaluator.py` 安全沙箱执行（Res [completed: 2026-06-07]
- [x] T404 [P] ViewPermission 领域模型 — `odap/biz/core/ontology/view/models/permission.py` `ViewPermission(BaseModel)` 含 `view_id` / `role` / `can_export` / `can_share` / `redaction_rules` (JSON) [completed: 2026-06-07]
- [x] T405 [REVIEW] ViewRepository 抽象接口 — `odap/biz/core/ontology/view/interfaces/view_repository.py` [completed: 2026-06-07]
- [x] T406 [REVIEW] ViewQueryEngine 抽象接口 — `odap/biz/core/ontology/view/interfaces/view_query_engine.py` 定义 `query(view_id, user_context) -> List[Dict]` [completed: 2026-06-07]
- [x] T407 SQLite View Storage — `odap/biz/core/ontology/view/storage/sqlite_view_storage.py` 实现 `object_views` / `view_permissions` 表 [completed: 2026-06-07]
- [x] T408 [REVIEW] ViewRepositoryImpl — `odap/biz/core/ontology/view/impl/view_repository_impl.py` [completed: 2026-06-07]
- [x] T409 [REVIEW] ViewQueryEngineImpl — `odap/biz/core/ontology/view/impl/view_query_engine_impl.py` 集成 OPA（读取时权限校验）+ 字段脱敏（redaction_rules） [completed: 2026-06-07]
- [x] T410 ViewService 编排层 — `odap/biz/core/ontology/view/services/view_service.py` [completed: 2026-06-07]
- [x] T411 View API 路由 — `odap/biz/core/ontology/view/api/routes.py` CRUD + POST `/api/ontology/views/{id}/query` [completed: 2026-06-07]
- [x] T412 [TDD] [REVIEW] View 单元测试 — `tests/unit/test_view.py` 覆盖视图 CRUD、字段投影、过滤、权限校验、脱敏规则 [completed: 2026-06-07]
- [x] T413 [SUBAGENT] 前端视图设计器 — `frontend/src/modules/ontology/components/ViewDesigner.tsx` L3 组件，可视化属性选择 + 过滤条件构建 + 角色绑定 [completed: 2026-06-07]
- [x] T414 [REVIEW] [SUBAGENT] 前端视图查询页面 — `frontend/src/modules/ontology/pages/ObjectViewPage.tsx` L5 页面，视图查询 + 导出（带权限控制） [completed: 2026-06-07]

### M4 里程碑：OntoFlow Goal-driven 演化（FR-037）

#### FR-037: OntoFlow Goal 驱动演化

- [x] T415 [P] [SUBAGENT] Goal 模块目录创建 — `odap/biz/core/ontology/goal/` 标准分层 [completed: 2026-06-06]
- [x] T416 [P] Goal 领域模型 — `odap/biz/core/ontology/goal/models/goal.py` `Goal(BaseModel)` 含 `id` / `title` / `description` / `business_objective` / `rationale` (LLM 生成) / `status` (proposed/approved/rejected/in-progress/achieved/abandoned) / `parent_goal_id` [completed: 2026-06-06]
- [x] T417 [P] ChangeProposal 领域模型 — `odap/biz/core/ontology/goal/models/proposal.py` `ChangeProposal(BaseModel)` 含 `id` / `goal_id` / `changes` (JSON Patch) / `impact_analysis` / `estimated_benefit` / `status` [completed: 2026-06-06]
- [x] T418 [P] ImpactAnalysis 领域模型 — `odap/biz/core/ontology/goal/models/impact.py` `ImpactAnalysis(BaseModel)` 含 `affected_types` / `affected_instances_count` / `breaking_changes` (List[str]) / `estimated_migration_cost` [completed: 2026-06-06]
- [x] T419 [REVIEW] GoalRepository 抽象接口 — `odap/biz/core/ontology/goal/interfaces/goal_repository.py` [completed: 2026-06-06]
- [x] T420 [REVIEW] ImpactAnalyzer 抽象接口 — `odap/biz/core/ontology/goal/interfaces/impact_analyzer.py` 定义 `analyze(changes: JSONPatch) -> ImpactAnalysis` [completed: 2026-06-06]
- [x] T421 SQLite Goal Storage — `odap/biz/core/ontology/goal/storage/sqlite_goal_storage.py` 实现 `goals` / `change_proposals` / `impact_analyses` 表 [completed: 2026-06-06]
- [x] T422 [REVIEW] GoalRepositoryImpl — `odap/biz/core/ontology/goal/impl/goal_repository_impl.py` [completed: 2026-06-06]
- [x] T423 LLM Rationale Generator — `odap/biz/core/ontology/goal/impl/rationale_generator.py` 调用 LLM 为 Goal 生成 business_rationale（多轮追问澄清） [completed: 2026-06-06]
- [x] T424 ImpactAnalyzerImpl — `odap/biz/core/ontology/goal/impl/impact_analyzer_impl.py` 静态分析：受影响 ObjectType / Action Type / 估算迁移成本 [completed: 2026-06-06]
- [x] T425 GoalService 编排层 — `odap/biz/core/ontology/goal/services/goal_service.py` [completed: 2026-06-06]
- [x] T426 Goal API 路由 — `odap/biz/core/ontology/goal/api/routes.py` CRUD + POST `/api/ontology/goals/{id}/propose-change` + GET `/api/ontology/goals/{id}/lineage` [completed: 2026-06-06]
- [x] T427 [TDD] Goal 单元测试 — `tests/unit/test_goal.py` 覆盖 Goal CRUD、LLM rationale 生成、Impact 分析、Goal lineage [completed: 2026-06-06]
- [x] T428 [SUBAGENT] 前端 Goal 看板 — `frontend/src/modules/ontology/pages/GoalKanban.tsx` L5 页面，Goal 状态看板（拖拽切换状态）+ 时间线 [completed: 2026-06-06]
- [x] T429 [SUBAGENT] 前端 Change Proposal 组件 — `frontend/src/modules/ontology/components/ChangeProposalCard.tsx` L3 组件，提案详情 + 影响分析可视化 + 审批按钮 [completed: 2026-06-06]
- [x] T430 [SUBAGENT] 前端 Goal Lineage 视图 — `frontend/src/modules/ontology/components/GoalLineage.tsx` L3 组件，父子 Goal + 关联变更 + G6 图谱渲染 [completed: 2026-06-06]

### Phase 11 集成与文档

- [x] T431 [REVIEW] ADR-055 状态修正 [completed: 2026-06-06] — `docs/07-adr/ADR-055.md` 补充"Action Type = 业务接口，Skill = 工程实现"分层原则
- [x] T432 FR-031..FR-037 用户文档 [completed: 2026-06-06] — `docs/03-modules/ontology/DESIGN.md` 补充 Data Health / Branch / Inheritance / Action / Computed / View / Goal 章节
- [x] T433 API 契约文档 [completed: 2026-06-06] — `specs/001-odap-platform/contracts/core-ontology-p4.md` 已创建，补充 curl 示例和错误码表（新增 §8 OntoFlow Goal 详细规范 + §9 错误码表扩展 + §10 完整 curl 示例）
- [x] T434 [TDD] Phase 11 集成测试 [completed: 2026-06-06] — `tests/integration/test_p4_features.py` 端到端测试 Branch 创建→Health 扫描→Action 执行→Goal 关联（25 个 Service 层用例 + 10 个 HTTP 集成用例）

---

## Dependencies & Execution Order

### Phase 依赖关系

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational)
    ↓
Phase 3 (US1 - P1 MVP) ←── 阻塞后续所有 Phase
    ↓
Phase 4 (US2) ──┐
Phase 5 (US3) ──┤←── 可并行
    ↓           ↓
Phase 6 (US6) ←── 依赖 Phase 4 + Phase 5
    ↓
Phase 7 (US4) ──┐
Phase 8 (US5) ──┤←── 可并行
    ↓           ↓
Phase 9 (Polish)
    ↓
Phase 10 (Brainstorm Edge Cases) ←── 6 个边缘场景补全
    ↓
Phase 11 (Palantir/OntoFlow P4) ←── 7 个新 FR，4 个里程碑
    ├── M1: Data Health (FR-031) + Branch & Merge (FR-032)
    ├── M2: Inheritance (FR-033) + Action Type (FR-034)
    ├── M3: Computed Property (FR-035) + Object View (FR-036)
    └── M4: OntoFlow Goal-driven (FR-037)
```

### 关键路径

```
T001-T025 → T026-T053 → T054-T133 → T134-T162 → T184-T239 → T240-T264 → T292-T312 → T313-T330 → T331-T434
```

### FR 间依赖

| FR | 依赖 FR | 原因 |
|----|---------|------|
| FR-002 | FR-001 | 版本管理依赖本体模型层定义 |
| FR-003 | FR-001 | 实例 CRUD 由本体模型层负责 |
| FR-004 | FR-001, MinIO | 多模态数据接入依赖实体类型定义和对象存储 |
| FR-015 | FR-002, FR-003 | 审计依赖版本管理和实例操作 |
| FR-029 | FR-001 | OntologyDocument 格式依赖实体类型/属性/关系模型 |
| FR-027 | FR-001 | 数据分类标记依赖 Property.classification_level |
| FR-005 | FR-001, OpenHarness | Agent 编排依赖本体知识和 OpenHarness Swarm |
| FR-006 | FR-005 | 决策可视化依赖 Agent 执行过程 |
| FR-014 | FR-005, OpenHarness | Skill 热插拔依赖 OpenHarness Skill 管理 |
| FR-007 | FR-001 | OPA 策略依赖本体资源定义 |
| FR-008 | FR-007 | ABAC 依赖 OPA 策略引擎 |
| FR-016 | FR-005, FR-023 | 认知引擎依赖 Agent 编排和统一查询 |
| FR-023 | FR-001, Graphiti | 统一查询依赖本体 Schema 和 Graphiti 双时态 |
| FR-024 | OpenHarness | 会话记忆依赖 OpenHarness Memory Plugin |
| FR-025 | FR-014, FR-023 | 工具注册表依赖 Skill 和 QueryService |
| FR-026 | FR-016, FR-023 | 语义层依赖意图识别和统一查询 |
| FR-018 | OpenHarness | Hook 系统依赖 OpenHarness 生命周期钩子 |
| FR-022 | FR-005, FR-018 | 闭环反馈依赖 Agent 执行和 Hook 系统 |
| FR-009 | FR-005, OpenHarness | 沙箱推演依赖 Agent 和 OpenHarness 沙箱 |
| FR-010 | FR-009 | 并行推演依赖沙箱环境 |
| FR-020 | FR-001 | 事件模拟器依赖本体定义 |
| FR-011 | FR-023, FR-024 | 问答依赖统一查询和会话记忆 |
| FR-017 | FR-025, OpenHarness | MCP 依赖工具注册表和 OpenHarness |
| FR-019 | FR-009, Graphiti | 决策推荐依赖推演结果和 Graphiti RAG |
| **FR-031** | **FR-001** | **Data Health 规则依赖 ObjectType 定义** |
| **FR-032** | **FR-001, FR-002** | **Branch & Merge 依赖 OntologyDocument 与版本管理** |
| **FR-033** | **FR-001** | **ObjectType 继承依赖实体类型模型** |
| **FR-034** | **FR-001, FR-005, FR-014** | **Action Type 依赖 ObjectType、Agent 与 Skill 委托** |
| **FR-035** | **FR-001, Graphiti** | **Computed Property 依赖实体类型 + Graphiti 物化存储** |
| **FR-036** | **FR-001, FR-007, FR-008** | **Object View 依赖实体类型 + OPA 读权限 + 字段脱敏** |
| **FR-037** | **FR-001, FR-002, FR-032** | **OntoFlow Goal 依赖 OntologyDocument + 版本 + Branch（变更提案）** |

---

## Parallel Execution Examples

### Phase 1 并行组

```
Group A (后端基础设施):  T001 → T002 → T003 → T004 → T005
Group B (前端组件体系):  T006 → T007 → T008 → T009 → T010 → T011 → T012
Group C (前端响应式):    T013 → T014
Group D (前端 i18n):     T015 → T016 → T017
Group E (OpenHarness):   T018 → T019 → T020 → T021 → T022 → T023 → T024
```

### Phase 3 并行组

```
Group A (FR-001 本体设计器):     T054 → T055 → T056 → T057 → T058 → T059 → T060 → T061-T067
Group B (FR-002 版本管理):       T068 → T069 → T070 → T071 → T072 → T073 → T074 → T075-T079 (依赖 T054)
Group C (FR-003 批量导入):       T080 → T081 → T082 → T083 → T084 → T085-T087 (依赖 T054)
Group D (FR-004 多模态):         T088 → T089 → T090 → T091 → T092 → T093-T095 (依赖 T004, T054)
Group E (FR-012 工作空间):       T096 → T097 → T098 → T099 → T100-T102 (可独立)
Group F (FR-013 场景切换):       T103 → T104 → T105 → T106-T108 (依赖 T097)
Group G (FR-029 OntologyDocument): T114 → T115 → T116 → T117-T118 (依赖 T033)
Group H (FR-030 i18n):           T124 → T125 → T126 → T127 → T128 → T129 → T130 → T131-T133 (可独立)
```

### Phase 4 + Phase 5 并行

```
Phase 4 (US2 Agent):  T134-T162
Phase 5 (US3 策略):   T163-T183
```

### Phase 7 + Phase 8 并行

```
Phase 7 (US4 推演):  T240-T264
Phase 8 (US5 问答):  T265-T291
```

### Phase 10 内部并行（Brainstorm 边缘场景，6 组独立任务）

```
Group A (SC-01 冲突解决):     T313 → T314 → T315 → T316 → T317 → T318 → T319 → T320 (8 任务)
Group B (SC-02 冷启动):       T321 → T322 → T323 (3 任务)
Group C (SC-03 分片):         T324 → T325 (2 任务)
Group D (SC-04 多租户):       T326 → T327 (2 任务)
Group E (SC-05 审计保留):     T328 → T329 (2 任务)
Group F (SC-06 熔断):         T330 (1 任务)
```

### Phase 11 内部并行（Palantir/OntoFlow，4 个里程碑按序交付但组内可并行）

```
M1 (FR-031 Data Health):   T331-T346 (16 任务，可与 M1-M2 内任务并行)
M1 (FR-032 Branch):        T347-T363 (17 任务，依赖 T068 FR-002 版本管理)

M2 (FR-033 Inheritance):   T364-T374 (11 任务)
M2 (FR-034 Action Type):   T375-T389 (15 任务，依赖 T212 FR-025 Skill 注册表)

M3 (FR-035 Computed):      T390-T401 (12 任务)
M3 (FR-036 Object View):   T402-T414 (13 任务，依赖 T171 FR-008 ABAC)

M4 (FR-037 OntoFlow Goal): T415-T430 (16 任务，依赖 T331-T363 M1 全部完成)

Phase 11 集成:              T431-T434 (4 任务，文档+集成测试)
```


## Superpowers Execution Notes

> 本节说明如何在实施阶段应用 Superpowers 执行标记。
> 详细标记规则见 [tasks-template.md](.specify/extensions/superspec/templates/tasks-template.md) 与 [superpowers-bridge.md](.specify/extensions/superspec/references/superpowers-bridge.md)。

### Marker 分布概览

| Marker | 含义 | 适用任务 | 行为 |
|--------|------|---------|------|
| `[P]` | 并行 | 不同文件、无依赖 | 使用 Task tool 并行 |
| `[TDD]` | 测试驱动 | 新增模块、测试、验证逻辑 | RED→GREEN→REFACTOR |
| `[REVIEW]` | 评审门 | ADR 变更、路由注册、接口定义、安全 | 暂停等待人工 review |
| `[SUBAGENT]` | 子代理 | 前端组件、模块目录结构、i18n 翻译 | 派发到子代理并行 |

### 按 Phase 的检查点协议

每个 Phase 结束时的强制检查：

1. **Phase 1 (Setup)**: 项目可启动 — 验证 `python bootstep.py status` 全绿
2. **Phase 2 (Foundational)**: 基础就绪 — 验证 `pytest tests/unit/ -v` 通过
3. **Phase 3 (US1 MVP)**: ⭐ MVP 完成 — 演示本体设计 + 版本回滚 + 数据摄入
4. **Phase 4-6 (US2/3/6)**: 核心能力 — 验证 OPA 拒绝 + Agent 意图识别
5. **Phase 7-8 (US4/5)**: 推演+问答 — 验证沙箱隔离 + 图表渲染
6. **Phase 9 (Polish)**: 质量门禁 — 覆盖率 ≥ 80% + Lint 0 error
7. **Phase 10 (Brainstorm)**: 边缘场景 — 验证冲突解决 + 冷启动 + 多租户隔离
8. **Phase 11 (Palantir/OntoFlow)**: 4 个里程碑 Gate Review
   - **M1 Gate**: Data Health 5 规则 + Branch 3-way merge 通过集成测试
   - **M2 Gate**: Inheritance 深度 ≤ 5 + Action Type Skill 委托通过审计
   - **M3 Gate**: Computed 增量重算 + View 字段脱敏通过权限测试
   - **M4 Gate**: Goal + Change Proposal + LLM rationale 通过业务评审

### 失败处理

- **TDD 任务失败**: 立即停止，禁止跳过 RED 阶段
- **REVIEW 任务失败**: 阻塞后续所有 [SUBAGENT] 派发
- **SUBAGENT 任务失败**: 重新派发同一子代理，超过 3 次降级为串行实现
- **关键路径阻塞**: 触发 `/speckit-superspec-status` 检查进度

### 与 Constitution 的对应

| Constitution 原则 | 对应 Marker | 验证手段 |
|-------------------|-------------|----------|
| I. 简单 | `[TDD]` | 函数体 < 40 行（CI 守卫 R-P3-001） |
| II. 可维护 | `[REVIEW]` | apiClient 统一、ADR 一致性 |
| III. 测试优先 | `[TDD]` | 覆盖率 ≥ 80% |
| IV. 避免过度设计 | `[REVIEW]` | 借鉴而非全盘对齐 |
| V. SDD 质量门 | `[REVIEW]` | G-1..G-12 测试通过 |

---

## Implementation Strategy

### 1. MVP 优先（Phase 1-3）

Phase 3 完成后即具备 MVP 能力：本体设计 + 版本管理 + 数据摄入 + 工作空间 + i18n。此时可进行内部演示和早期用户反馈收集。

### 2. 增量交付（Phase 4-6）

每个 Phase 完成后交付一组完整能力：
- Phase 4: Agent 协同调度 + 决策可视化 + Skill 热插拔
- Phase 5: OPA 策略治理 + ABAC 权限 + OAuth2/SSO
- Phase 6: 认知引擎 + 统一查询 + 记忆管理 + 工具注册 + 语义层 + Hook + 反馈闭环

### 3. 增强交付（Phase 7-8）

Phase 7 和 Phase 8 可并行开发：
- Phase 7: 沙箱推演 + 并行推演 + 事件模拟器
- Phase 8: 问答引擎 + MCP 集成 + 决策推荐

### 4. 质量收尾（Phase 9）

所有功能开发完成后，统一进行测试补全、ADR 修正、性能优化和组件迁移。

### 5. Brainstorm 边缘场景补全（Phase 10）

Phase 9 之后补充 6 个 brainstorm 边缘场景（SC-01..SC-06）：冲突解决、冷启动、分片、多租户、审计保留、熔断。共 18 任务（T313-T330），6 组可全部并行，约 4-5 周完成。

### 6. Palantir/OntoFlow 增强（Phase 11）

Phase 10 之后叠加 Palantir/OntoFlow 范式（FR-031..FR-037），分 4 个里程碑交付：

- **M1: Data Health + Branch & Merge**（FR-031, FR-032）
  - Data Health 引擎实现 5 种规则 + 调度扫描 + 通知
  - Branch & Merge 基于 RFC 6902 JSON Patch 实现 3-way merge
  - 33 任务（T331-T363）

- **M2: Inheritance + Action Type**（FR-033, FR-034）
  - Object Type 继承（最大深度 5）+ Mixin
  - Action Type 作为业务接口，通过 linked_skill_id 委托给 Skill 执行
  - 26 任务（T364-T389）

- **M3: Computed Property + Object View**（FR-035, FR-036）
  - 计算属性 + 物化视图 + 增量重算（基于 DAG）
  - Object View 角色视图 + OPA 读权限 + 字段脱敏
  - 25 任务（T390-T414）

- **M4: OntoFlow Goal-driven**（FR-037）
  - Goal + Change Proposal + Impact Analysis
  - LLM 生成 business_rationale
  - 16 任务（T415-T430）

- **集成与文档**：4 任务（T431-T434），含 ADR-055 修正、模块设计文档、API 契约补充、集成测试

总 122 任务，预计 12-15 周（每个里程碑 3-4 周）。

### 7. 测试策略

- **每个任务完成后立即编写单元测试**（不延迟到 Phase 9）
- **集成测试在对应 Phase 完成后编写**
- **E2E 测试在 Phase 9 统一补全**
- **质量门禁从 Phase 1 开始执行**：每个 PR 必须通过 lint + typecheck + unit test
- **Phase 10/11 单元测试覆盖**：冲突解决 4 策略、冷启动 3 模板、分片、租户隔离、审计归档、熔断；Data Health 5 规则、3-way merge、Action Skill 委托、计算属性沙箱、视图脱敏、Goal LLM rationale

### 8. 风险缓解

| 风险 | 缓解措施 | 对应任务 |
|------|----------|----------|
| OpenHarness API 不稳定 | 适配层抽象接口，缺失功能自行补充 | T018-T024 |
| Palantir 对齐过度抽象 | 仅实现 FR 需要的子集 | T029-T033 |
| Graphiti 双时态查询性能 | 建立时间索引，缓存常用查询 | T049, T310 |
| 前端重构范围大 | 优先完成基础设施，页面逐步迁移 | T006-T012, T308 |
| MinIO 运维复杂度 | Docker Compose 统一管理 | T001, T312 |
| 多方案并行推演资源消耗 | 限制并行度（最多 10），超限自动终止 | T247, T241 |
| 3-way merge 误合并导致数据损坏 | 合并前必须 dry-run，预览变更；冲突字段禁止自动选择 | T355, T360 |
| Action Type 与 Skill 重复定义 | 单一事实来源：ActionType.linked_skill_id 强制非空，UI 上禁止绕过 Skill 直接实现 | T376, T382 |
| Data Health 与 OPA 职责重叠 | 严格分工：OPA 管"是否允许写入"（write-time），Data Health 管"写入后是否健康"（post-write），文档明确边界 | T341, T338 |
| OntoFlow Goal 演化为空中楼阁 | 每个 Goal 必须关联至少一个 Change Proposal 才能进入 in-progress 状态 | T416, T425 |
| 物化视图增量重算雪崩 | DAG 反向传播 + 批量提交（每 1000 条一批），单次任务超时自动降级为全量 | T395, T399 |
| Phase 10/11 工期失控 | 严格按里程碑交付；M1 完成后 Gate Review，再启动 M2 | T363 标记 M1 完成 |
