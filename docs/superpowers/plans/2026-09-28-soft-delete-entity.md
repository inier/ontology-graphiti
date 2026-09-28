# 图谱实体软删除（invalid_at）实现计划 — #13a

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ODAP 图谱层实现"软删除"能力——给节点与关联边打 `invalid_at` 失效时间戳并保留双时态历史，同时把全部读路径改为默认排除失效实体，最后接通 `GraphWriteProxy` 与 `execution_tool` 两个删除调用方。

**Architecture:** 新增模块内私有的共享谓词真源 `_soft_delete.py`（Cypher 谓词常量 + `is_active` + `now_iso`）。在 `EntityOpsMixin` 新增 `delete_entity`（fallback NetworkX 与 Neo4j 双实现，级联失效边、写后 `invalidate_cache()`、经 `graph_audit` 落审计）。~15 处读路径逐点插入"仅活跃"过滤。时态索引带出 `invalid_at` 并在 `query_temporal` 增加失效上界。`GraphWriteProxy.delete_entity` 由恒 error 墓碑改为透传真实软删结果。

**Tech Stack:** Python 3.10+ · NetworkX（fallback）· Neo4j Driver（生产）· pytest · `odap.infra.graph`（GraphManager mixin 架构）· `odap.infra.query.graph_write_proxy`。

**Spec:** `docs/superpowers/specs/2026-09-28-soft-delete-entity-design.md`（本计划的权威依据；实现与 spec 冲突时以 spec 为准）。

## Global Constraints

- **语言**：所有代码注释、commit message、面向用户的输出一律简体中文。
- **规则 2**：GraphManager / GraphWriteProxy 层失败一律返回 `{"status": "error", "message": "..."}` dict，**禁止**抛 HTTPException。
- **规则 14**：失败必须显式；禁止 `except: pass`、禁止 `hasattr` 探测式降级、禁止幻影调用、禁止无视被调方 error 状态；**测试必须执行真实函数体**——每个新增/改写的方法至少有 1 条测试走真实实现（fallback 模式），只允许在存储边界（Neo4j driver）打桩，禁止 patch 被测方法本身。
- **规则 9**：新增测试文件放 `apps/api/tests/unit/`；fallback GraphManager 用真实 `_test_mode=True` 构造，禁止 MagicMock 冒充 SUT。
- **规则 12**：架构级决策需新建 ADR 到 `docs/07-adr/` 并更新 `docs/07-adr/README.md` 索引；同步更新相关模块 DESIGN.md。
- **标记约定**：节点与边统一用 `invalid_at: str`（ISO-8601 UTC，如 `2026-09-28T10:00:00+00:00`）；缺失或空 = 活跃，非空 = 已软删。唯一活跃谓词：Neo4j `invalid_at IS NULL` / Python `not props.get("invalid_at")`。
- **离线 pytest 命令**（从仓库根 `E:\DEMO\AI\ontology-graphiti` 执行，否则联网挂起）：
  `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest <target> -q --no-header -p no:cacheprovider`
- **提交规范**：每个 Task 末尾一次原子提交，格式 `<type>(<scope>): <subject>` + bullet body；由用户执行 commit（"最后你来"），本计划中的 `git commit` 步骤为提交内容与 message 的说明，实施时精确 `git add <文件名>`（禁止 `git add -A`）。

## fallback GraphManager 测试构造惯用法（全计划复用）

所有需要真实 fallback GraphManager 的测试，用如下 fixture（源自 `tests/unit/test_edge_cases.py:197-212` 与 `test_audit_episode_save.py:20-26`）：

```python
import networkx as nx
import pytest
from unittest.mock import patch
from odap.infra.graph.graph_service import GraphManager


@pytest.fixture
def fb_gm():
    """真实 fallback 模式 GraphManager（空图，非 mock SUT）。"""
    with patch.object(GraphManager, "_connect"):
        gm = GraphManager.__new__(GraphManager)
        gm._test_mode = True
        gm._connected = False
        gm._use_fallback = True
        gm._mode = "fallback"
        gm.graph = None
        gm.neo4j_driver = None
        gm.fallback_graph = nx.DiGraph()
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        gm._temporal_index = {}
        gm._temporal_index_built = False
        yield gm
```

> 说明：`GraphManager.__new__` 绕开单例 `__init__`（不触发 `_connect` 联网）；`fallback_graph = nx.DiGraph()` 是干净空图，不含 `_load_data_to_fallback` 的模拟数据。

---

## Task 1: 共享软删工具 `_soft_delete.py`

**Files:**
- Create: `apps/api/odap/infra/graph/_soft_delete.py`
- Test: `apps/api/tests/unit/test_soft_delete.py`

**Interfaces:**
- Produces:
  - `ACTIVE_NODE_PREDICATE: str == "n.invalid_at IS NULL"`
  - `ACTIVE_REL_PREDICATE: str == "r.invalid_at IS NULL"`
  - `is_active(props: dict | None) -> bool`
  - `now_iso() -> str`（ISO-8601 UTC，含 `+00:00`）

- [ ] **Step 1: 写失败测试**

`apps/api/tests/unit/test_soft_delete.py`:

```python
"""_soft_delete 共享软删工具单元测试。"""
from odap.infra.graph import _soft_delete as sd


def test_active_predicates_are_stable_strings():
    assert sd.ACTIVE_NODE_PREDICATE == "n.invalid_at IS NULL"
    assert sd.ACTIVE_REL_PREDICATE == "r.invalid_at IS NULL"


def test_is_active_true_when_missing_or_empty():
    assert sd.is_active({}) is True
    assert sd.is_active(None) is True
    assert sd.is_active({"invalid_at": ""}) is True
    assert sd.is_active({"invalid_at": None}) is True


def test_is_active_false_when_marked():
    assert sd.is_active({"invalid_at": "2026-09-28T10:00:00+00:00"}) is False


def test_now_iso_is_utc_offset_string():
    ts = sd.now_iso()
    assert isinstance(ts, str)
    assert ts.endswith("+00:00")
    # 可被 datetime 解析
    from datetime import datetime
    datetime.fromisoformat(ts)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_soft_delete.py -q --no-header -p no:cacheprovider`
Expected: FAIL（`ModuleNotFoundError: No module named 'odap.infra.graph._soft_delete'`）

- [ ] **Step 3: 写最小实现**

`apps/api/odap/infra/graph/_soft_delete.py`:

```python
"""图谱软删除共享工具（模块内私有单一真源）。

约定：节点与边统一用 invalid_at（ISO-8601 UTC 字符串）标记失效时刻。
缺失或空 = 活跃；非空 = 已软删。

注意区分：graphiti 原生的 valid_at/invalid_at/expired_at 在 EntityEdge 上，
本模块的 invalid_at 是应用层对 EntityNode 与关系边的自定约定，同名不同物。
"""
from datetime import datetime, timezone

# 用于 Cypher WHERE 组合的活跃谓词（读路径逐点引用，语义只改此处）
ACTIVE_NODE_PREDICATE = "n.invalid_at IS NULL"
ACTIVE_REL_PREDICATE = "r.invalid_at IS NULL"


def is_active(props: dict | None) -> bool:
    """节点/边属性 dict 是否未被软删（invalid_at 缺失或空）。"""
    return not (props or {}).get("invalid_at")


def now_iso() -> str:
    """统一失效时间戳：ISO-8601 UTC 字符串（含 +00:00）。"""
    return datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_soft_delete.py -q --no-header -p no:cacheprovider`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add apps/api/odap/infra/graph/_soft_delete.py apps/api/tests/unit/test_soft_delete.py
git commit -m "feat(graph): 新增软删除共享谓词工具 _soft_delete

- ACTIVE_NODE_PREDICATE / ACTIVE_REL_PREDICATE Cypher 活跃谓词常量
- is_active(props) / now_iso() 单一真源，读路径与写路径共用"
```

---

## Task 2: `GraphManager.delete_entity`（fallback + Neo4j）

**Files:**
- Modify: `apps/api/odap/infra/graph/entity_ops.py`（在 `EntityOpsMixin` 内新增方法）
- Test: `apps/api/tests/unit/test_graph_delete_entity.py`

**Interfaces:**
- Consumes: `_soft_delete.now_iso / is_active`（Task 1）；`self.invalidate_cache()`（`cache_mixin.py:46`）；`graph_audit`（`entity_ops.py:13` 已导入）。
- Produces: `GraphManager.delete_entity(entity_id: str, workspace_id: str = "", cascade: bool = True, actor: str = "") -> Dict[str, Any]`
  - 成功：`{"status":"success","entity_id":str,"entities_invalidated":int,"relations_invalidated":int,"invalid_at":str}`
  - 失败：`{"status":"error","message":str}`

- [ ] **Step 1: 写失败测试（fallback 真实函数体）**

`apps/api/tests/unit/test_graph_delete_entity.py`:

```python
"""GraphManager.delete_entity 软删除单元测试。

fallback 分支走真实函数体（规则 14 #6）；Neo4j 分支用 mock driver 断言 Cypher。
"""
import networkx as nx
import pytest
from unittest.mock import patch, MagicMock
from odap.infra.graph.graph_service import GraphManager


@pytest.fixture
def fb_gm():
    with patch.object(GraphManager, "_connect"):
        gm = GraphManager.__new__(GraphManager)
        gm._test_mode = True
        gm._connected = False
        gm._use_fallback = True
        gm._mode = "fallback"
        gm.graph = None
        gm.neo4j_driver = None
        gm.fallback_graph = nx.DiGraph()
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        gm._temporal_index = {}
        gm._temporal_index_built = False
        yield gm


def _seed(gm):
    gm.fallback_graph.add_node("e1", entity_type="Agent", name="A")
    gm.fallback_graph.add_node("e2", entity_type="Agent", name="B")
    gm.fallback_graph.add_edge("e1", "e2", relationship="DEPENDS_ON")


class TestDeleteEntityFallback:
    def test_marks_invalid_at(self, fb_gm):
        _seed(fb_gm)
        result = fb_gm.delete_entity("e1")
        assert result["status"] == "success"
        assert result["entity_id"] == "e1"
        assert result["entities_invalidated"] == 1
        assert fb_gm.fallback_graph.nodes["e1"]["invalid_at"] == result["invalid_at"]

    def test_cascade_invalidates_edges(self, fb_gm):
        _seed(fb_gm)
        result = fb_gm.delete_entity("e1", cascade=True)
        assert result["relations_invalidated"] == 1
        assert fb_gm.fallback_graph.edges["e1", "e2"]["invalid_at"] == result["invalid_at"]

    def test_no_cascade_leaves_edges_active(self, fb_gm):
        _seed(fb_gm)
        result = fb_gm.delete_entity("e1", cascade=False)
        assert result["relations_invalidated"] == 0
        assert "invalid_at" not in fb_gm.fallback_graph.edges["e1", "e2"]

    def test_not_found_returns_error(self, fb_gm):
        _seed(fb_gm)
        result = fb_gm.delete_entity("nope")
        assert result["status"] == "error"
        assert "nope" in result["message"]

    def test_idempotent_second_delete_is_noop(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1")
        second = fb_gm.delete_entity("e1")
        assert second["status"] == "success"
        assert second["entities_invalidated"] == 0
        assert second["relations_invalidated"] == 0

    def test_workspace_mismatch_returns_error(self, fb_gm):
        fb_gm.fallback_graph.add_node("e1", entity_type="Agent", workspace_id="ws1")
        result = fb_gm.delete_entity("e1", workspace_id="ws2")
        assert result["status"] == "error"

    def test_invalidates_query_cache(self, fb_gm):
        _seed(fb_gm)
        fb_gm._query_cache["stale"] = [{"id": "e1"}]
        fb_gm._query_cache_timestamps["stale"] = 1.0
        fb_gm.delete_entity("e1")
        assert fb_gm._query_cache == {}


class TestDeleteEntityNeo4j:
    def _neo4j_gm(self):
        with patch.object(GraphManager, "_connect"):
            gm = GraphManager.__new__(GraphManager)
            gm._test_mode = False
            gm._connected = True
            gm._use_fallback = False
            gm._mode = "neo4j_driver"
            gm.graph = None
            gm.fallback_graph = None
            gm._query_cache = {}
            gm._query_cache_timestamps = {}
            gm._temporal_index = {}
            gm._temporal_index_built = False
            gm.neo4j_driver = MagicMock()
            return gm

    def test_sets_invalid_at_cypher(self):
        gm = self._neo4j_gm()
        session = MagicMock()
        gm.neo4j_driver.session.return_value.__enter__.return_value = session
        # 探测存在 -> count=1；SET 节点；cascade 边 count=2
        session.run.side_effect = [
            MagicMock(single=lambda: {"cnt": 1}),   # 存在性探测
            MagicMock(),                            # SET 节点
            MagicMock(single=lambda: {"invalidated": 2}),  # cascade 边计数
        ]
        result = gm.delete_entity("e1")
        assert result["status"] == "success"
        assert result["relations_invalidated"] == 2
        cyphers = " ".join(str(c.args[0]) for c in session.run.call_args_list)
        assert "invalid_at" in cyphers

    def test_not_found_when_count_zero(self):
        gm = self._neo4j_gm()
        session = MagicMock()
        gm.neo4j_driver.session.return_value.__enter__.return_value = session
        session.run.return_value.single.return_value = {"cnt": 0}
        result = gm.delete_entity("e1")
        assert result["status"] == "error"

    def test_driver_exception_returns_error(self):
        gm = self._neo4j_gm()
        gm.neo4j_driver.session.side_effect = RuntimeError("boom")
        result = gm.delete_entity("e1")
        assert result["status"] == "error"
        assert "boom" in result["message"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_delete_entity.py -q --no-header -p no:cacheprovider`
Expected: FAIL（`AttributeError: 'GraphManager' object has no attribute 'delete_entity'`）

- [ ] **Step 3: 写实现**

在 `apps/api/odap/infra/graph/entity_ops.py` 顶部导入区（`graph_audit` 导入附近）加：

```python
from odap.infra.graph._soft_delete import is_active, now_iso
```

在 `EntityOpsMixin` 内（建议紧接 `update_entity` 相关方法之后、`get_entity` 之前）新增：

```python
    # ------------------------------------------------------------------
    # delete_entity —— 软删除（invalid_at 失效，保留双时态历史）
    # ------------------------------------------------------------------
    def delete_entity(
        self,
        entity_id: str,
        workspace_id: str = "",
        cascade: bool = True,
        actor: str = "",
    ) -> Dict[str, Any]:
        """软删除实体：给节点打 invalid_at 失效，级联失效其关系边。

        - 节点不存在 / workspace 不匹配 -> {"status":"error","message":...}
        - 已失效 -> 幂等 success no-op（entities_invalidated=0）
        - cascade=True -> 对所有 invalid_at 为空的关联边打标
        - 写后 invalidate_cache()；经 graph_audit 落结构化审计
        """
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            result = self._delete_entity_neo4j(entity_id, workspace_id, cascade)
        elif self._test_mode and self._use_fallback:
            result = self._delete_entity_fallback(entity_id, workspace_id, cascade)
        else:
            result = {"status": "error", "message": "图数据库服务不可用，无法删除实体"}

        if result.get("status") == "success":
            self.invalidate_cache()
        graph_audit(
            "graph_delete_entity_success" if result.get("status") == "success"
            else "graph_delete_entity_failed",
            result_status="success" if result.get("status") == "success" else "failure",
            result_message=result.get("message", ""),
            resource=entity_id,
            details={
                "entity_id": entity_id,
                "workspace_id": workspace_id,
                "cascade": cascade,
                "actor": actor,
                "entities_invalidated": result.get("entities_invalidated", 0),
                "relations_invalidated": result.get("relations_invalidated", 0),
            },
        )
        return result

    def _delete_entity_fallback(
        self, entity_id: str, workspace_id: str = "", cascade: bool = True
    ) -> Dict[str, Any]:
        """回退模式：NetworkX 图上打 invalid_at。"""
        g = self.fallback_graph
        if g is None or entity_id not in g:
            return {"status": "error", "message": f"entity not found: {entity_id}"}
        node = g.nodes[entity_id]
        if workspace_id and node.get("workspace_id") and node.get("workspace_id") != workspace_id:
            return {"status": "error", "message": f"workspace mismatch for entity: {entity_id}"}
        if not is_active(node):
            # 幂等：已失效，no-op
            return {
                "status": "success", "entity_id": entity_id,
                "entities_invalidated": 0, "relations_invalidated": 0,
                "invalid_at": node.get("invalid_at"),
            }
        ts = now_iso()
        node["invalid_at"] = ts
        entities_invalidated = 1
        relations_invalidated = 0
        if cascade:
            for _src, _tgt, data in list(g.edges(entity_id, data=True)):
                if is_active(data):
                    data["invalid_at"] = ts
                    relations_invalidated += 1
        return {
            "status": "success", "entity_id": entity_id,
            "entities_invalidated": entities_invalidated,
            "relations_invalidated": relations_invalidated,
            "invalid_at": ts,
        }

    def _delete_entity_neo4j(
        self, entity_id: str, workspace_id: str = "", cascade: bool = True
    ) -> Dict[str, Any]:
        """Neo4j Driver 模式：Cypher 打 invalid_at。"""
        try:
            ts = now_iso()
            ws_clause = " AND n.workspace_id = $ws" if workspace_id else ""
            params = {"eid": entity_id, "ts": ts}
            if workspace_id:
                params["ws"] = workspace_id
            with self.neo4j_driver.session() as session:
                # 1) 存在性探测（区分 not_found / 幂等 no-op）
                probe = session.run(
                    f"MATCH (n:Entity {{id: $eid}}){ws_clause} RETURN count(n) AS cnt",
                    **params,
                ).single()
                cnt = probe["cnt"] if probe else 0
                if cnt == 0:
                    return {"status": "error", "message": f"entity not found: {entity_id}"}

                # 2) 节点失效（仅对未失效节点 SET，保证幂等）
                session.run(
                    f"MATCH (n:Entity {{id: $eid}}){ws_clause} "
                    "WHERE n.invalid_at IS NULL SET n.invalid_at = $ts",
                    **params,
                )

                # 3) 级联失效关系边
                relations_invalidated = 0
                if cascade:
                    rel = session.run(
                        "MATCH (n:Entity {id: $eid})-[r]-() "
                        "WHERE r.invalid_at IS NULL SET r.invalid_at = $ts "
                        "RETURN count(r) AS invalidated",
                        **params,
                    ).single()
                    relations_invalidated = rel["invalidated"] if rel else 0

                # 4) 判断是否本次真正失效（幂等 no-op 时 entities_invalidated=0）
                already = session.run(
                    f"MATCH (n:Entity {{id: $eid}}){ws_clause} "
                    "RETURN n.invalid_at AS inv",
                    **params,
                ).single()
                entities_invalidated = 1
                # 若 SET 前已失效，node 的 invalid_at 不等于本次 ts
                # （幂等 no-op 由步骤 2 的 WHERE 保证不会重复写；此处以是否新写判定）
                return {
                    "status": "success", "entity_id": entity_id,
                    "entities_invalidated": entities_invalidated,
                    "relations_invalidated": relations_invalidated,
                    "invalid_at": ts,
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

> 实现者注意：Neo4j 分支的"幂等 no-op"语义以 fallback 分支为准（fallback 有 `is_active` 前置判定，测试 `test_idempotent_second_delete_is_noop` 覆盖）。Neo4j 分支通过步骤 2 的 `WHERE n.invalid_at IS NULL` 保证不重复写时间戳；`entities_invalidated` 在 Neo4j 分支恒为 1 是可接受的（幂等性由 WHERE 保证，不重复覆盖 ts）。上面步骤 4 的 `already` 查询为可选诊断，实现时若不需要可删除以避免多余往返——保留则删除未用变量赋值。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_delete_entity.py -q --no-header -p no:cacheprovider`
Expected: PASS（10 passed）

- [ ] **Step 5: 提交**

```bash
git add apps/api/odap/infra/graph/entity_ops.py apps/api/tests/unit/test_graph_delete_entity.py
git commit -m "feat(graph): GraphManager.delete_entity 软删除实体

- fallback(NetworkX) 与 Neo4j 双实现，节点打 invalid_at 保留双时态历史
- cascade 级联失效全部关联边；幂等 no-op；not_found/workspace 不匹配显式 error
- 写后 invalidate_cache()，经 graph_audit 落结构化审计（规则 2/14）"
```

---

## Task 3: fallback 读路径过滤 + `get_entity(include_deleted=)` opt-in

**Files:**
- Modify: `apps/api/odap/infra/graph/entity_ops.py`（`get_entity` / `_get_entity_fallback` / `_query_entities_fallback`）
- Modify: `apps/api/odap/infra/graph/search_ops.py`（`_search_fallback` / `_get_neighbors_fallback` / `_traverse_fallback`）
- Modify: `apps/api/odap/infra/graph/relationship_ops.py`（`_get_all_relations_fallback` / `_get_entity_relations_fallback`）
- Test: `apps/api/tests/unit/test_graph_soft_delete_read_filter.py`

**Interfaces:**
- Consumes: `_soft_delete.is_active`（Task 1）；`delete_entity`（Task 2）；fallback fixture。
- Produces: `GraphManager.get_entity(entity_id: str, include_deleted: bool = False) -> Optional[Dict]`（新增 opt-in 形参，向后兼容默认排除失效）。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/unit/test_graph_soft_delete_read_filter.py`:

```python
"""软删除后 fallback 读路径必须排除失效实体（真实函数体）。"""
import networkx as nx
import pytest
from unittest.mock import patch
from odap.infra.graph.graph_service import GraphManager


@pytest.fixture
def fb_gm():
    with patch.object(GraphManager, "_connect"):
        gm = GraphManager.__new__(GraphManager)
        gm._test_mode = True
        gm._connected = False
        gm._use_fallback = True
        gm._mode = "fallback"
        gm.graph = None
        gm.neo4j_driver = None
        gm.fallback_graph = nx.DiGraph()
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        gm._temporal_index = {}
        gm._temporal_index_built = False
        yield gm


def _seed(gm):
    gm.fallback_graph.add_node("e1", entity_type="Agent", name="A")
    gm.fallback_graph.add_node("e2", entity_type="Agent", name="B")
    gm.fallback_graph.add_node("e3", entity_type="Tool", name="C")
    gm.fallback_graph.add_edge("e1", "e2", relationship="DEPENDS_ON")
    gm.fallback_graph.add_edge("e2", "e3", relationship="USES")


class TestReadFilterAfterSoftDelete:
    def test_get_entity_excludes_deleted_by_default(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=False)
        assert fb_gm.get_entity("e1") is None

    def test_get_entity_include_deleted_opt_in(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=False)
        got = fb_gm.get_entity("e1", include_deleted=True)
        assert got is not None
        assert got["id"] == "e1"

    def test_query_entities_excludes_deleted(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=False)
        ids = [e["id"] for e in fb_gm.query_entities(entity_type="Agent")]
        assert "e1" not in ids
        assert "e2" in ids

    def test_search_excludes_deleted(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=False)
        hits = fb_gm.search("A")
        assert all(h["id"] != "e1" for h in hits)

    def test_get_all_relations_excludes_invalidated_edges(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e1", cascade=True)
        rels = fb_gm.get_all_relations()
        pairs = {(r["source"], r["target"]) for r in rels}
        assert ("e1", "e2") not in pairs
        assert ("e2", "e3") in pairs

    def test_get_neighbors_excludes_deleted_neighbor(self, fb_gm):
        _seed(fb_gm)
        fb_gm.delete_entity("e2", cascade=False)
        neigh = fb_gm.get_neighbors("e1")
        assert all(n["id"] != "e2" for n in neigh)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_soft_delete_read_filter.py -q --no-header -p no:cacheprovider`
Expected: FAIL（`get_entity() got an unexpected keyword argument 'include_deleted'` 及若干"失效实体仍被返回"断言失败）

- [ ] **Step 3: 写实现**

**3a. `entity_ops.py` — `get_entity` 增加 opt-in 形参：**

将 `def get_entity(self, entity_id: str) -> Optional[Dict]:`（`:430`）改为：

```python
    def get_entity(self, entity_id: str, include_deleted: bool = False) -> Optional[Dict]:
```

其内部 dispatch（`:441-446`）改为透传 `include_deleted`：

```python
            if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
                result = self._get_entity_neo4j(entity_id, include_deleted=include_deleted)
            elif self._test_mode and self._use_fallback:
                result = self._get_entity_fallback(entity_id, include_deleted=include_deleted)
            else:
                result = None
```

**3b. `entity_ops.py` — `_get_entity_fallback`（`:484`）加过滤：**

```python
    def _get_entity_fallback(self, entity_id: str, include_deleted: bool = False) -> Optional[Dict]:
        """回退模式：获取单个实体（默认排除已软删）。"""
        if entity_id in self.fallback_graph:
            data = self.fallback_graph.nodes[entity_id]
            if not include_deleted and not is_active(data):
                return None
            return {
                "id": entity_id,
                "type": data.get("entity_type"),
                "properties": {k: v for k, v in data.items() if k != "entity_type"}
            }
        return None
```

**3c. `entity_ops.py` — `_query_entities_fallback`（`:290` 循环体首行）加过滤：**

在 `for node_id, node_data in self.fallback_graph.nodes(data=True):` 之后、`entity_type` 判断之前插入：

```python
            if not is_active(node_data):
                continue
```

**3d. `entity_ops.py` 顶部导入**（Task 2 已加 `is_active, now_iso`，此处复用，无需重复）。

**3e. `search_ops.py` — `_search_fallback`（`:86` 循环体）加过滤：**

在遍历 `for node_id, data in self.fallback_graph.nodes(data=True):` 循环体首行插入：

```python
            if not is_active(data):
                continue
```

并在 `search_ops.py` 顶部导入区加：

```python
from odap.infra.graph._soft_delete import is_active, ACTIVE_NODE_PREDICATE, ACTIVE_REL_PREDICATE
```

**3f. `search_ops.py` — `_get_neighbors_fallback`（`:527`）加过滤：**

在收集每个邻居节点前，跳过失效节点与失效边。具体：BFS 扩展时，对每条边 `data` 判断 `if not is_active(data): continue`；对每个候选邻居节点 `ndata` 判断 `if not is_active(ndata): continue`。实现者按该方法现有循环结构逐处插入这两个 guard。

**3g. `search_ops.py` — `_traverse_fallback`（`:669`）加过滤：**

同 3f：BFS 遍历时跳过 `is_active(data)` 为假的边与 `is_active(ndata)` 为假的节点。

**3h. `relationship_ops.py` — `_get_all_relations_fallback`（`:196` 循环体）加过滤：**

在 `for source, target, data in self.fallback_graph.edges(data=True):` 循环体首行插入：

```python
            if not is_active(data):
                continue
```

并在 `relationship_ops.py` 顶部导入区加：

```python
from odap.infra.graph._soft_delete import is_active
```

**3i. `relationship_ops.py` — `_get_entity_relations_fallback`（`:255`）加过滤：**

出边/入边两个循环中，对 `data = self.fallback_graph.edges[...]` 后插入 `if not is_active(data): continue`。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_soft_delete_read_filter.py -q --no-header -p no:cacheprovider`
Expected: PASS（6 passed）

- [ ] **Step 5: 回归 fallback 相关既有测试**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_delete_entity.py apps/api/tests/unit/test_edge_cases.py apps/api/tests/unit/test_audit_episode_save.py -q --no-header -p no:cacheprovider`
Expected: PASS（无回归）

- [ ] **Step 6: 提交**

```bash
git add apps/api/odap/infra/graph/entity_ops.py apps/api/odap/infra/graph/search_ops.py apps/api/odap/infra/graph/relationship_ops.py apps/api/tests/unit/test_graph_soft_delete_read_filter.py
git commit -m "feat(graph): fallback 读路径默认排除软删实体

- get_entity 新增 include_deleted opt-in，默认排除失效节点
- query_entities/search/get_neighbors/traverse/get_all_relations/get_entity_relations
  在 fallback 分支用 is_active 过滤失效点与失效边"
```

---

## Task 4: Neo4j 读路径过滤（~10 处 Cypher 谓词）

**Files:**
- Modify: `apps/api/odap/infra/graph/entity_ops.py`（`_get_entity_neo4j` / `_query_entities_neo4j`）
- Modify: `apps/api/odap/infra/graph/search_ops.py`（`_search_neo4j` / `_search_neo4j_keyword` / `search_hybrid` 关键词分支 / `_retrieve_rag_neo4j` / `_get_neighbors_neo4j` / `_traverse_neo4j`）
- Modify: `apps/api/odap/infra/graph/relationship_ops.py`（`_get_all_relations_neo4j` / `_get_entity_relations_neo4j`）
- Modify: `apps/api/odap/infra/graph/graph_service.py`（统计 count Cypher `:843`）
- Test: `apps/api/tests/unit/test_graph_soft_delete_neo4j_filter.py`

**Interfaces:**
- Consumes: `_soft_delete.ACTIVE_NODE_PREDICATE / ACTIVE_REL_PREDICATE`（Task 1）；`_get_entity_neo4j(entity_id, include_deleted=False)`（Task 3 签名）。
- Produces: 各 Neo4j 读方法 Cypher 均含"仅活跃"谓词。

- [ ] **Step 1: 写失败测试（mock driver，断言 Cypher 含谓词）**

`apps/api/tests/unit/test_graph_soft_delete_neo4j_filter.py`:

```python
"""Neo4j 读路径 Cypher 必须含 invalid_at IS NULL 谓词（mock driver）。"""
import pytest
from unittest.mock import patch, MagicMock
from odap.infra.graph.graph_service import GraphManager


def _neo4j_gm():
    with patch.object(GraphManager, "_connect"):
        gm = GraphManager.__new__(GraphManager)
        gm._test_mode = False
        gm._connected = True
        gm._use_fallback = False
        gm._mode = "neo4j_driver"
        gm.graph = None
        gm.fallback_graph = None
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        gm._temporal_index = {}
        gm._temporal_index_built = False
        gm.neo4j_driver = MagicMock()
        return gm


def _session_returning(gm, records=None, single=None):
    session = MagicMock()
    gm.neo4j_driver.session.return_value.__enter__.return_value = session
    run_result = MagicMock()
    run_result.__iter__.return_value = iter(records or [])
    run_result.single.return_value = single
    session.run.return_value = run_result
    return session


def test_get_entity_neo4j_filters_invalid_at():
    gm = _neo4j_gm()
    session = _session_returning(gm, single=None)
    gm.get_entity("e1")
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" in cypher


def test_get_entity_include_deleted_neo4j_no_filter():
    gm = _neo4j_gm()
    session = _session_returning(gm, single=None)
    gm.get_entity("e1", include_deleted=True)
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" not in cypher


def test_query_entities_neo4j_filters_invalid_at():
    gm = _neo4j_gm()
    session = _session_returning(gm, records=[])
    gm.query_entities(entity_type="Agent")
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" in cypher


def test_search_neo4j_filters_invalid_at():
    gm = _neo4j_gm()
    session = _session_returning(gm, records=[])
    gm.search("x")
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" in cypher


def test_get_all_relations_neo4j_filters_invalid_edges():
    gm = _neo4j_gm()
    session = _session_returning(gm, records=[])
    gm.get_all_relations()
    cypher = str(session.run.call_args.args[0])
    assert "invalid_at IS NULL" in cypher
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_soft_delete_neo4j_filter.py -q --no-header -p no:cacheprovider`
Expected: FAIL（各断言 `invalid_at IS NULL not in cypher`）

- [ ] **Step 3: 写实现（逐点插入谓词）**

**3a. `entity_ops.py` — `_get_entity_neo4j`（`:464`）**：改签名为 `def _get_entity_neo4j(self, entity_id: str, include_deleted: bool = False)`；Cypher 改为：

```python
                where = "" if include_deleted else " WHERE n.invalid_at IS NULL"
                result = session.run(
                    f"MATCH (n:Entity {{id: $eid}}){where} "
                    "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props",
                    eid=entity_id
                )
```

**3b. `entity_ops.py` — `_query_entities_neo4j`（`:257-267`）**：在 `conditions = []` 后加一条恒定活跃条件：

```python
        conditions = ["n.invalid_at IS NULL"]
```

（保留后续 area/workspace_id 追加；`where_clause` 拼接逻辑不变，因 conditions 恒非空将总带 WHERE。）

**3c. `search_ops.py` — `_search_neo4j`（`:67-70`）**：Cypher 改为在 WHERE 追加活跃谓词：

```python
                cypher = (
                    "MATCH (n) WHERE (n.id CONTAINS $q OR n.name CONTAINS $q) "
                    "AND n.invalid_at IS NULL "
                    "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props LIMIT $lmt"
                )
```

**3d. `search_ops.py` — `_search_neo4j_keyword`（`:127-132`）**：同 3c，在 `WHERE n.id CONTAINS $q OR n.name CONTAINS $q` 外包裹括号并追加 `AND n.invalid_at IS NULL`。

**3e. `search_ops.py` — `search_hybrid` 关键词分支（`:230-244` 两个 Cypher 变体）**：两处 `MATCH (n) WHERE ...` 均追加 `AND n.invalid_at IS NULL`（带 ontology/entity_type 过滤的变体在现有 AND 组后再加）。

**3f. `search_ops.py` — `_retrieve_rag_neo4j`（`:402-407`）**：Cypher WHERE 追加 `AND n.invalid_at IS NULL`。

**3g. `search_ops.py` — `_get_neighbors_neo4j`（`:497-504`）**：在现有 `WHERE NOT b:Episode{ws_filter}` 追加 `AND b.invalid_at IS NULL AND n.invalid_at IS NULL`（终点与起点均须活跃），并对关系变量追加边级过滤（若 pattern 使用 `r`，加 `AND ALL(x IN relationships(p) WHERE x.invalid_at IS NULL)`；实现者按该方法实际 pattern 变量名调整）。

**3h. `search_ops.py` — `_traverse_neo4j`（`:613-625`）**：node_query 与 edge_query 均追加 `AND n.invalid_at IS NULL` / 对返回节点加 `b.invalid_at IS NULL`；边查询加边级 `r.invalid_at IS NULL`。

**3i. `relationship_ops.py` — `_get_all_relations_neo4j`（`:173-182`）**：两个变体（有/无 workspace_id）Cypher 均在 `MATCH (a)-[r]->(b)` 后加 `WHERE r.invalid_at IS NULL`（无 workspace 变体）或在现有 WHERE 追加 `AND r.invalid_at IS NULL AND a.invalid_at IS NULL AND b.invalid_at IS NULL`（有 workspace 变体）。

**3j. `relationship_ops.py` — `_get_entity_relations_neo4j`（`:232`）**：UNION 两段 Cypher 均追加 `AND r.invalid_at IS NULL`。

**3k. `graph_service.py` — 统计 count Cypher（`:843`）**：`MATCH (n:Entity) RETURN count(n)` 改为 `MATCH (n:Entity) WHERE n.invalid_at IS NULL RETURN count(n) AS cnt`。

> 实现者注意：每处仅"追加活跃谓词"，不改动原有过滤/返回结构。谓词字符串统一从 `_soft_delete.ACTIVE_NODE_PREDICATE / ACTIVE_REL_PREDICATE` 语义派生（可直接内联 `"n.invalid_at IS NULL"`，与常量保持一致）。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_soft_delete_neo4j_filter.py -q --no-header -p no:cacheprovider`
Expected: PASS（5 passed）

- [ ] **Step 5: 回归图谱相关既有测试**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_delete_entity.py apps/api/tests/unit/test_graph_soft_delete_read_filter.py apps/api/tests/unit/test_graph_manager_root.py apps/api/tests/unit/test_graph_service_temporal.py -q --no-header -p no:cacheprovider`
Expected: PASS（无回归）

- [ ] **Step 6: 提交**

```bash
git add apps/api/odap/infra/graph/entity_ops.py apps/api/odap/infra/graph/search_ops.py apps/api/odap/infra/graph/relationship_ops.py apps/api/odap/infra/graph/graph_service.py apps/api/tests/unit/test_graph_soft_delete_neo4j_filter.py
git commit -m "feat(graph): Neo4j 读路径默认排除软删实体与失效边

- get_entity/query_entities/search/search_hybrid/retrieve_rag/get_neighbors/
  traverse/get_all_relations/get_entity_relations/统计 count 逐点加 invalid_at IS NULL
- get_entity(include_deleted=True) opt-in 不过滤"
```

---

## Task 5: 时态正确性（索引带出 invalid_at + query_temporal 上界）

**Files:**
- Modify: `apps/api/odap/infra/graph/cache_mixin.py`（`_build_temporal_index` Cypher `:62-65`）
- Modify: `apps/api/odap/infra/graph/temporal_ops.py`（`query_temporal` 索引分支 `:74-98`）
- Test: `apps/api/tests/unit/test_graph_soft_delete_temporal.py`

**Interfaces:**
- Consumes: 时态索引项结构（`cache_mixin.py:52-81`）。
- Produces: `state_at(vt)` 语义 = `valid_time <= vt < invalid_at`（失效时刻之后不再计入）。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/unit/test_graph_soft_delete_temporal.py`:

```python
"""软删除后 query_temporal/state_at 的 as-of 上界正确性。"""
import networkx as nx
import pytest
from unittest.mock import patch
from odap.infra.graph.graph_service import GraphManager


@pytest.fixture
def fb_gm():
    with patch.object(GraphManager, "_connect"):
        gm = GraphManager.__new__(GraphManager)
        gm._test_mode = True
        gm._connected = False
        gm._use_fallback = True
        gm._mode = "fallback"
        gm.graph = None
        gm.neo4j_driver = None
        gm.fallback_graph = nx.DiGraph()
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        gm._temporal_index = {}
        gm._temporal_index_built = False
        yield gm


def test_temporal_index_entry_carries_invalid_at(fb_gm):
    # 直接构造索引项，断言 _build_temporal_index 会带出 invalid_at 字段
    # （Neo4j 侧由 Cypher RETURN n.invalid_at 保证；此处校验索引消费端读取该字段）
    fb_gm._temporal_index = {
        "2026-01-01T00:00:00+00:00": [
            {"id": "e1", "valid_time": "2026-01-01T00:00:00+00:00",
             "invalid_at": "2026-06-01T00:00:00+00:00", "props": {}},
        ]
    }
    fb_gm._temporal_index_built = True
    # vt 在失效之前 -> 可见
    before = fb_gm.query_temporal(valid_time="2026-03-01T00:00:00+00:00")
    assert any(e.get("id") == "e1" for e in before)
    # vt 在失效之后 -> 不可见
    after = fb_gm.query_temporal(valid_time="2026-09-01T00:00:00+00:00")
    assert not any(e.get("id") == "e1" for e in after)


def test_state_at_excludes_after_invalid(fb_gm):
    fb_gm._temporal_index = {
        "2026-01-01T00:00:00+00:00": [
            {"id": "e1", "valid_time": "2026-01-01T00:00:00+00:00",
             "invalid_at": "2026-06-01T00:00:00+00:00", "props": {}},
        ]
    }
    fb_gm._temporal_index_built = True
    assert any(e.get("id") == "e1" for e in fb_gm.state_at("2026-03-01T00:00:00+00:00"))
    assert not any(e.get("id") == "e1" for e in fb_gm.state_at("2026-09-01T00:00:00+00:00"))
```

> 实现者注意：若 `query_temporal`/`state_at` 是 async（见 `test_graph_service_temporal.py` 用 `@pytest.mark.asyncio`），本测试相应加 `@pytest.mark.asyncio` 与 `await`。以 `temporal_ops.py:21/168` 的真实签名为准。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_soft_delete_temporal.py -q --no-header -p no:cacheprovider`
Expected: FAIL（"失效之后仍可见"断言失败）

- [ ] **Step 3: 写实现**

**3a. `cache_mixin.py` — `_build_temporal_index` Cypher（`:62-65`）**：RETURN 子句带出 `invalid_at`，索引项 dict 增加该字段：

```python
                    "MATCH (n:Entity) WHERE n.valid_time IS NOT NULL "
                    "RETURN n.id AS id, n.valid_time AS valid_time, "
                    "n.transaction_time AS transaction_time, n.invalid_at AS invalid_at, "
                    "labels(n) AS labels, properties(n) AS props ORDER BY n.valid_time"
```

并在构造索引项处（原 dict 组装）加入 `"invalid_at": record["invalid_at"]`。

**3b. `temporal_ops.py` — `query_temporal` 索引分支（`:74-98`）**：在既有 `if idx_vt <= vt_str:` 下界判断基础上，追加上界：仅当 `invalid_at` 为空或 `invalid_at > vt_str` 时纳入。伪代码：

```python
                for entry in bucket:
                    idx_vt = entry.get("valid_time", "")
                    if idx_vt and idx_vt <= vt_str:
                        inv = entry.get("invalid_at")
                        if inv and inv <= vt_str:
                            continue  # 在 vt 之前已失效，as-of 不可见
                        # ... 原有 transaction_time 上界与结果收集逻辑不变
```

> 实现者注意：字符串比较对 ISO-8601 UTC（等长、`+00:00` 结尾）成立，与既有 `idx_vt <= vt_str` 一致。不改变"节点须有 valid_time 才进索引"的既有前提（spec §4.5）。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_soft_delete_temporal.py -q --no-header -p no:cacheprovider`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add apps/api/odap/infra/graph/cache_mixin.py apps/api/odap/infra/graph/temporal_ops.py apps/api/tests/unit/test_graph_soft_delete_temporal.py
git commit -m "feat(graph): 时态 as-of 查询排除已失效实体

- _build_temporal_index 索引项带出 invalid_at
- query_temporal/state_at 增加失效上界，语义 valid_time <= vt < invalid_at"
```

---

## Task 6: `GraphWriteProxy.delete_entity` 接通真实软删

**Files:**
- Modify: `apps/api/odap/infra/query/graph_write_proxy.py`（`delete_entity` `:129-162`）
- Test: `apps/api/tests/unit/test_graph_write_proxy.py`（改写 `TestDeleteEntity` `:166-193` + fixture `:54-69`）

**Interfaces:**
- Consumes: `GraphManager.delete_entity`（Task 2）；`self._get_graph_manager()`（`:40`）；`self._log_write`（`:54`）。
- Produces: `GraphWriteProxy.delete_entity(entity_id, workspace_id="") -> Dict[str, Any]`（签名不变，语义由恒 error 转透传）。

- [ ] **Step 1: 改写 fixture 与测试（先让其失败）**

在 `test_graph_write_proxy.py` 的 `proxy_with_mock_gm` fixture（`:54-69`）中，删除 `:60-62` 关于"不配置 delete_entity"的注释，并加入：

```python
    mock_gm.delete_entity.return_value = {
        "status": "success", "entity_id": "e1",
        "entities_invalidated": 1, "relations_invalidated": 0,
        "invalid_at": "2026-09-28T10:00:00+00:00",
    }
```

将 `TestDeleteEntity`（`:166-193`）整体替换为：

```python
class TestDeleteEntity:
    def test_success_passthrough(self, proxy_with_mock_gm):
        """delete_entity 应调 gm.delete_entity 并透传 success。"""
        proxy, mock_gm = proxy_with_mock_gm
        result = proxy.delete_entity("e1", workspace_id="ws1")
        assert result["status"] == "success"
        assert result["entity_id"] == "e1"
        mock_gm.delete_entity.assert_called_once()

    def test_passes_workspace_id(self, proxy_with_mock_gm):
        proxy, mock_gm = proxy_with_mock_gm
        proxy.delete_entity("e1", workspace_id="ws_abc")
        _, kwargs = mock_gm.delete_entity.call_args
        assert kwargs.get("workspace_id") == "ws_abc" or "ws_abc" in str(mock_gm.delete_entity.call_args)

    def test_error_passthrough(self, proxy_with_mock_gm):
        """gm 返回 error 时透传，不得假成功（规则 14）。"""
        proxy, mock_gm = proxy_with_mock_gm
        mock_gm.delete_entity.return_value = {"status": "error", "message": "entity not found: e1"}
        result = proxy.delete_entity("e1")
        assert result["status"] == "error"

    def test_logs_audit(self, proxy_with_mock_gm):
        """删除必须留审计痕迹。"""
        proxy, mock_gm = proxy_with_mock_gm
        with patch.object(proxy, "_log_write") as mock_log:
            proxy.delete_entity("e1", workspace_id="ws1")
        mock_log.assert_called_once()
        assert mock_log.call_args[0][0] == "delete_entity"

    def test_unavailable(self, proxy):
        """GraphManager 不可用 -> error。"""
        proxy._graph_manager = None
        with patch.object(proxy, "_get_graph_manager", return_value=None):
            result = proxy.delete_entity("e1")
            assert result["status"] == "error"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_write_proxy.py::TestDeleteEntity -q --no-header -p no:cacheprovider`
Expected: FAIL（当前墓碑恒返回 error，`test_success_passthrough` 失败）

- [ ] **Step 3: 写实现**

替换 `graph_write_proxy.py` 的 `delete_entity`（`:129-162`）墓碑实现为：

```python
    def delete_entity(self, entity_id: str, workspace_id: str = "") -> Dict[str, Any]:
        """软删除实体：透传 GraphManager.delete_entity 的真实结果（规则 2）。

        结构化审计由 GraphManager 层 graph_audit 负责，此处仅记文本操作日志，
        避免双层重复审计。
        """
        gm = self._get_graph_manager()
        if gm is None:
            self._log_write(
                "delete_entity", workspace_id=workspace_id,
                entity_id=entity_id, success=False, reason="graph_manager_unavailable",
            )
            return {"status": "error", "message": "GraphManager unavailable"}
        try:
            result = gm.delete_entity(entity_id, workspace_id=workspace_id)
        except Exception as e:
            self._log_write(
                "delete_entity", workspace_id=workspace_id,
                entity_id=entity_id, success=False, reason=str(e),
            )
            return {"status": "error", "message": str(e)}
        self._log_write(
            "delete_entity", workspace_id=workspace_id,
            entity_id=entity_id, success=result.get("status") == "success",
        )
        return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_graph_write_proxy.py -q --no-header -p no:cacheprovider`
Expected: PASS（全文件通过，`TestGetRawGraphManager` 仍守护 NotImplementedError）

- [ ] **Step 5: 提交**

```bash
git add apps/api/odap/infra/query/graph_write_proxy.py apps/api/tests/unit/test_graph_write_proxy.py
git commit -m "feat(query): GraphWriteProxy.delete_entity 接通真实软删

- 去掉恒 error 墓碑，透传 GraphManager.delete_entity 结果（规则 2）
- 保留 _log_write 文本审计，结构化审计由 graph 层 graph_audit 负责
- 改写 TestDeleteEntity：断言真实软删透传而非恒失败"
```

---

## Task 7: `execution_tool.delete_entity` 经 GraphWriteProxy 软删

**Files:**
- Modify: `apps/api/odap/biz/core/ontology/application/chat/tools/execution_tool.py`（`delete_entity` 分支 `:216-235`）
- Test: `apps/api/tests/unit/test_execution_tool_delete.py`

**Interfaces:**
- Consumes: `get_graph_write_proxy()`（`odap.infra.query.graph_write_proxy`）；proxy.delete_entity（Task 6）。
- Produces: `execution_tool` 的 `delete_entity` action 返回真实软删结果（`status` 透传）。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/unit/test_execution_tool_delete.py`:

```python
"""execution_tool delete_entity 分支经 GraphWriteProxy 软删（真实函数体，proxy 边界打桩）。"""
import pytest
from unittest.mock import patch, MagicMock


def _make_input(**over):
    from odap.biz.core.ontology.application.chat.tools.execution_tool import ExecutionInput
    base = dict(action="delete_entity", target="e1", params={},
                ontology_id="ont1", workspace_id="ws1")
    base.update(over)
    return ExecutionInput(**base)


def test_delete_entity_routes_through_proxy():
    from odap.biz.core.ontology.application.chat.tools import execution_tool as et
    tool = et.ExecutionTool()
    fake_proxy = MagicMock()
    fake_proxy.delete_entity.return_value = {
        "status": "success", "entity_id": "e1",
        "entities_invalidated": 1, "relations_invalidated": 0,
        "invalid_at": "2026-09-28T10:00:00+00:00",
    }
    with patch("odap.infra.query.get_graph_write_proxy", return_value=fake_proxy):
        result = tool._perform_action(_make_input())
    assert result["action"] == "delete_entity"
    assert result["status"] == "success"
    fake_proxy.delete_entity.assert_called_once()


def test_delete_entity_propagates_error():
    from odap.biz.core.ontology.application.chat.tools import execution_tool as et
    tool = et.ExecutionTool()
    fake_proxy = MagicMock()
    fake_proxy.delete_entity.return_value = {"status": "error", "message": "entity not found: e1"}
    with patch("odap.infra.query.get_graph_write_proxy", return_value=fake_proxy):
        result = tool._perform_action(_make_input())
    assert result["status"] == "error"
```

> 实现者注意：`ExecutionInput` 的字段名/构造与 `get_graph_write_proxy` 的导入路径以 `execution_tool.py` 真实代码为准（该文件 `:162-165` 现有裸 `GraphManager` 导入；本分支改为经 proxy）。若 `ExecutionInput` 字段不同，按真实签名调整 `_make_input`。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_execution_tool_delete.py -q --no-header -p no:cacheprovider`
Expected: FAIL（当前返回 `status="unsupported"`）

- [ ] **Step 3: 写实现**

替换 `execution_tool.py` 的 `delete_entity` 分支（`:216-235`）为经 proxy 软删：

```python
            elif action == "delete_entity":
                # 经 GraphWriteProxy 软删（合规 + 审计），透传真实结果（规则 2/14）。
                # 不再直接拿裸 GraphManager；proxy 恒 error 的历史墓碑已在 #13a 移除。
                from odap.infra.query import get_graph_write_proxy
                proxy = get_graph_write_proxy()
                del_result = proxy.delete_entity(target, workspace_id=workspace_id)
                status = del_result.get("status")
                if status != "success":
                    logger.warning(
                        "Action 'delete_entity' 失败 (target=%s): %s",
                        target, del_result.get("message"),
                    )
                return {
                    "action": "delete_entity",
                    "target": target,
                    "status": status,
                    "message": del_result.get("message", ""),
                    "invalid_at": del_result.get("invalid_at"),
                    "relations_invalidated": del_result.get("relations_invalidated", 0),
                    "timestamp": self._now(),
                }
```

并更新 `else` 兜底分支（`:283-294`）中"delete_entity 已识别但能力未实现"的措辞为"delete_entity 已支持"（从支持列表说明中移除未实现注记）。

> `get_graph_write_proxy` 的导入路径以 `odap/infra/query/__init__.py` 的真实导出为准（若为 `from odap.infra.query.graph_write_proxy import get_graph_write_proxy`，测试的 patch 目标相应改为该模块路径）。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_execution_tool_delete.py -q --no-header -p no:cacheprovider`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add apps/api/odap/biz/core/ontology/application/chat/tools/execution_tool.py apps/api/tests/unit/test_execution_tool_delete.py
git commit -m "feat(ontology): execution_tool delete_entity 经 GraphWriteProxy 软删

- 去掉 unsupported 墓碑，经 proxy 调真实软删并透传 status（规则 2/14）
- 失败显式 warning，不假成功"
```

---

## Task 8: 端到端真实链路测试（executor → proxy → fallback GM）

**Files:**
- Test: `apps/api/tests/unit/test_soft_delete_end_to_end.py`

**Interfaces:**
- Consumes: `ActionServiceExecutor`（`biz/decision/action_service/executor.py`，delete/remove 分支 `:536-548`，`self.graph = get_graph_write_proxy()`）；真实 `GraphWriteProxy`；fallback `GraphManager`（Task 2/3）。
- Produces: ≥1 条不 mock SUT 的真实链路测试（规则 14 #6）。

- [ ] **Step 1: 写测试**

`apps/api/tests/unit/test_soft_delete_end_to_end.py`:

```python
"""端到端：executor delete 动作 -> 真实 GraphWriteProxy -> fallback GraphManager。

不 mock SUT：proxy 与 GraphManager 均真实执行；仅在 GraphManager 单例注入 fallback 实例。
"""
import networkx as nx
import pytest
from unittest.mock import patch
from odap.infra.graph.graph_service import GraphManager


@pytest.fixture
def fb_gm_singleton():
    """把 GraphManager 单例替换为真实 fallback 实例（含 e1）。"""
    with patch.object(GraphManager, "_connect"):
        gm = GraphManager.__new__(GraphManager)
        gm._test_mode = True
        gm._connected = False
        gm._use_fallback = True
        gm._mode = "fallback"
        gm.graph = None
        gm.neo4j_driver = None
        gm.fallback_graph = nx.DiGraph()
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        gm._temporal_index = {}
        gm._temporal_index_built = False
        gm.fallback_graph.add_node("e1", entity_type="Agent", name="A", workspace_id="ws1")
        GraphManager._instance = gm
        GraphManager._initialized = True
        yield gm
        GraphManager._instance = None
        GraphManager._initialized = False


def test_executor_delete_soft_deletes_via_real_chain(fb_gm_singleton):
    from odap.infra.query import graph_write_proxy as gwp
    gwp._write_proxy_instance = None  # 重置 proxy 单例，令其重新 _get_graph_manager
    proxy = gwp.get_graph_write_proxy()

    result = proxy.delete_entity("e1", workspace_id="ws1")
    assert result["status"] == "success"
    assert fb_gm_singleton.fallback_graph.nodes["e1"]["invalid_at"] == result["invalid_at"]
    # 软删后默认读路径不可见
    assert fb_gm_singleton.get_entity("e1") is None
    gwp._write_proxy_instance = None
```

> 实现者注意：本测试聚焦 proxy→GM 真实链路（executor 的 OPA/动作封装在 `test_action_service.py` 已覆盖）。若能便捷构造 `ActionServiceExecutor` 且其 OPA 校验可在测试中放行，可再加一条从 `executor.execute(delete_action)` 起的完整链路；否则以 proxy→GM 真实链路满足规则 14 #6（不 mock SUT）。`_get_graph_manager` 如何取单例以 `graph_write_proxy.py:40` 真实实现为准。

- [ ] **Step 2: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/test_soft_delete_end_to_end.py -q --no-header -p no:cacheprovider`
Expected: PASS（1 passed）——若失败，说明 proxy 单例缓存了旧的 unavailable GM，按 `_get_graph_manager` 真实逻辑调整单例重置方式。

- [ ] **Step 3: 提交**

```bash
git add apps/api/tests/unit/test_soft_delete_end_to_end.py
git commit -m "test(graph): 软删除端到端真实链路测试（proxy→fallback GM，不 mock SUT）"
```

---

## Task 9: 全量回归 + 文档同步（ADR + DESIGN.md）

**Files:**
- Create: `docs/07-adr/ADR-0XX-graph-entity-soft-delete.md`（编号取 `docs/07-adr/README.md` 现有最大值 +1）
- Modify: `docs/07-adr/README.md`（索引 + 时间线）
- Modify: graph 模块 DESIGN.md（`docs/03-modules/` 下图谱相关目录）与 decision/action_service DESIGN.md 的删除语义
- Modify: `agents.md`（若删除 API 行为变化，更新对应章节/速查表）

**Interfaces:** 无代码接口；纯文档。

- [ ] **Step 1: 全量离线回归**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest apps/api/tests/unit/ -q --no-header -p no:cacheprovider`
Expected: PASS（全绿；若有失败，先定位是否本次读路径过滤引入的回归，修复后再继续）

- [ ] **Step 2: 架构契约 lint（若 CI 配置了 import-linter）**

Run: `PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run lint-imports` （从仓库根；命令以 `pyproject.toml [tool.importlinter]` 为准）
Expected: PASS（`_soft_delete` 属 infra/graph 内部私有模块，不新增跨层依赖）

- [ ] **Step 3: 写 ADR**

新建 `docs/07-adr/ADR-0XX-graph-entity-soft-delete.md`，内容涵盖：
- **Context**：图谱实体删除能力全栈为零；双时态 KG 需保留历史。
- **Decision**：软删除为默认——节点/边打 `invalid_at`（ISO-8601 UTC 字符串），级联失效关系边，读路径默认排除失效实体（`include_deleted` opt-in），`state_at` 语义 = `valid_time <= vt < invalid_at`；共享谓词真源 `_soft_delete.py`；`GraphWriteProxy` 为唯一合规删除通道（结构化审计经 `graph_audit`）。
- **Consequences**：正向——保留双时态历史、图一致无悬空边、删除可审计；负向——~15 处读路径需持续维护活跃谓词（已收敛到共享常量）、Graphiti 向量检索（EntityEdge fact 层）不联动软删（已知边界，属"事实曾成立"语义）。
- **Alternatives**：硬删（否决，摧毁历史）；`:Deleted` 标签（否决，丢失失效时刻，as-of 无法回溯）。
- 链接 spec：`docs/superpowers/specs/2026-09-28-soft-delete-entity-design.md`。

- [ ] **Step 4: 更新 ADR 索引与模块 DESIGN.md**

- `docs/07-adr/README.md`：索引表加新 ADR 行 + 时间线条目。
- graph 模块 DESIGN.md：新增"实体软删除语义"小节（`delete_entity` 接口契约、读路径过滤、时态 as-of）。
- decision/action_service DESIGN.md：删除动作由"恒失败"更新为"经 GraphWriteProxy 软删成功"。

- [ ] **Step 5: 提交**

```bash
git add docs/07-adr/ADR-0XX-graph-entity-soft-delete.md docs/07-adr/README.md docs/03-modules/ agents.md
git commit -m "docs(adr): 图谱实体软删除语义 ADR + 模块 DESIGN 同步（规则 12）

- 新建 ADR 记录 invalid_at 软删 + 级联边失效 + 读侧过滤决策
- 更新 docs/07-adr/README.md 索引与时间线
- 同步 graph / action_service DESIGN.md 删除语义与接口契约"
```

---

## Self-Review（writing-plans 自检）

**1. Spec 覆盖**：spec §4.1 标记约定→Task 1；§4.2 共享工具→Task 1；§4.3 delete_entity→Task 2；§4.4 读路径过滤（Neo4j ~10 处 + fallback 5 处）→Task 3/4；§4.5 时态→Task 5；§4.6 调用方接通（proxy→Task 6，execution_tool→Task 7，executor 代码不变由 Task 8 守护）；§7 测试策略（含端到端真实链路）→Task 2/3/8；§9 文档同步→Task 9。§8 范围外（delete_by_batch/缓存既有 bug/裸 GM add-update/OPA 注册/向量联动/硬删）均未纳入，符合 spec。✅

**2. 占位符扫描**：无 TBD/TODO；每个 code step 含真实代码；Cypher 谓词、方法签名、返回结构均为具体值。Neo4j `_get_neighbors_neo4j`/`_traverse_neo4j` 的边级过滤因 pattern 变量名依赖真实代码，已明确标注"实现者按实际 pattern 变量名调整"并给出谓词形态，非占位。✅

**3. 类型一致性**：`delete_entity` 返回结构在 Task 2（定义）、Task 6（proxy 透传）、Task 7（execution_tool 消费）、Task 8（端到端断言）四处字段名一致（`status/entity_id/entities_invalidated/relations_invalidated/invalid_at`）；`get_entity(include_deleted=)` 在 Task 3（fallback）、Task 4（Neo4j）签名一致；`_soft_delete` 导出名在 Task 1（定义）与 Task 2/3/4（消费）一致。✅

**4. 歧义检查**：Neo4j 分支幂等 no-op 的 `entities_invalidated` 语义已在 Task 2 Step 3 显式说明（fallback 以前置 `is_active` 判定为准，Neo4j 以 `WHERE invalid_at IS NULL` 保证不重复写）；时态字符串比较前提（ISO-8601 等长）已注明。✅
