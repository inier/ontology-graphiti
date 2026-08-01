# 设计文档：MdlEngine/Chain 推理结论持久化到 USL Candidate 表（HITL 飞轮）

**Branch**: `008-semantic-retrieval-bus`
**Date**: 2026-08-01
**Status**: Design（待用户审查 → writing-plans）
**关联**: spec 008 FR-004 / 007 semantic-admin-suite HITL 飞轮 / data-model §2.2

---

## 1. 背景与目标

### 1.1 问题

008 语义检索总线已完成 7 端点 REST + 7 工具 MCP 暴露（Phase 1-7），但 `/chain`（ChainEngine）和 `/mdl`（MdlEngine）的推理结论目前仅在内存返回，不落盘。推理产物无法进入 007 semantic-admin-suite 的 HITL 飞轮（DRAFT → 质检 → 评审 → 写回）进行人工校验和沉淀。

### 1.2 目标

让推理结论通过 opt-in 参数持久化到 `usl_schema_candidates` 表，进入 HITL 飞轮，不破坏现有 Thin Adapter 设计。

### 1.3 非目标

- 不改动 `MdlEngine`/`ChainEngine` 的推理逻辑（保持纯计算 Thin Adapter）
- 不改动 `SQLiteCandidateStorage` 的存储实现（复用已有 `bulk_insert_candidates`）
- 不实现 HITL 评审 UI（由 007 admin suite 已有页面承载）
- 不做推理结论去重（每次推理新建 candidates，HITL 自行处理）

---

## 2. 设计决策（4 项）

| # | 决策点 | 选择 | 理由 |
|---|--------|------|------|
| D1 | 触发条件 | **opt-in 参数** `persist_candidates=True/False`，默认 `False` | 避免检索时大量临时查询污染 Candidate 表；需要沉淀 HITL 时显式开启 |
| D2 | origin/status | `origin=llm`, `status=DRAFT` | 复用现有枚举；推理产物源自 LLM/规则链；DRAFT 是状态机起点，让 HITL 飞轮完整走一遍 |
| D3 | 映射粒度 | **主结论 + 关键节点**（方案 C） | 平衡可追溯与噪声；跳过 init/input==output 的占位步骤；parent_candidates_json 串成链 |
| D4 | 持久化层 | **独立 ReasoningPersistenceService**（方案 C） | engine 保持纯计算；service 层编排；MCP/REST 共用；单一职责可测 |

---

## 3. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│  调用层（MCP tools / REST routes）                            │
│    ontology_reason / ontology_mdl  +  persist_candidates     │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  RetrievalService（编排层，已有）                              │
│    reason(persist_candidates=False)                          │
│      ├─ engine.reason()          → reasoning dict（不变）     │
│      ├─ [新增] if persist_candidates:                         │
│      │     persistence.persist(reasoning, ws_id)             │
│      └─ return reasoning + candidates_meta                   │
└──────┬───────────────────────────┬──────────────────────────┘
       ↓                           ↓
┌──────────────────┐    ┌─────────────────────────────────────┐
│  MdlEngine       │    │  ReasoningPersistenceService（新增）  │
│  ChainEngine     │    │    ├─ _map_chain_to_candidates()     │
│  (不变，纯计算)   │    │    ├─ _map_mdl_to_candidates()       │
│                  │    │    ├─ _ensure_pipeline_run()         │
└──────────────────┘    │    └─ storage.bulk_insert()          │
                        └──────────────┬──────────────────────┘
                                       ↓
                        ┌─────────────────────────────────────┐
                        │  SQLiteCandidateStorage（已有，不改） │
                        │    usl_schema_candidates 表          │
                        └─────────────────────────────────────┘
```

**关键边界**：
- `MdlEngine`/`ChainEngine`：**零改动**（保持纯计算 Thin Adapter）
- `RetrievalService`：**小改**（新增 `persistence` 依赖 + `persist_candidates` 参数透传）
- `ReasoningPersistenceService`：**新建**（映射 + 写库逻辑，独立可测）
- `SQLiteCandidateStorage`：**零改动**（复用 `bulk_insert_candidates` / `create_pipeline_run`）
- MCP handlers / REST routes：透传 `persist_candidates` 参数（1 行小改）

---

## 4. 组件细节

### 4.1 新建：`ReasoningPersistenceService`

**位置**：`apps/api/odap/biz/core/ontology/semantic_retrieval/impl/reasoning_persistence_service.py`

**职责**：把 `reasoning` dict 映射为 candidate 记录并写库，单一职责、独立可测。

**公共 API**：
```python
class ReasoningPersistenceService:
    """推理结论 → USL Candidate 持久化（HITL 飞轮入口）。

    - opt-in 触发：仅 RetrievalService 显式调用时执行
    - 映射规则：chain 主结论+关键节点；mdl extraction.entities
    - 容错：写库异常不阻断推理返回（fire-and-forget + 日志）
    - 所有函数体 ≤ 40 行（Constitution I）
    """

    def __init__(self, candidate_storage: SQLiteCandidateStorage):
        self._storage = candidate_storage

    def persist(
        self, reasoning: Dict[str, Any], workspace_id: str
    ) -> Dict[str, Any]:
        """映射 reasoning → candidates 并写库，返回 {run_id, persisted_count, candidate_ids}。"""
```

**返回契约**：
- 成功：`{"run_id": "run-xxx", "persisted_count": 3, "candidate_ids": [...]}`
- 跳过：`{"persisted_count": 0, "skipped_reason": "..."}`
- 异常：由调用方 `_safe_persist` catch，返回 `{"persisted_count": 0, "error": "..."}`

### 4.2 映射规则

#### 4.2.1 chain 推理（方案 C：主结论 + 关键节点）

**过滤规则**：跳过 `rule_id="init"` 或 `input==output` 的步骤。

```
steps = [s0(init,A→A), s1(r1,A→B), s2(r2,B→B), s3(r3,B→C), s4(r4,C→D)]
                                ↑ 跳过(input=output)           ↑ 主结论

→ 落盘 3 条 candidate:
  #1 canonical=B, parent=[],           step_index=1
  #2 canonical=C, parent=[#1.id],      step_index=3  (s2 跳过)
  #3 canonical=D, parent=[#2.id],      step_index=4  (主结论)
```

**candidate 字段映射**：
```python
{
    "id": str(uuid.uuid4()),
    "run_id": run_id,                          # _ensure_pipeline_run 返回
    "canonical": step["output"],               # 推理得到的新术语/概念
    "en": "",
    "semantic_type": "对象类型",                # 默认（推理产物无明确类型）
    "synonyms": [step["input"]],               # 输入作为近义（可追溯）
    "aliases": [],
    "origin": "llm",
    "cluster_confidence": 0.0,
    "usl_align_confidence": 0.0,
    "review_confidence": reasoning.confidence, # 整条推理置信度
    "status": "DRAFT",
    "confidence": reasoning.confidence,
    "parent_candidates": [prev_cand_id],       # 前一关键节点的 candidate_id
    "provenance": {
        "source": "reasoning",
        "engine_mode": "chain",
        "chain_id": reasoning.chain_id,
        "step_id": step.step_id,
        "rule_id": step.rule_id,
        "step_index": idx,
        "duration_ms": step.duration_ms,
        "cycle_aborted": reasoning.cycle_detected,
        "truncated": <bool>                    # 是否因 max_depth 截断
    }
}
```

#### 4.2.2 mdl 推理

**candidate 字段映射**：
```python
{
    "id": str(uuid.uuid4()),
    "run_id": run_id,
    "canonical": entity["text"] or entity["name"],
    "en": entity.get("en", ""),
    "semantic_type": entity.get("type", "对象类型"),
    "synonyms": entity.get("aliases", []),
    "aliases": [],
    "origin": "llm",
    "cluster_confidence": 0.0,
    "usl_align_confidence": 0.0,
    "review_confidence": reasoning.confidence,
    "status": "DRAFT",
    "confidence": reasoning.confidence,
    "parent_candidates": [],
    "provenance": {
        "source": "reasoning",
        "engine_mode": "mdl",
        "chain_id": reasoning.chain_id,
        "template": reasoning.template,
        "entity_index": idx
    }
}
```

**特殊情形**：
- `status=degraded` → 不落盘（避免低价值记录污染）
- `cycle_detected=true` → 仍落盘已完成的关键节点，`provenance.cycle_aborted=true`
- mdl 无 extraction（parse-only 降级）→ 不落盘
- chain 起点 `s0`（rule_id="init"）→ 跳过

### 4.3 修改：`RetrievalService`

**改动范围**：构造函数新增可选 `persistence` 依赖；`reason()` 新增 `persist_candidates` 参数。

```python
class RetrievalService:
    def __init__(self, ..., persistence: Optional[ReasoningPersistenceService] = None):
        self._persistence = persistence            # 新增（可选）

    async def reason(self, workspace_id, *, query, mode="chain",
                     rules=None, max_depth=5,
                     persist_candidates: bool = False):   # 新增参数
        engine = self._resolve_reason_engine(mode)
        result = await engine.reason(workspace_id, query=query, ...)
        if persist_candidates and self._persistence:
            meta = self._safe_persist(result, workspace_id)
            result["candidates_meta"] = meta
        return result

    def _safe_persist(self, result, ws_id):
        """持久化失败不阻断推理返回（fire-and-forget + 日志）。"""
        try:
            return self._persistence.persist(result, ws_id)
        except Exception as exc:
            logger.warning("推理结论持久化失败: %s", exc)
            return {"persisted_count": 0, "error": str(exc)}
```

### 4.4 不改动的组件

- **`MdlEngine`** / **`ChainEngine`**：零改动，纯计算
- **`SQLiteCandidateStorage`**：零改动，复用 `bulk_insert_candidates` / `create_pipeline_run`
- **MCP handlers / REST routes**：透传 `persist_candidates` 参数（1 行小改）

---

## 5. 数据流

### 5.1 端到端调用流（`/chain` + `persist_candidates=true`）

```
客户端
  │ POST /api/v1/ontology/reason
  │   {query: "A 推理到 D", mode: "chain", persist_candidates: true}
  ↓
REST route (routes.py)
  │ svc.reason(ws_id, query, mode="chain", persist_candidates=True)
  ↓
RetrievalService.reason()
  │ 1. engine = self._chain_engine
  │ 2. result = await engine.reason(ws_id, query=query)   ← 纯计算，不变
  │      → {mode:"chain", reasoning:{chain_id, steps[], status, confidence, ...}}
  │ 3. if persist_candidates and self._persistence:
  │      meta = self._safe_persist(result, ws_id)
  │ 4. result["candidates_meta"] = meta
  │ 5. return result
  ↓
ReasoningPersistenceService.persist(reasoning, ws_id)
  │ a. 检查 status != "degraded" → 否则 skip
  │ b. _map_chain_to_candidates(reasoning, ws_id)
  │      steps = [s0(init,A→A), s1(r1,A→B), s2(r2,B→B), s3(r3,B→C), s4(r4,C→D)]
  │      过滤: s0(rule=init), s2(input==output) → 跳过
  │      保留: s1, s3, s4
  │      构建 3 条 candidate:
  │        #1 canonical=B, parent=[],           step_index=1, chain_id
  │        #2 canonical=C, parent=[#1.id],      step_index=3, chain_id
  │        #3 canonical=D, parent=[#2.id],      step_index=4, chain_id (主结论)
  │ c. run_id = _ensure_pipeline_run(ws_id, reasoning)
  │      → 新建 usl_pipeline_runs 记录
  │      → source_type="reasoning", triggered_by="reasoning_persist"
  │ d. inserted = _safe_bulk_insert(candidates, run_id)
  │      → SQLiteCandidateStorage.bulk_insert_candidates(cands)
  │      → 写入 usl_schema_candidates 表（status=DRAFT, origin=llm）
  │ e. return {run_id, persisted_count:3, candidate_ids:[#1,#2,#3]}
  ↓
RetrievalService 拼装返回:
  {
    "mode": "chain",
    "reasoning": {chain_id, steps[], status, confidence, ...},
    "warnings": [],
    "total": 5,
    "candidates_meta": {                    ← 新增字段
      "run_id": "run-xxx",
      "persisted_count": 3,
      "candidate_ids": ["cand-1","cand-2","cand-3"]
    }
  }
```

### 5.2 Pipeline Run 策略

**每次推理新建 run**（不复用）：
- `source_type="reasoning"`（标记推理产物来源）
- `triggered_by="reasoning_persist"`
- `doc_sources_json=[]`（推理无文档来源）
- `stats_json={"engine_mode":"chain", "chain_id":"chain-xxx", "step_count":5}`

这样在 Candidate 列表页可通过 `run_id` 查出整条推理的所有 candidates，HITL 评审时可按批次处理。

### 5.3 `candidates_meta` 字段契约

无论持久化成功/失败/跳过，`candidates_meta` 始终存在（`persist_candidates=true` 时）：

```python
# 成功
{"run_id": "run-xxx", "persisted_count": 3, "candidate_ids": [...]}

# 跳过（degraded / 无 candidates / 未知 mode）
{"persisted_count": 0, "skipped_reason": "reasoning degraded, skip persist"}

# 异常（写库失败，不阻断推理）
{"persisted_count": 0, "error": "sqlite3.OperationalError: ..."}
```

---

## 6. 错误处理

### 6.1 容错原则：持久化失败不阻断推理返回

推理是主路径，持久化是副作用。用户要的是推理结果，持久化失败不应让推理请求报错。

| 错误场景 | 处理 | 返回 |
|---------|------|------|
| `reasoning.status == "degraded"` | 跳过持久化 | `candidates_meta.skipped_reason` |
| 未知 `mode`（非 chain/mdl） | 跳过 | `candidates_meta.skipped_reason` |
| 无有效 candidates（steps 全被过滤） | 跳过 | `candidates_meta.skipped_reason` |
| `_ensure_pipeline_run` 失败（DB 锁/磁盘满） | catch + log + 不阻断 | `candidates_meta.error` |
| `bulk_insert_candidates` 部分失败 | catch + log + 不阻断 | `candidates_meta.error` |
| storage 未注入（`self._persistence is None`） | 静默跳过 | 无 `candidates_meta` 字段 |

### 6.2 审计日志

遵循项目硬约束（dual-channel + 不记录明文）：

```python
# ReasoningPersistenceService._safe_bulk_insert 内
# SQLite 主通道：写入 audit_logs 表（已有）
# Graphiti 副通道：try/except 不阻断（已有模式）
# 不记录 reasoning 内容，仅记录统计指标
audit_payload = {
    "action": "reasoning_persisted",
    "run_id": run_id,
    "workspace_id": ws_id,
    "engine_mode": mode,
    "chain_id": chain_id,
    "candidate_count": len(inserted),   # 仅计数
    "step_count": len(steps),           # 仅计数
    # 不记录 canonical/step.output 等明文
}
```

### 6.3 边界情形

| 情形 | 处理 |
|------|------|
| `cycle_detected=true` | 仍持久化已完成的关键节点，`provenance.cycle_aborted=true` |
| `max_depth` 截断 | 仍持久化已执行的节点，`provenance.truncated=true` |
| `persist_candidates=true` 但 MCP 工具调用 | MCP handler 透传参数，路径一致（FR-010） |
| 重复推理同一 query | 每次新建 run + 新 candidates（不去重，HITL 自行处理） |
| `confidence=0.0`（degraded 但 status 标 ok 的边界） | 仍持久化，confidence 写入 candidate 字段 |

---

## 7. Sandbox 验证策略

### 7.1 Sandbox 隔离原则

遵循项目测试约定（`test_semantic_admin_candidate_store.py` 注释明确）：
- **SQLite 用 tmp_path 真实 DB，严禁 MagicMock 模拟存储层**
- 每个测试用例用独立临时 DB，互不污染
- 集成测试用 FakeService 隔离真实引擎，不启动 HTTP 服务器

### 7.2 Sandbox 应用层级

| 层级 | Sandbox 机制 | 验证目标 |
|------|-------------|----------|
| **单元测试** | `tmp_path / "test.db"` 真实 SQLite + 直接构造 `ReasoningPersistenceService` | 映射规则正确性、容错、边界 |
| **集成测试** | `tmp_path` DB + `FakeEngine`（返回固定 reasoning dict）+ 真实 `RetrievalService` | service 编排、参数透传、`candidates_meta` 契约 |
| **回归测试** | 现有测试不改动（默认 `persist_candidates=False`） | 确保不破坏现有功能 |

### 7.3 Sandbox Fixtures

```python
# tests/unit/test_reasoning_persistence_service.py

@pytest.fixture
def sandbox_storage(tmp_path: Path) -> SQLiteCandidateStorage:
    """Sandbox：独立临时 DB，测试间互不污染。"""
    db = tmp_path / "reasoning_persist_test.db"
    return SQLiteCandidateStorage(db_path=str(db))

@pytest.fixture
def persistence_service(sandbox_storage) -> ReasoningPersistenceService:
    return ReasoningPersistenceService(sandbox_storage)

@pytest.fixture
def sample_chain_reasoning():
    """5 步推理（含 init + 1 个 input==output 占位 + 3 个关键节点）。"""
    return {
        "mode": "chain",
        "reasoning": {
            "chain_id": "chain-test123",
            "steps": [
                {"step_id":"s0","rule_id":"init","input":"A","output":"A","duration_ms":0},
                {"step_id":"s1","rule_id":"r1","input":"A","output":"B","duration_ms":50},
                {"step_id":"s2","rule_id":"r2","input":"B","output":"B","duration_ms":50},
                {"step_id":"s3","rule_id":"r3","input":"B","output":"C","duration_ms":50},
                {"step_id":"s4","rule_id":"r4","input":"C","output":"D","duration_ms":50},
            ],
            "status": "ok",
            "confidence": 0.85,
            "cycle_detected": False,
            "conflicts": [],
        },
        "warnings": [],
        "total": 5,
    }

@pytest.fixture
def sample_mdl_reasoning():
    return {
        "mode": "mdl",
        "reasoning": {
            "chain_id": "mdl-test456",
            "template": "entity_extract_v1",
            "entity": "测试实体",
            "status": "ok",
            "confidence": 0.75,
            "extraction": {
                "entities": [
                    {"text": "公司A", "type": "对象类型", "aliases": ["A公司"]},
                    {"text": "产品B", "type": "对象类型", "aliases": []},
                ],
                "relations": [],
            },
        },
        "warnings": [],
        "total": 1,
    }
```

### 7.4 Sandbox 验证检查点

每个测试用例需验证：
1. **DB 隔离**：测试前后 DB 表行数符合预期（无残留）
2. **字段完整性**：写入的 candidate 字段（canonical/origin/status/provenance）与映射规则一致
3. **链路追溯**：`parent_candidates_json` 正确指向前一关键节点的 candidate_id
4. **审计无明文**：`audit_logs` 表中 payload 仅含计数，不含 canonical/step.output
5. **容错不阻断**：模拟 DB 异常时，`persist()` 不抛出，返回 `error` 字段

---

## 8. 测试策略

### 8.1 TDD 三层测试

| 层级 | 文件 | 测试数 | 关注点 |
|------|------|-------|--------|
| **单元** | `tests/unit/test_reasoning_persistence_service.py`（新建） | ~8 | 映射规则、容错、边界 |
| **集成** | `tests/integration/test_reasoning_persistence_integration.py`（新建） | ~4 | RetrievalService + persistence 端到端 |
| **回归** | 现有 `test_semantic_retrieval_*.py` | 0 改动 | 确保不破坏现有（默认 `persist_candidates=False`） |

### 8.2 单元测试用例（`ReasoningPersistenceService`）

```
T-PERS-1: chain 推理 → 关键节点过滤（s0/s2 跳过，s1/s3/s4 落盘）
T-PERS-2: mdl 推理 → extraction.entities 各落 1 条
T-PERS-3: status=degraded → 跳过持久化，返回 skipped_reason
T-PERS-4: 未知 mode → 跳过，返回 skipped_reason
T-PERS-5: steps 全被过滤（仅 init）→ 跳过，返回 skipped_reason
T-PERS-6: bulk_insert 异常 → 不抛出，返回 error，推理结果正常返回
T-PERS-7: parent_candidates_json 链路正确（#2.parent 指向 #1.id）
T-PERS-8: provenance_json 含 chain_id/step_index/engine_mode/cycle_aborted
```

### 8.3 集成测试用例（`RetrievalService` 端到端）

```
T-INT-1: RetrievalService.reason(persist_candidates=True) → candidates_meta 存在
T-INT-2: RetrievalService.reason(persist_candidates=False) → 无 candidates_meta（回归）
T-INT-3: 持久化失败 → 推理结果仍返回 + candidates_meta.error
T-INT-4: MCP handler 透传 persist_candidates → 结果与 REST 一致（FR-010）
```

### 8.4 Constitution I 合规

- `ReasoningPersistenceService` 每个方法 ≤40 行（映射逻辑拆分）
- `RetrievalService.reason` 新增逻辑 ≤5 行（透传 + `_safe_persist`）
- 无单实现接口（`ReasoningPersistenceService` 是具体类，非 interface）

---

## 9. 实现文件清单

### 9.1 新建文件（2 个）

| 文件 | 用途 |
|------|------|
| `apps/api/odap/biz/core/ontology/semantic_retrieval/impl/reasoning_persistence_service.py` | 持久化服务（映射 + 写库） |
| `apps/api/tests/unit/test_reasoning_persistence_service.py` | 单元测试（8 用例） |

### 9.2 修改文件（3 个）

| 文件 | 改动 |
|------|------|
| `apps/api/odap/biz/core/ontology/semantic_retrieval/impl/retrieval_service.py` | 构造函数加 `persistence` 依赖；`reason()` 加 `persist_candidates` 参数 |
| `apps/api/odap/biz/core/ontology/semantic_retrieval/api/routes.py` | `/chain` 和 `/mdl` 路由透传 `persist_candidates` |
| `apps/api/odap/biz/core/ontology/mcp/semantic_retrieval_tools.py` | `ontology_reason`/`ontology_mdl` handler 透传 `persist_candidates` |

### 9.3 可选新建文件

| 文件 | 用途 |
|------|------|
| `apps/api/tests/integration/test_reasoning_persistence_integration.py` | 集成测试（4 用例） |

---

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 推理产生大量 candidates 污染表 | 中 | 中 | opt-in 默认关闭；关键节点过滤减少数量 |
| parent_candidates_json 链路断裂 | 低 | 中 | 单测 T-PERS-7 专门验证链路完整性 |
| MCP 与 REST 持久化不一致 | 低 | 高 | 共用 RetrievalService；集成测试 T-INT-4 验证 FR-010 |
| 持久化异常阻断推理 | 低 | 高 | `_safe_persist` try/except 兜底；单测 T-PERS-6 验证 |
| 审计日志记录明文 | 低 | 高 | 审计 payload 仅含计数；sandbox 验证检查点 4 专测 |

---

## 11. 后续演进（YAGNI 边界）

本设计**不包含**以下内容，留待后续按需实现：
- 推理结论去重（查 USL 库判断是否已存在）
- 批量推理持久化（一次调多个 reasoning）
- HITL 评审 UI 集成（由 007 admin suite 已有页面承载）
- 推理结论质量评分（G1/G2/G3 质检闸自动触发）
- 推理结论自动写回图谱（WRITTEN_BACK 状态）

---

## 附录 A：决策对话记录

1. **触发条件** → A（opt-in 参数，默认 False）
2. **origin/status** → A（origin=llm, status=DRAFT）
3. **映射粒度** → C（主结论 + 关键节点，跳过 init/input==output）
4. **持久化层** → C（独立 ReasoningPersistenceService，service 层编排）
