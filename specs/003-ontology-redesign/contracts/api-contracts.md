# API Contracts: 本体设计器彻底重构

**Branch**: `003-ontology-redesign` | **Date**: 2026-06-09

## 1. 本体管理 API

### 1.1 本体 CRUD

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/ontologies` | 列出当前工作空间下的所有本体 | Required |
| POST | `/api/ontologies` | 创建新本体（含初始版本） | Required |
| GET | `/api/ontologies/{ontology_id}` | 获取本体详情 | Required |
| PUT | `/api/ontologies/{ontology_id}` | 更新本体信息 | Required |
| DELETE | `/api/ontologies/{ontology_id}` | 删除本体 | Admin |

#### POST /api/ontologies

**Request**:
```json
{
  "name": "电商本体",
  "description": "电商领域本体定义",
  "workspace_id": "ws-001",
  "scenario_id": "scenario-001"
}
```

**Response** (201):
```json
{
  "ontology_id": "ont-a1b2c3d4",
  "name": "电商本体",
  "description": "电商领域本体定义",
  "workspace_id": "ws-001",
  "scenario_id": "scenario-001",
  "current_version": "v0.1.0",
  "status": "draft",
  "created_at": "2026-06-09T10:00:00Z",
  "updated_at": "2026-06-09T10:00:00Z"
}
```

### 1.2 本体版本管理

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/ontologies/{ontology_id}/versions` | 列出版本历史 | Required |
| POST | `/api/ontologies/{ontology_id}/versions/commit` | 提交版本快照 | Required |
| GET | `/api/ontologies/{ontology_id}/versions/{version_id}/diff` | 版本差异对比 | Required |
| POST | `/api/ontologies/{ontology_id}/versions/{version_id}/rollback` | 回滚到指定版本 | Required |

#### POST /api/ontologies/{ontology_id}/versions/commit

**Request**:
```json
{
  "changelog": "新增用户和订单对象类型"
}
```

**Response** (200):
```json
{
  "version_id": "v20260609-002",
  "version_number": "0.2.0",
  "is_stable": true,
  "changelog": "新增用户和订单对象类型",
  "created_at": "2026-06-09T11:00:00Z"
}
```

---

## 2. 对象类型管理 API（统一 Schema 层）

### 2.1 ObjectType CRUD

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/ontologies/{ontology_id}/object-types` | 列出对象类型 | Required |
| POST | `/api/ontologies/{ontology_id}/object-types` | 创建对象类型 | Required |
| GET | `/api/ontologies/{ontology_id}/object-types/{type_id}` | 获取对象类型详情 | Required |
| PUT | `/api/ontologies/{ontology_id}/object-types/{type_id}` | 更新对象类型 | Required |
| DELETE | `/api/ontologies/{ontology_id}/object-types/{type_id}` | 删除对象类型 | Required |

#### POST /api/ontologies/{ontology_id}/object-types

**Request**:
```json
{
  "name": "User",
  "display_name": "用户",
  "description": "系统用户",
  "classification_level": "U",
  "properties": [
    {
      "name": "username",
      "display_name": "用户名",
      "property_type": "STRING",
      "required": true
    },
    {
      "name": "email",
      "display_name": "邮箱",
      "property_type": "STRING",
      "required": true
    }
  ],
  "links": [
    {
      "name": "places",
      "target_type": "Order",
      "cardinality": "ONE_TO_MANY",
      "link_type": "ASSOCIATION",
      "reverse_name": "placed_by"
    }
  ]
}
```

**Response** (201):
```json
{
  "type_id": "type-x1y2z3",
  "ontology_id": "ont-a1b2c3d4",
  "name": "User",
  "display_name": "用户",
  "description": "系统用户",
  "classification_level": "U",
  "properties": [...],
  "links": [...],
  "actions": [],
  "primary_key": [],
  "created_at": "2026-06-09T10:30:00Z"
}
```

### 2.2 LinkType 管理

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/ontologies/{ontology_id}/object-types/{type_id}/links` | 添加关系类型 | Required |
| PUT | `/api/ontologies/{ontology_id}/object-types/{type_id}/links/{link_id}` | 更新关系类型 | Required |
| DELETE | `/api/ontologies/{ontology_id}/object-types/{type_id}/links/{link_id}` | 删除关系类型 | Required |

### 2.3 ActionType 管理

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/ontologies/{ontology_id}/action-types` | 列出动作类型 | Required |
| POST | `/api/ontologies/{ontology_id}/action-types` | 创建动作类型 | Required |
| PUT | `/api/ontologies/{ontology_id}/action-types/{action_type_id}` | 更新动作类型 | Required |
| DELETE | `/api/ontologies/{ontology_id}/action-types/{action_type_id}` | 删除动作类型 | Required |

---

## 3. 业务实体 Schema 管理 API

### 3.1 Schema 定义（本体设计器使用）

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/ontologies/{ontology_id}/schemas/business-processes` | 列出业务过程结构定义 | Required |
| POST | `/api/ontologies/{ontology_id}/schemas/business-processes` | 创建业务过程结构定义 | Required |
| PUT | `/api/ontologies/{ontology_id}/schemas/business-processes/{id}` | 更新业务过程结构定义 | Required |
| DELETE | `/api/ontologies/{ontology_id}/schemas/business-processes/{id}` | 删除业务过程结构定义 | Required |

> 同样模式适用于 `/schemas/business-rules`、`/schemas/business-logics`、`/schemas/business-indicators`

### 3.2 实例数据（子菜单页面使用）

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/business-processes?ontology_id={id}&is_schema=false` | 列出业务过程实例 | Required |
| POST | `/api/business-processes` | 创建业务过程实例 | Required |

> 现有 API 保持不变，新增 `is_schema` 查询参数过滤

---

## 4. 数据库抽取 API

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/ontologies/{ontology_id}/extract/database/test-connection` | 测试数据库连接 | Required |
| POST | `/api/ontologies/{ontology_id}/extract/database` | 从数据库抽取本体 | Required |
| GET | `/api/ontologies/{ontology_id}/extract/sessions/{session_id}` | 获取抽取会话状态 | Required |
| POST | `/api/ontologies/{ontology_id}/extract/sessions/{session_id}/confirm` | 确认导入抽取结果 | Required |

#### POST /api/ontologies/{ontology_id}/extract/database/test-connection

**Request**:
```json
{
  "db_type": "postgresql",
  "host": "localhost",
  "port": 5432,
  "database": "mydb",
  "username": "readonly",
  "password": "secret"
}
```

**Response** (200):
```json
{
  "status": "success",
  "message": "连接成功",
  "table_count": 25,
  "schema_name": "public"
}
```

#### POST /api/ontologies/{ontology_id}/extract/database

**Request**:
```json
{
  "db_type": "postgresql",
  "host": "localhost",
  "port": 5432,
  "database": "mydb",
  "username": "readonly",
  "password": "secret",
  "table_filter": ["users", "orders", "products"],
  "use_llm_enrichment": true
}
```

**Response** (202):
```json
{
  "session_id": "ext-session-001",
  "status": "extracting",
  "message": "正在提取数据库 Schema..."
}
```

---

## 5. 自然语言提取 API（Hyper-Extract 增强）

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/extraction/extract/natural-language` | 从自然语言文本提取本体 | Required |
| POST | `/api/extraction/extract/document` | 从上传文档提取本体 | Required |
| POST | `/api/extraction/extract/knowledge-base` | 从知识库提取本体 | Required |
| GET | `/api/extraction/sessions/{session_id}` | 获取提取会话状态 | Required |
| POST | `/api/extraction/sessions/{session_id}/confirm` | 确认导入提取结果 | Required |
| GET | `/api/extraction/templates` | 列出可用 HE 模板 | Required |
| POST | `/api/extraction/templates/recommend` | 根据文本推荐模板 | Required |
| GET | `/api/extraction/provenance/{entity_id}` | 查询实体溯源信息 | Required |
| GET | `/api/extraction/provenance/by-source/{doc_id}` | 反向查询文档产生的实体 | Required |

#### POST /api/extraction/extract/natural-language

**Request**:
```json
{
  "ontology_id": "ont-001",
  "text": "电商系统需要管理用户、商品和订单。用户可以下单购买商品，订单包含多个商品项。库存不足时触发补货规则。",
  "source_type": "text",
  "template_id": null,
  "method": "graph_rag",
  "auto_search": false
}
```

**Response** (202):
```json
{
  "session_id": "ext-session-002",
  "status": "extracting",
  "template_used": "general/base_graph",
  "message": "正在使用 Hyper-Extract 提取本体结构..."
}
```

#### POST /api/extraction/extract/document

**Request** (multipart/form-data):
```
ontology_id: ont-001
file: <binary file data>
template_id: null
method: graph_rag
```

**Response** (202):
```json
{
  "session_id": "ext-session-003",
  "status": "extracting",
  "template_used": "general/doc_structure",
  "message": "正在解析文档并提取本体结构...",
  "chunks_total": 5,
  "chunks_processed": 0
}
```

#### POST /api/extraction/extract/knowledge-base

**Request**:
```json
{
  "ontology_id": "ont-001",
  "kb_id": "kb-001",
  "template_id": null,
  "method": "graph_rag",
  "batch_size": 10
}
```

**Response** (202):
```json
{
  "session_id": "ext-session-004",
  "status": "extracting",
  "template_used": "general/base_graph",
  "message": "正在从知识库增量提取...",
  "docs_total": 25,
  "docs_processed": 0
}
```

#### GET /api/extraction/sessions/{session_id}

**Response** (200):
```json
{
  "session_id": "ext-session-002",
  "ontology_id": "ont-001",
  "extraction_type": "natural_language",
  "status": "reviewing",
  "template_used": "general/base_graph",
  "method_used": "graph_rag",
  "result_data": {
    "schema": {
      "object_types": [...],
      "link_types": [...],
      "action_types": [...],
      "rule_types": [...]
    },
    "instances": {
      "entities": [...],
      "relations": [...]
    }
  },
  "conflicts": [
    {
      "type": "duplicate_name",
      "name": "User",
      "existing_type_id": "type-existing",
      "proposed_name": "User"
    }
  ],
  "provenance_summary": {
    "source_docs": 1,
    "total_chunks": 1,
    "total_entities": 3,
    "total_relations": 2
  },
  "created_at": "2026-06-23T10:00:00"
}
```

#### POST /api/extraction/sessions/{session_id}/confirm

**Request**:
```json
{
  "selected_type_ids": ["type-001", "type-002"],
  "selected_entity_ids": ["ent-001", "ent-002"],
  "merge_strategy": "skip",
  "write_channels": ["graph_write_proxy", "graphiti_episode"]
}
```

**Response** (200):
```json
{
  "status": "success",
  "imported_schema_types": 4,
  "imported_entities": 3,
  "imported_relations": 2,
  "channel_a_status": "success",
  "channel_b_status": "success",
  "provenance_records": 5
}
```

#### GET /api/extraction/provenance/{entity_id}

**Response** (200):
```json
{
  "entity_id": "ent-001",
  "entity_type": "object_instance",
  "source_doc_id": "doc-001",
  "source_doc_name": "电商系统需求文档.pdf",
  "vector_chunk_id": "chunk-003",
  "doc_fragment_id": "page:2,para:3",
  "extraction_method": "graph_rag",
  "he_template_version": "general/base_graph@v1",
  "confidence_score": 0.92,
  "timestamp": "2026-06-23T10:05:00"
}
```

#### GET /api/extraction/templates

**Query Parameters**: `domain=general&auto_type=graph&page=1&page_size=20`

**Response** (200):
```json
{
  "templates": [
    {
      "template_id": "tpl-001",
      "name": "general/base_graph",
      "description": "通用知识图谱提取模板",
      "domain": "general",
      "auto_type": "graph",
      "method": "graph_rag",
      "source": "preset"
    }
  ],
  "total": 80,
  "page": 1
}
```

---

## 6. 图谱 API

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/ontologies/{ontology_id}/graph` | 获取本体图谱数据（节点+边） | Required |

**Response** (200):
```json
{
  "nodes": [
    {
      "id": "type-x1y2z3",
      "name": "User",
      "type": "object_type",
      "properties": {"property_count": 5, "link_count": 2}
    }
  ],
  "edges": [
    {
      "id": "link-a1b2c3",
      "source": "type-x1y2z3",
      "target": "type-d4e5f6",
      "name": "places",
      "type": "association",
      "cardinality": "ONE_TO_MANY"
    }
  ]
}
```

---

## 7. 错误响应格式

所有 API 统一错误格式：

```json
{
  "detail": "错误描述信息"
}
```

| HTTP Status | 场景 |
|-------------|------|
| 400 | 请求参数无效 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 冲突（如同名对象类型已存在） |
| 422 | 请求体验证失败 |
| 500 | 服务器内部错误 |
