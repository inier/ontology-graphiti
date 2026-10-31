---
id: odap.l9.api-contract-matrix
status: active
owner: qa
version: ''
layer: L9
concern: api-contract-matrix
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 三向对账矩阵的人读形态，由 scripts/check_api_contract.py 生成
---

# API 契约对账矩阵（F13）

- 对账范围：`/api/v1`；后端路由来源：`live`；共 19 条路径。
- 结论：BLOCKING 0 / WARN 0 / INFO 12 / OK 7
- 口径：前端=源码中的 API 路径字面量；契约=openapi-v2.yaml；后端=实际路由表。

## 阻断级偏差（必须处理）

无。

## 需登记/对齐

无。

## 后端已就绪待前端接入

| 方法(契约) | 方法(后端) | 路径 | 前端 | 契约 | 后端 | 参数(契约/后端) | 处理 |
|---|---|---|---|---|---|---|---|
| GET | GET | `/api/v1/docs/governance/documents` | N | Y | Y | - / - | 前端尚未接入（本轮可不处理） |
| GET | GET | `/api/v1/docs/governance/documents/{}` | N | Y | Y | doc_id / doc_id | 前端尚未接入（本轮可不处理） |
| POST | POST | `/api/v1/docs/governance/documents/{}/supersede` | N | Y | Y | doc_id / doc_id | 前端尚未接入（本轮可不处理） |
| POST | POST | `/api/v1/monitoring/performance/reset` | N | Y | Y | - / - | 前端尚未接入（本轮可不处理） |
| POST | POST | `/api/v1/ontology/qa` | N | Y | Y | - / - | 前端尚未接入（本轮可不处理） |
| POST | POST | `/api/v1/ontology/qa/actions/{}/approve` | N | Y | Y | action_id / action_id | 前端尚未接入（本轮可不处理） |
| POST | POST | `/api/v1/ontology/qa/actions/{}/execute` | N | Y | Y | action_id / action_id | 前端尚未接入（本轮可不处理） |
| GET | GET | `/api/v1/ontology/qa/{}/actions` | N | Y | Y | trace_id / trace_id | 前端尚未接入（本轮可不处理） |
| GET | GET | `/api/v1/ontology/qa/{}/provenance` | N | Y | Y | trace_id / trace_id | 前端尚未接入（本轮可不处理） |
| POST | POST | `/api/v1/wiki/entries/{}/publish` | N | Y | Y | entry_id / entry_id | 前端尚未接入（本轮可不处理） |
| POST | POST | `/api/v1/wiki/sync/export` | N | Y | Y | - / - | 前端尚未接入（本轮可不处理） |
| POST | POST | `/api/v1/wiki/sync/import` | N | Y | Y | - / - | 前端尚未接入（本轮可不处理） |
