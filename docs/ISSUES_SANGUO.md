# 三国演义本体构建 — 平台问题追踪

> 本文档记录在构建"三国演义"本体过程中发现的**ODAP 平台问题**。
> 平台代码 vs 三国本体的边界：本文档只追踪**平台代码本身的问题**（路径错误、API 缺失、Bug、文档不一致等）。
> 三国本体的设计/数据问题在 `docs/sanguo/*.md` 中单独记录。

## 状态图例

- 🔴 Open - 待修复
- 🟡 In Progress - 修复中
- 🟢 Resolved - 已修复
- ⚪ Wontfix - 不修复（注明原因）

---

## ISSUE-001 🔴 — AGENTS.md 文档与实际 API 路径不一致

**发现时间**: 2026-06-09
**阶段**: P0 Smoke Test
**严重性**: P1（文档问题，不阻塞功能）
**发现者**: Smoke test for `/api/ontology`, `/api/skills`, `/api/qa`

### 现象

[AGENTS.md §6.3 常用验证请求](file:///e:/DEMO/AI/ontology-graphiti/AGENTS.md) 给出以下 curl 示例：

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/ontology          # 404 Not Found

curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/workspaces        # 200 OK
```

但通过 `GET /openapi.json` 探索，平台**没有** `/api/ontology` 或 `/api/skills` 这两个顶层路径，实际路径是：

| 文档声称 | 实际路径 |
|----------|----------|
| `/api/ontology` | `/api/ontology/model/entity-types`, `/api/ontology/model/instances`, `/api/ontology/oms/object-types` 等子路径 |
| `/api/skills` | `/api/skill/skills`, `/api/skill/catalog`, `/api/skill/register` （**单数**，非复数） |
| `/api/qa` | `/api/qa/ask`, `/api/qa/ask/stream`, `/api/qa/sessions` 等子路径 |

### 复现步骤

```python
import requests
r = requests.get("http://localhost:8000/api/ontology")
# 期望 200，实际 404
```

### 影响

- 新开发者按文档操作会困惑
- 不影响功能（实际路径正常工作），但与文档脱节

### 修复计划

在 P8 阶段批量更新 AGENTS.md 中的 curl 示例，使用实际路径。也可在 `/api/` 下加 alias 路由兼容老路径。

### 修复状态

- [ ] 待修复（不阻塞三国构建，先记下来）

---

## ISSUE-002 🟢 — 平台已注册 Agent tools (8 个)

**发现时间**: 2026-06-09
**阶段**: P0
**严重性**: 资讯性

### 现象

`GET /api/agent/tools` 返回 8 个工具：

| Tool | Category | 用途 |
|------|----------|------|
| query_entities | graph | 查询实体 |
| query_relations | graph | 查询关系 |
| analyze_graph | analysis | 图谱结构分析 |
| search_graph | graph | 搜索图谱 |
| get_entity_details | graph | 实体详情 |
| list_workspaces | workspace | 列出工作空间 |
| get_workspace_info | workspace | 工作空间详情 |
| create_workspace_summary | workspace | 工作空间摘要 |

### 利用方式

三国战纪智能体可以直接复用 `query_entities`、`search_graph`、`get_entity_details` 查询平台数据。**不需要重复造轮子**。

---

## ISSUE-003 🔴 — 测试发现：需要验证 scenario/ontology create 流程

**发现时间**: 2026-06-09
**阶段**: P1 待验证
**严重性**: P0（阻塞三国构建）
**发现者**: 探索性测试

### 待验证项

1. `POST /api/workspaces` 创建工作空间
2. `POST /api/workspaces/{ws_id}/scenarios` 创建场景
3. `POST /api/ontology/model/entity-types` 创建实体类型
4. `POST /api/ontology/model/instances` 创建实例
5. `POST /api/ontology/ingestion/extract` 提取事件

### 计划

在 P2 阶段编写三国数据模块时，**先写一个 init_sanguo.py** 跑通这 5 个 API 的 happy path，把任何失败/字段问题都记入本文档。

---

## ISSUE-004 🔴 — Health 端点路径异常

**发现时间**: 2026-06-09
**阶段**: P0

### 现象

`GET /health` 返回 200，但响应体**同时**包含 `openharness_v1: true` 和 `openharness_v2` 完整对象（嵌套）—— 这表明健康检查聚合了多个子系统的状态。

**这本身不是 Bug**，但意味着：后续 SanguoAgent 应注册到 OpenHarness v2 的 agent_loop，这样健康检查才能反映它。

### 备注

不是平台问题，是需要在 SanguoAgent 实现时**正确注册**到 v2 agent_loop。

---

## ISSUE-005 🟡 — OMS object-types POST 缺少 `name` 字段

**发现时间**: 2026-06-09
**阶段**: P1（API 创建流程测试）
**严重性**: P2（OMS 可选路径，不阻塞核心设计模型路径）

### 现象

调用 `POST /api/ontology/oms/object-types` 时，返回 422 错误：

```json
{"detail":[{"type":"missing","loc":["body","name"],"msg":"Field required",
"input":{"type_id":"sanguo.character", ...}}]}
```

### 复现步骤

```python
import requests
TOKEN = "..."
r = requests.post(
    "http://localhost:8000/api/ontology/oms/object-types",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "type_id": "sanguo.character",     # ← 只有 type_id
        "display_name": "三国人物",
        "description": "...",
    }
)
# 422 Unprocessable Entity: name 字段必填
```

### 根本原因

OMS 接口要求 `name` 字段（不仅是 `type_id`），与文档不一致。`/api/ontology/model/entity-types` 接口只要求 `name` + `display_name`，OMS 还需要 `name` 字段。

### 影响

- 仅影响 OMS 路径
- 设计层 (`/api/ontology/model/*`) 路径完全正常，三国构建主要走这条路

### 修复计划

- P8 阶段给 OMS schema 添加 `name` 字段或在路由层兼容
- 三国构建时**主要使用** `/api/ontology/model/entity-types` + `/api/ontology/model/instances`，OMS 仅作辅助

### 修复状态

- [x] 已记录，已规避（采用 design 层路径），P8 阶段统一处理

---

## ISSUE-006 🟢 — Scenario 自动创建 ontology

**发现时间**: 2026-06-09
**阶段**: P1
**严重性**: 资讯性（已利用）

### 现象

`POST /api/workspaces/{ws_id}/scenarios` 在创建场景的同时，**自动**创建了本体并填充 `ontology_id`、`ontology_ids`、`current_ontology_version` 字段。

返回示例：
```json
{
  "scenario_id": "scenario-20260608-161821",
  "name": "X-1",
  "ontology_id": "e856d403-7351-452d-af9c-9cd1323efdc4",
  "ontology_ids": ["e856d403-7351-452d-af9c-9cd1323efdc4"],
  "current_ontology_version": null
}
```

### 利用方式

三国构建流程可简化为：创建 scenario → 拿到 ontology_id → 在该 ontology 上 POST entity-types/instances。**不需要单独创建本体**。

---

## ISSUE-007 🟢 — 平台已具备完整 Q&A 能力（8 tools + LLM）

**发现时间**: 2026-06-09
**阶段**: P1
**严重性**: 资讯性

### 现象

`POST /api/qa/ask` 已能正常工作。`/api/skill/catalog` 显示 8 个 tools 已注册。三国智能体只需要：
1. 注入三国数据（实体/关系）
2. 注册三国特有 skills
3. 实现 SanguoAgent 调度这些 skills

不需要重写 QA 引擎或 agent loop。

---

## 待补充问题模板

```markdown
## ISSUE-NNN 🟢/🔴/🟡 — 标题

**发现时间**: YYYY-MM-DD
**阶段**: P0/P1/...
**严重性**: P0/P1/P2

### 现象
（贴日志/响应/截图）

### 复现步骤
```python
# 复现代码
```

### 影响
- 阻塞哪些功能
- 影响哪些场景

### 修复计划
（具体步骤）

### 修复状态
- [ ] 待办
```
