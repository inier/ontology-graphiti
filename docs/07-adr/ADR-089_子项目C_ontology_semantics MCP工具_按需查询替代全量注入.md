# ADR-089: 子项目 C · `ontology_semantics` MCP 工具——按需查询替代全量注入

## Status
**已接受（2026-10-09，v2 同日修订）。承接 ADR-088 子项目 A 的归因能力，把 `EntityExtractor` 的全量注入（term_resolver + entity_set）改为按需查询（`ontology_semantics` MCP 工具）。本 ADR 记录 13 项关键决策（C-D1~C-D13），实施前需 spec 复审通过。**

> **v2 修订（用户 2026-10-09 指示「支持界面显示切换，有一个默认 mode」+「不能按简单方式走，要考虑功能的完整性和可用性」）**：提取模式从「仅代码配置」升级为**运行时可切换的受管配置**（存既有 `sa_config`），新增 C-D11（mode 受管配置 + 专用端点）、C-D12（前端切换界面）、C-D13（三级解析：sa_config > env > 默认 query）。默认 mode = `query`。

> 触发来源：EvoOntology 论文（arXiv 2609.15779）核心论点「查询优于注入」——本项目 `EntityExtractor.set_entity_context(term_resolver, entity_set)` 是这条论点的现成活样本。
> 承接链路：ADR-088 让 gap 带 attribution（知道缺什么）→ 本 ADR 让理解层按需查（只问需要的）→ 未来 ADR 让 LLM 改"思考-调用"循环（更上游，本文不议）。
> 关联：ADR-088（子项目 A 归因）/ ADR-079（理解层架构）/ ADR-061（Semantic Admin Suite）/ C3 契约（ontology internals only via public facade）；AGENTS.md 规则 2/3/6/8/9/12/14。

---

## Context

### 现状（证据见 spec §1 + 本轮代码勘验）

`EntityExtractor`（`intent_recognizer.py:106-194`）当前形态：

- `__init__` 持 `term_resolver` + `entity_set`（全量注入）
- `set_entity_context(term_resolver, entity_set)` 在理解层入口被调用一次
- `_normalize_entity` 每次调 `term_resolver.resolve(entity, domain_id)` 走 in-memory 字典查表 + 集合 `in` 检查
- 注入式 `entity_set` 大小无明确文档；可视为「不到 1k 的字符串集合」

`mcp/semantic_retrieval_tools.py` 已有 7 个 MCP 工具（`ontology_query / _graph / _nl / _metric / _reason / _mdl / _hybrid`），全部是**检索执行器**——给定 query 跑出结果，但**没有「给一个 entity 描述它的 schema 形态 + 邻居引擎」**这个语义层「可导航面」能力。

### 问题陈述

EvoOntology 论文摘要的核心论断（中文复述）：**「注入式语义层每次调用都付全额 token 成本，且受上下文窗口封顶；放到工具后面只付 agent 真正问的那部分。」** 本项目在以下三处承受这个论断描述的代价：

1. `EntityExtractor` 每次冷启动加载全量 `term_resolver` 字典 + `entity_set` 集合
2. 理解层 LLM 的 prompt 模板若带「请从以下术语中选」清单，会随字典增长撑爆上下文
3. 单次 query 实际只关心 1~N 个候选词，但**预付**了全量加载成本

论文自承的空白：「**没做 cost accounting**，」——所以本 ADR 必须自带成本对账：每次工具调用记录 `cost_json`，注入 vs 查询模式均摊成本对比写进 benchmark 报告。

### 为什么不是「直接干掉 entity_set」

`entity_set` 集合过滤是**幻觉拦截**的最后一道墙（intent_recognizer.py:188-193），去掉它意味着 LLM 输出未归一化的实体直接进 SQL 拼写。**不能砍**。正确做法是：保留拦截语义，但拦截所需的「canonical 集合」改成**按需查 ontology 工具**（`ontology_semantics`），而不是预加载到内存。

---

## Decisions

### C-D1. 复用现有 7 工具注册机制

`mcp/semantic_retrieval_tools.py:223-261` 的 `register_all()` 是事实标准——`registry.register_function(name, description, func, category)` 模式已稳定，handler 是 `async (dict) -> dict`。新增第 8 个工具 `ontology_semantics` 走同一模板，**不另造注册机制**。FR-010「MCP 工具结果与 REST 完全一致」自然延伸——同步建 HTTP 端点 `/api/ontology/mcp/semantics`（POST）。

### C-D2. 工具签名三层映射

`(expression, domain_id, kinds) → {content, schema, tool, cost}`。`kinds: list[str]` 允许 caller 只查 content（快路径，省 schema 字段的存储/网络往返）。三层语义：

- **content** = USL 术语层：`{canonical, synonyms, near_synonyms}`，由 `RetrievalService.nl_search` 产出
- **schema** = TBox 结构层：`{object_type, properties, relation_types}`，由 `RetrievalService.search(mode="graph")` 产出
- **tool** = 检索工具层：`{engines: list[str]}`，由静态规则「object_type → 推荐引擎」映射产出
- **cost** = 成本对账：`{round_trips, llm_tokens_*, cache_hits, wall_ms, error?}`

这正是 EvoOntology 论文的 schema/content/tool 三层对应。`kinds` 字段让 caller 端做「按需粒度」优化。

### C-D3. `EntityExtractor` 三模式

`set_entity_context(..., mode='off'|'inject'|'query')`，默认 `query`：

- `off`：原词直通（= 历史生产行为，可一键回滚）
- `inject`：预加载全量 USL 字典 + 实体集合后注入（对照/兼容路径）
- `query`：按需查询（`ontology_semantics` 工具），per-extract 内存缓存

**as-built 修正（本轮勘验）**：`set_entity_context` 在生产**从未被调用**，故历史生产实际是 `off`（原词直通），归一化与幻觉过滤是未接线死代码。本 ADR 的默认 `query` 因此是一处**有意的、可配置的行为变更**（显式登记）。

### C-D4. 复用现有 retrieval，不新建引擎

`RetrievalService` 已有 `nl_search`（content 层 USL 消歧）与 `search`（schema/tool 层 `mode=graph`）；缺的是「按 entity 维度组装三层」——这是 `ontology_semantics` 工具的职责，**不**新建 retrieval 引擎。工程理由：C3 契约禁止 `semantic_admin → ontology_api` 深插，且新建引擎需走 ADR（规则 12），没必要。

### C-D5. 成本对账（论文自承空白的填补）

`cost_audit` 表（不可变）记录每次调用：

```sql
CREATE TABLE cost_audit (
    id TEXT PRIMARY KEY,
    call_kind TEXT NOT NULL,         -- 'ontology_semantics' | 'entity_extract'
    mode TEXT NOT NULL,              -- 'inject' | 'query'
    scope_key TEXT NOT NULL,
    expression TEXT,
    cost_json TEXT NOT NULL,         -- {llm_tokens_in, llm_tokens_out, round_trips, cache_hits, wall_ms, error?}
    model_id TEXT,
    prompt_version TEXT,
    recorded_at TEXT NOT NULL
);
```

每个 `entity_extract` 调用也记一行 `call_kind='entity_extract'`，`mode=inject` 旧路径与 `mode=query` 新路径同表对比。模型指纹（`model_id` + `prompt_version`）沿用 ADR-088 纪律——LM Studio 换模型即报告作废。

`biz/data/qa/evaluation/compare_inject_vs_query.py` 是对照脚本：离线模式不接 LLM，仅测 round trip 与 wall_ms。N≥50 时 query 模式均摊 wall_ms ≤ inject 模式 × 1.5，否则视作回归。

### C-D6. 失败降级：handler 不 raise，`cost.error` 显式

理解层不能因为工具暂时不通就断流（向 LLM 走原词兜底）。三层 handler 每个 span 包 `try/except Exception → 记 cost.error`，handler 整体不 raise；`EntityExtractor` 端 `SemanticsProvider.query` 把异常转 `ToolError`，`_normalize_entity` 捕获后走「返回原词 + warning」兜底（D6 之外客户端侧再一层兜底，符合规则 14「兜底可观测」）。

### C-D7. HTTP 端点 `/api/ontology/mcp/semantics`

镜像现有 7 工具的 REST 端点风格（`/api/ontology/mcp/query` 等已存在），给前端诊断/手验用，**不进生产流程**（生产 agent 走 MCP 协议不绕 HTTP）。端点存在意义：性能监控、错误排查、离线 benchmark 喂数据。

### C-D8. 第 8 个工具，不动既有 7 个

避免牵动 OpenHarness 端消费方的 tool manifest 兼容代码。既有 7 工具的 OpenAPI schema 零变化（验收 E-11）。

### C-D9. 报告不可变纪律延伸

`cost_audit` 表只 INSERT 不 UPDATE/DELETE；与 ADR-088 的 `gap_reports`、`drift_reports` 同样纪律。**不**给 cost 表加索引（写多读少；按 `scope_key` + `recorded_at` 范围查询建临时视图足够）。

### C-D11. mode 为运行时受管配置（专用端点）

mode ∈ {`query`, `inject`} 存 `sa_config`（scope=`entity_extractor`，key=`mode`，`config_value={"value": ...}`）。提供专用便利端点 `GET/PUT /api/semantic-admin/extractor-mode`：

- `GET` 返回 `{mode, effective_mode, default_mode, available_modes, descriptions, updated_by, updated_at}`——单点承载可选集/默认值/语义说明，前端**不硬编码**。
- `PUT`（`verify_admin` 守）写 `sa_config`；非法 mode → 400；返回同 GET 结构。

为什么用专用端点而非直接裸调既有 `/api/semantic-admin/config/{scope}/{key}`：①`available_modes`/`default_mode`/描述是稳定的产品契约，应由后端单点定义；②`effective_mode`（经三级解析的综合结果）不是裸配置值；③给未来的「切换影响提示」留扩展位。

### C-D12. 前端切换界面（ExtractorModeCard）

`ExtractorModeCard` 挂载于**缺口统计页（`GapStatsPage`）顶部**：Radio/Segmented 切换 + 当前生效 mode 高亮 + 最近修改人/时间 + 每 mode 语义说明 + 切换后 Alert 提示重跑回归集。**不改动 7 个顶层 Tab 不变量**（模式效果直接体现为 mapping_failure 缺口，缺口页是其观测点，语义自洽）。

### C-D13. mode 三级解析

`resolve_extractor_mode()`：`sa_config` > `EXTRACTOR_MODE` env > `DEFAULT_MODE='query'`。`set_entity_context(mode=None)` 时按此解析。理由：配置未初始化也能工作（env/默认兜底），兼容测试（env）与容器（配置）两种部署；读取失败按默认 + warning（规则 14）。

### C-D14. 生产接线（本子项目的价值交付）

`UnderstandingStage.__init__` 追加 `self.entity_extractor.set_entity_context(mode=resolve_extractor_mode())`。此举使 `query`（默认）在生产生效——**开启归一化 + 幻觉过滤，并使 MAPPING_FAILURE 缺口信号在归一化失败时真正触发**（此前该信号永不触发）。`off` 模式保持原词直通（历史行为，可回滚）。

**为什么这是子项目 C 的真正价值**：不只是「注入换查询」，而是「让按需上下文在生产可用」——原实现的能力从未被接线。默认 `query` = 显式的、可配置的行为变更。

### C-D10. 缓存层只在客户端，不在 MCP 工具

`EntityExtractor` 内部 per-extract() in-memory 缓存；MCP 工具本身**不缓存**（cache 必须可关）。理由：

1. 防止幽灵一致性问题（USL 字典更新后 agent 拿到旧结果）
2. 可关缓存的 query 行为更接近 EvoOntology 论文假设（论文的 query 是无状态的）
3. 性能调优留给 client side，server side 行为稳定

## Status & Verification

- **状态**：**已实施**（2026-10-09）。
- **Spec**：`docs/superpowers/specs/2026-10-09-subproject-c-ontology-semantics-tool-design.md`（v2）
- **验收 E-1~E-19**：19 项测试（v2 新增 E-13~E-19 覆盖 mode 三级解析 / 专用端点 / 前端卡片 / 生产接线 / off 模式零变化）
- **回归红线**：`test_intent_recognizer.py` / `test_nl_engine.py` / `test_sa_config*.py` / `test_semantic_retrieval_tools.py` 必须零回归
- **lint-imports**：4 契约保持 KEPT

### 实施中修正：构造器默认值不得覆盖 ADR-079 上下文驱动行为

实施后回归发现两处既有测试失败（`test_gap_attribution_emitter.py::test_intent_recognizer_discard_carries_content_attribution`、`test_gap_wiring.py::test_intent_recognizer_discard_emits`），同源问题亦影响 `test_adr079_llm_boundary.py` 的多个用例。

**根因**：本 ADR 给 `EntityExtractor.__init__` 引入 `mode` 参数并默认 `"off"`，使「注入了 `term_resolver`/`entity_set` 就应做归一化 + 本体集合过滤」这一 ADR-079 既有语义被默认值**短路**——裸构造 + 注入上下文时不再过滤，未知实体不再触发 `mapping_failure` 缺口信号。

**修正**：`mode` 未显式指定时**按上下文推导**——注入了 `term_resolver`/`entity_set` → `inject`；两者皆无 → `off`（原词安全直通）。显式 `mode=` 或 `set_entity_context(mode=...)` 时以显式为准，三模式语义不变。该推导使裸构造路径与 ADR-079 历史行为逐行等价（`_normalize_inject` 即原 `_normalize_entity` 逻辑）。

## 备选方案（未采用）

1. **直接给 LLM 喂全部 USL 字典**（prompt 前缀）：撑爆上下文、上下文窗口封顶——这是 EvoOntology 论文批评的形态，**反向采纳**。
2. **每 query 一次全量 Neo4j 查询**：绕过 `entity_set` 预加载，但每次 query 仍是 N 条记录全量返回，**没省成本**。
3. **把 USL 字典物化到 vector store**（Embedding 相似度搜索）：语义匹配可能放宽归一化精度，**违反**「候选不在 canonical 集合就 None」的拦截语义（intent_recognizer.py:188-193）。
4. **完全去掉 `entity_set` 过滤**：去幻觉拦截，**否决**（回归本项目核心防御）。
