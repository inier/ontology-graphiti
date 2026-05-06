# 智能问答驱动的本体构建系统 API 规范

> **版本**: v3.0.0 | **基础路径**: `/api`

---

## 目录

1. [整体流程说明](#1-整体流程说明)
2. [统一数据摄入 API](#2-统一数据摄入-api)
3. [独立摄入端点](#3-独立摄入端点)
4. [构建状态 API](#4-构建状态-api)
5. [本体版本管理 API](#5-本体版本管理-api)
6. [通用数据结构](#6-通用数据结构)
7. [错误码说明](#7-错误码说明)
8. [摄入 API 设计规范](#8-摄入-api-设计规范)

---

## 1. 整体流程说明

### 1.1 整合后的工作流程

系统现已实现数据摄入与本体构建的完整整合，所有数据摄入方式都会自动触发本体构建过程，无需单独调用本体构建接口。

**完整流程如下**：

1. **数据摄入**：通过多种输入方式（新闻、URL、手动输入、JSON，自然语言、随机事件）获取数据
2. **自动触发**：数据摄入完成后，系统自动触发本体构建过程
3. **转化处理**：执行实体和关系提取，构建图谱模型
4. **版本管理**：创建本体版本，记录变更历史
5. **状态追踪**：通过构建状态 API 监控整个过程

**核心改进**：
- 移除了单独的本体构建输入端，所有数据摄入方式都能触发构建
- 增加了转化过程的详细追踪
- 实现了本体版本的自动管理
- 提供了完整的构建状态查询接口
- **统一了输入输出结构**，简化前端接入复杂度

---

## 2. 统一数据摄入 API

> **重要**: 详细规范请参阅 [INGEST_API_SPEC.md](./INGEST_API_SPEC.md)

### 2.1 统一调用格式

所有数据摄入方式使用统一的 API 方法，前端只需记忆一种调用格式：

```javascript
await api.ingest({
  type: 'news',       // 摄入类型
  data: {...},        // 根据类型传递不同结构的数据
  scenario_id: 'xxx'  // 场景ID（可选）
});
```

### 2.2 支持的摄入类型

| type 值 | 描述 | data 结构示例 |
|---------|------|---------------|
| `news` | 新闻摄入 | 字符串 URL 或对象 `{url, event_context, max_sources}` |
| `manual` | 手动输入 | 字符串文本或对象 `{title, description}` |
| `json` | JSON 摄入 | JSON 格式字符串 |
| `natural_language` | 自然语言 | 字符串文本 |
| `random` | 随机生成 | 对象 `{parties, scenario_context, count}` |

### 2.3 统一响应结构

所有摄入方式返回一致的响应结构：

```json
{
  "ingest_id": "abc123",
  "status": "completed",
  "source_details": {...},
  "original_content": "...",
  "extracted_data": {
    "source_data": [...],
    "document_ids": [...],
    "document_count": 1,
    "entities_count": 5,
    "relations_count": 3,
    "events_count": 2
  }
}
```

---

## 3. 独立摄入端点

### 3.1 新闻数据摄入

**端点**: `POST /api/ontology/ingest/news`

**描述**: 从新闻来源摄入数据，支持 URL 抓取和关键词检索两种模式。

**请求体**:

```json
{
  "query": "string",       // 检索关键词（可选）
  "url": "string",        // 新闻网页URL（可选）
  "scenario_id": "string" // 场景ID（可选）
}
```

**响应体**:

```json
{
  "ingest_id": "string",
  "status": "completed",
  "source_details": {...},
  "original_content": "...",
  "extracted_data": {
    "source_data": [...],
    "document_ids": [...],
    "document_count": 1
  }
}
```

---

### 3.2 手动数据输入

**端点**: `POST /api/ontology/ingest/manual`

**描述**: 手动输入数据进行摄入。

**请求体**:

```json
{
  "form_data": {
    "title": "string",
    "description": "string"
  },
  "scenario_id": "string" // 场景ID（可选）
}
```

**响应体**:

```json
{
  "ingest_id": "string",
  "status": "completed",
  "source_details": {"form_data_keys": ["title", "description"]},
  "original_content": "...",
  "extracted_data": {
    "source_data": [...],
    "document_ids": [...],
    "document_count": 1,
    "entities_count": 2,
    "relations_count": 1,
    "events_count": 1
  }
}
```

---

### 3.3 自然语言输入

**端点**: `POST /api/ontology/ingest/natural_language`

**描述**: 通过自然语言描述摄入数据。

**请求体**:

```json
{
  "description": "string",   // 自然语言描述
  "scenario_id": "string"    // 场景ID（可选）
}
```

**响应体**:

```json
{
  "ingest_id": "string",
  "status": "completed",
  "source_details": {"text_length": 50},
  "original_content": "...",
  "extracted_data": {
    "source_data": [...],
    "document_ids": [...],
    "document_count": 1,
    "entities_count": 2,
    "relations_count": 1,
    "events_count": 1
  }
}
```

---

### 3.4 JSON 数据摄入

**端点**: `POST /api/ontology/ingest/json`

**描述**: 通过 JSON 格式摄入结构化数据。

**请求体**:

```json
{
  "json_data": "string",     // JSON 格式数据
  "scenario_id": "string"    // 场景ID（可选）
}
```

**响应体**:

```json
{
  "ingest_id": "string",
  "status": "completed",
  "source_details": {"json_length": 256},
  "original_content": "...",
  "extracted_data": {
    "source_data": [...],
    "document_ids": [...],
    "document_count": 1,
    "entities_count": 3,
    "relations_count": 2,
    "events_count": 1
  }
}
```

---

### 3.5 随机事件生成

**端点**: `POST /api/ontology/ingest/random`

**描述**: 生成随机事件数据进行摄入。

**请求体**:

```json
{
  "parties": ["string"],           // 参与方列表
  "scenario_context": {},          // 场景上下文（可选）
  "count": 1,                      // 生成数量（可选）
  "scenario_id": "string"          // 场景ID（可选）
}
```

**响应体**:

```json
{
  "ingest_id": "string",
  "status": "completed",
  "source_details": {"parties": ["蓝方", "红方"], "count": 2},
  "original_content": "...",
  "extracted_data": {
    "source_data": [...],
    "document_ids": [...],
    "document_count": 2,
    "total_entities": 4,
    "total_relations": 2,
    "total_events": 2
  }
}
```

---

## 4. 构建状态 API

### 4.1 获取构建状态

**端点**: `GET /api/ontology/ingest/builds/{build_id}`

**描述**: 获取指定构建任务的详细状态。

**路径参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| build_id | string | 是 | 构建任务 ID |

**响应体**:

```json
{
  "build_id": "string",
  "status": "completed",
  "progress": 100.0,
  "message": "本体构建完成",
  "entities_extracted": 45,
  "relations_extracted": 38,
  "nodes_created": 45,
  "edges_created": 38,
  "errors": []
}
```

---

### 4.2 获取构建历史

**端点**: `GET /api/ontology/ingest/builds`

**描述**: 获取所有构建任务的历史记录。

**查询参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| scenario_id | string | 否 | 按场景 ID 过滤 |
| limit | integer | 否 | 限制返回数量 |

**响应体**:

```json
[
  {
    "build_id": "string",
    "status": "completed",
    "progress": 100.0,
    "message": "本体构建完成",
    "entities_extracted": 45,
    "relations_extracted": 38,
    "nodes_created": 45,
    "edges_created": 38,
    "created_at": "2026-04-26T10:35:00Z"
  }
]
```

---

## 5. 本体版本管理 API

### 5.1 版本回滚

**端点**: `POST /api/ontology/ingest/versions/rollback`

**描述**: 将本体回滚到指定版本。

**请求体**:

```json
{
  "version_id": "string",         // 目标版本ID（必填）
  "scenario_id": "string"          // 场景ID（必填）
}
```

**响应体**:

```json
{
  "status": "success",
  "version_id": "v20260425-c3d4",
  "message": "已回滚到版本 v20260425-c3d4"
}
```

---

### 5.2 列出版本

**端点**: `GET /api/ontology/ingest/versions`

**描述**: 列出所有本体版本。

**查询参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| scenario_id | string | 否 | 按场景 ID 过滤 |

**响应体**:

```json
[
  {
    "version_id": "v20260426-a1b2",
    "scenario_id": "scenario-001",
    "created_at": "2026-04-26T10:35:00Z",
    "commit_message": "本体构建: 测试事件"
  }
]
```

---

## 6. 通用数据结构

### 6.1 分页响应

```json
{
  "data": [],
  "page": 1,
  "page_size": 10,
  "total": 100,
  "has_more": true
}
```

### 6.2 错误响应

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数验证失败",
    "details": [
      {
        "field": "scenario_id",
        "message": "scenario_id 不能为空"
      }
    ]
  },
  "request_id": "req-abc123"
}
```

### 6.3 状态枚举

| 状态值 | 描述 |
|--------|------|
| pending | 等待处理 |
| processing | 处理中 |
| completed | 已完成 |
| failed | 失败 |
| cancelled | 已取消 |

---

## 7. 错误码说明

| 错误码 | HTTP 状态码 | 描述 |
|--------|-------------|------|
| INVALID_PARAMETER | 400 | 请求参数无效 |
| MISSING_PARAMETER | 400 | 缺少必需参数 |
| INVALID_URL | 400 | URL 格式无效 |
| RESOURCE_NOT_FOUND | 404 | 请求的资源不存在 |
| VERSION_NOT_FOUND | 404 | 指定版本不存在 |
| TASK_NOT_FOUND | 404 | 任务不存在 |
| ONTOLOGY_BUILD_FAILED | 500 | 本体构建失败 |
| INGEST_FAILED | 500 | 数据摄入失败 |
| VERSION_ROLLBACK_FAILED | 500 | 版本回滚失败 |
| INTERNAL_ERROR | 500 | 内部服务器错误 |

---

## 8. 摄入 API 设计规范

### 8.1 规范文档

详细的摄入 API 设计规范请参阅：[INGEST_API_SPEC.md](./INGEST_API_SPEC.md)

该规范文档包含：

- **统一输入结构**：定义所有摄入方式使用相同的 `type` 和 `data` 字段
- **统一输出结构**：定义所有摄入方式返回一致的响应格式
- **source_data 字段规范**：统一的数据结构（url、title、text、description、publish_date）
- **后端实现规范**：每个方法必须包含完整的文档注释
- **前端实现规范**：统一的 API 调用方法和类型定义
- **设计优势**：统一接口带来的各方面优势

### 8.2 快速参考

**前端统一调用示例**：

```javascript
// 所有摄入方式使用相同的调用格式
const result = await api.ingest({
  type: 'manual',      // 选择摄入类型
  data: '文本内容',     // 摄入数据
  scenario_id: 'xxx'   // 场景ID（可选）
});

// 处理结果
if (result.status === 'completed') {
  const documentIds = result.extracted_data.document_ids;
  // 使用 documentIds 获取详细数据
}
```

**后端统一返回结构**：

```json
{
  "ingest_id": "abc123",
  "status": "completed",
  "source_details": {...},
  "original_content": "...",
  "extracted_data": {
    "source_data": [...],
    "document_ids": [...],
    "document_count": 1,
    "entities_count": 5,
    "relations_count": 3,
    "events_count": 2
  }
}
```

---

## 附录

### A.1 请求/响应示例完整流程

```bash
# 1. 统一数据摄入（自动触发本体构建）
curl -X POST http://localhost:8000/api/ontology/ingest \
  -H "Content-Type: application/json" \
  -d '{"data": "测试数据", "data_type": "text", "scenario_id": "scenario-001"}'
# 响应: {"ingest_id": "ingest-xxx", "status": "completed", "extracted_data": {...}}

# 2. 手动数据输入（自动触发本体构建）
curl -X POST http://localhost:8000/api/ontology/ingest/manual \
  -H "Content-Type: application/json" \
  -d '{"form_data": {"title": "测试事件", "description": "测试本体构建"}}'
# 响应: {"ingest_id": "ingest-yyy", "status": "completed", "extracted_data": {...}}

# 3. 获取构建状态
curl -X GET http://localhost:8000/api/ontology/ingest/builds/build-zzz

# 4. 获取构建历史
curl -X GET "http://localhost:8000/api/ontology/ingest/builds?scenario_id=scenario-001"

# 5. 列出版本
curl -X GET "http://localhost:8000/api/ontology/ingest/versions?scenario_id=scenario-001"

# 6. 回滚版本
curl -X POST http://localhost:8000/api/ontology/ingest/versions/rollback \
  -H "Content-Type: application/json" \
  -d '{"version_id": "v20260425-c3d4", "scenario_id": "scenario-001"}'
```

---

**文档版本历史**:

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v3.0.0 | 2026-04-26 | 添加统一摄入 API 规范引用，更新响应结构说明 |
| v2.0.0 | 2026-04-26 | 整合数据摄入与本体构建流程，添加构建状态和版本管理接口 |
| v1.0.0 | 2026-04-26 | 初始版本 |
