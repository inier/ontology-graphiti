# EvoOntology 借鉴采纳设计（归因分层 + 配对回放门控）

- **状态**：已实现（2026-10-09 ADR-088 落稿后，子项目 A/B 以 TDD 实现完毕：7 个新测试文件全绿、既有 test_gap_* 6 文件零回归；待 dev 容器手验 spec §7 第 2 项）
- **日期**：2026-10-08（定稿 2026-10-09；实现 2026-10-09）
- **范围**：子项目 A —— gap_pool 归因分层（attribution）；子项目 B —— 缺口回归集 + 配对回放门控（paired replay）。子项目 C（按需查询替代注入）、D（类型化编辑提案）为后续立项（§4.3 仅立项框）——**均已于 2026-10-09 立项并实施**（C→ADR-089，D→ADR-090）。
- **关联**：ADR-086 概念缺口回路（本设计是其增量演进）、ADR-087 语义漂移检测（"报告即不可变证据"纪律）、spec 008 语义检索 / FR-010、FR-026 结构化语义层；外部参照 **EvoOntology**（RUC，arXiv 2609.15779，`ruc-datalab/EvoOntology`，MIT）——借鉴其 attribution-guided typed edits 与 backbone-conditional paired evaluation 两个机制，**明确不采纳其自动接受（auto-accept）**
- **规则约束**：AGENTS.md 规则 2（服务层返回 `{"status","message"}` dict）、规则 6（routes→services→storage）、规则 8（SQLite 每次 connect/close、JSON TEXT、ISO 时间）、规则 9（新模块零测试不提交）、规则 12（架构级决策需 ADR + 文档同步）、规则 14（失败显式、兜底可观测、禁止幻影调用/hasattr 探测式降级、测试必须执行真实函数体）

---

## 1. 背景与问题

ADR-086 落地后，gap_pool 已是**能"闭"的回路**（四类信号源接线 → heat 聚合 → promote → 审批 → writeback → 状态回流），但对照 EvoOntology 暴露出两个结构性缺口，使它还不是**能"验证"的回路**：

1. **无归因维度**。`ConceptGap.source_counts` 回答的是"**哪条链路**失败了"（term_resolve_miss / mapping_failure / qa_unanswered / nl_query_unanswered），不回答"**哪个本体元素**缺失或错了"。后果：`promote()` 只能把裸 expression 丢给 `CandidateService.create_candidate_from_gap()`（`candidate_service.py:675`），产出的 `semantic_type` 写死"对象类型"——缺口与变更之间的映射靠人脑补全。
2. **无效果度量**。`resolve_check()` 是单点静态判定：term 类现场查一次 `UslTermResolver.canonical_of(emit=False)`，非 term 类直接 `{"resolvable": False, "via": "none"}` 并明示"不假装能判定"（诚实，但也承认了做不了）。`stats()` 只有 `adoption_rate`（人工通过率）——**"改完之后系统是否真的变好"没有任何度量**。BeModel 验收标准"同一个问题下次能答上"目前只在 promote 单点上被检验，从未在问答主路径上被检验。

EvoOntology 的两个机制恰好对位补洞：**归因引导的类型化编辑**（先把失败归因到 schema/content/tool 三层中的具体元素，再生成针对性修改）与**门控接受**（编辑只在"同一 backbone、held-out 验证任务上的配对评估通过"后才生效）。

移植时守住 ODAP 基线：**裁决权归人**（ADR-086"采不采永远人决定"）。paired 评估在本设计中是**给人看的证据**，不是自动接受器——EvoOntology 的本体只装数据语义，改错顶多 SQL 写偏；ODAP 的本体挂着 OPA 权限、审计关键路径、分支合并与版本不可变，自动写回的爆炸半径完全不同。

## 2. 已锁定决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| attribution 形态 | gap 级 `attribution_counts_json`（`{layer: count}` 全量计数）+ occurrence 级 `attribution` 键（逐条，随 50 条截断） | 完全镜像既有 `source_counts_json` / `sources_json` 双层模式，无新模式引入 |
| layer 枚举 | `schema`（TBox 结构）/ `content`（USL 术语·映射）/ `tool`（检索引擎·模板·路由） | 对齐 EvoOntology 三层；也是后续子项目 D 路由 promote 的判据 |
| 归因是最佳努力 | 信号点上下文不足以判定 layer 时**省略**（None），绝不造数 | 规则 14；归因缺失只影响统计粒度，不影响回路 |
| 归因来源 | 信号点自身携带上下文（emitter 参数），**不做**事后轨迹分析 | 仓库无 agent trajectory/trace store（仅 `agent_factory.py` 提及），无追溯素材 |
| 基础设施降级不归因 | `chain_engine.py:130` degraded 维持**不接**入缺口池 | ADR-086 既有纪律：池内信号纯语义 |
| emitter 签名 | `report_gap_signal(..., attribution: Optional[Dict] = None)`，默认 None，**既有四类接线点零改动也兼容** | 向后兼容；四类接线点本期按 §4.1 表逐点补填 |
| 回归集数据源 | gap 的 occurrence（expression/query 原文 + scope）固化为 `BenchmarkDataset` | 缺口天然就是"曾经答不上的问题集"——现成 held-out 验证集，不另造数据 |
| 回归集不可变 | 固化后不随 gap 后续变化更新 | 对齐 ADR-087"报告即不可变证据" |
| 回放判定标准 | `verdict=pass` 当且仅当 **回归数=0 且 修复数≥1**（fixed=unanswered→answered） | 修复是目的，回归是红线；两条件独立可测 |
| answered 判定 | **信号收集器模式**：回放期间把 `gap_emitter.report_gap_signal` 打补丁为内存收集器，以 QA/NL 信号是否触发判定 answered；若勘验发现 pipeline response 自带 fallback 标记则优先用标记 | 复用既有信号定义（QA_UNANSWERED 语义即"答不上"），不新造判定标准，不脆弱匹配兜底文案 |
| 回放读侧纪律 | 回放期间**绝不写 concept_gaps**（heat 不变、REJECTED 不复活） | 对齐 ADR-086 resolve-check 只读守卫 M1；否则回放自我污染统计 |
| 模型指纹 | 报告必须记录 `model_id` + prompt 版本；模型/prompt 变更后旧报告标记失效，须重跑 | EvoOntology backbone-conditional 的落地形态：本体价值是 model-dependent 的；本项目经 LM Studio 跑本地 GGUF，换模型是常态 |
| 门控归人 | paired 报告挂审批/详情页作为证据展示，**不自动接受或驳回** | "采不采永远人决定"（ADR-086 基线）；EvoOntology auto-accept 明确不采纳 |
| resolve-check 入口 | `resolve_check` 保持 fast 语义**不动**，paired 走独立端点 | fast 是便宜只读判定，paired 是贵重操作（跑两轮 pipeline），混端点会诱导前端把贵操作当便宜操作误调 |
| 触发时机 | 手动 `POST .../replay`（本期）+ writeback 成功后侧道自动回放（开关 `GAP_REGRESSION_AUTO_REPLAY`，默认 **off**） | 默认关：回放成本未实测（EvoOntology 自己也没做 cost accounting）；侧道模式照 `writeback_service.py:116` 的 on_candidate_resolved 范式，异常绝不传播 |
| 组件归属 | 子项目 B 落 `gap_pool/regression/` 子包，**不新建顶级模块** | 回归集是缺口回路的验证臂，生命周期与 gap_pool 同域 |
| 前端范围 | 本期**无新页面**——gaps 详情页加"配对回放"按钮与报告块、stats 页加 by_layer 卡片 | 免 menu seed 变更与迁移脚本（ADR-086 的 seed 幂等陷阱不触发） |
| ADR | 新增 **ADR-088 EvoOntology 借鉴采纳：归因分层与配对回放门控**（含"门控归人不归模型"决策记录） | 规则 12 架构级决策 |

## 3. 关键事实（决定实现方式）

- **存储是单表 JSON TEXT 模式**：`sqlite_gap_storage.py` 每次 connect/close，`source_counts_json` 全量计数 + `sources_json` 最近 50 条 occurrence（`_SOURCES_CAP=50`）。attribution 双层结构直接照抄此模式。occurrence 现结构 `{source, ref, at, detail}`，加 `attribution` 键即兼容。
- **既有库迁移**：`_init_db` 只有 `CREATE TABLE IF NOT EXISTS`，无列级迁移能力。加列须 `PRAGMA table_info` 探测后 `ALTER TABLE ... ADD COLUMN`（幂等）。旧数据 attribution 列为 NULL → 读侧 `_safe_json` 回退 `{}`（既有容错已覆盖）。
- **emitter 是单点收敛**：`gap_emitter.report_gap_signal` 是四类信号唯一入口（惰性导入 GapService 防循环依赖），加参数不破坏任何调用方。`intent_recognizer.py:163-167` 已示范接线（带 ref/detail）。
- **resolve-check 的只读守卫**：`usl_term_resolver.py:105-110` `canonical_of(..., emit=False)` 注释明示"读侧绝不写"（终审 M1）。回放判定器必须遵守同一纪律（§4.2 收集器在回放结束后**丢弃**收集信号，不落库）。
- **writeback 回调点现成**：`usl_writeback/services/writeback_service.py:116` 已调 `GapService().on_candidate_resolved(candidate_id, outcome, term_id=term_id)`——自动回放的侧道接线挂同一位置。
- **评估基础设施现成**：`biz/data/qa/evaluation/benchmark.py` 有 `BenchmarkRunner` / `BenchmarkDataset` / `BenchmarkCase` / `EvaluationReport`（MRR/NDCG/Recall、EM/F1/faithfulness、p50/p95）。**两个坑**：① Runner 注释明示必须用 `get_query_pipeline()` 共享单例（裸 `QueryPipeline()` 支柱恒空）；② `BenchmarkCase.reference_answer` 对缺口场景大多为空，EM/F1 会全零——**不能硬套 QA 指标**，本设计用信号收集器判定 answered，指标层只记录 `fixed/regressed/unchanged` 计数 + 延迟。
- **`create_candidate_from_gap` 支持透传**：payload 已支持 `semantic_type` / `definition`（`candidate_service.py:678-679`），子项目 A 落地时 content 层可顺带把 `target_kind` 传入 `semantic_type`（小增强，不触碰审批链）。
- **drift_scan 无 api 层**：`drift_scan/` 仅 models/services/storage 三层，无 routes.py。本设计不依赖它，但其"报告不可变"纪律被借用。
- **测试基线**：`apps/api/tests/unit/biz/semantic_admin/` 已有 `test_gap_{pool_storage,emitter,routes,promote,loop_acceptance,wiring}.py` 6 个 gap 相关文件——本期改动**不得使其回归**，尤其 `test_gap_loop_acceptance.py`。

## 4. 设计

### 4.1 子项目 A：归因分层（attribution）

**模型**（`gap_pool/models/gap.py`）：

```python
class GapLayer(str, Enum):
    SCHEMA = "schema"    # TBox 结构：object_type / property / relation / event / action
    CONTENT = "content"  # USL 术语 / canonical / 同义词 / 映射
    TOOL = "tool"        # 检索引擎 / MDL 模板 / 路由规则
```

`ConceptGap` 增加 `attribution_counts: Dict[str, int]`；occurrence dict 增加 `attribution` 键（`{"layer": ..., "target_kind": ..., "target_ref": ...}`，可 None）。

**emitter**（`gap_emitter.py`）：`report_gap_signal` 加 `attribution: Optional[Dict] = None`。四类接线点的填法：

| 信号点（ADR-086 接线清单） | layer | target_kind | target_ref |
|--------|------|------|------|
| TERM_RESOLVE_MISS（`usl_term_resolver.py:117/133` 两个发射点） | content | term | expression 原文 |
| MAPPING_FAILURE（`intent_recognizer.py:162` 丢弃分支） | content | term | 候选词 |
| NL_QUERY_UNANSWERED（`nl_engine.py:69`） | tool | engine | nl_engine |
| QA_UNANSWERED（`qa_engine.py:1322` fallback 分支） | tool | engine | qa_engine.fallback |

> 实现期勘验修正（2026-10-09）：本表初稿误列 `mdl_engine.py:122` / `metric_engine.py:80-87` 为 MAPPING_FAILURE 发射点——实际它们不发射缺口信号（ADR-086 as-built 仅 5 个发射点：resolver×2 / intent_recognizer / nl_engine / qa_engine）。按规则 14 不为归因而新增信号发射，此两行删除。

上下文不足时（如 QA fallback 无法区分是术语缺还是引擎弱）只填能确定的字段或整体省略——**不造数**。

**storage**：表加列 `attribution_counts_json TEXT NOT NULL DEFAULT '{}'`；`record_signal` 在 counts 累加处同步累加 attribution 计数；occurrence 追加时带 attribution 键。`list_gaps` 加 `layer` 过滤（`json_extract(attribution_counts_json, '$.{layer}') > 0`，同 source 过滤模式）。

**service**：`record_signal` 透传 attribution；`stats()` 返回加 `by_layer`。

**promote 小增强**（不触碰审批链）：`GapService.promote()` 把 gap 的 content 层 attribution 的 `target_kind` 透传给 `create_candidate_from_gap` 的 `semantic_type`（无 attribution 时维持"对象类型"默认，行为不变）。

### 4.2 子项目 B：缺口回归集 + 配对回放

**组件边界**（`gap_pool/regression/` 子包）：

```
regression/
  __init__.py
  builder.py     # RegressionSetBuilder：按 scope + 过滤条件把 gaps 固化为不可变回归集
  storage.py     # SQLiteGapRegressionStorage：gap_regression_sets / gap_replay_reports 两表
  runner.py      # PairedReplayRunner：两轮回放 + 信号收集器 + 差分判定
  service.py     # RegressionService：build / replay / list_sets / get_set / list_reports / get_report
```

调用方向严格 routes→services→storage；services 返回 `{"status","message",...}` dict。

**数据模型**（`gap_regression.db`，规则 8）：

表 `gap_regression_sets`（不可变）：

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | uuid4 |
| name | TEXT | 生成名（含时间戳 + scope） |
| scope_key | TEXT | 同 gap 的 `workspace::domain` |
| cases_json | TEXT | `[{query, expression, gap_id, source}]`，固化后不改 |
| source_gap_ids_json | TEXT | 溯源 gap id 列表 |
| model_id | TEXT | 构建时模型指纹 |
| case_count | INTEGER | len(cases) |
| created_at | TEXT | ISO |

表 `gap_replay_reports`（不可变）：

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | uuid4 |
| set_id | TEXT FK | |
| model_id / prompt_version | TEXT | backbone 指纹；与构建集不一致时报告头部警示 |
| verdict | TEXT | pass / fail / error（失败显式） |
| fixed_count / regressed_count / unchanged_count | INTEGER | 全部 `len(...)` 真实计数，无推断 |
| rounds_json | TEXT | 前后两轮 per-case `{query, before_answered, after_answered}` |
| cost_json | TEXT | 两轮耗时（+可得时的 token 数）——EvoOntology 未做 cost accounting，这里补上 |
| error_detail | TEXT NULL | verdict=error 时必填具体原因（不写"回放失败"笼统话） |
| created_at | TEXT | ISO |

**判定逻辑**：per-case `answered` 由**信号收集器**判定——runner 在回放期间以模块级补丁把 `gap_emitter.report_gap_signal` 替换为内存收集器（记录 QA_UNANSWERED / NL_QUERY_UNANSWERED 信号即 unanswered），两轮结束恢复原函数并**丢弃**收集结果（绝不落库）。`fixed = before unanswered ∧ after answered`；`regressed` 反之。`verdict=pass ⇔ regressed_count=0 ∧ fixed_count≥1`。实现时先勘验 pipeline response 是否自带 fallback 标记，有则优先用标记（免补丁、免线程安全顾虑）；补丁为顺序 await 执行，风险与替代方案写入 ADR-088。

> **实现期澄清（2026-10-09，已记入 ADR-088 D3 附注）**：勘验确认 `QueryResponse` 不带 fallback 标记，收集器模式为最终实现。生产语义定为 **before = 捕获证据**（回归集来自缺口，缺口即"当时答不上"的证据，before_answered=False 由集合语义给出，不重放历史）+ **after = 现场回放**；真·双轮现场配对经 `before_executor` / `after_executor` 注入支持（测试用，regressed 判定在该模式下可达）。理由：现场跑两轮"当前 vs 当前"恒 fixed=0，无法回答"补上了之后是否真的能答上"；捕获证据是唯一不造数的历史基线。

**API**（prefix `/api/semantic-admin/gap-regression`）：

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/sets/build` | get_current_user | body: `{status?, workspace_id?, domain_id?, min_heat?}`；分析操作、对语义资产只读 |
| GET | `/sets` | get_current_user | 回归集列表（分页） |
| GET | `/sets/{id}` | get_current_user | 含 cases |
| POST | `/sets/{id}/replay` | get_current_user | 同步执行配对回放，返回 report（集规模 ≤50，可控） |
| GET | `/reports` | get_current_user | 报告列表 |
| GET | `/reports/{id}` | get_current_user | 报告详情 |

`resolve_check` **不动**（fast 语义保留）。

**writeback 侧道**：`writeback_service.py:116` 处，开关 `GAP_REGRESSION_AUTO_REPLAY`（默认 off）开启时 `asyncio.create_task` 触发对应 scope 最新回归集回放，异常只 logger.warning，绝不传播 writeback 主路径。

**前端**（无新页面）：gaps 详情页加"配对回放"入口 + 最新 report 块（verdict / fixed / regressed / cost）；stats 页加 `by_layer` 卡片。

### 4.3 后续立项（已于 2026-10-09 立项并实施）

> **状态更新（2026-10-09）**：子项目 C 与 D 均已立项落 ADR 并完成实现——C 见 [ADR-089](../../07-adr/ADR-089_子项目C_ontology_semantics%20MCP工具_按需查询替代全量注入.md) 与 spec `2026-10-09-subproject-c-ontology-semantics-tool-design.md`；D 见 [ADR-090](../../07-adr/ADR-090_子项目D_promote按attribution_layer路由_类型化编辑.md) 与 spec `2026-10-09-subproject-d-promote-routing-design.md`。以下为当初的立项框原文（保留作溯源）。

**子项目 C：按需查询替代全量注入（P1，需 ADR）** ✅ 已实施
- 新 MCP 工具 `ontology_semantics`（`biz/core/ontology/mcp/`）：`(expression, domain_id, kinds) → {canonical, synonyms, object_type, properties, relation_types, engines}`——schema/content/tool 三层的"导航面"；现有 7 工具全是检索执行器，三层中仅 content 有查询入口（nl_engine 消歧）。
- `EntityExtractor.set_entity_context`（`intent_recognizer.py:120`）由全量 entity_set 注入改为查询式 provider，全量集合保留为小规模快路径/降级。
- 验收：用 `benchmark.py` 现有基准跑注入 vs 查询两版，对比 F1 与延迟——**必须实测**，EvoOntology 未对账 token 节省与 round-trip/prefix-cache 代价。
- **实施补充**：落成三模式 `off/inject/query`（默认 `query`，`sa_config`(`entity_extractor.mode`) > `EXTRACTOR_MODE` env > `query` 三级解析）+ 前端 `ExtractorModeCard` 切换卡 + `cost_audit` 不可变成本对账。

**子项目 D：类型化编辑提案（P1，需 ADR，依赖子项目 A）** ✅ 已实施
- `promote()` 按 `attribution.layer` 路由：`content` → 现有 USL candidate 路径不变；`schema` → 生成 `ChangeProposal`（RFC 6902 JSON Patch 打到 doc_snapshot 路径），复用 `ImpactAnalyzer` 算爆炸半径，人工审批后走 Branch&Merge（FR-037 OntoFlow 全链路已有）；`tool` → 落 unified_router 路由规则 / MDL 模板，或产出工单，不自动改。
- 不新造机制，纯接线 gap_pool / goal / branch-merge 三套既有设施。
- **实施补充**：优先级定为 `schema > tool > content` 风险倒序（体系化，根因优先）；`tool` 路径升级为**完整工单工作流**（6 态状态机 + P0~P3 SLA + 事件审计 + 前端界面，新子服务 `routing_tickets`）；`schema` 路径经 C3 门面 `create_schema_proposal` 落 `change_proposals`（draft 门控，不立即跑 ImpactAnalyzer）；新增 `route-preview` 无副作用预览端点。

## 5. 测试策略（规则 9 / 14.6）

单测目录 `apps/api/tests/unit/biz/semantic_admin/`，运行命令带离线变量（同 2026-10-07 两份 spec 的 Global Constraints 约定）。

- `test_gap_attribution_storage.py`：tmp_path 真 DB——旧库（无 attribution 列）自动 ALTER 迁移且幂等；attribution 计数累加；occurrence 截断后 attribution 键仍在最近 50 条内；layer 过滤与 total 同源；坏 JSON 回退 `{}`。
- `test_gap_attribution_emitter.py`：走真实函数体——真 `UslTermResolver.load_terms` 建表后制造 miss，断言 occurrence 带content 层 attribution；不带 attribution 的调用（旧签名路径）行为不变。
- `test_regression_builder.py`：固化不可变（同参数二次 build 生成**新**集不覆盖旧的）；scope 隔离；min_heat 过滤。
- `test_paired_replay.py`：走真实函数体——`get_query_pipeline()` + 注入可控 fake resolver 构造"变更前 unanswered / 变更后 answered"用例，断言 fixed/regressed/verdict 判定；**断言回放期间 concept_gaps 表零写入**（heat 不变、REJECTED 不复活——M1 纪律）；收集器异常时 verdict=error 且 error_detail 非空。
- `test_regression_routes.py`：状态码映射、`except HTTPException: raise` 透传、鉴权 Depends override。
- **回路验收升级** `test_regression_loop_acceptance.py`：signal → gap（带 attribution）→ build set → promote → approve → writeback → replay → `verdict=pass ∧ fixed≥1`——把 BeModel"同一个问题下次能答上"从单点判定升级为回放判定。

既有 `test_gap_*.py` 6 个文件必须全绿（回归红线）。

## 6. 文档同步（规则 12）

- 新增 **ADR-088 EvoOntology 借鉴采纳：归因分层与配对回放门控**（含三项关键决策记录：门控归人不归模型；信号收集器模式及其线程安全权衡；cost 记录补 EvoOntology 之缺）+ `docs/07-adr/README.md` 索引。
- `docs/03-modules/README.md`：gap_pool 条目下补 regression 子服务。
- `router_registry.py` 注册新 prefix + AGENTS.md 附录 E 速查表。
- 无 menu seed 变更（无新页面）。
- 提交前对照 `docs/09-checklists/DOC_SYNC_CHECKLIST.md` 逐项检查。

## 7. 验收标准

1. §5 全部新测试文件绿，既有 `test_gap_*.py` 6 文件零回归。
2. dev 容器（`python apps/api/bootstep.py dev`）手验：制造一次 MAPPING_FAILURE → list 页可见 attribution → build 回归集 → promote → 审批 → writeback → replay 报告 `verdict=pass`、`fixed_count≥1`，详情页可见报告块。
3. 旧库启动自动迁移（加列），既有 gap 数据完好、stats 正常。
4. `stats.by_layer` 全部来自真实记录，无推断。
5. 回放期间 `concept_gaps` 表零写入（可 SQL 断言 heat 不变）。

## 8. 非目标（Out of Scope）

- **自动接受/驳回**：EvoOntology auto-accept 明确不采纳（OPA 权限 / 审计关键路径 / 版本不可定的爆炸半径不同）；paired 报告只作人工裁决证据。
- 子项目 C / D 的实现（本 spec 仅立项，见 §4.3）。**注：2026-10-09 已分别以 ADR-089 / ADR-090 立项并实施，其实现范围见对应 spec。**
- gap 跨 workspace 回归集合并视图。
- 轨迹级归因（从 agent 执行 trace 归因）——待运行时具备 trace 存储后另议。
- 回归集定时自动巡检（本期仅手动 build/replay + writeback 侧道开关）。
- BM25/向量等检索质量指标进 replay 报告（EM/F1 对无参考答案的缺口场景不适配，本期只用 answered 差分）。
