# 图谱实体软删除（invalid_at）设计 — #13a

- **状态**：待复审
- **日期**：2026-09-28
- **范围**：#13a 核心软删除能力 + executor / execution_tool 接通
- **关联**：#13b（批次删除回滚链，独立 spec，依赖本设计的软删能力）
- **规则约束**：AGENTS.md 规则 2（服务层返回 `{"status","message"}` dict）、规则 6（routes→services→impl→storage）、规则 12（架构级决策需 ADR + 文档同步）、规则 14（失败显式、兜底可观测、禁止幻影调用/hasattr 探测式降级、测试必须执行真实函数体）

---

## 1. 背景与问题

ODAP 是基于 Graphiti 的双时态知识图谱平台。当前**图谱实体删除能力在全栈所有层均为零**：

- `GraphManager`（`apps/api/odap/infra/graph/`）无任何实体级删除方法；唯一硬删是全量 `clear_graph()` 的 `MATCH (n) DETACH DELETE n`（`graph_service.py:1060`）。
- `GraphWriteProxy.delete_entity`（`apps/api/odap/infra/query/graph_write_proxy.py:129-162`）是显式报错占位，恒返回 `status="error"`。
- `delete_by_batch` 从未存在。
- `get_raw_graph_manager`（同文件 `:327-341`）是 `raise NotImplementedError` 墓碑（有意保留，禁止业务绕审计拿裸 GraphManager）。
- 软删除基础设施缺失：双时态只有**读侧**（`query_temporal`/`state_at`），写侧不打任何失效时间戳；节点当前**零时间戳属性**。

三处调用方已按规则 14 改为“显式失败”，注释一致写明“删除语义待决策”：

1. `biz/decision/action_service/executor.py:536-548` — delete/remove 动作调 `self.graph.delete_entity(target_id)`，因 proxy 恒 error 必然 `success=False`。
2. `biz/core/ontology/construction/rollback/rollback_manager.py:56-79` — `BatchDeleteUndo.undo()` 显式返回 failed（归 #13b）。
3. `biz/core/ontology/application/chat/tools/execution_tool.py:216-235` — `delete_entity` 分支返回 `{"status":"unsupported"}`。

本设计决策并实现删除语义，打通行动闭环删除路径（executor + execution_tool），批次回滚留待 #13b。

## 2. 已锁定决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 删除语义 | **软删除为默认**（打 `invalid_at` 失效，保留双时态历史），不开放硬删业务通道 | 对齐双时态 KG 与 Graphiti 定位；硬删摧毁历史不可逆 |
| 级联策略 | **同步失效其全部关系**（边打 `invalid_at`） | 保持图一致，无悬空边；对齐 graphiti 边级原生 `invalid_at` |
| 接入范围 | executor(delete/remove) + execution_tool(delete_entity) 本次一起接通 | 一次性打通行动闭环删除路径 |
| 标记机制 | 节点 `invalid_at` **时间戳属性**（非 `:Deleted` 标签） | 保留失效时刻，支持 `state_at` as-of 正确回溯 |
| 范围拆分 | #13a 核心软删 / #13b 批次回滚 分两个 spec | 批次回滚链是另一条独立断链，耦合低 |

## 3. 关键事实（决定实现方式）

- **读侧完全不过滤失效实体**：~10 处 Neo4j 读路径 + 5 处 fallback 读路径 + `query_temporal`/`state_at` 全部照旧返回失效节点。软删除要生效**必须逐条给读路径加过滤**，无统一收敛点。
- **graphiti 的 `valid_at/invalid_at/expired_at` 原生在 EntityEdge 上**（`graphiti_core/edges.py:263-285`），EntityNode 只有 `created_at`。节点级 `invalid_at` 是**应用层自定约定**，与边级同名不同物，代码注释需明确区分。
- **本层既有时态约定是 `valid_time`/`transaction_time`**（`cache_mixin.py:62-64`），且 infra/graph 内无人写入。本次不改动这套约定，仅新增 `invalid_at`；二者关系在实现注释中标注。
- **写侧属性类型不一致**：`add_entity` 走 `_sanitize_neo4j_properties` 会把 datetime 转 ISO 字符串且丢弃 `None`（`graph_service.py:966-991`）；`update_entity` 不清洗，datetime 以 Neo4j 原生 temporal 落库（`entity_ops.py:373-389`）。→ **`invalid_at` 统一存 ISO-8601 字符串**，规避类型分裂。
- **缓存**：`invalidate_cache()`（`cache_mixin.py:46-50`）清 `_query_cache` + `_temporal_index`。当前 add/update/clear 后**无人调用**，`query_entities`/`query_temporal` 有 300s TTL。→ 软删除写后**必须显式调 `invalidate_cache()`**，否则最长 5 分钟仍返回失效实体。（add/update 的既有缓存 bug 不在本次范围。）
- **审计断点**：`GraphWriteProxy._log_write`（`graph_write_proxy.py:54-61`）只是 `logger.info`，不接 `unified_audit`；GraphManager 层的 `clear_graph`/`update_entity` 走 `graph_audit`→`unified_audit.log_audit`。→ 软删除的结构化审计在 **GraphManager 层用 `graph_audit`**（与既有写操作一致）。

## 4. 设计

### 4.1 标记约定

- 节点：`invalid_at: str`（ISO-8601 UTC，如 `2026-09-28T10:00:00+00:00`）。缺失或空 = 活跃；非空 = 已软删（在该时刻失效）。
- 关系（边）：同名 `invalid_at: str`。级联失效时对所有关联边打标（仅对 `invalid_at` 为空的边写，幂等）。
- 判定“活跃”的唯一谓词：`invalid_at IS NULL`（Neo4j）/ `not props.get("invalid_at")`（Python/fallback）。

### 4.2 共享过滤工具（方案 B）

新建 `apps/api/odap/infra/graph/_soft_delete.py`（模块内私有），提供单一真源：

```python
ACTIVE_NODE_PREDICATE = "n.invalid_at IS NULL"      # 用于 Cypher WHERE 组合
ACTIVE_REL_PREDICATE = "r.invalid_at IS NULL"

def is_active(props: dict) -> bool:
    """节点/边属性 dict 是否未被软删（invalid_at 缺失或空）。"""
    return not (props or {}).get("invalid_at")

def now_iso() -> str:
    """统一失效时间戳：ISO-8601 UTC 字符串。"""
```

各读路径引用该常量/helper，语义将来只改一处。

### 4.3 GraphManager 新增软删除方法

在 `entity_ops.py`（EntityOpsMixin）新增：

```python
def delete_entity(
    self, entity_id: str, workspace_id: str = "",
    cascade: bool = True, actor: str = "",
) -> Dict[str, Any]:
    """软删除实体：打 invalid_at 失效，保留双时态历史。

    - 节点不存在 → {"status": "error", "message": "entity not found: <id>"}
    - 已失效 → 幂等 success no-op（relations_invalidated=0）
    - cascade=True → 同步对所有关联边打 invalid_at
    - 写后 invalidate_cache()；经 graph_audit 落结构化审计
    返回：{"status":"success","entity_id":...,"entities_invalidated":int,
           "relations_invalidated":int,"invalid_at":<iso>}
    """
```

实现要点：
- **Neo4j 模式**：
  - `MATCH (n:Entity {id:$eid}) SET n.invalid_at=$ts`（若传 `workspace_id` 则加 `AND n.workspace_id=$ws` 做隔离校验；不匹配视为 not found）。
  - cascade：`MATCH (n:Entity {id:$eid})-[r]-() WHERE r.invalid_at IS NULL SET r.invalid_at=$ts`，用 `count()` 取失效边数。
  - 先探测节点是否存在（`MATCH ... RETURN count(n)`）以区分 not_found / 幂等 no-op。
- **Fallback 模式**（`_test_mode`，`nx.DiGraph`）：写 `self.fallback_graph.nodes[eid]["invalid_at"]=ts`；cascade 遍历 `edges(eid)` 写边属性。
- 写后调 `self.invalidate_cache()`。
- 经 `graph_audit(op="delete_entity", ...)` 落审计（含 entity_id、workspace_id、relations_invalidated、actor）。
- 失败显式：driver 不可用 / 异常 → 返回 `{"status":"error","message":...}`（规则 2/14），不静默。

> `delete_by_batch` **不在本 spec**（#13b）。

### 4.4 读路径过滤（方案 B，逐点插入 `ACTIVE_NODE_PREDICATE`）

**Neo4j（~10 处）**，统一在 WHERE 加 `AND n.invalid_at IS NULL`（或对起点/终点分别加）：
- `_get_entity_neo4j`（`entity_ops.py:469`）— 默认排除；新增 `include_deleted: bool=False` opt-in。
- `_query_entities_neo4j`（`entity_ops.py:267`）
- `_search_neo4j`（`search_ops.py:68`）、`_search_neo4j_keyword`（`search_ops.py:128`）、`search_hybrid` 关键词分支（`search_ops.py:230/241`）
- `_retrieve_rag_neo4j`（`search_ops.py:403`）
- `_get_neighbors_neo4j`（`search_ops.py:498`）— 排除失效**点与边**
- `_traverse_neo4j`（`search_ops.py:614/620`）— 排除失效**点与边**
- `_get_all_relations_neo4j`（`relationship_ops.py:174/180`）— 排除失效**边**
- 统计（`graph_service.py:843`）— count 仅活跃节点

**Fallback（5 处）**，用 `is_active(data)` skip：
- `_get_entity_fallback`、`_query_entities_fallback`（`entity_ops.py`）
- `_search_fallback`、`_get_neighbors_fallback`、`_traverse_fallback`（`search_ops.py`）
- fallback 版 `get_all_relations` 同样排除失效边。

**Graphiti 向量检索分支**（`search_hybrid`/`_search_graphiti` 调 `self.graph.search(...)`，返回 EntityEdge fact）：与节点级软删不同层面；本次**不改**，但在 spec 标注为已知边界（软删节点后，历史 episode/edge 向量检索仍可能命中其 fact，属双时态“事实曾成立”语义，非缺陷）。

### 4.5 时态正确性

- `_build_temporal_index`（`cache_mixin.py:52-81`）：索引项带出 `invalid_at`。
- `query_temporal` 索引分支（`temporal_ops.py:74-87`）：在**既有** `valid_time <= vt` 下界基础上，追加 `invalid_at` 上界——仅当 `invalid_at IS NULL OR invalid_at > vt_str` 才纳入，使 `state_at(vt)` 不把在 `vt` 之后才失效的实体错误计入/漏计。语义：`state_at(vt)` 返回“在 vt 时刻仍有效”的实体（`valid_time <= vt < invalid_at`）。
- 该上界过滤是**对现有索引机制的纯增量**：不改变“节点须有 `valid_time` 才进时态索引”的既有前提（`cache_mixin.py:62-64`，默认无 `valid_time` 的节点本就不在索引内、走 Graphiti episode 分支）。本设计不引入 `valid_time` 写入，仅确保**已进入索引**的节点在失效后不再被 as-of 查询计入。

### 4.6 调用方接通

- **GraphWriteProxy.delete_entity**（`graph_write_proxy.py:129-162`）：去掉墓碑 error-return，改为：
  ```python
  gm = self._get_graph_manager()
  if gm is None:
      return {"status": "error", "message": "GraphManager unavailable"}
  result = gm.delete_entity(entity_id, workspace_id=workspace_id, actor=...)
  self._log_write("delete_entity", workspace_id=workspace_id,
                  entity_id=entity_id, success=result.get("status") == "success")
  return result   # 透传 GraphManager 的 {"status",...}（规则 2）
  ```
  保留 `_log_write` 文本日志；结构化审计由 GraphManager 层 `graph_audit` 负责（避免双层重复审计）。
- **executor**（`action_service/executor.py:536-548`）：delete/remove 分支代码**不变**——proxy 转真实成功后，`_write_failure` 自然返回 None，`success=True`。既有 `test_delete_failure_reports_not_deleted` 仍守护“proxy 报 error 时不得假成功”。
- **execution_tool**（`chat/tools/execution_tool.py:216-235`）：`delete_entity` 分支从返回 `unsupported` 改为经 **GraphWriteProxy** 调软删（合规 + 审计），透传结果。execution_tool 的 add/update 仍用裸 `GraphManager`（`:162-165`）是**独立问题，本次不动**，仅标注（潜在归 #23）。

### 4.7 权限

- `query_guard_hook.WRITE_TOOLS` 已含 `delete_entity`（OPA fail-closed，`:6-14`），但该工具未在 `QueryServiceToolRegistry` 注册（`:134-158`）。
- executor 的 delete 动作已有 OPA 校验（`test_action_service` OPA fail-closed 用 `action_type_id="delete"`）。
- 本次**不新注册** delete 工具到 QueryServiceToolRegistry（execution_tool 走 proxy 已获审计）；OPA 删除工具注册标注为范围外。

## 5. 接口契约（供 #13b 与实现引用）

- `GraphManager.delete_entity(entity_id, workspace_id="", cascade=True, actor="") -> Dict[str,Any]`
  - 成功：`{"status":"success","entity_id":str,"entities_invalidated":int,"relations_invalidated":int,"invalid_at":str}`
  - 失败：`{"status":"error","message":str}`
- `GraphWriteProxy.delete_entity(entity_id, workspace_id="") -> Dict[str,Any]`（签名不变，语义由恒 error 转为透传真实结果）
- `_soft_delete.ACTIVE_NODE_PREDICATE / ACTIVE_REL_PREDICATE / is_active(props) / now_iso()`

## 6. 错误处理（规则 2 / 14）

- GraphManager / Proxy 层一律返回 `{"status":"error","message":...}`，不抛 HTTPException。
- not_found、driver 不可用、Cypher 异常均显式 error，不静默降级、不 hasattr 探测、不假成功。
- 幂等：对已失效实体再次删除 = success no-op（`relations_invalidated=0`），非 error。

## 7. 测试策略（TDD，规则 14 #6：≥1 条走真实函数体）

- **GraphManager fallback 模式（真实 `_test_mode=True`，非 mock SUT）**：
  - `delete_entity` 打 `invalid_at`；cascade 失效全部关联边；幂等 no-op；not_found→error。
  - 软删后 `get_entity`（默认）/`query_entities`/`search`/`get_neighbors`/`traverse`/`get_all_relations` 均排除；`get_entity(include_deleted=True)` 仍可见。
  - `state_at(vt)`：失效时刻之前可见、之后不可见。
  - 软删后 `invalidate_cache()` 生效（`query_entities` 不返回旧缓存）。
- **GraphManager Neo4j 模式（mock driver）**：断言 SET `invalid_at` 的 Cypher、cascade 边 Cypher、各读路径 Cypher 含 `invalid_at IS NULL` 谓词。
- **GraphWriteProxy**：`delete_entity` 调 `gm.delete_entity` 并透传 status；`_log_write("delete_entity", ...)` 被调；gm 不可用→error。（改写现有 `TestDeleteEntity`：从“断言恒 error/unsupported”改为“断言真实软删透传”。）
- **端到端真实链路（≥1 条，不 mock SUT）**：executor delete 动作 → 真实 GraphWriteProxy → fallback GraphManager，断言实体被软删且 `success=True`。
- **execution_tool**：`delete_entity` 分支走 proxy 返回 success。
- **回归**：现有 `test_graph_write_proxy.py` / `test_action_service.py` 全绿（按新语义调整断言，不删守护“失败显式”的用例）。

## 8. 范围外（明确不做）

- `delete_by_batch` / batch_id 生产链 / `rollback_manager._get_completed_steps` 的 `get_context` dataclass-vs-dict 缺陷 → **#13b**。
- add/update/clear_graph 后不调 `invalidate_cache()` 的既有缓存 bug。
- execution_tool 的 add/update 走裸 GraphManager（绕 proxy/审计）。
- OPA delete 工具注册到 QueryServiceToolRegistry。
- Graphiti 向量检索（EntityEdge fact 层）的软删联动。
- 硬删除业务通道。

## 9. 文档同步（规则 12）

实现阶段需：
- 新建 **ADR**（`docs/07-adr/`）：记录“图谱实体软删除语义 = invalid_at 失效 + 级联边失效 + 读侧过滤”的架构决策，更新 `docs/07-adr/README.md` 索引。
- 更新 `docs/03-modules/` 下 graph / decision(action_service) 相关 DESIGN.md 的删除语义与接口。
- 若涉及 API 行为变化，更新 `agents.md` 对应章节。

## 10. 风险

| 风险 | 缓解 |
|------|------|
| 改 ~15 处读路径引入 QA/检索回归 | 共享谓词单一真源；每处改动配 fallback 真实测试；全量离线回归 |
| `invalid_at` 字符串 vs datetime 类型分裂 | 统一 ISO 字符串；`now_iso()` 单点产出 |
| 缓存导致软删不即时 | delete_entity 内显式 invalidate_cache + 专项测试 |
| 边级 `invalid_at` 与 graphiti 原生边字段语义混淆 | 注释区分“应用节点级约定” vs “graphiti 边级原生”；本设计只在应用写的 RELATES_TO 边上打标 |
| 双时态 as-of 语义理解偏差 | `state_at` 明确定义为 `valid_time <= vt < invalid_at`，配时态测试 |
