---
id: odap.l15.specs-2026-10-09-subproject-c-ontology-semantics-tool-design
status: reference
owner: architect
version: ''
layer: L15
concern: design-spec-record
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: superpowers 设计规格存档，结论已落 ADR 或代码，规格本身冻结
governance_evidence: docs/07-adr/README.md 各 ADR 的 specs 引用（如 ADR-087 引用 2026-10-07-semantic-drift-detection-design）
---

# 子项目 C · `ontology_semantics` MCP 工具——按需查询替代全量注入

- **状态**：**已实施**（v2，2026-10-09 纳入用户三项指示；已按本 spec 以 TDD 落地，见 ADR-089「Status & Verification」）
- **日期**：2026-10-09
- **对应 ADR**：ADR-089（开工前落稿，规则 12）
- **来源 spec**：`docs/superpowers/specs/2026-10-08-evoontology-adoption-design.md` §4.3
- **承接**：ADR-088 子项目 A 已让 `EntityExtractor` 知道「缺什么」（attribution），但它仍然走全量注入「拿全部上下文」。本 spec 把它改成「按需查询」。

## v2 修订说明（用户 2026-10-09 指示）

用户指示：**「支持界面显示切换，有一个默认 mode」** + **「不能按简单方式走，要考虑功能的完整性和可用性」**。据此本版修订：

- 提取模式（`inject` / `query`）从「仅代码配置」升级为**运行时可切换的受管配置**：存入既有 `sa_config`（scope `entity_extractor`，key `mode`），提供**专用便利端点** + **前端切换界面**，无需重启、无需改代码。
- 默认 mode = `query`（详见 C-D3）。
- 切换界面须体现「完整性 + 可用性」：显示当前生效 mode、可选 mode 及语义说明、最近修改人/时间、切换影响提示（是否需要重跑回归集）。

## 背景

`EntityExtractor`（`intent_recognizer.py:106-194`）目前的工作模式是：

1. `set_entity_context(term_resolver, entity_set)` 在理解层入口一次性注入
2. `_normalize_entity` 调 `term_resolver.resolve(entity, domain_id)` 查 USL 字典
3. `canonical in entity_set` 做集合过滤

### ⚠️ as-built 修正（本轮勘验，规则 14 诚实注记）

**`set_entity_context` 在整个 `biz/` 中从未被调用**（仅定义处出现，全仓 grep 确认）：

- `UnderstandingStage.__init__` 构造 `EntityExtractor(llm_client)`，**不传** `term_resolver`/`entity_set`
- `QueryPipeline.__init__` 构造 `UnderstandingStage(llm_client)`，也不注入
- 因此 `_normalize_entity` 走「两者皆 None → 返回原词」分支：**生产实际是「原词直通」，USL 归一化与幻觉过滤是未接线的死代码**
- 后果：`intent_recognizer.py:163` 的 MAPPING_FAILURE 缺口信号**在生产永不触发**（该分支仅在 context 注入时可达）

这重塑了子项目 C 的定义：它不只是「把注入换成查询」，而是**让按需实体上下文在生产真正可用**——用按需查询开启归一化 + 幻觉过滤，而无需预加载全量字典。

`extracted_entities` 下游消费勘验（决定行为变更风险）：仅 `audit_storage`（记录）+ `query_pipeline.py:238-239`（拼一句 prompt 文本），**不参与 Cypher 生成或检索执行**。故开启归一化对检索结果的影响面小、可控。

EvoOntology 论文（arXiv 2609.15779）的核心论点之一是「查询优于注入」：注入式上下文每次调用付全额 token，且受上下文窗口封顶；放到工具后面只付 agent 真正问的那部分。

论文自承的空白：「没做 cost accounting」——所以本 spec 必须自带成本对账。

## 已锁定决策表

| 编号 | 决策 | 理由 |
|------|------|------|
| C-D1 | 新增 `ontology_semantics` MCP 工具，复用现有 7 工具注册模式（`mcp/semantic_retrieval_tools.py:223-261`） | 不另造注册机制，FR-010「MCP 工具结果与 REST 完全一致」自然延伸 |
| C-D2 | 工具签名 `(expression, domain_id, kinds) → {content, schema, tool, cost}` | 三层映射（schema/content/tool）镜像 EvoOntology 主张；`kinds` 允许 caller 只查 content（快路径） |
| C-D3 | `EntityExtractor` 改**三模式** `off`/`inject`/`query`，**默认 `query`**；mode 为运行时受管配置（C-D11），可在界面切换 | `off`=历史行为（原词直通，可回滚）；`inject`=预加载对照；`query`=按需查询（默认） |
| C-D4 | 复用现有 `RetrievalService.nl_search`（content）+ `.search`（schema/tool），不新建引擎 | 引擎能力已存在，缺的是「按 entity 维度组装」；C3 契约禁止深插 ontology_api |
| C-D5 | 每次调用产 `cost_json`（`{llm_tokens_in, llm_tokens_out, round_trips, cache_hits, wall_ms, error?}`），落不可变 `cost_audit` 表；regression 报告对比 inject/query 均摊成本 | 补论文自承空白；与 ADR-088「paired 报告含 cost」纪律一致 |
| C-D6 | handler **失败降级**（不 raise、`cost.error` 显式记录）；`EntityExtractor` 客户端侧再兜底走原词 | 规则 14「失败显式兜底可观测」；理解层不能因工具暂时不通而断流 |
| C-D7 | HTTP 诊断端点 `/api/ontology/mcp/semantics`（POST） | 镜像现有 7 工具 REST 风格；给诊断/手验/离线 benchmark 用 |
| C-D8 | `ontology_semantics` 是第 8 个工具，既有 7 个契约零变化 | 避免牵动 OpenHarness 消费方 |
| C-D9 | `cost_audit` 表不可变（只 INSERT） | 「报告即不可变证据」纪律延伸 |
| C-D10 | 缓存层只在 `EntityExtractor` 内部（per-extract 内存）；MCP 工具本身不缓存 | 防幽灵一致性；贴近论文的无状态 query 假设 |
| **C-D11** | **mode 存 `sa_config`（scope=`entity_extractor`, key=`mode`），值 ∈ {`off`,`inject`,`query`}；提供专用端点 `GET/PUT /api/semantic-admin/extractor-mode`** | 复用既有动态配置底座；专用端点承载 `available_modes`/`default_mode`/语义说明/校验，避免前端硬编码 |
| **C-D12** | **前端 `ExtractorModeCard` 切换界面（Segmented 三选一），挂载于缺口统计页（`GapStatsPage`）顶部**；显示当前生效 mode、可选 mode 语义、最近修改人/时间、切换后提示 | 提取模式直接决定 mapping_failure 缺口如何产生，缺口页是其效果观测点，语义自洽；不改动 7 个顶层 Tab 不变量 |
| **C-D13** | **mode 读取为「配置优先 + 环境变量兜底 + 代码默认」三级**：`sa_config` > `EXTRACTOR_MODE` env > `query`。`set_entity_context` 未显式传 mode 时按此解析 | 配置未初始化也能工作；兼容测试/容器两种部署 |
| **C-D14** | **接线 `UnderstandingStage`**：`__init__` 调 `self.entity_extractor.set_entity_context(mode=resolve_extractor_mode())`，使 `query` 模式在生产生效（启用归一化 + 幻觉过滤）。`off` 模式保持原词直通（= 历史行为，可回滚） | 这是本子项目**真正的价值交付**——让按需上下文在生产可用；且默认 `query` 意味着这是一处**有意的、可配置的行为变更**（spec 显式登记） |

## 关键事实（实施前必看）

| 事实 | 来源 |
|------|------|
| 现有 7 工具注册模板 `register_all()`，handler 是 `async (dict) -> dict` | `mcp/semantic_retrieval_tools.py:223-261` |
| `RetrievalService.nl_search` 已实现 USL 消歧 → content 层直接复用 | `services/retrieval_service.py:94` |
| `RetrievalService.search(mode="auto")` 路由到合适引擎 → schema/tool 层用 | `services/retrieval_service.py:65` |
| `sa_config` 已有通用 CRUD：`GET/PUT/DELETE /api/semantic-admin/config/{scope}/{key}`（`verify_admin` 守 PUT）；`SaConfigService.set_config/get_config` | `sa_config/api/routes.py:59-113`；`sa_config/services/sa_config_service.py:13-47` |
| `SaConfigEntry.config_value` 是 dict（可存 `{"value": "query"}`）；scope 自由字符串 | `sa_config/models/sa_config_entry.py:33-48` |
| 前端已有 `saConfigApi.ts`（listConfig/getConfig/setConfig） | `apps/web/src/modules/semantic-admin/services/saConfigApi.ts` |
| 前端 semantic-admin 有 7 个顶层 Tab（测试锁定 7）；gaps 是**子路由非 Tab** | `constants.tsx` / `AppRoutes.tsx:119-133` |
| C3 契约禁 `semantic_admin → ontology_api` 深插；`EntityExtractor` 在 `biz/data`，可经 public 门面调 retrieval | `apps/api/pyproject.toml:177` |
| `entity_set` 大小无量级数据；可视为「不到 1k 的字符串集合」 | 待 measure（验收 §） |
| **`set_entity_context` 在生产从未被调用**（全仓唯一出现处是定义）；`UnderstandingStage.__init__` 构造 `EntityExtractor(llm_client)` 不注入 | `intent_recognizer.py:120` 定义 / `:232` 构造 / `query_pipeline.py:35` |
| **`extracted_entities` 不参与 Cypher/检索**：仅 `audit_storage` 记录 + `query_pipeline.py:238-239` 拼 prompt 文本 | grep 全仓确认 |
| **MAPPING_FAILURE 缺口信号在生产永不触发**（仅 context 注入时可达） | `intent_recognizer.py:163`（ADR-088 接线，但入口未启用） |

## 设计

### 1. `ontology_semantics` MCP 工具

`mcp/semantics_tools.py`（与 `semantic_retrieval_tools.py` 同风格）：

```python
async def handler(args: dict) -> dict:
    expression: str = args["expression"]
    domain_id: str = args.get("domain_id", "")
    kinds: list[str] = args.get("kinds", ["content", "schema", "tool"])
    cost = _CostRecorder()
    out = {}
    if "content" in kinds:
        with cost.span("nl_search"):
            r = await _retrieval_service.nl_search(
                workspace_id=domain_id or "default", query=expression, limit=1)
        out["content"] = _extract_content(r)       # canonical / synonyms / near_synonyms
    if "schema" in kinds:
        with cost.span("object_type_probe"):
            r = await _retrieval_service.search(
                workspace_id=domain_id or "default",
                request=SearchRequest(query=expression, mode="graph", limit=5))
        out["schema"] = _extract_schema(r)         # object_type / properties / relation_types
    if "tool" in kinds:
        out["tool"] = _suggest_engines(expression)  # 该走哪个检索引擎
    out["cost"] = cost.snapshot()
    return out
```

每个 span 包 `try/except Exception → 记 cost.error，字段返回空`；handler 自身不 raise。

### 2. `EntityExtractor` 三模式 + 运行时配置 + 生产接线

`set_entity_context` 加 `mode` 参数（缺省 `None` → 走 C-D13 三级解析）：

```python
def set_entity_context(self, term_resolver=None, entity_set=None, *,
                        mode: Optional[str] = None) -> None:
    self.mode = mode or resolve_extractor_mode()   # C-D13: sa_config > env > 'query'
    if self.mode == "inject":
        self.term_resolver = term_resolver
        self.entity_set = entity_set
        self._semantics_provider = None
    elif self.mode == "query":
        self.term_resolver = None
        self.entity_set = None
        self._semantics_provider = SemanticsProvider(...)
        self._cache = {}       # per extract() 清空
    else:  # off
        self.term_resolver = None
        self.entity_set = None
        self._semantics_provider = None
```

`_normalize_entity` 三模式分派：

```python
def _normalize_entity(self, entity, domain_id=""):
    if self.mode == "off":
        return entity                        # 原词直通（历史行为）
    if self.mode == "inject":
        ...（旧逻辑：term_resolver + entity_set）
    # query
    if (entity, domain_id) in self._cache:
        return self._cache[(entity, domain_id)]
    try:
        r = self._semantics_provider.query(
            expression=entity, domain_id=domain_id, kinds=["content"])
    except ToolError as e:
        logger.warning("ontology_semantics 调用失败(%s): %s", entity, e)
        return entity                        # 客户端兜底
    canonical = r.get("content", {}).get("canonical")
    self._cache[(entity, domain_id)] = canonical
    return canonical                         # None → 触发 MAPPING_FAILURE 缺口信号
```

**生产接线（C-D14）**：`UnderstandingStage.__init__` 追加

```python
self.entity_extractor = EntityExtractor(llm_client)
self.entity_extractor.set_entity_context(mode=resolve_extractor_mode())
```

此举使 `query`（默认）在生产生效——**开启归一化 + 幻觉过滤，并使 MAPPING_FAILURE 缺口信号在归一化失败时真正触发**。`off` 模式保持原词直通（= 历史行为，可一键回滚）。

### 3. mode 受管配置（C-D11）

**存储**：`sa_config` scope=`entity_extractor`，key=`mode`，`config_value={"value": "query"|"inject"}`。

**解析器**（`odap/biz/data/qa/pipeline/understanding/extractor_mode.py`）：

```python
DEFAULT_MODE = "query"
AVAILABLE_MODES = ("off", "inject", "query")
MODE_DESCRIPTIONS = {
    "off":    "关闭归一化：实体原词直通（历史行为，可回滚）",
    "inject": "预加载全量 USL 字典 + 实体集合后注入（对照/兼容）",
    "query":  "按需查询本体（ontology_semantics 工具）：归一化 + 幻觉过滤（默认）",
}

def resolve_extractor_mode() -> str:
    """三级解析：sa_config > EXTRACTOR_MODE env > DEFAULT_MODE。读取失败按默认（规则14 warning）。"""
    v = _read_from_sa_config()            # 异常→None + warning
    if v in AVAILABLE_MODES:
        return v
    v = os.environ.get("EXTRACTOR_MODE")
    if v in AVAILABLE_MODES:
        return v
    return DEFAULT_MODE
```

**专用端点**（`sa_config/api/routes.py` 或新 `extractor_mode` 子路由，二选一——取后者以便独立 tag）：

```
GET  /api/semantic-admin/extractor-mode
     → {status, mode, effective_mode, default_mode, available_modes,
        descriptions: {query: "...", inject: "..."}, updated_by, updated_at}
PUT  /api/semantic-admin/extractor-mode   (verify_admin)
     body {mode: "query"|"inject", updated_by?}
     → 同 GET 响应 + status=ok；非法 mode → 400
```

`GET` 的 `mode` = 显式配置值（未配置则 null）；`effective_mode` = C-D13 解析结果（前端高亮「当前生效」）。**专用端点存在意义**：单点承载 `available_modes`/`default_mode`/描述/校验，前端不硬编码；切换后可返回「影响提示」（见 §4）。

### 4. 前端 `ExtractorModeCard`（C-D12）

- 位置：`GapStatsPage` 顶部一张 Card（不改 7 Tab 不变量）
- 内容：Radio/Segmented 切换（`query` = 按需查询（默认） / `inject` = 全量注入）；当前生效 mode 高亮；最近修改人 + 时间；每个 mode 一行语义说明；切换后 Alert 提示「模式已切换，建议在 12 小时内重跑缺口回归集以刷新 paired 报告（ADR-088）」
- 服务：新增 `extractorModeApi.ts`（get/set），或复用 `saConfigApi`；**取新增**（专用端点，返回结构更丰富）
- 权限：PUT 走 admin（后端已守）；前端无权限时按钮禁用 + tooltip

### 5. 成本对账

`cost_audit` 表（不可变，见 C-D5/C-D9）：

```sql
CREATE TABLE cost_audit (
    id TEXT PRIMARY KEY,
    call_kind TEXT NOT NULL,     -- 'ontology_semantics' | 'entity_extract'
    mode TEXT NOT NULL,          -- 'inject' | 'query'
    scope_key TEXT NOT NULL,
    expression TEXT,
    cost_json TEXT NOT NULL,     -- {llm_tokens_in, llm_tokens_out, round_trips, cache_hits, wall_ms, error?}
    model_id TEXT, prompt_version TEXT, recorded_at TEXT NOT NULL
);
```

`biz/data/qa/evaluation/compare_inject_vs_query.py`：同一批 query 分别以两 mode 跑，输出对比表 + 汇总。离线模式不接 LLM。

## 测试策略

| 编号 | 场景 | 期望 | 测试文件 |
|------|------|------|---------|
| E-1 | handler content 层 | 命中 USL 术语 → canonical + synonyms | `test_semantics_tool.py` |
| E-2 | handler schema 层 | object_type / properties / relation_types | 同上 |
| E-3 | `kinds=["content"]` | round_trips=1；无 schema 字段 | 同上 |
| E-4 | 检索服务不可达 | `cost.error` 非空；不 raise；三层字段空 | 同上 |
| E-5 | query 模式缓存命中 | 第二次 normalize 同 entity 不再调 tool | `test_entity_extractor_query_mode.py` |
| E-6 | query 模式 tool 失败 | 原词兜底 + warning | 同上 |
| E-7 | inject 模式行为不变 | 既有 `test_intent_recognizer.py` 零回归 | 全跑 |
| E-8 | `cost_audit` 落库 | 每调用一行；含 wall_ms | `test_cost_audit_storage.py` |
| E-9 | benchmark 对比脚本 | 离线不调 LLM；每 mode 一行汇总 | `test_compare_inject_vs_query.py` |
| E-10 | MCP 8 工具注册 | `register_all()` 返回 8 键；既有 7 不变 | `test_semantics_tool_registration.py` |
| E-11 | 既有 7 工具契约 | OpenAPI schema 不变 | 契约测试 |
| E-12 | 端到端 query 模式 | query → 命中 ontology → 提取正确 | `test_entity_extractor_e2e_query.py` |
| **E-13** | mode 三级解析 | sa_config 优先；无配置→env；无 env→query | `test_extractor_mode_resolver.py` |
| **E-14** | 专用端点 GET | 返回 available_modes(3)/default_mode/descriptions/effective_mode | `test_extractor_mode_routes.py` |
| **E-15** | 专用端点 PUT | 合法 mode 落 sa_config；非法 → 400；非 admin → 403 | 同上 |
| **E-16** | 切换后 `resolve_extractor_mode` 变化 | PUT 后 GET effective_mode 反映新值 | 同上 |
| **E-17** | 前端 `ExtractorModeCard` | 渲染 3 选项、切换调用 set、错误显示 | `ExtractorModeCard.test.tsx` |
| **E-18** | 生产接线（C-D14） | `UnderstandingStage` 构造后 `entity_extractor.mode == resolve_extractor_mode()` | `test_entity_extractor_query_mode.py` |
| **E-19** | `off` 模式零行为变化 | off 下 extract 返回原词（= 历史行为） | 同上 |

回归红线：`test_intent_recognizer.py` / `test_nl_engine.py` / `test_sa_config*.py` / `test_semantic_retrieval_tools.py`（如存在）零回归。

## 文档同步

| 文件 | 改动 |
|------|------|
| `docs/03-modules/README.md` ontology 子包条目 | 加 `ontology_semantics` MCP 工具 + 三层映射 |
| `docs/03-modules/README.md` sa_config 条目 | 加 `entity_extractor/mode` 受管配置项 |
| `AGENTS.md` 附录 E 速查表 | 加 `/api/ontology/mcp/semantics` + `/api/semantic-admin/extractor-mode` 两条 |
| `docs/superpowers/specs/2026-10-08-evoontology-adoption-design.md` §4.3 | 「待立项框」改「子项目 C 已完成」并链接本 spec |
| `docs/07-adr/README.md` | ADR-089 已登记（v2 追加 C-D11~C-D13） |

## 验收标准

- **代码**：15 个新测试文件全绿；既有 8 个测试文件零回归。
- **lint-imports**：4 契约保持 KEPT。
- **手验**：
  1. `POST /api/ontology/mcp/semantics {expression:"司马懿",domain_id:"sanguo",kinds:["content","schema","tool"]}` 返回非空 canonical + object_type + engines + cost；同 query 跑两次，第二次 `cache_hits>0`。
  2. `GET /api/semantic-admin/extractor-mode` → `default_mode="query"`、`available_modes=["off","inject","query"]`、`effective_mode` 非空、含三段描述。
  3. `PUT` 切到 `inject` → `GET effective_mode="inject"`；界面切换后刷新仍为 inject（持久化）。
  4. 缺口统计页看到 `ExtractorModeCard`（三选一），切换生效。
  5. **行为变更验证**：默认 `query` 下，`UnderstandingStage` 的 `entity_extractor.mode=="query"`；未知实体被过滤 + 触发 MAPPING_FAILURE 缺口；切 `off` 后恢复原词直通。
- **成本对比**（离线 benchmark）：N≥50 的回归集上 query 模式均摊 wall_ms ≤ inject 模式 × 1.5，否则视作回归。

## 非目标

- **不**替换 `RetrievalService` 内部实现；只在外面加组装层。
- **不**改 MCP 工具注册表结构或平台 tool_registry 接口。
- **不**做跨工作区实体集缓存（仅 per-extract 内存）。
- **不**自动选择 mode（由配置/界面决定；默认 query）。
- **不**为 `inject`/`off` 模式新增能力（分别为对照与回滚路径）。
- **不**改 7 个顶层 Tab（模式卡挂既有页面内）。
- **不**改变 `extracted_entities` 的消费契约（下游 audit + prompt 文本不变）。
