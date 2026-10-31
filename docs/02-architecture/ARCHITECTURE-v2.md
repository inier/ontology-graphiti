---
id: odap.l2.architecture-v2
status: authoritative
owner: architect
version: '2.0'
layer: L2
concern: architecture
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 目标架构唯一真相源
governance_evidence: ADR-097:25；本文件标题「ODAP 目标架构 v2」
---

# ODAP 目标架构 v2（ARCHITECTURE-v2）

> 版本：v2.0 | 日期：2026-10-17 | 作者：首席架构师 | 状态：正式
> 上游依据：`docs/12-evaluation/ARCHITECTURE-EVALUATION.md`（v1.0）+ `CONTEXT.md`（统一语言表 v1.0）+ ADR-001~090（既有决策）
> 本文档为本轮**唯一架构真相源**。`docs/02-architecture/ARCHITECTURE_*.md` 其余 10 篇将在本轮归档为 `status: superseded`（详见 §5.2）。
> 本文档不使用 emoji；不定义紫色→粉色/品红渐变；所有版本号来自实际文件（见 §8）。

---

## 1. 架构总览

### 1.1 分层架构（依赖只能向下）

```
┌───────────────────────────────────────────────────────────────┐
│ 表现层 web/  (FastAPI 路由中心化装配 + 前端 SPA)                │
│   职责：参数校验、鉴权、调用 biz service、组装响应。零业务。      │
│   约束：入口只装配；单文件 ≤300 行。                            │
├───────────────────────────────────────────────────────────────┤
│ 业务层 biz/  (core / decision / integration / platform /        │
│              data / simulation / management / semantic_admin)   │
│   职责：业务规则、事务编排、调用 infra provider。                │
│   约束：不 import web；不返回 HTTP 对象；跨域走对方 service 门面。│
├───────────────────────────────────────────────────────────────┤
│ 领域能力层 tools/  (领域 Skills: base + registry + 9 技能包)     │
│   新增 C5 契约：infra 不得经 tools 间接触达 biz（本轮补齐）。     │
├───────────────────────────────────────────────────────────────┤
│ 基础设施层 infra/  (graph / query / opa / security / openharness │
│                     / llm / storage / queue / events ...)        │
│   职责：连接、客户端实例、数据读写、外部系统适配。                │
│   约束：不得直接 import biz（C4 棘轮，10 条存量边分批烧账）。      │
├───────────────────────────────────────────────────────────────┤
│ 公共叶子层 common/  (常量、无依赖的共享 schema)                  │
│   约束：不得依赖 biz/infra/web（C1 严格）。                     │
└───────────────────────────────────────────────────────────────┘
                             ↓
   外部系统：Neo4j(ABox) · SQLite/TBox(odap_main.db) · Redis · MinIO · OPA
```

**与现状的关系（增量重构，不推倒重来）**：分层方向已验证正确（`biz→web` 反向依赖 0 条，见评估报告 §2.1）。v2 的新增/强化点是：补齐 C5（tools 边界）契约、把「本体约束编排层」作为 `biz/core/ontology` 下的**新增一等编排能力**、以及前端渲染栈与 Token 体系的收敛。

### 1.2 四步法与横向能力映射

- **建本体** `biz/core/ontology/construction|design` + HE 抽取。
- **见本体** `ontology explorer`（前端）+ `infra/query`（图查询）。
- **演本体** `biz/simulation`（deduction + decision，双时态隔离 `scenario_id` + `valid=false`）。
- **用本体** `biz/core/ontology/semantic_retrieval`（语义检索服务总线）+ `OntologyGateway` 门面 + MCP。
- **横向能力**：USL（`biz/semantic_admin/usl_manager`）贯穿四步；本体约束编排层（§2）横向约束全链路。

---

## 2. 本体约束编排层（核心新增）

> 目标：让「输入与输出均受本体规则约束」，并让每条结论**可溯源**。
> 位置：`apps/api/odap/biz/core/ontology/orchestration/`（新增子包，经 `ontology.public` 门面暴露，遵守 C3）。
> 复用：不新造 DSL；规则侧复用 OPA `.rego` 与既有公理引擎（ADR-075/077/085）。

### 2.1 六步约束管线（Pipeline）

```
[1] 意图识别 ──▶ [2] 本体映射 ──▶ [3] 规则校验 ──▶ [4] 检索/推理 ──▶ [5] 生成 ──▶ [6] 输出契约校验
   Intent          Ontology          Rule            Retrieval/        Answer        Output
   Router          Aligner           Guard           Reasoning         Composer      ContractGate
```

每一步的**输入/输出契约、失败降级路径**如下（`Prov` 表示携带 provenance 记录）：

| 步 | 组件 | 输入契约 | 输出契约 | 失败降级路径 |
|----|------|----------|----------|--------------|
| 1 | `IntentRouter` | `{query, user_ctx, workspace_id}` | `IntentFrame{intent_type, slots, confidence, prov}` | 置信度低于阈值 → 返回澄清问句（HITL，不猜） |
| 2 | `OntologyAligner` | `IntentFrame` + TBox 快照 | `MappedQuery{object_types[], relation_types[], entity_links[], unmapped[], prov}` | 存在 `unmapped` → 进入**概念缺口回路**（复用 ADR-086 `gap_pool`），不静默丢弃 |
| 3 | `RuleGuard` | `MappedQuery` | `GuardResult{allowed, violations[], obligations[], prov}` | OPA 不可用 → **fail-closed**（默认拒绝高风险动作），只放行只读查询且标注 `degraded=true` |
| 4 | `RetrievalExecutor` | `GuardResult`(allowed) | `RetrievalResult{chains[], source_refs[], prov}` | 单引擎失败 → 走 `unified_router` 降级链（graph→nl→mdl→metric），并记录 `degraded_engines[]` |
| 5 | `AnswerComposer` | `RetrievalResult` + 输出形状约束 | `DraftAnswer{content, citations[], prov}` | 证据不足 → 返回「证据不足」而非编造（no-answer 路径） |
| 6 | `OutputContractGate` | `DraftAnswer` + 输出 TBox 约束 | `AnswerEnvelope{content, citations, provenance, contract_ok}` | 输出违约 → 标注 `blocked_reasons[]`，降级为「部分答案 + 违约说明」 |

### 2.2 「输入/输出均受本体约束」的可执行定义

- **输入侧约束**：`OntologyAligner` 只接受能在 TBox 中找到 `ObjectType`/`RelationType` 的槽位；无法映射的槽位进缺口回路，**禁止**用 LLM 幻觉直接补全并执行。
- **输出侧约束**：`OutputContractGate` 用 TBox 的 SHACL 形状（复用 ADR-085 `shacl_store`）校验结构化输出；不符形状的输出被阻断或标注。
- **约束的载体**：TBox（SQLite `odap_main.db`，真相源）+ SHACL 形状（`semantic_admin/shacl_store`）+ OPA 策略（`infra/opa/policies/*.rego`）。三者合一构成「公理 + 规则 + 形状」约束集。

### 2.3 溯源（Provenance）设计

每个管线步骤产出 `Prov` 记录，最终聚合为 `Provenance` 对象。**溯源须可机械校验**：

```json
{
  "trace_id": "urn:odap:trace:...",
  "steps": [
    {"step": "intent", "component": "IntentRouter", "version": "v2.0",
     "evidence": [{"kind": "dict_hit", "ref": "USL:term:order-return"}],
     "ts": "2026-10-17T08:00:00Z"},
    {"step": "map", "component": "OntologyAligner", "version": "v2.0",
     "evidence": [{"kind": "tbox_node", "ref": "ObjectType:Order"}], "ts": "..."},
    {"step": "guard", "component": "RuleGuard",
     "evidence": [{"kind": "opa_decision", "ref": "policies/ontology_assistant.rego#allow", "decision": true}], "ts": "..."},
    {"step": "retrieve", "component": "RetrievalExecutor",
     "evidence": [{"kind": "graph_edge", "ref": "neo4j:edge:...", "asof": "2026-10-16T00:00:00Z"}], "ts": "..."}
  ],
  "citations": ["doc:kb/123#chunk-4", "metric:order_return_rate@2026Q3"],
  "tbox_version": "sha256:...",
  "contract_ok": true
}
```

**机械校验规则**：
1. `trace_id` 全局唯一，`steps` 覆盖全部 6 步（缺步即不合格）。
2. 每个 `evidence.ref` 必须可被解析（TBox 节点存在 / OPA decision 可复算 / Neo4j 边存在 / 文档 chunk 存在）。
3. `tbox_version` 必须与本次使用的 TBox 快照哈希一致（版本锚定）。
4. 校验脚本 `scripts/verify_provenance.py`（Phase 2 新增）对上述规则做门禁。

---

## 3. 意图识别与泛化

### 3.1 分层识别方案（四级漏斗，逐级降本）

```
用户 query
   ↓
[L1] 词典/别名匹配      USL 术语表 + 同义词（确定性，零成本）
   ↓ 未命中
[L2] 语义路由           embedding 召回候选 intent（复用 agent_router_semantic_routing）
   ↓ 低置信
[L3] LLM 消歧           小模型/规则约束下的意图分类（受限候选集 + 强制 JSON 输出）
   ↓ 仍未定
[L4] 本体槽位填充       受 TBox 约束的槽位抽取；无法映射 → 缺口回路 → HITL 澄清
```

- L1/L2 复用既有资产：USL 术语表（`semantic_admin/usl_manager`）、`biz/core/agent` 语义路由（ADR-043）。
- L3 约束：LLM 只在**受限候选 intent 集**内选择，禁止开放式生成；输出强制 JSON Schema。
- L4 与 §2.2 输入侧约束对齐：槽位必须能落 TBox。

### 3.2 泛化能力度量（离线评测集 + 指标）

**评测集**（Phase 2 建设，落 `apps/api/tests/eval/intent/`）：

| 维度 | 说明 | 目标量 |
|------|------|--------|
| 同义改写 | 同一意图的不同表述（含口语化、简称） | ≥ 200 条 |
| 跨域迁移 | 训练/词表未见过的领域术语 | ≥ 100 条 |
| 复合意图 | 一句话含两个以上意图/多跳 | ≥ 100 条 |
| 干扰项 | 近义但意图不同的负样本 | ≥ 100 条 |

**指标**（每次改动跑一次，进回归集）：

- `Intent-Acc@1`：意图识别 Top-1 准确率。目标 ≥ 0.90。
- `Slot-F1`：槽位填充 F1。目标 ≥ 0.85。
- `Gen-Gap`：泛化缺口率 = 在「跨域迁移」集上的 Acc@1 与内置集 Acc@1 之差。目标 ≤ 0.10（越小越泛化）。
- `Clarify-Rate`：无法确定时触发澄清的比例（宁澄清不猜）。目标：误答率 ≤ 0.02 时 Clarify-Rate 可上浮。
- `Unmapped-Rate`：映射不到 TBox 的比例（喂给缺口回路）。用于驱动本体补全。

**门禁**：上述指标随 CI 回归集执行；`Intent-Acc@1` 或 `Slot-F1` 跌破基线即拦截合并。

---

## 4. 端到端数据流

### 4.1 全链路

```
非结构化输入                     结构化输入
(文档/网页/文本/PDF)            (系统表/指标定义)
       │                              │
       ▼                              ▼
 [抽取层] HE 抽取               [映射层] schema→TBox 映射
 (packages/hyper-extract,        (ontology_mapper)
  复用 YAML 模板，不造 DSL)
       │                              │
       └──────────────┬───────────────┘
                      ▼
          [落库层] TBox(SQLite 真相源) ──投影──▶ ABox(Neo4j, Instance 标签)
                      │                              │
                      ▼ (TBox 变更发领域事件)         ▼
              最终一致对账 + drift_scan 兜底     双时态(valid_from/valid_to)
                      │                              │
                      └──────────────┬───────────────┘
                                     ▼
                    [语义检索服务总线] semantic_retrieval
                    统一检索 / 分项检索(chain|nl|mdl|graph|metric) / 混合检索
                                     ▼
                    [本体约束编排层 §2] 意图→映射→校验→检索→生成→输出校验
                                     ▼
                          智能问答 AnswerEnvelope
                                     ▼
                       溯源 Provenance(§2.3) ──▶ 前端可视化溯源链
                                     ▼
                    [Action 层 / HITL] 后续执行建议 + 人工确认闸门
```

### 4.2 双时态与双存储一致性口径（本轮定，见 OPEN-DECISIONS 第 5 条）

- **TBox 为真相源**（SQLite `odap_main.db`）；ABox 是 TBox 的**投影 + 实例数据**（Neo4j）。
- 一致性策略：**最终一致**。TBox 变更 → 领域事件（`infra/events/event_bus`）→ ABox 投影器消费 → 版本戳对账；`drift_scan` 定期兜底扫描。
- 一致性 SLO 待业务确认（登记为 OPEN）。

### 4.3 Action 层与 HITL

- 编排管线第 6 步之后，若 `AnswerEnvelope` 携带 `suggested_actions[]`，进入 **Action 层**：动作按风险分级。
- 低风险（只读/预览）自动执行或一键执行；高风险（写入/对外/不可逆）强制 **HITL 人工确认**，复用既有 `qa/agui/HITLPanel` 与 OPA `semantic_admin_approval.rego`。
- 每个被执行的动作也产生 provenance，形成「先取证、再决策、后行动」闭环（与用户知识库「Ontology 决策结构化实践」一致）。

---

## 5. LLM Wiki 架构（产品模块 + 仓库文档治理双向打通）

> 现状：**完全缺失**（`grep -rl "llm.wiki\|llm_wiki"` 零命中）。本轮首建。

### 5.1 双向打通模型

```
┌────────────────────────┐        ┌────────────────────────────┐
│ 产品侧 LLM Wiki 模块     │◀─────▶│ 仓库 docs/ 工程文档治理       │
│ (前端 wiki 页 + 后端 API)│  同步  │ (259 篇 md, front-matter)    │
└────────────────────────┘        └────────────────────────────┘
        │                                        │
        └────────────┬───────────────────────────┘
                     ▼
            [文档纳管模型 §5.2]
                     ▼
            [与本体/USL 的关系 §5.5]
```

- **产品侧**：面向用户的知识条目（wiki page），支持编辑、版本、引用。
- **仓库侧**：`docs/` 下的工程文档，通过 front-matter 纳入同一纳管模型。
- **双向同步**：仓库文档可通过「导入」动作生成 wiki 条目（保留 `source_ref` 指向仓库路径）；wiki 条目可「导出/回写」为仓库 md（受写权限与审批约束）。

### 5.2 文档纳管模型（统一）

```yaml
# 每篇纳入纳管的文档（仓库 md 用 front-matter，wiki 条目用同构字段）
id: doc-<ulid>                 # 全局唯一，可寻址
title: ...
status: draft|review|published|superseded|archived
owner: <user/role id>          # 责任人，必填（无 owner 不合格）
version: 2.0.0                 # 语义化
source_ref: repo:docs/07-adr/ADR-091_...  # 仓库侧来源（wiki 条目可能为空）
superseded_by: doc-<ulid>|null # 被谁取代（真相源链）
supersedes: [doc-<ulid>]       # 取代了谁
content_hash: sha256:...
last_verified: 2026-10-17      # 最后核验日期（陈旧检测依据）
tags: [...]
citations: [{kind, ref}]       # 引用关系（可机械校验）
```

### 5.3 去重 / 合并 / 状态机

- **去重**：`content_hash` 相同 → 判重；相似度（embedding）高于阈值 → 提示合并候选。
- **合并**：保留一条 canonical，其余置 `status: superseded` + `superseded_by` 指向 canonical（**不删除**，保留可追溯历史）。
- **状态机**：`draft → review → published → superseded|archived`；`published` 必须有 owner 且 `last_verified` 未过期。

### 5.4 引用关系图

- 从 `citations[].ref` 构建**文档引用图**；提供「谁引用了本文档 / 本文档引用了谁」查询。
- CI 门禁复用并扩展 `scripts/check_dangling_doc_links.py`：悬空引用（引用不存在的 id）即 FAIL。

### 5.5 与本体 / USL 的关系

- **文档 ↔ 概念**：wiki 条目可关联 TBox 的 `ObjectType`/术语（`concept_refs[]`），使文档成为本体的「人文解释层」。
- **文档 → 语义检索**：wiki 条目进语义检索服务总线（作为 `nl`/`chain` 检索的证据源，带 `source_ref`）。
- **USL 术语 ↔ 文档**：USL 术语可挂权威文档链接（术语的权威定义出处），溯源可回溯到文档。

---

## 6. 图谱渲染栈收敛决策

### 6.1 方案对比矩阵（≥3 方案）

| 方案 | 保留栈 | 迁移成本 | 能力覆盖 | 包体 | 风险 | 评分 |
|------|--------|----------|----------|------|------|------|
| A 收敛到 sigma 系 | sigma + @react-sigma/core + graphology | 中（g6/cytoscape 需迁） | 大图浏览强、编辑弱 | 小 | g6/cytoscape 特有交互需重建 | 8.0 |
| B 收敛到 g6 系 | @antv/g6 (+@ant-design/graphs) | 高（sigma/cytoscape 全迁） | 图分析强、与 AntD 生态近 | 中 | sigma 大图性能优势丢失 | 7.2 |
| C 收敛到 xyflow 系 | @xyflow/react | 高（大图浏览需自建虚拟化） | 编辑/流程强、大图浏览弱 | 小 | 大图（百万级）不可行 | 6.5 |
| **D 按语义分工收敛（选定）** | **拓扑浏览=sigma+graphology；编辑态流程=xyflow；统计图=echarts** | 低-中（仅 g6→xyflow、下线零引用的 ant-design-graphs） | 三类场景各用其长 | 中（去重后下降） | 需明确「跨栈能力边界」纪律 | **8.6** |

### 6.2 锁定决策（详见 ADR-091）

- **唯一图谱拓扑栈**：`sigma` + `@react-sigma/core` + `@react-sigma/minimap` + `graphology`（数据结构/布局算法）。承接全部图谱浏览页（`/ontology/explorer`、`/ontology/semantic-map`、`/ontology/abution-graph` 等）。
- **唯一编排/关系编辑器栈**：`@xyflow/react`（蓝图/流程编排，语义为「编辑」而非「浏览」，独立保留）。
- **唯一统计图表栈**：`echarts`（非图拓扑，独立保留）。
- **下线**：`@ant-design/graphs`（零引用，移除依赖）。
- **迁移**：`@antv/g6`（`DecisionChainGraph.tsx`）→ `@xyflow/react`；`cytoscape`（4 文件）→ 浏览/算法迁 `sigma`+`graphology`、层级/DAG 编辑迁 `@xyflow/react`（**不再保留 cytoscape 例外**，其独有能力已由 graphology 覆盖）。
- **Token 消费（硬约束）**：图谱栈消费 `--odap-graph-*`（`docs/04-ui/design-tokens.css:521-553`），图表栈消费 `--odap-chart-*`（`:555-572`）；禁止渲染库自带主题色与硬编码色值；颜色之外叠加 shape+icon 冗余编码。
- **纪律**：同一语义类别只允许一个库；新增图库须走 ADR。

### 6.3 图标库锁定（详见 ADR-092）

**方案对比**：

| 方案 | 库 | 满足描边规格 | 迁移成本 | 与知识库一致 | 评分 |
|------|-----|--------------|----------|--------------|------|
| A（原倾向） | `@ant-design/icons` Outlined | **不满足**（填充式 SVG，无 stroke-width/linecap/linejoin 控制） | 零 | 否 | 5.0 |
| **B 选定** | **`lucide-react`** | **完全满足**（24px 网格 / stroke / round cap-join / fill:none / strokeWidth 可设 1.5） | 高（186 文件，codemod + 映射表分批） | **是**（enterprise/ai-native） | **8.6** |
| C | `@tabler/icons-react` | 满足 | 高 | 部分 | 7.0 |

**锁定决策**：`lucide-react` 作为全项目唯一图标库。

- **描边规格（设计侧不可变约束）**：`strokeWidth={1.5}`、round cap/join、`fill:none`（对齐 `--odap-size-icon-stroke:1.5`）。
- **尺寸**：统一 `16 / 20 / 24` px 三档（对齐 `--odap-size-icon-inline/button/standalone`），禁止其他尺寸与 emoji。
- **颜色**：`currentColor`，继承 `--odap-color-*`。
- **为何不选 `@ant-design/icons`**：其图标为填充式 SVG path（1024 viewBox，`fill="currentColor"`），**不暴露 stroke 控制**，无法满足设计侧「统一描边 1.5」的不可变规格，锁定它会导致 Phase 3 返工；知识库 `industries/*` 亦推荐 Lucide 描边风。
- **迁移策略**：产出「`@ant-design/icons` → Lucide」映射表 + codemod（`scripts/migrate_icons.mjs`）；按模块分批（导航 → 图谱页 → 业务页），Feature Flag 灰度，旧图标保留一 release；`@ant-design/icons` 仅在 AntD 组件内部渲染时作为传递依赖保留（不在「项目图标系统」范围）。
- **P0-1 合规**：全项目禁用 emoji 作功能图标；现存 55 个含 emoji 的 tsx 文件逐批替换为 Lucide 图标。
- **必覆盖图标集**：工作区 6 类、图谱节点 8 类、工具栏 12 类（清单见 ADR-092 §Decision 第 5 条）。

---

## 7. Design Token 与主题系统架构（详见 ADR-093）

### 7.1 Token 三层结构（primitive → semantic → component）

**Token 真源（唯一）**：设计侧已交付 `docs/04-ui/design-tokens.css`（CSS 真源）+ `docs/04-ui/design-tokens.json`（机器可读真源），二者必须完全一致。本节以其实际命名为准，不另起前缀。

```
Primitive（原始值，全项目唯一允许出现 hex 的层）
   --odap-primitive-cobalt-600: #1E45DB;   --odap-primitive-teal-500: #12A98E;
   --odap-space-4: 16px;  --odap-radius-md: 8px;  --odap-elevation-sm: ...;
        │
        ▼
Semantic（语义别名，主题切换点）
   --odap-color-accent: var(--odap-accent-600);
   --odap-color-bg / --odap-color-surface / --odap-color-fg / --odap-color-border;
   --odap-color-success / warn / danger / info;
   --odap-accent-* 由 [data-accent=cobalt|teal|indigo|graphite] 填充
        │
        ▼
Component（组件专用）
   --odap-button-primary-bg: var(--odap-color-accent-solid);
   --odap-graph-node-*  /  --odap-chart-series-*
```

- **外观/强调色驱动**：`<html data-appearance="luminous|nebula" data-accent="cobalt|teal|indigo|graphite">`（`design-tokens.css:8,320-411`）。
- **P0-2 合规**：品牌渐变**取消**（`--odap-gradient-brand` 不再存在）；如需渐变只允许**同色相深浅**（`--odap-color-accent` ↔ `--odap-color-accent-hover`）。评估报告 §1.5 的违规点 `colorThemeUtils.ts:142-144` 整段删除。
- **图谱/图表 Token**：`--odap-graph-*`（`:521-553`，含 8 类节点分类色）、`--odap-chart-*`（`:555-572`，8 序列色），供 ADR-091 锁定的渲染栈消费。

### 7.2 多主题 / 风格切换机制

- 通过 `<html data-appearance>` + `[data-appearance]`（亮/暗面）与 `<html data-accent>` + `[data-accent]`（强调色族）切换 semantic 层，primitive 层不动。
- 风格差异只落在 semantic/component 层，避免组件代码感知主题。
- 由 `useThemeRuntime` 写入 `html` 属性（`UIUX-DESIGN-v2.md` §3.6），切换经 Zustand store（复用 `shared/stores`）触发并持久化。

### 7.3 与 AntD 6 ConfigProvider 对接

- **唯一对接路径**：`CSS 变量（真源）→ html[data-*] → ConfigProvider.token + ConfigProvider.components`。
- 用 `getComputedStyle(document.documentElement).getPropertyValue('--odap-...')` 实时读取 CSS 真源，保证与 CSS 一致（`AdminLayout.tsx:655-691` 的 `ConfigProvider` 用法正确，v2 在其上扩展而非推翻）。
- **禁止硬编码颜色**：组件代码只用 `var(--odap-*)` 或 AntD token；现存 1044 处硬编码 hex（排除 #fff/#000）在 Phase 3 按模块清理，清理率进质量门禁。
- **动效约束**：统一 `--odap-duration-*` / `--odap-ease-*`（无 spring/overshoot）；`global.css:125` 过冲缓动删除。

---

## 8. 模块化与解耦

### 8.1 前后端模块边界与契约

- **唯一契约**：`docs/02-architecture/openapi-v2.yaml`（OpenAPI 3.0）。前端据此生成 TS 类型 + MSW mock；后端据此实现。变更须更新 spec 并经 Team Lead 同步前后端。
- **后端模块边界**：`biz/{core,decision,integration,platform,data,simulation,management,semantic_admin}` 按领域分包；跨域只经对方 `public` 门面（C3）。
- **前端模块边界**：`modules/<域>/{pages,components,services,stores}`；API 调用统一封装（拆分 `api.ts` 2329 行为按域 `services/`）。

### 8.2 可组合性设计（Composable 编排）

- 后端：组合根装配（`biz/providers_bootstrap.py` + `infra/providers.py` 依赖倒置）——续用 ADR-081 模式，新增能力以 provider 注入，不硬编码。
- 前端：图谱栈收敛为「一类语义一库」；编排管线六步均可独立替换（每步一个 provider 接口）。
- **接口即插槽**：编排层每步定义一个 Protocol（`IntentRouter`/`OntologyAligner`/`RuleGuard`/`RetrievalExecutor`/`AnswerComposer`/`OutputContractGate`），可替换实现（如换 LLM、换检索后端）而不改编排。

### 8.3 Feature Flag 灰度

- 新增 `feature_flags` 表（键 `key/enabled/rollouts{user_ids,percentage}`）+ `hashUserId(userId) % 100` 百分比灰度。
- 本轮涉及的大改（图谱栈替换、Token 重建、Wiki 上线）全部经 Feature Flag 灰度，按「内测→5%→50%→全量」推进。

---

## 9. 版本锚定（实际安装版本，禁止幻觉）

### 9.1 前端（`apps/web/package.json` 实测）

| 层 | 依赖 | 实际版本 |
|----|------|----------|
| 框架 | `react` / `react-dom` | `^19.2.4` |
| 语言 | `typescript` | `~6.0.2` |
| 构建 | `vite` / `@vitejs/plugin-react` | `^8.0.4` / `^6.0.1` |
| UI | `antd` | `^6.3.5` |
| UI 扩展 | `@ant-design/pro-components` / `@ant-design/icons` | `^3.1.12-0` / `^6.1.1` |
| 图表 | `@ant-design/charts` / `@ant-design/plots` | `^2.6.7` / `^2.6.8` |
| 拓扑图 | `sigma` / `@react-sigma/core` / `@react-sigma/minimap` | `^3.0.3` / `^5.0.6` / `^5.0.6` |
| 图算法 | `graphology` (+8 子包) | `^0.26.0` |
| 流程编排 | `@xyflow/react` | `^12.10.2` |
| 决策链(迁出中) | `@antv/g6` | `^5.1.0` |
| 局部图 | `cytoscape` (+6 插件) | `^3.34.0` |
| 统计图 | `echarts` | `^6.0.0` |
| 状态 | `zustand` | `^5.0.12` |
| 路由 | `react-router-dom` | `^7.14.1` |
| 国际化 | `i18next` / `react-i18next` / `i18next-http-backend` | `^26.3.1` / `^17.0.8` / `^4.0.0` |
| Agent 协议 | AG-UI（自研客户端 `qa/agui/AGUIProvider.tsx` + `ai-assistant/hooks/useAIChat.ts`） | — |
| 测试 | `vitest` / `@testing-library/react` / `jsdom` | `^4.0.0` / `^16.1.0` / `^25.0.0` |
| 待移除 | `@ant-design/graphs` | `^2.1.1`（零引用） |
| 本轮新增 | `lucide-react` | 版本由 Phase 2 安装时锁定（描边规格见 ADR-092） |

> **Agent 前端集成口径（ADR-099，2026-10-22）**：前端 Agent 集成唯一协议为 **AG-UI**。原先在册的 `ai`（Vercel AI SDK）与 `@openharness/react` 已移除 —— 二者在 `apps/web/src` 零引用，且 SDK 的 `createOHTransport` 只解析 AI SDK 5 data stream 协议，而本项目后端实现的是 AG-UI（`apps/api/odap/infra/openharness/agui/`），协议层不兼容。ADR-070 亦已定调「AG-UI 协议覆盖所有场景，前端只需一套解析器」。复引入条件见 ADR-099。

> 设计 Token 真源：`docs/04-ui/design-tokens.css` + `docs/04-ui/design-tokens.json`（设计侧 Phase 1 交付，`--odap-*` 前缀）。

### 9.2 后端（`pyproject.toml` + `apps/api/pyproject.toml` 实测）

| 层 | 依赖 | 实际版本 |
|----|------|----------|
| 运行时 | Python | `>=3.10`（`pyproject.toml:5`） |
| 框架 | FastAPI + Pydantic v2 | 版本见 `apps/api/pyproject.toml`（本报告标 **待从 lockfile 精确核**） |
| 测试 | `pytest>=8.0.0` / `pytest-asyncio>=0.23.0` / `pytest-mock>=3.12.0` | 同左 |
| Lint | `ruff>=0.5.0` / `black>=23.0.0` / `flake8>=6.1.0` | 同左 |
| 架构适应度 | `import-linter>=2.0` | 同左 |
| 异步任务 | Celery（`apps/api/odap/celery_app.py`） | 版本 **待从 lockfile 精确核** |
| 工作区 | uv workspace：`apps/api` / `packages/openharness` / `packages/hyper-extract` | `pyproject.toml:7-16` |

### 9.3 存储与外部系统（现状，`CONTEXT.md` + 代码）

| 组件 | 用途 | 证据 |
|------|------|------|
| SQLite `odap_main.db` | TBox（真相源） | `CONTEXT.md:11` |
| Neo4j | ABox（`Instance` 标签） | `CONTEXT.md:12` |
| Redis | 缓存/队列 | 任务书背景 |
| MinIO | 对象存储 | 任务书背景 |
| OPA `.rego` | 策略治理 | `infra/opa/policies/*.rego`（16+ 文件） |

> 标注「待从 lockfile 精确核」的项：本轮未逐一解析 `uv.lock`/`pnpm-lock.yaml` 精确 pin，Phase 2 实现前须以 lockfile 为准，禁止按「通用印象」写 API。

---

## 10. 收敛与迁移总表（本轮授权合并/下线）

| 对象 | 动作 | 目标 | 影响面 | 回滚 | ADR |
|------|------|------|--------|------|-----|
| `@ant-design/graphs` | 移除依赖 | 减包体 | lockfile | `pnpm add` 还原 | ADR-091 |
| `@antv/g6` | 迁移 | → `@xyflow/react` | `DecisionChainGraph.tsx` | 保留旧栈一 release | ADR-091 |
| `cytoscape` (+6 插件) | 迁移 | 浏览/算法 → `sigma`+`graphology`；层级/DAG 编辑 → `@xyflow/react` | 4 文件 | 保留旧栈一 release + Feature Flag | ADR-091 |
| `@ant-design/icons`（作为项目图标系统） | 迁移 | → `lucide-react`（描边 1.5 / 16-20-24） | 186 文件 + 55 含 emoji 文件 | 旧图标保留一 release | ADR-092 |
| `colorThemeUtils.ts` 行内注入 / `global.css` 跨色相渐变 | 删除/重建 | 接入 `design-tokens.css` | 主题与主按钮视觉 | semantic token 单点回退 | ADR-093 |
| `docs/02-architecture/ARCHITECTURE_*.md`（10 篇） | 归档 | `ARCHITECTURE-v2.md` | 文档引用 | git 历史可恢复 | ADR-097 |
| `/semantic-admin/pipeline` | 归一 | `/semantic-admin/pipeline-runs` | 菜单/外链 | 恢复一条 Route | ADR-097 |
| `frontend_compat` 兼容层 | 收敛后下线 | 原生 `/api/v1/*` | 968 行 + 前端调用 | 保留至零调用 | ADR-098 |
| 单文件超 300 行（后端 219 / 前端 88） | 按模块拆分 | 全部 ≤300 | 大面积重构 | 分批 + Feature Flag | ADR-094 |

---

## 11. 关键风险与降级路径

| 风险 | 降级路径 |
|------|----------|
| OPA 不可用 | `RuleGuard` fail-closed，仅放行只读查询并标 `degraded=true` |
| LLM 不可用 | 编排层降级为 L1/L2 词典+语义路由，返回「能力受限」提示，不编造 |
| Neo4j 不可用 | 检索走 `mdl`/`metric`（结构化）与文档 `nl`，标注 `graph_unavailable` |
| 单引擎失败 | `unified_router` 引擎降级链 + `degraded_engines[]` 记录 |
| 输出不满足 TBox 形状 | `OutputContractGate` 阻断/标注 `blocked_reasons[]`，不退化为「假通过」 |

---

## 附录：交付物清单

- 本文件 `docs/02-architecture/ARCHITECTURE-v2.md`
- `docs/12-evaluation/ARCHITECTURE-EVALUATION.md`
- `docs/02-architecture/openapi-v2.yaml`
- `docs/07-adr/ADR-091` ~ `ADR-098`
- `docs/decisions/OPEN-DECISIONS.md`
