# API Contracts: Semantic Retrieval Service Bus

**Feature**: 008-semantic-retrieval-bus
**Date**: 2026-07-30
**Base URL**: `/api/semantic-retrieval`
**Auth**: 所有端点强制认证（`Depends(get_current_user)`），`workspace_id` 从 JWT 提取

> 与现有 `/api/reasoning/retrieve` 并存（ADR-073），不替换。本路由组是 AI Agent 和 BI 工具的统一入口。

## 通用约定

- **认证**: 所有端点 `user=Depends(get_current_user)`，`workspace_id` 取自 `user.get("workspace_id")`
- **审计**: 所有端点调用 `storage_audit(action="semantic_retrieval", details={query_type, result_count, duration_ms}, service="semantic_retrieval")`，**不记录 query 内容**（FR-013）
- **数据过滤**: 默认 `WHERE NOT (e:USL__Candidate) AND e.valid = true`；`include_simulated`/`include_candidates` 可放开（FR-011）
- **错误响应**: 统一 `{detail: str, code: str}`，HTTP 状态码遵循 FastAPI 默认
- **分页**: `page` 从 1 开始，`page_size` 默认 20、上限 100

---

## 端点总览

| 方法 | 路径 | 模式 | Phase | 说明 |
|------|------|------|-------|------|
| POST | `/query` | 统一检索 | 1 | 自动路由到最合适引擎 |
| POST | `/graph` | 分项-图检索 | 1 | 实体/关系图查询 |
| POST | `/nl` | 分项-NL检索 | 1 | 自然语言查询（USL 消歧） |
| POST | `/metric` | 分项-指标 | 1 | 聚合统计（BI） |
| POST | `/chain` | 分项-链式推理 | 2 | 多步逻辑推导 |
| POST | `/mdl` | 分项-MDL/DSL | 2 | 结构化模板推理 |
| POST | `/hybrid` | 混合检索 | 3 | 多组件编排 |

---

## Phase 1 端点

### POST /api/semantic-retrieval/query（统一检索）

自动根据输入特征选择引擎。NL 输入→nl 引擎；含聚合关键词→metric；否则→graph。

**Request**:
```json
{
  "query": "readiness 低于 0.6 的装备有哪些",
  "mode": "auto",
  "filters": {"object_type": "装备"},
  "page": 1,
  "page_size": 20
}
```

**Response** (200):
```json
{
  "request_id": "req_abc123",
  "mode": "nl",
  "entities": [
    {"entity_id": "ent_001", "object_type": "装备", "properties": {"readiness": 0.4}, "score": 0.95}
  ],
  "relations": [],
  "total": 1,
  "page": 1,
  "duration_ms": 240,
  "warnings": []
}
```

### POST /api/semantic-retrieval/graph（图检索）

直接图结构查询，适配 `QueryService.search_entities`。

**Request**:
```json
{
  "query": "部署于",
  "mode": "graph",
  "filters": {"object_type": "装备", "relation_type": "部署于"},
  "page": 1,
  "page_size": 50
}
```

**Response** (200): 同 `/query`，`entities` + `relations` 填充。

### POST /api/semantic-retrieval/nl（自然语言检索）

NL 输入 → USL `get_domain_by_term` 术语映射 → 图检索。

**Request**:
```json
{
  "query": "低 readiness 装备部署在哪些系统上",
  "mode": "nl"
}
```

**Response** (200): `entities` + `relations`（含完整路径），`warnings` 含术语映射提示（如"平台→系统"）。

### POST /api/semantic-retrieval/metric（指标查询）

聚合统计，支持 count/density/trend。

**Request**:
```json
{
  "query": "metric",
  "mode": "metric",
  "filters": {"metric_type": "trend", "target": "object_type", "target_filter": "装备", "granularity": "day"}
}
```

**Response** (200):
```json
{
  "request_id": "req_def456",
  "mode": "metric",
  "metrics": [
    {"metric_name": "装备_新增_日趋势", "value": 12, "unit": "count", "dimensions": {"date": "2026-07-29"}}
  ],
  "total": 30,
  "page": 1,
  "duration_ms": 1800,
  "warnings": []
}
```

---

## Phase 2 端点

### POST /api/semantic-retrieval/chain（链式推理）

适配 `DeductionEngine.simulate_chain`，新增循环检测层。

**Request**:
```json
{
  "query": "装备A 间接依赖的所有平台",
  "mode": "chain",
  "filters": {"rules": ["部署于→依赖→传导"], "max_depth": 5}
}
```

**Response** (200):
```json
{
  "request_id": "req_ghi789",
  "mode": "chain",
  "reasoning": {
    "chain_id": "chain_001",
    "steps": [
      {"step_id": "s1", "rule_id": "部署于", "input": "装备A", "output": "系统B", "duration_ms": 50}
    ],
    "conclusion": "装备A 间接依赖平台C",
    "confidence": 0.85,
    "cycle_detected": false,
    "conflicts": []
  },
  "total": 1,
  "page": 1,
  "duration_ms": 320,
  "warnings": []
}
```

**循环检测响应** (200, `warnings` 含循环信息):
```json
{
  "reasoning": {
    "cycle_detected": true,
    "cycle_path": ["A", "B", "C", "A"]
  },
  "warnings": ["检测到循环依赖 A→B→C→A，推理已中止"]
}
```

### POST /api/semantic-retrieval/mdl（MDL/DSL 推理）

复用 HE YAML 模板语法。

**Request**:
```json
{
  "query": "template: risk_propagation\nentity: 装备A\nparams: {threshold: 0.6}",
  "mode": "mdl"
}
```

**Response** (200): 同 `/chain` 结构。

---

## Phase 3 端点

### POST /api/semantic-retrieval/hybrid（混合检索）

编排多组件，适配 `PipelineService`。

**Request**:
```json
{
  "components": [
    {"type": "graph", "params": {"query": "部署于", "filters": {"object_type": "装备"}}, "on_failure": "abort"},
    {"type": "chain", "params": {"query": "风险传导", "filters": {"max_depth": 3}}, "on_failure": "skip"},
    {"type": "metric", "params": {"filters": {"metric_type": "count", "target": "object_type"}}, "on_failure": "degrade"}
  ]
}
```

**Response** (200):
```json
{
  "request_id": "req_jkl012",
  "mode": "hybrid",
  "entities": [...],
  "relations": [...],
  "metrics": [...],
  "total": 42,
  "page": 1,
  "duration_ms": 4500,
  "warnings": ["组件 chain 执行失败，已跳过"]
}
```

---

## MCP 工具契约（Phase 3）

注册到现有 MCP Server（ADR-026 bridge），供 OpenHarness 等 Agent 框架调用。

| 工具名 | 映射端点 | input_schema 关键字段 |
|--------|---------|----------------------|
| `ontology_query` | POST /query | `query: str`, `filters?: dict` |
| `ontology_reason` | POST /chain | `query: str`, `rules?: list[str]`, `max_depth?: int` |
| `ontology_metric` | POST /metric | `metric_type: str`, `target: str`, `granularity?: str` |

MCP 调用结果与直接 REST API 调用完全一致（FR-010）。

---

## 错误码

| HTTP | code | 场景 |
|------|------|------|
| 401 | `UNAUTHORIZED` | 缺失/无效 token |
| 403 | `WORKSPACE_FORBIDDEN` | 跨 workspace 访问（FR-012） |
| 422 | `VALIDATION_ERROR` | 请求参数校验失败 |
| 400 | `EMPTY_ONTOLOGY` | 本体无数据（返回空结果而非错误，仅当查询语法错误时 400） |
| 500 | `RETRIEVAL_FAILED` | 引擎内部错误 |

**注**: 本体无数据时返回 200 + 空结果集（edge case），不返回错误。

## 安全约束

- 所有端点 `Depends(get_current_user)`，禁止改为可选认证（项目硬约束）
- `workspace_id` 仅从 JWT 提取，拒绝请求体传入（FR-012）
- 审计 `details` 禁止包含 `query` 字段（FR-013）
- `page_size` 上限 100，防 DoS
- 链式推理 `max_depth` 上限 10，防无限递归（FR-014 循环防护）
