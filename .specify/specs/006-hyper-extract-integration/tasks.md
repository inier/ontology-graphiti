# Tasks: Hyper-Extract 集成

**Input**: Design document from `docs/superpowers/specs/2026-06-16-hyper-extract-integration-design.md`

**Prerequisites**: 设计文档 v2 (Review 修订版)

**Organization**: 任务按实施阶段分组，支持并行执行和独立验证。

## Format: `[ID] [Marker] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[TDD]**: 必须遵循 RED-GREEN-REFACTOR
- **[REVIEW]**: 需要代码审查后才能继续
- **[SUBAGENT]**: 可委派给子代理执行

---

## Phase 1: Setup (项目初始化)

**Purpose**: 引入 Hyper-Extract Submodule，创建模块骨架

- [x] T001 [P] 添加 Hyper-Extract 为 Git Submodule
  - `git submodule add https://github.com/yifanfeng97/Hyper-Extract.git hyper-extract`
  - 更新 `.gitmodules`
  - 验证 `git submodule update --init --recursive` 正常工作
- [x] T002 [P] 创建 `odap/biz/data/hyper_extract/` 模块骨架
  - `__init__.py`, `api/`, `services/`, `impl/`, `models/`, `storage/`
  - 按设计文档 Section 3.1 的目录结构创建所有文件
- [x] T003 [P] 更新 `requirements.txt`
  - 新增 `hyperextract>=0.2.0`（或 `-e ./hyper-extract` 如果用 Submodule 本地安装）
  - 验证 `pip install -r requirements.txt` 正常

**Checkpoint**: Submodule 可初始化，模块骨架存在，依赖可安装

---

## Phase 2: Foundational (核心基础设施)

**Purpose**: HE 适配层 + 本体映射层，所有用户故事的前置依赖

**⚠️ CRITICAL**: 此阶段完成前，任何用户故事都无法开始

- [x] T004 实现 `HEAdapter` — Hyper-Extract Python API 适配
  - 文件: `odap/biz/data/hyper_extract/impl/he_adapter.py`
  - 封装 HE `Template.parse()` 调用
  - 处理 LLM 配置（复用 ODAP 的 `OPENAI_API_KEY` / `OPENAI_API_BASE`）
  - 异常处理：LLM 调用失败返回 `{"status": "error", "message": "..."}`
  - `is_available()` 方法检测 HE 是否可用
- [x] T005 [TDD] 实现 `OntologyMapper` — KnowledgeAbstract → OntologyDocument
  - 文件: `odap/biz/data/hyper_extract/impl/ontology_mapper.py`
  - 通过 `OntologyService.list_object_types()` / `list_link_types()` / `list_action_types()` 获取类型定义
  - 类型校验：entity.type 必须在 object_type_names 中
  - 关系校验：relation.type 必须在 link_type_names 中
  - 属性映射：HE 提取属性 → 四层属性结构 (basic/statistical/capabilities/constraints)
  - ID 生成：`deterministic_entity_id(entity_type, name)`
  - 未知类型处理：严格模式丢弃 / 宽松模式标记 "unclassified"
  - **测试**: `tests/unit/test_ontology_mapper.py`（使用 tmp_path 真实 DB，不用 MagicMock）
- [x] T006 [TDD] 实现 `OntologyTemplateGenerator` — 本体定义 → HE YAML 模板
  - 文件: `odap/biz/data/hyper_extract/services/template_generator.py`
  - 通过 `OntologyService` 获取类型定义（非 OntologyDefinition 类）
  - `list_object_types(ontology_id)` → template entities.fields
  - `list_link_types(ontology_id)` → template relations.fields
  - `list_action_types(ontology_id)` → template events.fields + 升级为 temporal_graph
  - **测试**: `tests/unit/test_template_generator.py`
- [x] T007 [P] 实现提取任务模型和存储
  - 文件: `odap/biz/data/hyper_extract/models/extraction_task.py`
  - 文件: `odap/biz/data/hyper_extract/storage/sqlite_extraction_storage.py`
  - `ExtractionTask` 模型：task_id, text_hash, ontology_id, status, result, created_at
  - `SQLiteExtractionStorage`：CRUD + 状态更新（遵循 AGENTS.md SQLite 规则）
  - `storage/__init__.py` 别名导出: `Storage = SQLiteExtractionStorage`
  - **测试**: `tests/unit/test_extraction_storage.py`（使用 tmp_path 真实 DB）

**Checkpoint**: HE 可调用，提取结果可映射为 OntologyDocument，模板可自动生成

---

## Phase 3: User Story 1 — 双通道知识提取与写入 (Priority: P1) 🎯 MVP

**Goal**: 从文本提取结构化知识，双通道写入 Neo4j（GraphWriteProxy + Graphiti add_episode）

**Independent Test**: 给定一段文本和 ontology_id，能提取实体/关系，写入 Neo4j，Graphiti search 能发现

### Tests for User Story 1

- [x] T008 [TDD] [US1] `DualChannelWriter` 单元测试
  - 文件: `tests/unit/test_dual_channel_writer.py`
  - 测试通道 A（GraphWriteProxy）写入完整属性
  - 测试通道 B（graphiti.add_episode）建立双时态索引
  - 测试通道 B 失败不影响通道 A
  - 测试 valid_time 提取逻辑
  - Mock GraphWriteProxy 和 GraphManager（非存储层测试）

### Implementation for User Story 1

- [x] T009 [US1] 实现 `DualChannelWriter` — 双通道互补写入
  - 文件: `odap/biz/data/hyper_extract/impl/dual_channel_writer.py`
  - 通道 A: `GraphWriteProxy.add_entity()` / `add_relationship()` 写入完整属性
  - 通道 B: `GraphManager.add_episode()` 建立双时态索引 + 语义搜索
  - valid_time 提取：从 HE events → 文档元数据 → 用户指定 → datetime.now()
  - 通道 B 异常隔离：失败仅 log，不影响通道 A
  - **禁止**绕过 GraphWriteProxy 直接操作 Neo4j
- [x] T010 [US1] 实现 `ExtractService` — 编排层
  - 文件: `odap/biz/data/hyper_extract/services/extract_service.py`
  - `async def extract_and_write(text, ontology_id, scenario_id, workspace_id)`
  - 流程: 安全过滤 → 生成模板 → HE 提取 → 本体映射 → 双通道写入 → 记录任务
  - 复用 `ContentSanitizer` 做内容安全过滤
  - 返回 `Dict[str, Any]`（遵循 AGENTS.md 服务层规则）
- [x] T011 [US1] 实现 API 路由和 Schema
  - 文件: `odap/biz/data/hyper_extract/api/routes.py`
  - 文件: `odap/biz/data/hyper_extract/api/schemas.py`
  - `POST /api/he/extract` — 触发知识提取
  - `GET /api/he/templates/{ontology_id}` — 查看自动生成的模板
  - 路由层必须 `except HTTPException: raise` 透传
  - 在 `odap/web/app.py` 中 `include_router(he_router)`
- [x] T012 [REVIEW] [US1] 集成验证
  - 手动测试: 给定文本 + ontology_id，调用 `POST /api/he/extract`
  - 验证通道 A: Neo4j 中 Entity 节点包含完整属性
  - 验证通道 B: Graphiti `search()` 能发现提取的实体
  - 验证审计日志: GraphWriteProxy 的 `_log_write()` 有记录

**Checkpoint**: 知识提取 MVP 可用 — 文本 → 提取 → 双通道写入 → 可搜索

---

## Phase 4: User Story 2 — Agent Skill 注册与权限控制 (Priority: P2)

**Goal**: 将知识提取能力注册为 Agent Skill，支持 OPA 权限控制和重试

**Independent Test**: Agent 可通过 Skill 调用知识提取，OPA 策略生效，失败自动重试

### Implementation for User Story 2

- [x] T013 [US2] 实现 `KnowledgeExtractSkill`
  - 文件: `odap/tools/web/web_skills.py`（新增）
  - 继承 `BaseSkill`，实现 `async def execute()`
  - `SkillMetadata(name="knowledge_extract", category="ontology", requires_opa_check=True, opa_action="data_collection:extract")`
  - `KnowledgeExtractInput(SkillInput)`: text, ontology_id, scenario_id, template_override
  - 返回 `SkillOutput(success, data, execution_time_ms, skill_name, request_id)`
- [x] T014 [P] [US2] 新增 OPA 策略
  - 文件: `odap/infra/opa/policies/data_collection.rego`
  - admin 角色允许 extract
  - analyst 角色仅允许同工作空间 extract
- [x] T015 [US2] 注册 Skill 到 SkillRegistryV2
  - 在 Skill 初始化流程中 `registry.register(KnowledgeExtractSkill())`
  - 验证 SkillExecutorV2 的重试机制（最多 3 次）自动生效
  - 验证 OPA 权限检查在执行前触发
- [x] T016 [REVIEW] [US2] Skill 集成验证
  - 通过 Agent Chat 调用 knowledge_extract Skill
  - 验证 OPA 策略：非授权角色被拒绝
  - 验证重试：模拟 LLM 失败，确认自动重试

**Checkpoint**: Agent 可通过 Skill 调用知识提取，权限和重试机制生效

---

## Phase 5: User Story 3 — IngestService 集成 (Priority: P3)

**Goal**: IngestService 的摄入方法内部切换为 HE 提取，对上层透明

**Independent Test**: 调用 `ingest_from_natural_language(text, ontology_id=xxx)` 走 HE 路径

### Implementation for User Story 3

- [x] T017 [US3] 修改 `IngestService.ingest_from_natural_language()`
  - 文件: `odap/biz/core/ontology/design/services/ingest_service.py`
  - 新增可选参数 `ontology_id: str = None`
  - 当 `ontology_id` 提供且 HE 可用时，走 HE 提取路径
  - 否则降级到原有 LLM 提取（不变）
  - 返回值仍为 `str`（record_id），不破坏现有接口
- [x] T018 [P] [US3] 修改其他摄入方法（可选）
  - `ingest_from_url()`: 新增可选 `ontology_id`
  - `ingest_from_news()`: 新增可选 `ontology_id`
  - `ingest_from_json()`: 新增可选 `ontology_id`
  - 每个方法内部：有 ontology_id → HE 路径，否则 → 原有路径
- [x] T019 [US3] 集成验证
  - 调用 `ingest_from_natural_language(text, scenario_id, ontology_id)` → HE 路径
  - 调用 `ingest_from_natural_language(text, scenario_id)` → 原有路径（降级）
  - 验证两种路径的写入结果一致（通道 A + 通道 B）

**Checkpoint**: IngestService 支持 HE 增强提取，向后兼容

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 优化、安全加固、文档

- [x] T020 [P] 前端摄入界面增强 — HE 提取选项
  - 在摄入面板中新增"本体定义"选择框
  - 选择后传入 `ontology_id` 参数
- [x] T021 [P] HE 增量演化支持
  - 封装 HE `evolve()` 方法
  - 支持追加新文档扩展已有知识库
- [x] T022 [P] 批量提取并行化
  - 使用 `asyncio.gather()` 并行处理多文档
  - 在 `ExtractService` 中新增 `extract_batch()` 方法
- [x] T023 [P] 安全加固
  - 验证 GraphWriteProxy 的 `_validate_label()` 在所有写入路径生效
  - 验证 ContentSanitizer 对恶意输入的过滤
  - 验证 OPA 策略覆盖所有提取入口

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1 完成 — **阻塞所有用户故事**
- **User Story 1 (Phase 3)**: 依赖 Phase 2 完成
- **User Story 2 (Phase 4)**: 依赖 Phase 3 完成（需要 ExtractService）
- **User Story 3 (Phase 5)**: 依赖 Phase 3 完成（需要 ExtractService）
- **Polish (Phase 6)**: 依赖所有用户故事完成

### User Story Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational (T004-T007)
    ↓
Phase 3: US1 — 双通道提取写入 (T008-T012) 🎯 MVP
    ↓
    ├→ Phase 4: US2 — Skill 注册 (T013-T016)
    └→ Phase 5: US3 — IngestService 集成 (T017-T019)
         ↓
    Phase 6: Polish (T020-T023)
```

### Parallel Opportunities

- Phase 1: T001, T002, T003 可并行
- Phase 2: T007 可与 T004/T005/T006 并行
- Phase 4 和 Phase 5 可并行（不同文件，无依赖）
- Phase 6: T020, T021, T022, T023 可并行

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational
3. 完成 Phase 3: User Story 1
4. **STOP and VALIDATE**: 手动测试双通道写入 + Graphiti search
5. 可演示 MVP

### Incremental Delivery

1. Setup + Foundational → 基础设施就绪
2. US1 → 双通道提取写入可工作（MVP）
3. US2 → Agent 可通过 Skill 调用提取
4. US3 → IngestService 原生支持 HE 提取
5. Polish → 前端增强 + 批量并行 + 增量演化
