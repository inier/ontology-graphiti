# 三国战纪智能体 - 平台问题记录

> 构建过程中发现的 ODAP 平台功能问题，按严重程度排序

## P0 - 阻塞级

### ISSUE-001: QA 引擎不检索本体模型实例
- **现象**: 通过 `/api/ontology/model/instances/batch` 注入的实例数据，QA 引擎无法检索
- **根因**: QA RAG 管道只有 3 条检索路径（Graphiti / IngestStorage / SemanticMapStorage），不包含 ModelStorage
- **影响**: 所有通过本体设计 API 创建的实例数据对 QA 不可见
- **修复**: 在 `RAGPipeline` 中增加 `_retrieve_from_model_storage` 方法，同时修改 `QAEngineV2.__init__` 和 `_get_qa_engine()` 注入 `model_storage`
- **状态**: ✅ 已修复（qa_engine.py + routes.py + _deps.py）

### ISSUE-002: 实例 workspace_id 不匹配
- **现象**: 批量创建实例时 `workspace_id` 默认为 `"default"`，但 QA 请求传实际 workspace ID，导致按 workspace 过滤时返回 0 条
- **根因**: `batch_create_instances` 的 `workspace_id` 字段默认值是 `"default"`，前端/脚本未传正确值
- **影响**: 即使 QA 能检索 ModelStorage，按 workspace 过滤也找不到数据
- **修复**: `_retrieve_from_model_storage` 同时查指定 workspace 和 `"default"` workspace
- **状态**: ✅ 已修复（qa_engine.py）

## P1 - 重要级

### ISSUE-003: QA LLM 调用超时
- **现象**: QA 引擎的 LLM 调用连接 `integrate.api.nvidia.com` 超时（10s timeout），导致返回原始 RAG 上下文而非自然语言回答
- **根因**: LLM 配置指向 nvidia.com，但容器内网络无法访问
- **影响**: QA 回答质量极差，用户看到的是原始检索结果而非自然语言
- **修复**: 需要检查 `.env.docker` 中的 LLM 配置，确保使用可达的 API 端点
- **状态**: ❌ 未修复（环境配置问题）

### ISSUE-004: 实体类型已存在时返回 500
- **现象**: `POST /api/ontology/model/entity-types` 创建已存在的类型时返回 500 而非 409
- **根因**: 后端未做唯一性检查，直接抛出内部错误
- **影响**: 重复创建时需要客户端做异常处理和重试
- **修复**: 建议后端返回 409 Conflict
- **状态**: ❌ 未修复（平台问题）

### ISSUE-005: 场景 API 路径不一致
- **现象**: 场景 API 是 `/api/workspaces/{ws_id}/scenarios` 而非 `/api/scenarios`
- **根因**: 场景是工作空间的子资源，RESTful 嵌套路径
- **影响**: 容易误用 API 路径
- **修复**: 文档/API 文档需明确说明
- **状态**: ❌ 未修复（文档问题）

### ISSUE-006: Agent API 路径为 /api/agent-management 而非 /api/agents
- **现象**: 智能体管理 API 前缀是 `/api/agent-management` 而非直觉的 `/api/agents`
- **根因**: 历史命名
- **影响**: API 发现困难
- **修复**: 建议增加 `/api/agents` 别名或在 API 文档中明确标注
- **状态**: ❌ 未修复（平台问题）

## P2 - 改进级

### ISSUE-007: 现有 Skills 大量读 Mock 数据
- **现象**: `analysis/computation/recommendation/visualization` 类别的 Skill 全部从 `load_simulation_data()` 读取硬编码 Mock 数据
- **根因**: 初始开发时为军事领域 Demo 设计
- **影响**: 这些 Skill 对三国场景完全无用
- **修复**: 需要将 Mock 数据源替换为从图谱/本体实例查询
- **状态**: ❌ 未修复（架构改进）

### ISSUE-008: Intelligence Agent 硬编码军事领域 prompt
- **现象**: `IntelligenceAgent` 的 system prompt 包含"雷达""敌方""蓝方/红方"等军事术语
- **根因**: 初始开发时为军事领域设计
- **影响**: 三国战纪智能体使用时 prompt 不匹配
- **修复**: 需要参数化 system prompt，根据 agent 的 `description` 动态生成
- **状态**: ❌ 未修复（架构改进）

### ISSUE-009: Agent 暴露的 Skill 类别有限
- **现象**: Intelligence Agent 仅暴露 `intelligence/analysis/ontology/recommendation` 四类 Skill，不包含 `graph` 类
- **根因**: 初始设计限制
- **影响**: 三国智能体无法使用 `query_entities/search_graph` 等通用图谱 Skill
- **修复**: 扩展 Agent 的 Skill 类别白名单
- **状态**: ❌ 未修复（架构改进）

## P1.5 - 前后端路由不匹配（已修复）

### ISSUE-010: 前端 /api/query/entities 404
- **现象**: 前端 `api.queryEntities()` 调用 `POST /api/query/entities` 返回 404
- **根因**: 后端 query 路由只有 DSL 查询（`POST /api/query`），无结构化实体查询端点
- **修复**: 在 `odap/infra/query/routes.py` 增加 `/entities`、`/relations`、`/complex`、`/history` 端点
- **状态**: ✅ 已修复

### ISSUE-011: 前端 /api/ontology/ingest/documents/list 404
- **现象**: 前端 `api.getOntologyDocuments()` 调用 `GET /api/ontology/ingest/documents/list` 返回 404
- **根因**: `query_api.routes` 路由未在 `app.py` 中注册；且导入路径错误（`..services.ingest_service` 不存在）
- **修复**: 1) 修正导入路径为绝对导入；2) 在 `app.py` 中注册 `ontology_ingest_router`
- **状态**: ✅ 已修复

### ISSUE-012: 前端 /api/scenarios/{id}/entities 404
- **现象**: 前端 `api.getEntities()` 调用 `GET /api/scenarios/{scenarioId}/entities` 返回 404
- **根因**: 后端场景路由在 `/api/workspaces/{ws_id}/scenarios/` 下，无独立 `/api/scenarios/` 路由
- **修复**: 在 `workspace/api/routes.py` 增加 `scenario_compat_router`，注册到 `app.py`
- **状态**: ✅ 已修复

### ISSUE-013: 前端 /api/ontology/model/{docId}/entity-types 404
- **现象**: 前端 `ontologyApi.listEntityTypes("default")` 调用 `GET /api/ontology/model/default/entity-types` 返回 404
- **根因**: 后端路由为 `/api/ontology/model/entity-types`（无 documentId 路径段），前端 API 设计包含 documentId
- **修复**: 在 `model/api/routes.py` 增加带 `{document_id}` 路径段的兼容路由
- **状态**: ✅ 已修复

### ISSUE-014: 前端 /api/ontology/model/default 404
- **现象**: 前端 `ontologyApi.loadOntologyDocument("default")` 返回 404
- **根因**: `model_service.get_document("default")` 找不到名为 "default" 的文档
- **修复**: 在 `load_ontology_document` 路由中，文档不存在时返回空结构而非 404
- **状态**: ✅ 已修复

## 当前状态总结

| 项目 | 状态 |
|------|------|
| 工作空间 X | ✅ 已创建 |
| 场景 X-1 | ✅ 已创建 |
| 5 个实体类型 | ✅ 已注册 |
| 157 个实例 | ✅ 已注入 |
| 三国战纪智能体 | ✅ 已创建 (agent_9ecd9ab1b72e) |
| QA 检索三国数据 | ✅ 已验证（需修复 LLM 超时才能生成自然语言回答） |
| 智能体 Agent Loop | ❌ 受限于 LLM 超时 + 军事 prompt + Skill 类别限制 |
