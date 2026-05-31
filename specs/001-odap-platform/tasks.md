# Implementation Tasks: ODAP 本体驱动分析决策平台

**Branch**: `001-odap-platform` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Total Tasks**: 252 | **Phases**: 9 | **User Stories**: 6

---

## Phase 1: Setup — 项目基础设施

> 预计工期: 1-2 周 | 无前置依赖 | 可并行执行

- [ ] T001 [P] MinIO Docker Compose 配置 — `docker/docker-compose.yml` 新增 minio 服务（端口 9000/9001，healthcheck，volume minio_data）
- [ ] T002 [P] MinIO 环境变量配置 — `.env.example` 新增 MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY / MINIO_SECURE
- [ ] T003 [P] MinIO Python SDK 安装 — `requirements.txt` 新增 `minio` 依赖
- [ ] T004 MinIO 客户端封装 — `odap/infra/storage/minio_client.py` 实现 MinIOClient 单例（upload_object / download_object / get_presigned_url / delete_object / ensure_bucket）
- [ ] T005 MinIO 客户端单元测试 — `tests/unit/test_minio_client.py` 覆盖上传/下载/预签名URL/桶管理
- [ ] T006 [P] 前端 UIAdapter 抽象接口定义 — `frontend/src/modules/shared/components/adapter/UIAdapter.ts` 定义 getButton / getInput / getTable / getModal / getForm / getSelect / getTag / getTooltip / getMessage / getNotification 接口
- [ ] T007 [P] 前端 AntDesignAdapter 实现 — `frontend/src/modules/shared/components/adapter/AntDesignAdapter.ts` 基于 Ant Design 6 实现 UIAdapter 接口
- [ ] T008 [P] 前端 adapter 导出 — `frontend/src/modules/shared/components/adapter/index.ts` 导出当前 Adapter 实例
- [ ] T009 [P] 前端 L1 Atoms 原子组件创建 — `frontend/src/modules/shared/components/atoms/` 创建 Button / Input / Badge / Tooltip / Icon 组件 + `index.ts` 统一导出
- [ ] T010 [P] 前端 L2 Molecules 分子组件创建 — `frontend/src/modules/shared/components/molecules/` 创建 FormField / SearchBar / Card / Modal 组件 + `index.ts` 统一导出
- [ ] T011 [P] 前端 L3 Organisms 组织组件创建 — `frontend/src/modules/shared/components/organisms/` 创建 DataTable / FormPanel / GraphView / ChatPanel 组件 + `index.ts` 统一导出
- [ ] T012 [P] 前端 L4 Templates 模板组件创建 — `frontend/src/modules/shared/components/templates/` 创建 MasterDetail / SplitView / FullScreen 组件 + `index.ts` 统一导出
- [ ] T013 [P] 前端响应式断点常量 — `frontend/src/modules/shared/styles/breakpoints.ts` 定义 6 断点常量（xs/sm/md/lg/xl/xxl）+ CSS 媒体查询 mixin
- [ ] T014 [P] 前端 useResponsive Hook — `frontend/src/modules/shared/hooks/useResponsive.ts` 返回当前断点信息 + 设备类型判断
- [ ] T015 [P] 前端 i18n 基础设施 — `frontend/src/modules/shared/stores/i18nStore.ts` 配置 i18next 实例 + react-i18next 集成 + 按模块命名空间加载
- [ ] T016 [P] 前端共享翻译文件 — `frontend/src/modules/shared/locales/zh-CN/common.json` + `frontend/src/modules/shared/locales/en-US/common.json` 共享翻译条目
- [ ] T017 [P] 前端 useI18n Hook — `frontend/src/modules/shared/hooks/useI18n.ts` 封装 useTranslation + 语言切换方法
- [ ] T018 [P] OpenHarness v2 适配层扩展 — `odap/infra/openharness/v2_adapter.py` 增强 OpenHarnessIntegration 单例，支持 lifespan 初始化
- [ ] T019 [P] OpenHarness Swarm 适配器 — `odap/infra/openharness/swarm_adapter.py` 封装 OpenHarness Swarm 进程内调用
- [ ] T020 [P] OpenHarness Skill 适配器 — `odap/infra/openharness/skill_adapter.py` 封装 OpenHarness Skill 注册/发现
- [ ] T021 [P] OpenHarness Memory 适配器 — `odap/infra/openharness/memory_adapter.py` 封装 OpenHarness Memory Plugin
- [ ] T022 [P] OpenHarness Hook 适配器 — `odap/infra/openharness/hook_adapter.py` 封装 OpenHarness 生命周期钩子
- [ ] T023 [P] OpenHarness Tool 适配器增强 — `odap/infra/openharness/tool_adapter.py` 增强 GraphitiToolAdapter，支持统一工具注册
- [ ] T024 OpenHarness 适配层单元测试 — `tests/unit/test_openharness_adapters.py` 覆盖各适配器初始化和接口调用
- [ ] T025 FastAPI lifespan 集成 OpenHarness — `odap/web/app.py` 在 lifespan 中初始化 OpenHarness（v1 + v2）

---

## Phase 2: Foundational — 阻塞性前置条件

> 预计工期: 2-3 周 | 依赖 Phase 1 | 部分可并行

- [ ] T026 本体模型层目录结构创建 — `odap/biz/core/ontology/model/` 创建 api/ models/ interfaces/ impl/ services/ storage/ 子目录 + `__init__.py`
- [ ] T027 本体管理引擎目录结构创建 — `odap/biz/core/ontology/engine/` 创建 api/ models/ interfaces/ impl/ services/ storage/ 子目录 + `__init__.py`
- [ ] T028 本体数据摄入目录结构创建 — `odap/biz/core/ontology/ingestion/` 创建 api/ impl/ services/ storage/ 子目录 + `__init__.py`
- [ ] T029 EntityType 领域模型定义 — `odap/biz/core/ontology/model/models/entity_type.py` EntityType(BaseModel) 含 name / properties / primary_key / constraints / classification_level
- [ ] T030 Property 领域模型定义 — `odap/biz/core/ontology/model/models/property.py` Property(BaseModel) 含 name / data_type / required / default_value / classification_level / constraints
- [ ] T031 Relation 领域模型定义 — `odap/biz/core/ontology/model/models/relation.py` Relation(BaseModel) 含 source_type / target_type / relation_type / cardinality / link_type
- [ ] T032 Constraint 领域模型定义 — `odap/biz/core/ontology/model/models/constraint.py` Constraint(BaseModel) 含 constraint_type / expression / error_message
- [ ] T033 OntologyDocument 领域模型定义 — `odap/biz/core/ontology/model/models/ontology_document.py` OntologyDocument(BaseModel) 含 id / name / version / object_types / action_types / relations / metadata，对齐 Palantir AIP
- [ ] T034 本体模型层模型导出 — `odap/biz/core/ontology/model/models/__init__.py` 统一导出所有模型类
- [ ] T035 本体模型层模型单元测试 — `tests/unit/test_ontology_model.py` 覆盖 EntityType / Property / Relation / Constraint / OntologyDocument 必填字段验证、默认值、容器字段 default_factory、Enum 值
- [ ] T036 Version 领域模型定义 — `odap/biz/core/ontology/engine/models/version.py` OntologyVersion(BaseModel) 含 version_number / changelog / status / valid_time / transaction_time
- [ ] T037 Audit 领域模型定义 — `odap/biz/core/ontology/engine/models/audit.py` AuditRecord(BaseModel) 含 source / process_steps / transform_rules / timestamp
- [ ] T038 Validation 领域模型定义 — `odap/biz/core/ontology/engine/models/validation.py` ValidationResult(BaseModel) 含 is_valid / errors / warnings
- [ ] T039 本体管理引擎模型导出 — `odap/biz/core/ontology/engine/models/__init__.py` 统一导出
- [ ] T040 本体管理引擎模型单元测试 — `tests/unit/test_ontology_engine.py` 覆盖 Version / Audit / Validation 模型验证
- [ ] T041 ModelRepository 抽象接口定义 — `odap/biz/core/ontology/model/interfaces/model_repository.py` ABC 定义 save_entity_type / get_entity_type / list_entity_types / delete_entity_type / save_instance / get_instance / list_instances / delete_instance
- [ ] T042 VersionManager 抽象接口定义 — `odap/biz/core/ontology/engine/interfaces/version_manager.py` ABC 定义 create_version / get_version / rollback_version / compare_versions / query_at_time
- [ ] T043 AuditRecorder 抽象接口定义 — `odap/biz/core/ontology/engine/interfaces/audit_recorder.py` ABC 定义 record_audit / get_audit / list_audits
- [ ] T044 ValidationEngine 抽象接口定义 — `odap/biz/core/ontology/engine/interfaces/validation_engine.py` ABC 定义 validate_properties / validate_consistency / validate_constraints
- [ ] T045 SQLite Model Storage 实现 — `odap/biz/core/ontology/model/storage/sqlite_model_storage.py` SQLiteModelStorage 实现 entity_types / properties / relations / constraints / instances 表 CRUD + `__init__.py` 别名导出
- [ ] T046 SQLite Model Storage 单元测试 — `tests/unit/test_ontology_model.py` 新增 TestSQLiteModelStorage 类覆盖 CRUD 全流程、get 不存在返回 None、JSON 字段序列化/反序列化
- [ ] T047 SQLite Engine Storage 实现 — `odap/biz/core/ontology/engine/storage/sqlite_engine_storage.py` SQLiteEngineStorage 实现 versions / audit_records 表 CRUD + `__init__.py` 别名导出
- [ ] T048 SQLite Engine Storage 单元测试 — `tests/unit/test_ontology_engine.py` 新增 TestSQLiteEngineStorage 类覆盖版本 CRUD、审计记录 CRUD
- [ ] T049 Graphiti 双时态基础设施增强 — `odap/infra/graph/graph_service.py` 增强 query_temporal() 方法，正确区分 valid_time 和 transaction_time（reference_time 对应 valid_time，created_at 对应 transaction_time）
- [ ] T050 Graphiti 双时态单元测试 — `tests/unit/test_graph_service_temporal.py` 覆盖双时态查询、历史查询、时间点快照
- [ ] T051 DataClassification 枚举定义 — `odap/infra/security/data_classification.py` DataClassification(str, Enum) 四级分类 TS/S/C/U + 数据写入时自动标记分类级别逻辑
- [ ] T052 Encryption 模块实现 — `odap/infra/security/encryption.py` 实现 TLS 1.3 强制配置 + AES-256-GCM 加密/解密函数（TS/S 级数据加密存储）
- [ ] T053 数据分类与加密单元测试 — `tests/unit/test_data_classification.py` 覆盖分类枚举值、加密/解密流程、分类级别判定

---

## Phase 3: US1 — 本体设计与知识结构化 (P1) 🎯 MVP

> 预计工期: 8-10 周 | 依赖 Phase 2 | US1: 本体设计与知识结构化

### FR-001: 本体设计器

- [ ] T054 ModelRepositoryImpl 实现 — `odap/biz/core/ontology/model/impl/model_repository_impl.py` 实现 save_entity_type / get_entity_type / list_entity_types / delete_entity_type / save_instance / get_instance / list_instances / delete_instance，实例唯一性基于主键属性组合判定
- [ ] T055 ModelService 实现 — `odap/biz/core/ontology/model/services/model_service.py` 编排层，返回 Dict[str, Any]，Enum→.value / datetime→.isoformat 类型转换
- [ ] T056 本体模型层 schemas 定义 — `odap/biz/core/ontology/model/api/schemas.py` CreateEntityTypeRequest / UpdateEntityTypeRequest / EntityTypeResponse / CreateInstanceRequest / InstanceResponse 等 Pydantic 模型
- [ ] T057 本体模型层路由实现 — `odap/biz/core/ontology/model/api/routes.py` APIRouter(prefix="/api/ontology/model") 实体类型 CRUD + 实例 CRUD 路由，except HTTPException: raise
- [ ] T058 本体模型层路由注册 — `odap/web/app.py` include_router(ontology_model_router)
- [ ] T059 本体模型层服务单元测试 — `tests/unit/test_ontology_model.py` 新增 TestModelService 类覆盖成功返回扁平 dict、错误返回 {"status": "error"}、类型转换
- [ ] T060 本体模型层路由单元测试 — `tests/unit/test_ontology_model.py` 新增 TestModelRoutes 类覆盖 HTTP 状态码映射、404/400/500 场景
- [ ] T061 前端本体模型设计器页面 — `frontend/src/modules/ontology/pages/OntologyModelDesigner.tsx` L5 页面组件，左侧实体类型列表 + 中间属性编辑面板 + 右侧关系图预览
- [ ] T062 前端实体类型编辑组件 — `frontend/src/modules/ontology/components/EntityTypeEditor.tsx` L3 组织组件，属性列表编辑 + 主键选择 + 约束配置
- [ ] T063 前端实例管理组件 — `frontend/src/modules/ontology/components/InstanceManager.tsx` L3 组织组件，实例 CRUD + 分页列表 + 属性编辑
- [ ] T064 前端本体模块 API 服务 — `frontend/src/modules/ontology/services/ontologyApi.ts` 封装 /api/ontology/model/* 接口调用
- [ ] T065 前端本体模块 Store — `frontend/src/modules/ontology/stores/ontologyStore.ts` Zustand store 管理实体类型/实例状态
- [ ] T066 前端本体模块翻译文件 — `frontend/src/modules/ontology/locales/zh-CN/ontology.json` + `frontend/src/modules/ontology/locales/en-US/ontology.json`
- [ ] T067 前端本体模块路由更新 — `frontend/src/AppRoutes.tsx` 更新 /ontology 路由指向 OntologyModelDesigner

### FR-002: 本体版本管理

- [ ] T068 VersionManagerImpl 实现 — `odap/biz/core/ontology/engine/impl/version_manager_impl.py` 实现 create_version / get_version / rollback_version / compare_versions / query_at_time，基于 Graphiti 双时态
- [ ] T069 AuditRecorderImpl 实现 — `odap/biz/core/ontology/engine/impl/audit_recorder_impl.py` 实现数据摄入审计记录
- [ ] T070 ValidationEngineImpl 实现 — `odap/biz/core/ontology/engine/impl/validation_engine_impl.py` 实现属性完整性检查 / 一致性验证 / 约束校验
- [ ] T071 EngineService 实现 — `odap/biz/core/ontology/engine/services/engine_service.py` 编排层，协调版本管理/审计/验证
- [ ] T072 本体管理引擎 schemas 定义 — `odap/biz/core/ontology/engine/api/schemas.py` CreateVersionRequest / VersionResponse / RollbackRequest / CompareResponse / ValidateRequest / AuditResponse 等
- [ ] T073 本体管理引擎路由实现 — `odap/biz/core/ontology/engine/api/routes.py` APIRouter(prefix="/api/ontology/engine") 版本管理 + 验证 + 审计路由
- [ ] T074 本体管理引擎路由注册 — `odap/web/app.py` include_router(ontology_engine_router)
- [ ] T075 版本管理服务单元测试 — `tests/unit/test_ontology_engine.py` 新增 TestVersionManager 类覆盖版本创建/查询/回滚/对比/时序查询
- [ ] T076 验证引擎单元测试 — `tests/unit/test_ontology_engine.py` 新增 TestValidationEngine 类覆盖属性完整性/一致性/约束校验
- [ ] T077 前端版本管理面板 — `frontend/src/modules/ontology/components/VersionPanel.tsx` L3 组织组件，版本时间线 + 变更对比 + 一键回滚
- [ ] T078 前端版本对比组件 — `frontend/src/modules/ontology/components/VersionCompare.tsx` L3 组织组件，双版本差异高亮展示
- [ ] T079 前端版本模块 Store — `frontend/src/modules/version/stores/versionStore.ts` Zustand store 管理版本状态

### FR-003: 本体实例 CRUD + 批量导入

- [ ] T080 批量导入处理器实现 — `odap/biz/core/ontology/ingestion/impl/batch_importer.py` BatchImporter 支持 CSV/JSON 批量导入，自动验证属性完整性，无效数据标记跳过，返回导入结果摘要
- [ ] T081 IngestService 实现 — `odap/biz/core/ontology/ingestion/services/ingest_service.py` 编排层，协调批量导入和验证
- [ ] T082 数据摄入 schemas 定义 — `odap/biz/core/ontology/ingestion/api/schemas.py` BatchImportRequest / BatchImportResponse 等
- [ ] T083 数据摄入路由实现 — `odap/biz/core/ontology/ingestion/api/routes.py` APIRouter(prefix="/api/ontology/ingestion") 批量导入路由
- [ ] T084 数据摄入路由注册 — `odap/web/app.py` include_router(ontology_ingestion_router)
- [ ] T085 批量导入单元测试 — `tests/unit/test_ontology_model.py` 新增 TestBatchImporter 类覆盖 CSV/JSON 导入、无效数据处理、结果摘要
- [ ] T086 前端批量导入组件 — `frontend/src/modules/ingest/components/BatchImporter.tsx` L3 组织组件，文件上传 + 格式选择 + 导入进度 + 结果摘要展示
- [ ] T087 前端摄入模块 Store — `frontend/src/modules/ingest/stores/ingestStore.ts` Zustand store 管理导入状态

### FR-004: 多模态数据接入

- [ ] T088 PDF 处理器实现 — `odap/biz/core/ontology/ingestion/impl/pdf_processor.py` PDF 文本提取（PyPDF2/pdfplumber）
- [ ] T089 Word 处理器实现 — `odap/biz/core/ontology/ingestion/impl/word_processor.py` Word 文档解析（python-docx）
- [ ] T090 OCR 处理器实现 — `odap/biz/core/ontology/ingestion/impl/ocr_processor.py` 图片 OCR（Tesseract/PaddleOCR）
- [ ] T091 文件上传路由实现 — `odap/biz/core/ontology/ingestion/api/routes.py` 新增 POST /api/ontology/ingestion/upload（multipart/form-data）+ GET /api/ontology/ingestion/tasks/{task_id} + POST /api/ontology/ingestion/extract
- [ ] T092 多模态处理器集成 — `odap/infra/data_pipeline/multimodal_processor.py` 整合 PDF/Word/OCR 处理器，统一文件上传→MinIO 存储→文本/OCR 提取→LLM 实体抽取→本体实例更新流程
- [ ] T093 多模态处理单元测试 — `tests/unit/test_ontology_model.py` 新增 TestMultimodalProcessor 类覆盖 PDF/Word/OCR 提取、MinIO 集成
- [ ] T094 前端文件上传组件 — `frontend/src/modules/ingest/components/FileUploader.tsx` L3 组织组件，拖拽上传 + 格式识别 + 进度条
- [ ] T095 前端导入任务状态组件 — `frontend/src/modules/ingest/components/ImportTaskStatus.tsx` L2 分子组件，任务状态展示 + 实体抽取触发

### FR-012: 工作空间管理

- [ ] T096 Workspace 隔离级别增强 — `odap/biz/platform/workspace/models/` 新增 IsolationLevel(str, Enum) — low/standard/high/strict
- [ ] T097 Workspace 4 级隔离实现 — `odap/biz/platform/workspace/impl/` SQLite workspace_id 过滤 + Neo4j workspace_id 标签隔离 + Redis workspace_id 前缀隔离 + MinIO 按工作空间分桶
- [ ] T098 Workspace 导入导出 — `odap/biz/platform/workspace/impl/` 实现 JSON 格式完整工作空间导出和导入
- [ ] T099 Workspace API 增强 — `odap/biz/platform/workspace/api/routes.py` 新增 POST /api/workspace/{id}/export + POST /api/workspace/{id}/import
- [ ] T100 Workspace 单元测试 — `tests/unit/test_workspace.py` 新增 TestWorkspaceIsolation 类覆盖 4 级隔离、导入导出
- [ ] T101 前端工作空间管理器增强 — `frontend/src/modules/workspace/pages/WorkspaceManager.tsx` L5 页面，隔离级别选择 + 导入导出操作
- [ ] T102 前端工作空间 Store — `frontend/src/modules/workspace/stores/workspaceStore.ts` Zustand store 增强隔离级别管理

### FR-013: 场景切换

- [ ] T103 场景切换服务增强 — `odap/biz/platform/workspace/services/scenario_service.py` 场景切换时自动加载关联本体列表/技能配置/OPA 策略/Agent 配置，切换事件通过 Hook 系统广播
- [ ] T104 场景本体 N:M 关联 — `odap/biz/platform/workspace/impl/` 场景与本体 N:M 关联，解绑需检查依赖
- [ ] T105 场景 API 路由 — `odap/biz/platform/workspace/api/routes.py` 新增 POST /api/workspace/{ws_id}/scenarios + POST /api/workspace/{ws_id}/scenarios/{id}/activate + POST /api/workspace/{ws_id}/scenarios/{id}/ontologies
- [ ] T106 场景切换单元测试 — `tests/unit/test_workspace.py` 新增 TestScenarioSwitch 类覆盖场景创建/激活/本体绑定/解绑依赖检查
- [ ] T107 前端场景切换器增强 — `frontend/src/modules/workspace/components/WorkspaceSwitcher.tsx` L3 组织组件，场景切换 + 全局状态更新 + 本体/技能/策略自动切换
- [ ] T108 前端场景 Store — `frontend/src/modules/workspace/stores/scenarioStore.ts` Zustand store 管理场景状态

### FR-015: 数据摄入审计

- [ ] T109 数据摄入审计记录增强 — `odap/biz/core/ontology/engine/impl/audit_recorder_impl.py` 增强记录数据来源（上传文件/批量导入/API 调用/Agent 操作）、处理过程、转换规则
- [ ] T110 审计统一通道集成 — `odap/infra/security/unified_audit.py` 集成本体管理引擎审计记录，写入 SQLite + Graphiti 审计通道
- [ ] T111 审计 API 路由 — `odap/biz/core/ontology/engine/api/routes.py` 新增 GET /api/ontology/engine/audit + GET /api/ontology/engine/audit/{audit_id}
- [ ] T112 审计记录单元测试 — `tests/unit/test_ontology_engine.py` 新增 TestAuditRecorder 类覆盖数据来源/处理过程/转换规则记录
- [ ] T113 前端审计时间线组件 — `frontend/src/modules/audit/components/AuditTimeline.tsx` L3 组织组件，审计记录时间线展示 + 详情查看

### FR-029: OntologyDocument JSON 统一格式

- [ ] T114 OntologyDocument 格式转换方法 — `odap/biz/core/ontology/model/models/ontology_document.py` 实现 from_palantir() / to_palantir() / from_owl() / to_owl() 转换方法
- [ ] T115 现有 schema 迁移到 OntologyDocument 格式 — `odap/biz/core/ontology/schema/document.py` 迁移现有 OntologyDocument 格式对齐 Palantir AIP
- [ ] T116 OntologyDocument API 路由 — `odap/biz/core/ontology/model/api/routes.py` 新增 GET /api/ontology/model/documents/{ontology_id} + POST /api/ontology/model/documents + PUT /api/ontology/model/documents/{ontology_id} + POST /api/ontology/model/documents/{ontology_id}/export
- [ ] T117 OntologyDocument 单元测试 — `tests/unit/test_ontology_model.py` 新增 TestOntologyDocument 类覆盖格式转换、导入导出、Palantir/OWL 对齐
- [ ] T118 前端 OntologyDocument 导入导出组件 — `frontend/src/modules/ontology/components/DocumentImporter.tsx` L3 组织组件，OntologyDocument JSON 导入 + 多格式导出

### FR-027: 数据分类标记 + 传输加密

- [ ] T119 Property 模型增加 classification_level — `odap/biz/core/ontology/model/models/property.py` 增加 classification_level 字段，默认 U
- [ ] T120 数据写入时自动标记分类级别 — `odap/biz/core/ontology/model/impl/model_repository_impl.py` 数据写入时根据 Property.classification_level 自动标记
- [ ] T121 传输加密 FastAPI HTTPS 配置 — `odap/web/app.py` 强制 TLS 1.3 配置
- [ ] T122 数据分类 API — `odap/infra/security/` 新增 GET /api/security/classification-levels 路由
- [ ] T123 数据分类单元测试 — `tests/unit/test_data_classification.py` 新增 TestClassificationMarking 类覆盖自动标记、分类级别查询

### FR-030: 国际化

- [ ] T124 后端 i18n 模块创建 — `odap/biz/platform/i18n/` 创建 api/ models/ services/ storage/ 子目录
- [ ] T125 Translation 领域模型定义 — `odap/biz/platform/i18n/models/translation.py` Translation(BaseModel) 含 key / module / locale / value
- [ ] T126 SQLite i18n Storage 实现 — `odap/biz/platform/i18n/storage/sqlite_i18n_storage.py` SQLiteI18nStorage 翻译条目 CRUD + `__init__.py` 别名导出
- [ ] T127 I18nService 实现 — `odap/biz/platform/i18n/services/i18n_service.py` 翻译管理 + LLM 翻译调用（调用 OpenAI API 批量翻译未翻译条目）
- [ ] T128 i18n schemas 定义 — `odap/biz/platform/i18n/api/schemas.py` TranslationRequest / TranslationResponse / AutoTranslateRequest 等
- [ ] T129 i18n 路由实现 — `odap/biz/platform/i18n/api/routes.py` APIRouter(prefix="/api/i18n") 翻译 CRUD + LLM 自动翻译 + 模块/语言列表
- [ ] T130 i18n 路由注册 — `odap/web/app.py` include_router(i18n_router)
- [ ] T131 i18n 单元测试 — `tests/unit/test_i18n.py` 覆盖翻译 CRUD、LLM 翻译调用、模块/语言列表
- [ ] T132 前端 i18n 管理页面 — `frontend/src/modules/i18n-admin/pages/I18nAdminPage.tsx` L5 页面，翻译条目列表 + 在线编辑 + LLM 自动翻译按钮 + 人工审核
- [ ] T133 前端 i18n API 服务 — `frontend/src/modules/i18n-admin/services/i18nApi.ts` 封装 /api/i18n/* 接口调用

---

## Phase 4: US2 — 多智能体协同调度 (P2)

> 预计工期: 4-5 周 | 依赖 Phase 3 | US2: 多智能体协同调度

### FR-005: 多 Agent 协同调度

- [ ] T134 DomainSwarm OODA 循环实现 — `odap/biz/core/agent/impl/swarm_orchestrator.py` DomainSwarm 继承/封装 OpenHarness Swarm，实现 OODA 循环（Observe→Orient→Decide→Act）
- [ ] T135 IntentRouter 混合路由实现 — `odap/biz/core/agent/impl/intent_router.py` 规则路由（基于本体事实的意图-角色映射表）+ LLM 路由（不确定时调用 LLM 分类意图）+ 默认路由（不确定时路由到 Intelligence Agent）
- [ ] T136 SubAgentPlanner 任务分解实现 — `odap/biz/core/agent/impl/swarm_orchestrator.py` 按意图自动规划 subAgent 任务分解
- [ ] T137 OODA Loop 实现增强 — `odap/biz/core/agent/impl/ooda_loop.py` OODA 各阶段与 OpenHarness 对齐：Observe→Tool 调用、Orient→Hook 后处理、Decide→QueryEngine、Act→Tool 执行
- [ ] T138 Agent 角色模型定义 — `odap/biz/core/agent/models/` AgentRole(str, Enum) — Commander/Intelligence/Operations（可扩展）+ AgentConfig(BaseModel)
- [ ] T139 Agent schemas 定义 — `odap/biz/core/agent/api/schemas.py` DispatchRequest / DispatchResponse / TaskStatusResponse / SwarmConfigRequest 等
- [ ] T140 Agent 路由实现 — `odap/biz/core/agent/api/routes.py` APIRouter(prefix="/api/agent") 意图分发 + 任务状态 + 决策链路 + Swarm 配置
- [ ] T141 Agent 路由注册 — `odap/web/app.py` include_router(agent_router)
- [ ] T142 Agent 服务单元测试 — `tests/unit/test_agent.py` 覆盖 DomainSwarm OODA 循环、IntentRouter 混合路由、SubAgentPlanner 任务分解
- [ ] T143 前端 Agent 聊天页面增强 — `frontend/src/modules/agent/pages/AgentChat.tsx` L5 页面，自然语言输入 + 意图识别展示 + Agent 响应
- [ ] T144 前端 Agent 列表页面 — `frontend/src/modules/agent/pages/MyAgents.tsx` L5 页面，Agent 角色配置 + Swarm 配置
- [ ] T145 前端 Agent Store — `frontend/src/modules/agent/stores/agentStore.ts` Zustand store 管理 Agent 状态
- [ ] T146 前端 Agent API 服务 — `frontend/src/modules/agent/services/agentApi.ts` 封装 /api/agent/* 接口调用
- [ ] T147 前端 Agent 翻译文件 — `frontend/src/modules/agent/locales/zh-CN/agent.json` + `frontend/src/modules/agent/locales/en-US/agent.json`

### FR-006: Agent 决策过程可视化

- [ ] T148 DecisionChain 数据结构定义 — `odap/biz/core/agent/models/` DecisionChain(BaseModel) 含 steps（OODA 各阶段）/ reasoning（推理过程）/ evidence（依据）
- [ ] T149 决策过程 Hook 记录 — `odap/biz/core/agent/impl/swarm_orchestrator.py` Agent 执行时通过 Hook 系统记录每个 OODA 步骤
- [ ] T150 决策过程 API 路由 — `odap/biz/core/agent/api/routes.py` 新增 GET /api/agent/decisions/{decision_id} + GET /api/agent/decisions/{decision_id}/chain
- [ ] T151 决策过程 WebSocket 推送 — `odap/web/ws/event_bus.py` 新增 WS /ws/agent/decisions 实时推送决策过程
- [ ] T152 决策过程单元测试 — `tests/unit/test_agent.py` 新增 TestDecisionChain 类覆盖决策链路记录和查询
- [ ] T153 前端决策链路时间线组件 — `frontend/src/modules/agent/components/DecisionTimeline.tsx` L3 组织组件，按时间顺序展示决策步骤
- [ ] T154 前端思维链视图组件 — `frontend/src/modules/agent/components/ReasoningChain.tsx` L3 组织组件，展示推理过程和依据，点击步骤查看详情

### FR-014: Skill 热插拔

- [ ] T155 Skill 热插拔实现 — `odap/biz/platform/skill_system/impl/hotplug.py` register_skill(skill_def) / unregister_skill(skill_id) / discover_skills(query)，通过 OpenHarness Skill 管理功能注册和发现
- [ ] T156 Skill 生命周期管理 — `odap/biz/platform/skill_system/models/` SkillStatus(str, Enum) — draft/active/deprecated/archived + SkillDefinition(BaseModel)
- [ ] T157 现有技能包迁移 — `odap/tools/` 下 9 个技能包迁移为 OpenHarness Skill 格式
- [ ] T158 Skill API 路由 — `odap/biz/platform/skill_system/api/routes.py` 新增 POST /api/skill/register + DELETE /api/skill/{id} + GET /api/skill/discover + GET /api/skill/{id}/status
- [ ] T159 Skill 路由注册 — `odap/web/app.py` include_router(skill_router)
- [ ] T160 Skill 热插拔单元测试 — `tests/unit/test_skill_system.py` 覆盖注册/注销/发现/生命周期状态转换
- [ ] T161 前端技能管理页面增强 — `frontend/src/modules/system/pages/SkillManagement.tsx` L5 页面，Skill 注册/注销/发现/状态管理
- [ ] T162 前端技能 Store — `frontend/src/modules/system/stores/skillStore.ts` Zustand store 管理 Skill 状态

---

## Phase 5: US3 — 策略治理与权限控制 (P2)

> 预计工期: 3-4 周 | 依赖 Phase 3 | US3: 策略治理与权限控制 | 可与 Phase 4 并行

### FR-007: OPA 策略 Markdown 编写 + 热更新

- [ ] T163 Markdown→Rego 编译器实现 — `odap/infra/opa/markdown_compiler.py` 解析 Markdown DSL 标题→Rego 规则名、当/且→条件组合、时允许/拒绝→规则体、编译验证、fail-close 机制
- [ ] T164 OPA 策略版本管理 — `odap/infra/opa/opa_service.py` 增加 SQLite 策略版本历史存储，支持回滚
- [ ] T165 OPA 策略热更新增强 — `odap/infra/opa/opa_service.py` 增强 hot_update_bundle()，编译后通过 OPA API 加载策略，30 秒内生效，编译失败保持旧策略
- [ ] T166 OPA 策略 schemas 定义 — `odap/infra/opa/routes.py` 新增 MarkdownPolicyRequest / MarkdownPolicyResponse / CompileStatusResponse 等
- [ ] T167 OPA 策略 API 路由 — `odap/infra/opa/routes.py` 新增 POST /api/policy/markdown + GET /api/policy/markdown/{id} + PUT /api/policy/markdown/{id} + POST /api/policy/markdown/{id}/compile + GET /api/policy/markdown/{id}/status
- [ ] T168 OPA 策略单元测试 — `tests/unit/test_opa.py` 覆盖 Markdown→Rego 编译、编译失败 fail-close、热更新、版本回滚
- [ ] T169 前端策略编辑器 — `frontend/src/modules/config/components/PolicyEditor.tsx` L3 组织组件，Markdown 编辑 + 预览 + 编译状态展示
- [ ] T170 前端策略管理页面 — `frontend/src/modules/config/pages/PolicyManager.tsx` L5 页面，策略列表 + 编辑 + 编译 + 热更新

### FR-008: ABAC 权限校验 + 审计日志

- [ ] T171 ABAC 四维模型实现 — `odap/infra/opa/opa_service.py` 增强 check_permission(subject, action, resource, env)，OPA 策略校验返回 allow/deny + 原因
- [ ] T172 ABAC Rego 策略扩展 — `odap/infra/opa/policies/abac.rego` 扩展 Rego 策略支持 Subject/Action/Resource/Environment 四维属性 + 数据分类级别访问控制
- [ ] T173 审计日志增强 — `odap/infra/security/unified_audit.py` 增加写操作审计记录 actor/action/resource/result/timestamp，写入 SQLite + Graphiti 审计通道
- [ ] T174 审计 API 增强 — `odap/infra/security/audit_api.py` 新增 GET /api/audit/logs（分页+过滤）+ GET /api/audit/timeline（资源审计时间线）
- [ ] T175 ABAC + 审计单元测试 — `tests/unit/test_opa.py` 新增 TestABAC 类覆盖四维权限校验、数据分类级别控制、审计日志记录
- [ ] T176 前端审计日志页面 — `frontend/src/modules/audit/pages/AuditLogPage.tsx` L5 页面，审计日志列表 + 时间线展示 + 过滤查询
- [ ] T177 前端审计 Store — `frontend/src/modules/audit/stores/auditStore.ts` Zustand store 管理审计日志状态

### FR-021: OAuth2/OIDC + 本地账号认证

- [ ] T178 OAuth2/OIDC Provider 集成 — `odap/infra/security/oauth2_providers.py` 支持企业 SSO（Keycloak/Auth0/Okta），Authorization Code Flow + PKCE，Token 交换 OAuth2→JWT
- [ ] T179 本地账号密码认证增强 — `odap/infra/security/auth_service.py` 增加 bcrypt 密码哈希 + JWT 双 Token（Access 15min / Refresh 7d）
- [ ] T180 认证 API 路由增强 — `odap/infra/security/auth_routes.py` 新增 POST /api/auth/login + POST /api/auth/sso/{provider} + POST /api/auth/refresh + POST /api/auth/logout
- [ ] T181 认证单元测试 — `tests/unit/test_auth.py` 覆盖本地账号登录、SSO 登录、Token 刷新、登出
- [ ] T182 前端登录页增强 — `frontend/src/modules/shared/pages/LoginPage.tsx` 增加 SSO 登录按钮 + 本地账号密码表单
- [ ] T183 前端 authStore 增强 — `frontend/src/modules/shared/stores/authStore.ts` 增加 SSO 登录流程 + Token 刷新逻辑

---

## Phase 6: US6 — 用户认知引擎 (P2)

> 预计工期: 6-8 周 | 依赖 Phase 4 + Phase 5 | US6: 用户认知引擎

### FR-016: 用户认知引擎

- [ ] T184 意图识别器实现 — `odap/biz/core/cognition/impl/intent_recognizer.py` 基于 LLM + 本体事实的意图分类，支持角色上下文，输出 intent_type + confidence + parameters
- [ ] T185 知识导航器实现 — `odap/biz/core/cognition/impl/knowledge_navigator.py` 基于本体的知识图谱导航，推理路径可视化（高亮路径+逐步回溯）
- [ ] T186 解释引擎实现 — `odap/biz/core/cognition/impl/explanation_engine.py` AI 决策过程可解释性，推理链路展示（"为什么"问题的回答）
- [ ] T187 角色视图管理器实现 — `odap/biz/core/cognition/impl/role_view_manager.py` 不同角色（Commander/Intelligence/Operations）定制化视图，角色切换后界面自动适配
- [ ] T188 认知引擎领域模型定义 — `odap/biz/core/cognition/models/` IntentResult / NavigationPath / Explanation / RoleViewConfig 等 BaseModel
- [ ] T189 CognitionService 实现 — `odap/biz/core/cognition/services/cognition_service.py` 编排层，协调意图识别/知识导航/解释引擎/角色视图
- [ ] T190 认知引擎 schemas 定义 — `odap/biz/core/cognition/api/schemas.py` RecognizeIntentRequest / NavigateRequest / ExplainRequest / RoleViewResponse 等
- [ ] T191 认知引擎路由实现 — `odap/biz/core/cognition/api/routes.py` APIRouter(prefix="/api/cognition") 意图识别 + 知识导航 + 解释 + 角色视图
- [ ] T192 认知引擎路由注册 — `odap/web/app.py` include_router(cognition_router)
- [ ] T193 认知引擎单元测试 — `tests/unit/test_cognition.py` 覆盖意图识别、知识导航、解释引擎、角色视图管理
- [ ] T194 前端认知引擎集成 — `frontend/src/modules/agent/components/CognitionPanel.tsx` L3 组织组件，意图识别结果展示 + 推理链路可视化 + 角色视图切换
- [ ] T195 前端推理路径可视化组件 — `frontend/src/modules/agent/components/ReasoningPath.tsx` L3 组织组件，基于 G6 的推理路径高亮 + 逐步回溯
- [ ] T196 前端认知 Store — `frontend/src/modules/agent/stores/cognitionStore.ts` Zustand store 管理认知引擎状态

### FR-023: 统一查询服务

- [ ] T197 TemporalSource Protocol 定义 — `odap/infra/query/protocols.py` 新增 TemporalSource Protocol，定义 query_temporal / query_history / query_at_time 接口
- [ ] T198 TemporalSourceImpl 实现 — `odap/infra/query/sources/temporal_source.py` 封装 GraphManager.query_temporal() 和 get_entity_history()，基于 Graphiti 双时态
- [ ] T199 QueryService 增强 — `odap/infra/query/service.py` 增强 query() 方法支持 temporal 查询源，通过 OpenHarness Tool 接口注册
- [ ] T200 Agent Safe 只读模式增强 — `odap/infra/openharness/query_guard_hook.py` 增强 QueryServiceWriteGuard，Agent 默认只暴露 READ_TOOLS，WRITE_TOOLS 需 OPA 审批
- [ ] T201 查询源 Tool 注册 — `odap/infra/query/` 将 4 种查询源注册为 OpenHarness BaseTool（query_schema / query_entity / query_topo / query_temporal）
- [ ] T202 统一查询 API 路由 — `odap/infra/query/routes.py` 新增 POST /api/query + GET /api/query/sources + POST /api/query/validate
- [ ] T203 统一查询单元测试 — `tests/unit/test_query.py` 覆盖 4 种查询源、Agent Safe 只读模式、架构守卫（验证 Agent 代码无直接 graph_manager 写调用）
- [ ] T204 前端查询服务组件 — `frontend/src/modules/knowledge/components/QueryPanel.tsx` L3 组织组件，统一查询界面 + 查询源选择 + 结果展示

### FR-024: 会话记忆管理

- [ ] T205 短期记忆实现 — `odap/biz/platform/session_memory/impl/short_term_memory.py` 对话上下文，Redis 存储，TTL 30min，基于 OpenHarness Memory Plugin
- [ ] T206 工作记忆实现 — `odap/biz/platform/session_memory/impl/working_memory.py` 当前任务状态，Redis 存储，TTL 2h，基于 OpenHarness Memory Plugin
- [ ] T207 长期记忆实现 — `odap/biz/platform/session_memory/impl/long_term_memory.py` 持久化到 Graphiti，无 TTL，基于语义相似度 + 时间衰减检索
- [ ] T208 会话记忆 API 路由 — `odap/biz/platform/session_memory/api/routes.py` GET /api/memory/session/{session_id} + POST /api/memory/session/{session_id}/clear + GET /api/memory/long-term
- [ ] T209 会话记忆路由注册 — `odap/web/app.py` include_router(memory_router)
- [ ] T210 会话记忆单元测试 — `tests/unit/test_session_memory.py` 覆盖短期/工作/长期记忆 CRUD、TTL 过期、语义检索
- [ ] T211 前端会话记忆组件 — `frontend/src/modules/agent/components/SessionMemory.tsx` L3 组织组件，会话上下文展示 + 记忆管理

### FR-025: 统一工具注册表

- [ ] T212 ToolRegistry 实现 — `odap/biz/platform/tool_registry/impl/registry.py` register_tool(tool_def) / unregister_tool(tool_id) / invoke_tool(tool_id, params) / list_tools(category)，基于 OpenHarness Tool 接口
- [ ] T213 语义发现实现 — `odap/biz/platform/tool_registry/impl/semantic_discovery.py` 基于自然语言描述匹配工具
- [ ] T214 工具注册表领域模型 — `odap/biz/platform/tool_registry/models/` ToolDefinition(BaseModel) 含 id / name / category / description / input_schema / permissions
- [ ] T215 工具注册表 API 路由 — `odap/biz/platform/tool_registry/api/routes.py` POST /api/tools/register + DELETE /api/tools/{id} + POST /api/tools/{id}/invoke + GET /api/tools + POST /api/tools/discover
- [ ] T216 工具注册表路由注册 — `odap/web/app.py` include_router(tool_registry_router)
- [ ] T217 工具注册表单元测试 — `tests/unit/test_tool_registry.py` 覆盖注册/注销/调用/列表/语义发现
- [ ] T218 前端工具管理组件 — `frontend/src/modules/system/components/ToolRegistry.tsx` L3 组织组件，工具列表 + 注册/注销 + 语义发现

### FR-026: 结构化语义层

- [ ] T219 意图解析器实现 — `odap/biz/core/ontology/` 新增 semantic_layer/ 目录，`intent_parser.py` 自然语言意图解析为 StructuredQuery
- [ ] T220 查询规划器实现 — `odap/biz/core/ontology/semantic_layer/query_planner.py` StructuredQuery 规划为 Agent Task 序列
- [ ] T221 歧义消除器实现 — `odap/biz/core/ontology/semantic_layer/disambiguator.py` 同义词/近似词映射 + 扩写规则（用户可配置）
- [ ] T222 语义层 API 路由 — `odap/biz/core/ontology/semantic_layer/api/routes.py` POST /api/semantic/parse-intent + POST /api/semantic/plan-tasks + GET /api/semantic/synonyms + POST /api/semantic/synonyms + GET /api/semantic/expansion-rules + POST /api/semantic/expansion-rules
- [ ] T223 语义层路由注册 — `odap/web/app.py` include_router(semantic_router)
- [ ] T224 语义层单元测试 — `tests/unit/test_semantic_layer.py` 覆盖意图解析、任务规划、同义词映射、扩写规则
- [ ] T225 前端语义层配置组件 — `frontend/src/modules/ontology/components/SemanticConfig.tsx` L3 组织组件，同义词/近似词映射配置 + 扩写规则配置

### FR-018: Hook 系统

- [ ] T226 HookManager 实现 — `odap/biz/integration/hook_system/impl/hook_manager.py` Pre-Hook（OPA 策略注入、参数校验）+ Post-Hook（审计日志、性能监控）+ Hook 注册表（管理优先级和依赖），基于 OpenHarness 生命周期钩子
- [ ] T227 Hook 领域模型定义 — `odap/biz/integration/hook_system/models/` HookDefinition(BaseModel) 含 id / type(pre/post) / priority / handler / enabled
- [ ] T228 Hook API 路由 — `odap/biz/integration/hook_system/api/routes.py` POST /api/hooks/register + DELETE /api/hooks/{id} + GET /api/hooks + POST /api/hooks/{id}/enable + POST /api/hooks/{id}/disable
- [ ] T229 Hook 路由注册 — `odap/web/app.py` include_router(hook_router)
- [ ] T230 Hook 系统单元测试 — `tests/unit/test_hook_system.py` 覆盖 Pre/Post Hook 注册/执行、优先级排序、OPA 策略注入、审计日志记录
- [ ] T231 前端 Hook 管理组件 — `frontend/src/modules/system/components/HookManager.tsx` L3 组织组件，Hook 列表 + 注册/注销 + 启用/禁用

### FR-022: 闭环反馈机制

- [ ] T232 Feedback Collector 实现 — `odap/biz/simulation/feedback/impl/collector.py` 执行结果收集（感知层输入），作为 OpenHarness 外层封装
- [ ] T233 Feedback Analyzer 实现 — `odap/biz/simulation/feedback/impl/analyzer.py` 决策效果分析（量化评估），通过 OpenHarness Hook 机制触发
- [ ] T234 Feedback Aggregator 实现 — `odap/biz/simulation/feedback/impl/aggregator.py` 历史经验聚合（沉淀到知识图谱），写入 Graphiti
- [ ] T235 FeedbackLoop 实现 — `odap/biz/simulation/feedback/impl/feedback_loop.py` 包装 DomainSwarm，增加 Propagate 阶段，完成 OODA→OADP 闭环
- [ ] T236 反馈 API 路由 — `odap/biz/simulation/feedback/api/routes.py` POST /api/feedback/collect + GET /api/feedback/analysis/{task_id} + GET /api/feedback/aggregate + POST /api/feedback/close-loop
- [ ] T237 反馈路由注册 — `odap/web/app.py` include_router(feedback_router)
- [ ] T238 反馈机制单元测试 — `tests/unit/test_feedback.py` 覆盖收集/分析/聚合/闭环触发/Graphiti 写入
- [ ] T239 前端反馈展示组件 — `frontend/src/modules/simulation/components/FeedbackPanel.tsx` L3 组织组件，反馈分析展示 + 经验聚合可视化

---

## Phase 7: US4 — 模拟推演与决策支持 (P3)

> 预计工期: 4-5 周 | 依赖 Phase 6 | US4: 模拟推演与决策支持

### FR-009: 沙箱推演环境

- [ ] T240 SandboxManager 实现 — `odap/biz/simulation/simulation_sandbox/impl/sandbox_manager.py` create_sandbox / run_simulation / get_sandbox_status / destroy_sandbox，基于 OpenHarness 沙箱机制进程级隔离
- [ ] T241 沙箱资源限制 — `odap/biz/simulation/simulation_sandbox/impl/sandbox_manager.py` 内存/时间超限自动终止，返回部分结果和超时提示
- [ ] T242 沙箱结果导出 — `odap/biz/simulation/simulation_sandbox/impl/sandbox_manager.py` 推演结果可导出到生产环境（需审批）
- [ ] T243 沙箱 API 路由 — `odap/biz/simulation/simulation_sandbox/api/routes.py` POST /api/simulation/sandbox + POST /api/simulation/sandbox/{id}/run + GET /api/simulation/sandbox/{id}/status + GET /api/simulation/sandbox/{id}/results + DELETE /api/simulation/sandbox/{id}
- [ ] T244 沙箱路由注册 — `odap/web/app.py` include_router(sandbox_router)
- [ ] T245 沙箱单元测试 — `tests/unit/test_simulation.py` 覆盖沙箱创建/运行/销毁、资源超限终止、结果导出
- [ ] T246 前端沙箱管理页面 — `frontend/src/modules/simulation/pages/SandboxManager.tsx` L5 页面，沙箱创建/运行/监控/销毁

### FR-010: 多方案并行推演 + What-if

- [ ] T247 ParallelRunner 实现 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` run_parallel(scenarios) 最多 10 个方案并行 + run_what_if(base_scenario, param_variations) 参数敏感性分析
- [ ] T248 推演结果对比 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` 结果以并排对比视图展示，高亮关键指标差异
- [ ] T249 推演进度 WebSocket 推送 — `odap/web/ws/event_bus.py` 新增 WS /ws/simulation/progress 实时推送推演进度
- [ ] T250 推演历史双时态存储 — `odap/biz/simulation/simulation_sandbox/impl/parallel_runner.py` 推演结果附带 valid_time + transaction_time，基于 Graphiti 双时态
- [ ] T251 并行推演 API 路由 — `odap/biz/simulation/simulation_sandbox/api/routes.py` 新增 POST /api/simulation/parallel + POST /api/simulation/what-if + GET /api/simulation/comparison
- [ ] T252 并行推演单元测试 — `tests/unit/test_simulation.py` 新增 TestParallelRunner 类覆盖并行推演、What-if 分析、结果对比
- [ ] T253 前端并行推演组件 — `frontend/src/modules/simulation/components/ParallelComparison.tsx` L3 组织组件，多方案并排对比 + 关键指标差异高亮
- [ ] T254 前端 What-if 参数面板 — `frontend/src/modules/simulation/components/WhatIfPanel.tsx` L3 组织组件，参数敏感性分析配置 + 结果展示
- [ ] T255 前端推演进度组件 — `frontend/src/modules/simulation/components/SimulationProgress.tsx` L2 分子组件，WebSocket 实时推演进度展示

### FR-020: 事件模拟器

- [ ] T256 EventGenerator 实现 — `odap/biz/simulation/event_simulator/impl/event_generator.py` 按剧本/模板自动生成事件序列，事件必须基于当前工作空间的本体定义展开
- [ ] T257 TimelineEngine 实现 — `odap/biz/simulation/event_simulator/impl/timeline_engine.py` 模拟时钟独立控制（加速/减速/暂停），事件按时间线顺序注入
- [ ] T258 ScenarioTemplate 实现 — `odap/biz/simulation/event_simulator/impl/scenario_template.py` 预定义事件模板库 + 支持自定义模板
- [ ] T259 事件手动注入 — `odap/biz/simulation/event_simulator/impl/event_generator.py` 手动注入关键事件，事件注入驱动本体状态演化
- [ ] T260 事件模拟器 API 路由 — `odap/biz/simulation/event_simulator/api/routes.py` POST /api/event-simulator/generate + POST /api/event-simulator/inject + GET /api/event-simulator/timeline/{id} + POST /api/event-simulator/clock/control + GET /api/event-simulator/templates
- [ ] T261 事件模拟器路由注册 — `odap/web/app.py` include_router(event_simulator_router)
- [ ] T262 事件模拟器单元测试 — `tests/unit/test_event_simulator.py` 覆盖事件生成/注入/时间线/时钟控制/模板管理
- [ ] T263 前端事件模拟器页面 — `frontend/src/modules/simulation/pages/EventSimulator.tsx` L5 页面，事件生成 + 时间线展示 + 时钟控制 + 模板管理
- [ ] T264 前端时间线组件 — `frontend/src/modules/simulation/components/TimelineView.tsx` L3 组织组件，事件时间线可视化 + 时钟控制面板

---

## Phase 8: US5 — 问答引擎与知识检索 (P3)

> 预计工期: 4-5 周 | 依赖 Phase 6 | US5: 问答引擎与知识检索 | 可与 Phase 7 并行

### FR-011: 自然语言问答 + 图谱检索

- [ ] T265 QA Engine 增强 — `odap/biz/data/qa/impl/qa_engine.py` 融合本体知识 + 图谱检索 + LLM 生成，多轮对话上下文理解（基于会话记忆）
- [ ] T266 TemporalReasoner 实现 — `odap/biz/data/qa/impl/temporal_reasoner.py` 基于 Graphiti valid_time 的时序查询，支持三类时序问答（"当时发生了什么"/"什么时候变成这样"/"某时间点综合状态"）
- [ ] T267 ChartRenderer 实现 — `odap/biz/data/qa/impl/chart_renderer.py` 混合渲染模式：轻量交互型前端渲染（G6+Leaflet+ECharts），计算密集型后端渲染，支持 8 种以上图表类型
- [ ] T268 一键添加视图到问答上下文 — `odap/biz/data/qa/impl/qa_engine.py` 用户可一键将当前视图信息添加到问答上下文
- [ ] T269 QA schemas 定义 — `odap/biz/data/qa/api/schemas.py` AskRequest / AskResponse / TemporalAskRequest / ChartRequest / SessionResponse 等
- [ ] T270 QA API 路由 — `odap/biz/data/qa/api/routes.py` POST /api/qa/ask + POST /api/qa/ask/temporal + GET /api/qa/sessions/{id} + POST /api/qa/chart
- [ ] T271 QA 路由注册 — `odap/web/app.py` include_router(qa_router)
- [ ] T272 QA 单元测试 — `tests/unit/test_qa.py` 覆盖问答引擎、时序推理、图表渲染、多轮对话
- [ ] T273 前端问答页面增强 — `frontend/src/modules/qa/pages/QAPage.tsx` L5 页面，自然语言输入 + 多轮对话 + 图表展示 + 一键添加视图上下文
- [ ] T274 前端图表渲染组件 — `frontend/src/modules/qa/components/ChartRenderer.tsx` L3 组织组件，8 种以上图表类型渲染（ECharts + G6 + Leaflet）
- [ ] T275 前端 QA Store — `frontend/src/modules/qa/stores/qaStore.ts` Zustand store 管理问答会话状态

### FR-017: MCP 协议集成

- [ ] T276 MCP ServerManager 实现 — `odap/biz/integration/mcp_adapter/impl/server_manager.py` register_server / unregister_server / call_tool，基于 OpenHarness 实现 MCP v1.0 协议
- [ ] T277 MCP 连接池实现 — `odap/biz/integration/mcp_adapter/impl/connection_pool.py` MCP Server 连接池管理，MCP Server 在独立沙箱进程中运行
- [ ] T278 MCP Tool 注册 — `odap/biz/integration/mcp_adapter/impl/server_manager.py` MCP Server 通过统一工具注册表注册为 Tool
- [ ] T279 MCP 领域模型定义 — `odap/biz/integration/mcp_adapter/models/` MCPServerConfig(BaseModel) 含 id / name / endpoint / tools / status
- [ ] T280 MCP API 路由 — `odap/biz/integration/mcp_adapter/api/routes.py` POST /api/mcp/servers + DELETE /api/mcp/servers/{id} + GET /api/mcp/servers + POST /api/mcp/servers/{id}/tools/{tool_name} + GET /api/mcp/servers/{id}/status
- [ ] T281 MCP 路由注册 — `odap/web/app.py` include_router(mcp_router)
- [ ] T282 MCP 单元测试 — `tests/unit/test_mcp_adapter.py` 覆盖 Server 注册/注销/工具调用/连接池/沙箱隔离
- [ ] T283 前端 MCP 管理组件 — `frontend/src/modules/system/components/MCPManager.tsx` L3 组织组件，MCP Server 列表 + 注册/注销 + 状态监控 + 工具调用

### FR-019: 决策推荐引擎

- [ ] T284 RecommendationEngine 增强 — `odap/biz/decision/decision_recommendation/impl/recommendation_engine.py` generate_recommendations / assess_risks / rank_recommendations / explain_recommendation，基于 Graphiti RAG 增强推理
- [ ] T285 决策推荐与推演集成 — `odap/biz/decision/decision_recommendation/impl/recommendation_engine.py` 与推演结果集成，为推演结果提供方案推荐
- [ ] T286 历史推荐经验沉淀 — `odap/biz/decision/decision_recommendation/impl/recommendation_engine.py` 历史推荐经验沉淀到知识图谱（Graphiti）
- [ ] T287 决策推荐 schemas 定义 — `odap/biz/decision/decision_recommendation/api/schemas.py` RecommendRequest / RecommendationResponse / RiskAssessmentResponse / ExplainResponse 等
- [ ] T288 决策推荐 API 路由 — `odap/biz/decision/decision_recommendation/api/routes.py` POST /api/decision/recommend + POST /api/decision/risk-assessment + GET /api/decision/recommendations/{id}/explain + GET /api/decision/history
- [ ] T289 决策推荐路由注册 — `odap/web/app.py` include_router(decision_router)
- [ ] T290 决策推荐单元测试 — `tests/unit/test_decision_recommendation.py` 覆盖方案推荐/风险评估/排序/可解释性/RAG 增强
- [ ] T291 前端决策推荐组件 — `frontend/src/modules/simulation/components/RecommendationPanel.tsx` L3 组织组件，方案推荐展示 + 风险评估 + 决策理由解释

---

## Phase 9: Polish & Cross-Cutting

> 预计工期: 2-3 周 | 依赖 Phase 7 + Phase 8 | 贯穿所有阶段的收尾工作

### FR-028: 测试金字塔 + 质量门禁

- [ ] T292 质量门禁脚本 — `scripts/quality-gate.sh` 统一质量门禁脚本：后端 ruff check + pytest --cov-fail-under=80，前端 lint + typecheck + test
- [ ] T293 集成测试补全 — `tests/integration/` 补全 test_ontology_graphiti.py / test_agent_openharness.py / test_opa_integration.py / test_mcp_integration.py
- [ ] T294 E2E 测试补全 — `tests/e2e/` 补全 test_ontology_workflow.py / test_agent_workflow.py / test_simulation_workflow.py（Playwright）
- [ ] T295 CI/CD 配置 — `.github/workflows/quality-gate.yml` GitHub Actions 自动运行 lint + typecheck + test + 覆盖率报告

### ADR 状态修正

- [ ] T296 ADR-030 状态修正 — `docs/07-adr/ADR-030.md` 状态从 Accepted 修正为 Superseded（OpenHarness 立即集成覆盖推迟决策）
- [ ] T297 ADR-036 补充严格对齐说明 — `docs/07-adr/ADR-036.md` 补充"严格对齐 Palantir AIP 本体模型"说明
- [ ] T298 ADR-037 补充完整 i18n 实现 — `docs/07-adr/ADR-037.md` 补充完整 i18n 实现（后台管理+LLM 翻译）
- [ ] T299 ADR-038 补充本体拆分说明 — `docs/07-adr/ADR-038.md` 补充本体模型层+本体管理引擎拆分说明
- [ ] T300 ADR-043 补充混合路由策略 — `docs/07-adr/ADR-043.md` 补充混合路由策略（规则优先+LLM 兜底）
- [ ] T301 ADR-047 补充 OpenHarness Tool 接口 — `docs/07-adr/ADR-047.md` 补充基于 OpenHarness Tool 接口实现
- [ ] T302 ADR-048 补充本体拆分和 Palantir 参考 — `docs/07-adr/ADR-048.md` 补充本体模型层拆分和 Palantir 参考
- [ ] T303 ADR-049 补充 OpenHarness 依赖 — `docs/07-adr/ADR-049.md` 补充基于 OpenHarness 设计的依赖说明
- [ ] T304 ADR-026 补充 OpenHarness MCP 依赖 — `docs/07-adr/ADR-026.md` 补充基于 OpenHarness 实现 MCP 的依赖说明
- [ ] T305 ADR-027 补充 OpenHarness 钩子依赖 — `docs/07-adr/ADR-027.md` 补充基于 OpenHarness 生命周期钩子的依赖说明
- [ ] T306 ADR-051 补充 OpenHarness 外层封装 — `docs/07-adr/ADR-051.md` 补充基于 OpenHarness 外层封装的依赖说明
- [ ] T307 ADR-029 补充统一工具注册表 — `docs/07-adr/ADR-029.md` 补充统一工具注册表基于 OpenHarness Tool 接口

### 前端组件迁移 + 性能优化

- [ ] T308 现有页面迁移到 5 级组件体系 — `frontend/src/modules/` 逐步迁移现有页面到 L5 级别，使用 L1-L4 组件重构
- [ ] T309 前端全局样式统一 — `frontend/src/modules/shared/styles/global.css` 统一 CSS Variables + Ant Design Token 系统 + 移动优先响应式
- [ ] T310 Graphiti 双时态查询性能优化 — `odap/infra/graph/graph_service.py` 建立时间索引 + 缓存常用查询结果
- [ ] T311 API P95 性能优化 — 后端 API P95 < 500ms 优化，QA P95 < 3s 优化，推演 < 30s 优化
- [ ] T312 bootstep.py MinIO 服务集成 — `bootstep.py` 新增 MinIO 容器启动/停止/状态检查支持

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
```

### 关键路径

```
T001-T025 → T026-T053 → T054-T133 → T134-T162 → T184-T239 → T240-T264 → T292-T312
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

### 5. 测试策略

- **每个任务完成后立即编写单元测试**（不延迟到 Phase 9）
- **集成测试在对应 Phase 完成后编写**
- **E2E 测试在 Phase 9 统一补全**
- **质量门禁从 Phase 1 开始执行**：每个 PR 必须通过 lint + typecheck + unit test

### 6. 风险缓解

| 风险 | 缓解措施 | 对应任务 |
|------|----------|----------|
| OpenHarness API 不稳定 | 适配层抽象接口，缺失功能自行补充 | T018-T024 |
| Palantir 对齐过度抽象 | 仅实现 FR 需要的子集 | T029-T033 |
| Graphiti 双时态查询性能 | 建立时间索引，缓存常用查询 | T049, T310 |
| 前端重构范围大 | 优先完成基础设施，页面逐步迁移 | T006-T012, T308 |
| MinIO 运维复杂度 | Docker Compose 统一管理 | T001, T312 |
| 多方案并行推演资源消耗 | 限制并行度（最多 10），超限自动终止 | T247, T241 |
