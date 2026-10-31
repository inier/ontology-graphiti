---
id: odap.l7.adr-079-本体论与llm结合边界
status: active
owner: architect
version: ''
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

# ADR-079: 本体论与 LLM 结合边界（推理层 / 理解层 / 生成层三层治理）

## 状态

**Accepted**（2026-08-20）

## 上下文

ODAP 是本体驱动平台：本体（Ontology）+ USL（统一语义层）提供确定性的语义骨架。同时 QA 问答、智能体、意图识别等环节大量使用 LLM。二者结合时出现两类方向性错误：

1. **LLM 越界**：让 LLM 参与语义判断 / 查询分解 / 推理 / 排序，产生幻觉与不确定性，破坏多跳推理的正确性（2026-08-20 之前 `MultiHopPlanner._plan_with_llm`、`QueryRewriter` HyDE、`CypherGenerator` LLM 生成、`Reranker` 魔法权重等均属此类）。
2. **零 LLM 矫枉过正**：把"推理必须确定性"错误泛化为"全链路零 LLM"，导致模糊、有歧义的自然语言输入无法解析（如"老刘"无法通过精确字典查到"刘备"），漏召回且无补偿机制。

根本问题是缺少一条**清晰的边界原则**：LLM 在哪些环节可以参与、以什么方式参与、失败时如何确定性兜底。

本 ADR 建立三层治理模型，作为后续所有涉及 LLM 改造的权威依据。

## 决策

### 1. 三层治理模型

```
┌────────────────────────────────────────────────────────────────────┐
│                       生成层（Generation）                           │
│    LLM 把确定性结果转成自然语言；每个事实句必须锚定来源（引用/溯源）     │
│    LLM 可自由生成，但事实不允许编造（无来源即不得断言）                 │
├────────────────────────────────────────────────────────────────────┤
│                       理解层（Understanding）                        │
│    LLM 只能「选择」，不能「创造」；选择范围 = 本体 closed set          │
│    - 意图 → QueryIntent 枚举                                        │
│    - 实体 → USL 术语 / 本体实体集合                                   │
│    - 关系 → 本体的 relation types                                    │
│    选择失败 → 确定性兜底（默认值 / 澄清）                              │
├────────────────────────────────────────────────────────────────────┤
│                       推理层（Reasoning）                            │
│    LLM 零参与。推理 = 确定性引擎（Datalog / 图遍历 / 规则）             │
│    多跳路径、结论、排序全部确定性，可复现                              │
└────────────────────────────────────────────────────────────────────┘
```

### 2. 三层责任与 LLM 参与规则

| 层 | 责任 | LLM 角色 | 确定性要求 | 失败兜底 |
|----|------|----------|-----------|----------|
| **推理层** | 多跳遍历、结论推导、结果排序、约束校验 | **禁止** | 100% 确定性 | — |
| **理解层** | 意图分发、实体链接、关系映射、查询改写 | **只选不创**（closed set 内选择） | 结果必须落在 closed set 内 | 默认值 / 触发澄清 |
| **生成层** | 答案组织、自然语言表达、摘要 | **可自由生成** | 事实必须锚定来源 | 事实无来源即不生成 |

### 3. 核心判定规则

**「选择 vs 创造 vs 判断」三分法**：

| 动作 | 定义 | LLM 是否允许 | 示例 |
|------|------|-------------|------|
| **选择（select）** | 从本体已定义的有限集合中挑一个 | ✅ 允许，但结果强校验 | 意图分类：从 `QueryIntent` 枚举选一个 |
| **创造（create）** | 生成本体中不存在的新对象 | ⚠️ 仅生成层允许；理解/推理层禁止 | 生成层写一段回答文字 |
| **判断（judge）** | 决定推理走向 / 语义等价 / 排序 | ❌ 禁止（属推理层） | "判断这两个词是否同义" |

**同义词泛化 = 判断 → 必须走 USL 字典精确查表，禁止字符相似度 / 向量近似 / LLM 语义判断。**

### 4. 理解层「选择」的强校验与兜底

LLM 在理解层每次「选择」都必须满足：

1. **closed set 约束**：输出必须是本体定义集合的成员（token 级精确匹配，非子串/近似）。
2. **归一化**：LLM 选出的实体/术语必须经 `UslTermResolver` 归一化到 canonical（"老刘" → 候选"刘备" → canonical 校验）。
3. **失败兜底**：
   - 结果不在 closed set 内 → 丢弃，回退确定性规则结果。
   - 归一化后仍不在本体实体集合 / 多候选冲突 → **触发澄清**（`clarify`），不静默猜测。
   - 规则可唯一确定时 → 不调用 LLM（规则权威）。

### 5. 推理层「确定性」的硬边界

推理层（对应 `reasoning/` 确定性引擎、`qa` 多跳执行、图遍历）禁止以下行为：

- 禁止 LLM 生成查询计划 / Cypher / 子查询分解
- 禁止向量相似度 / 分数决定推理路径
- 禁止 magic number 阈值判语义等价
- 向量 topK / score 仅用于**展示排序**（UI 呈现），不得决定推理走向

推理路径由**本体结构**（实体类型 + 关系类型 + USL 术语）精确遍历决定。

### 6. 生成层「事实锚定」

生成层（`response_generator` / 答案合成）允许 LLM 自由组织语言，但：

- 每个事实句必须**锚定**到推理层的确定性结果（引用 doc_id / 实体 / 来源）。
- 无来源的事实**不得断言**（宁可说"未查到"，不可编造）。
- 澄清话术由生成层产生，但澄清的**触发**由理解层确定性决定。

## 概念澄清：领域 / 工作空间 / 场景 / 本体 四者关系

> 本节澄清理解层"场景归一化"所依赖的四个核心概念及其层级关系。
> 来源：各模型定义的字段与 `graphiti_writeback_adapter.resolve_ontology` 的运行时映射。

### 7.1 四者定义与作用（模型定稿）

| 概念 | 定义 | 作用 | 绑定关系（定稿） |
|------|------|------|------------------|
| **Workspace（工作空间）** | 顶级资源容器 | **隔离边界**（权限/数据/资源的可见范围） | 拥有多个本体、场景、智能体（`bound_ontology_ids`） |
| **Ontology（本体）** | **独立的一等资源**（概念 schema/TBox） | 定义实体/关系/动作的概念骨架，被多个消费方共享 | 挂 `workspace_id`（必填，做隔离）；**不反向持有场景** |
| **Scenario（场景）** | 业务场景实例 | 组织一次具体业务上下文 | **引用**本体（`ontology_id` 单值权威） |
| **Agent（智能体）** | 智能体实例 | 推理/问答/编排的执行者 | **引用**本体（`ontology_id`，缺失时回退 workspace 默认） |
| **Domain（领域）** | `UslDomain` | 语义领域：术语/同义词的语义边界 | 本体内部的语义组织（`code`），运行时映射到本体 |

```
Workspace（隔离边界：权限/数据可见范围）
   ├── Ontology（独立一等资源，挂 workspace 做隔离）
   │        └── Domain（本体内部语义域，USL__{code} 运行时映射）
   │              └── UslTerm（术语 canonical/synonyms/aliases）
   ├── Scenario（使用方：引用某个 ontology + version）  ← 单向引用，不拥有
   └── Agent（使用方：引用某个 ontology + version）      ← 单向引用，不拥有
```

### 7.2 关键关系判定（模型定稿，含权威数据源）

**场景 ↔ 本体的权威关系是独立关联表 `scenario_ontology_bindings`（多对多 + 状态）：**

```sql
scenario_ontology_bindings (
    id PRIMARY KEY,
    scenario_id NOT NULL,
    ontology_id NOT NULL,
    binding_status DEFAULT 'active',   -- active / inactive / pending
    bound_by, bound_at, unbound_at,
    UNIQUE(scenario_id, ontology_id)    -- 一个场景可绑多个本体，一个本体可被多个场景引用
)
```

1. **本体是独立一等资源，不是场景/智能体的子资源**：
   本体只挂 `workspace_id` 做隔离；场景与智能体是**使用方**，通过关联表引用本体，
   而非"拥有"本体。同一本体可被多个场景/智能体复用。

2. **权威数据源 = `scenario_ontology_bindings`，`Scenario` 上的字段是冗余缓存**：
   - `bind_ontology_to_scenario` / `unbind_ontology_from_scenario` 写关联表后，
     同步 `UPDATE scenarios SET ontology_ids = ...`（派生缓存）。
   - 消费方（如 `QAEngine._get_ontology_ids_for_scenario`）**优先查关联表**，
     `Scenario.ontology_id` / `ontology_ids` 仅作 fallback。
   - 因此：**废弃 `Scenario.ontology_id`（单值旧字段）与 `Ontology.scenario_id`
     （反向冗余）**；`Scenario.ontology_ids` 保留为关联表的派生缓存。

3. **Agent 补本体引用**：
   `AgentConfig` 增加 `ontology_id`（可空）；空则回退 `workspace.bound_ontology_ids`
   取默认。多本体场景下智能体必须能精确指定推理所用本体，否则"用错本体"。

4. **Domain ≠ Scenario**：
   Domain 是语义领域（"老刘"归到哪个概念），Scenario 是业务场景实例，二者不可混用
   （`domain_id or scenario_id` 是反模式）。

### 7.3 理解层场景归一化的正确数据流

```
request.scenario_id
   → 查 scenario_ontology_bindings（权威关联表，binding_status='active'）
      → 得本体 ID 列表（一个场景可绑多个本体）
         → 查各本体的语义域（USL Domain code）
            → domain_id（如 "sanguo"）
               → EntityExtractor.extract(query, domain_id="sanguo")
```

**反模式**（当前实现，需修正）：
```python
domain_id = context.get("domain_id") or context.get("scenario_id") or ""
```
此写法把 `domain_id` 与 `scenario_id` 当作等价物，仅在"场景恰好与领域同编码"时碰巧正确，概念上是错的。正确做法是经 `scenario_ontology_bindings` → 本体 → 语义域 的解析链，而非直接透传 `scenario_id`。

### 7.4 归一化遵循的隔离层级

术语归一化（`UslTermResolver.resolve`）的**作用域是 Domain**，而非 Workspace 或 Scenario：
- 同一 Workspace 下可有多个 Scenario，每个 Scenario 绑定不同 Ontology，进而对应不同 Domain。
- 因此归一化字典必须**按 Domain 隔离**，跨 Domain 不共享同义词映射（"老刘"在 `sanguo`→"刘备"，在 `xiyou` 无此映射）。

## 后果

### 正面
- 边界清晰，杜绝"LLM 越界导致幻觉"与"零 LLM 导致漏召回"两个极端
- 推理层可复现、可审计、可测试（确定性）
- 理解层兼顾自然语言模糊性（LLM 选择）与本体约束（closed set + 归一化）
- 生成层输出有据可查（事实锚定）

### 负面与缓解
- 理解层 LLM「选择」仍需强校验与兜底逻辑，实现成本略高 → 缓解：`UslTermResolver` + 枚举校验是纯函数，可测试
- 澄清机制增加交互轮次 → 缓解：规则可唯一确定时不触发澄清，仅真正歧义才澄清

### 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| LLM 在理解层「选择」仍可能选错（closed set 内但语义错） | 中 | 归一化 + 多候选冲突触发澄清；置信度低于阈值回退规则 |
| 生成层 LLM 编造事实 | 中 | 事实句强制来源锚定，无来源即不生成 |
| "零 LLM"惯性回潮 | 低 | 本 ADR 作为权威依据，改造前先查此文档 |

## 可逆性

**高**。本 ADR 是原则性约束，不改变任何现有模块结构；后续按此原则重构代码时，每处改造可独立回滚。

## 关联

- ADR-050（OADP 业务语义体系：理解/决策/执行分层）
- ADR-056 / ADR-057（语义层 / USL 统一语义层）
- ADR-075（确定性推理引擎，推理层实现）
- ADR-039（QA 引擎架构，理解层/生成层实现）
- ADR-073（基于本体的数据服务四步落地）

## 待办（据此重构，不在本 ADR 内执行）

1. ~~恢复 `EntityExtractor` 的 LLM 实体链接，输出经 `UslTermResolver` 归一化 + 本体实体集合过滤，失败触发澄清。~~（已完成 2026-08-20）
2. ~~生成层 `response_generator` 接入事实锚定（来源引用）。~~（已完成 2026-08-20）
3. ~~对 2026-08-20 已完成的确定性改造做合规复核。~~（已完成 2026-08-20：IntentRecognizer/EntityExtractor 的 LLM「选择」兜底未被误删）
4. **修正理解层场景归一化的解析链**（§7.3）：将 `context.get("domain_id") or context.get("scenario_id")` 的反模式，改为 `scenario_ontology_bindings → 本体 → 语义域 code → Domain` 的正确解析链。
5. 术语归一化作用域按 Domain 隔离（§7.4），确保跨 Domain 不共享同义词映射。
6. ~~废弃 `Ontology.scenario_id` 反向冗余~~（部分完成 2026-08-21：保留列做向后兼容，`create_ontology` 已标注为非权威；schema 未删列）
7. ~~`AgentConfig` 补 `ontology_id`~~（已完成 2026-08-21：字段已加）
8. ~~补 `Ontology.domain_code` 权威字段（含迁移）~~（已完成 2026-08-21：`ontologies` 表新增 `domain_code` 列 + `_migrate` 幂等补列；`save_ontology`/`create_ontology`/`resolve_ontology` 全链路写入；`resolve_ontology` 查找改为 domain_code 精确匹配优先、name 约定兜底）
9. **修正理解层场景归一化解析链**（§7.3 待办第 4 项，未完成）：`context.get("domain_id") or context.get("scenario_id")` 反模式仍未改为 `scenario_ontology_bindings → ontology.domain_code → domain_id` 解析链。
