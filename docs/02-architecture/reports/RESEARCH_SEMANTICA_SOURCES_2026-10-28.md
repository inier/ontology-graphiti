---
id: odap.l2.reports-research-semantica-sources-2026-10-28
status: reference
owner: architect
version: ''
layer: L2
concern: architecture
lifecycle: historical
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 一次性架构审计/评审/研究报告，结论已并入现行架构文档
governance_evidence: docs/02-architecture/README.md 目录说明；文件名含审计日期或 REPORT/AUDIT 标识
---

# 主源调研：Semantica 0.7.0 与 ODAP 嵌入可行性（2026-10 复核）

> **调研日期**：2026-10-28
> **调研对象**：[semantica-agi/semantica](https://github.com/semantica-agi/semantica) v0.7.0（2026-09-22 发布，MIT）；PyPI `semantica`；官网 [getsemantica.ai](https://getsemantica.ai/)；文档站 [docs.getsemantica.ai](https://docs.getsemantica.ai/llms.txt)
> **前序报告**：[RESEARCH_SEMANTICA_COMPARISON_2026-08-14.md](./RESEARCH_SEMANTICA_COMPARISON_2026-08-14.md)（对应 v0.6.5）
> **调研方法**：仅主源。证据来自 PyPI JSON API 与 wheel 制品实解、GitHub 仓库源码/发布/issue、官方文档站、官网文案。**未采信任何二手博客或评测文章**；无法从主源确认的条目显式标注"未核实"。
> **边界**：本次仅研究与记录，未修改任何业务代码，未向 ODAP 引入依赖。

## 0. 结论（先给判断）

**Semantica 0.7.0 不能作为 ODAP 的"统一企业知识智能底座"层。** 它适合被当作**能力清单与领域模型的参考源**，不适合被当作**运行时依赖**。

| 采用方式 | 判定 | 决定性理由 |
|---|---|---|
| 整体替代（ODAP 业务层下沉到 Semantica） | **否** | 无 workspace/租户隔离、无 async、REST 为桩、中文标签被拒；四项均为硬阻断（见 §4.1） |
| 作为独立服务旁挂（REST） | **否** | `semantica/server.py` 的 `/build` 为未接线桩，`/health` 无条件 200，编排层存在 `{"status": "placeholder"}` 返回（§3.12） |
| 作为库进程内嵌（全量） | **否** | 512 MB 安装体积、963 ms `semantica.reasoning` 导入、与 Graphiti 形成第二事实源（§2.3、§4.2） |
| 作为库局部内嵌（3 个接触面 + 适配层） | **有限可行** | 仅 ingest 连接器、chunking、PROV 存证核对；必须包在 ODAP 自己的端口后面（§7.1） |
| 只借鉴设计 / 数据模型 | **是（主要价值）** | 决策域模型、7 类冲突策略、PROV 校验链、22 chunker × 30 ingestor 的能力矩阵 |

一句话：**功能面很宽、单点深度不均、工程契约未定**的 0.x 项目。它的产出是"该做什么"的清单，不是"可以直接调用"的组件。

## 1. 项目基本面（2026-10 实测）

### 1.1 版本、节奏与体积

| 事实 | 数值 | 来源 |
|---|---|---|
| 当前版本 | **0.7.0**，发布于 **2026-09-22** | [PyPI JSON](https://pypi.org/pypi/semantica/json)、[v0.7.0 release](https://github.com/semantica-agi/semantica/releases/tag/v0.7.0) |
| 上一版（前序报告基线） | 0.6.5 | 同上（releases 列表） |
| 发布总数 | 25 个 release，首个 2025-11-21 | [releases](https://github.com/semantica-agi/semantica/releases) |
| 发布节奏（自我声明） | MAJOR 每季度（含破坏性变更）、MINOR 每月、PATCH 按需 | [docs: governance/versioning](https://docs.getsemantica.ai/llms.txt) 索引页 |
| 实际提交强度 | 约 **150 commits/月** | GitHub REST `/repos/.../stats/participation`，2026-10-28 |
| 源码规模 | 393 个 .py / **214,522 LOC**（含 tests） | wheel 制品解包统计 |
| 0.7.0 相对 0.6.5 的模块变化 | **+44 个新模块，0 个删除** | 两版 wheel 目录 diff |

### 1.2 社区与维护结构

| 指标 | 数值（2026-10-28） | 来源 |
|---|---|---|
| Stars / Forks | **14,276 / 1,673** | GitHub REST `/repos/semantica-agi/semantica` |
| Contributors | **134** | GitHub REST `/contributors?per_page=1` + Link 头 |
| Open issues / Open PRs | **79 / 60** | GitHub REST `/issues?state=open` 计数 |
| Closed issues / Closed PRs | 558 / 约 1.4k | 同上 `state=closed` |
| PyPI 近 30 天下载 | **14,741** | [pypistats 口径经 PyPI JSON 交叉](https://pypi.org/project/semantica/) |
| 治理模式 | "maintained by the Semantica team with community contributions"，48h review SLA | [docs: governance](https://docs.getsemantica.ai/llms.txt) |
| 核心团队规模 / 资助方 | **未核实**（无公开 team 页或 FUNDING 文件可确认人数） | — |

> 判读：14k stars 与 134 contributors 说明**关注度高于交付深度**（2,117 个测试、无 rete/decision/ontology 专项测试，§3）。60 个 open PR 积压意味着外部贡献合并慢。

### 1.3 许可与商业化边界

| 项 | 事实 | 来源 |
|---|---|---|
| 代码许可 | **MIT**（仓库根 `LICENSE`） | [LICENSE](https://github.com/semantica-agi/semantica/blob/main/LICENSE) |
| 商业产品 | Free(MIT) / **Paid Pilot** / **Managed Cloud 与 Self-Hosted Enterprise 均标注 "In Development"** | [getsemantica.ai/pricing](https://getsemantica.ai/pricing) |
| 许可风险 | MIT 允许闭源商用与再分发；但**"Enterprise/Self-Hosted"尚在开发**，若未来把多租户/审计/SSO 放进商业版，ODAP 自建这些能力不会遇到许可障碍，但会失去"买了就有"的期待 | 同上 |
| 商标/品牌 | 未声明 trademark 政策（未核实） | — |

> 判读：MIT 是干净的。**风险不在许可，在路线**——厂商把企业级能力（多租户、治理、SLA）留给尚未发布的商业版，等于确认 OSS 版不会补上 ODAP 最需要的那些能力。

### 1.4 生产案例

官网仅公开 **2 个**案例：[Nereus（2026-03）](https://getsemantica.ai/case-studies)、[Ausgrid（2026-05）](https://getsemantica.ai/case-studies)。均无架构细节、无规模数字、无 SLA 描述，无法据此判断"生产可用"。

> 判读：**14k stars 对应 2 个公开案例**，且都不是金融/制药这类强审计行业。以此支撑"企业知识智能底座"的选型论证不成立。

### 1.5 质量与安全信号（0.7.0 发布后仍在 open 的 issue）

| Issue | 内容 | 为什么重要 |
|---|---|---|
| [#2135](https://github.com/semantica-agi/semantica/issues/2135) | 定时安全扫描在 main 失败：authlib 1.8.0 命中 CVE-2026-114615/114616/114617/114618/114620/96760（修复于 1.9.x）、litellm 1.100.1（CVE-2026-114612）、msgpack 1.2.2（CVE-2026-114613） | 间接依赖即攻击面；ODAP 若引入会把 3 个高危包带进同一进程 |
| [#2136](https://github.com/semantica-agi/semantica/issues/2136) | `provenance/integrity.py` 的 `compute_checksum()` 把 16 个字段**直接拼接、无分隔符**，`{"entity_type":"ab","activity_id":"c"}` 与 `{"entity_type":"a","activity_id":"bc"}` 哈希相同；`verify_checksum()`/`verify_chain()` 仍报"完整性通过"；而 docstring 宣称支持 FDA 21 CFR Part 11 / SOX / HIPAA | 这是**合规声明与实现的实质性偏差**。ODAP 若把审计存证托付给它，等于引入一个会"假通过"的校验器（违反 AGENTS.md 第 14 条） |
| [#2137](https://github.com/semantica-agi/semantica/issues/2137) | `BridgeAxiom.apply` 吞掉 provenance 写入失败 | 静默失败，同样违反 fail-explicit |
| [#2138](https://github.com/semantica-agi/semantica/issues/2138) | `BridgeAxiom` 无单位、无适用时间窗、无不确定性字段 | 领域模型尚未收敛，schema 还会变 |

## 2. 真实包结构、API 形态与依赖重量

### 2.1 子包（以 0.7.0 wheel 实际目录为准，非 README 宣传）

| 子包 | 职责 | 实测状态 |
|---|---|---|
| `semantica/kg` | 图构建、实体/关系抽取入口 | 存在，导入 834 ms |
| `semantica/reasoning` | Rete、Datalog、SPARQL、时序、TMS | 存在，导入 963 ms（最重） |
| `semantica/context` | DecisionRecorder/DecisionQuery、上下文装配 | 存在 |
| `semantica/ontology` | SHACL/OWL/SKOS 生成与校验 | 存在，依赖 pyshacl、rdflib |
| `semantica/provenance` | PROV-O、checksum、SQLite 存储 | 存在 |
| `semantica/conflicts` | 冲突检测/消解、SourceTracker | 存在 |
| `semantica/deduplication` | 两阶段 ER、blocking、merge | 存在 |
| `semantica/graph_store` | LPG（Neo4j/FalkorDB/AGE/Neptune） | 存在 |
| `semantica/triplet_store` | RDF（Oxigraph/Blazegraph/Jena/RDF4J） | 存在，**与 graph_store 互不相通** |
| `semantica/pipeline` | PipelineBuilder + ExecutionEngine | 存在，`validate_pipeline` 崩溃（§3.10） |
| `semantica/ingestors` / `chunkers` | 30 / 22 个实现 | 存在 |
| `semantica/server.py`、`semantica_mcp/`、`integrations/` | REST / MCP / 第三方集成 | server 为桩；`integrations/` 与 `semantica_mcp/` 是**未加包名前缀的顶层目录**，打包面不干净 |

### 2.2 公共 API 形态（决定能否"当库用"）

| 观察 | 证据 | 影响 |
|---|---|---|
| `semantica/__init__.py` 的 `__all__` 为**空列表** | [__init__.py](https://github.com/semantica-agi/semantica/blob/main/semantica/__init__.py) | 无稳定顶层导出面，用户只能深入子模块路径 |
| 顶层用模块代理 + 白名单，**白名单未含** `context`/`reasoning`/`provenance`/`conflicts`/`deduplication` | 同上 | 恰好是 ODAP 最关心的五个子包无法从顶层访问 → 只能硬编码内部路径，升级即断 |
| 全同步 API，**无 async 变体** | 全仓库无 `async def` 公共入口 | 与 FastAPI 异步栈只能靠线程池桥接（§4.1） |
| 无类型化契约文件（无 `.pyi`、无公开 Protocol/ABC 层） | wheel 内无 stubs | "稳定公共 API"不成立，只能按源码调用 |

### 2.3 依赖重量与导入成本（本地实测）

| 指标 | 0.6.5 | 0.7.0 | 说明 |
|---|---|---|---|
| 核心依赖数 | 42 | **22** | 依赖瘦身是 0.7.0 的真实改进 |
| extras 数 | — | **62** | 大量能力藏在 extra 后面（gensim、litellm、crewai 等） |
| `requires-python` | 兼容 3.8/3.9 | **">=3.10,<3.14"** | pyproject 注释引用 #1506 说明放弃 3.8/3.9 |
| 安装下载量 | — | **47 wheels / 118.3 MB** | `pip download` 实测 |
| 安装后体积 | — | **512 MB** | venv 实测 |
| `import semantica` | — | **23 ms** | 因为 `__init__` 几乎不导入 |
| `import semantica.reasoning` | — | **963 ms** | 真正付代价的地方 |
| `import semantica.kg` | — | **834 ms** | 同上 |

> 判读：**顶层 23 ms 是假象**——它什么也没导入。一旦用上 reasoning/kg，进程冷启动即付 0.8–1.0 s。512 MB 与 FastAPI 主进程共存意味着镜像体积和内存基线一起抬升。Python 版本下界 3.10 与 ODAP（`apps/api/pyproject.toml` 已 `>=3.10`）一致，无冲突。

## 3. 能力成熟度复核

### 3.1 能力 - 成熟度 - 证据（主表）

成熟度口径：**可用**＝有实现且有测试/实测通过；**可用但有坑**＝能用但存在契约或正确性缺陷；**原型**＝存在但关键路径缺失或依赖可选件；**桩**＝返回固定值/占位。

| 能力 | 实现位置 | 成熟度 | 证据 | 对 ODAP 可用性 |
|---|---|---|---|---|
| 决策记录 DecisionRecorder | `context/decision_recorder.py` | 可用但有坑 | 同步；`_store_decision_node` 用 `CREATE (d:Decision {...})`，**非幂等**（重复写入产生重复节点）；`link_entities` 建 `ABOUT` 边 | 不可直接用（§3.2） |
| 决策追溯 trace_decision_path | `context/decision_query.py` | 原型 | 签名只有 `(decision_id, relationship_types)`，**无 `max_depth`**，与文档不符 | 不可用 |
| 决策影响分析 | 同上 | 原型 | `analyze_decision_influence(max_depth=3)` 缺可选组件时返回 `{"error": "Advanced features not available"}`；真实计算依赖 gensim/Node2Vec | 不可用（且静默降级） |
| Rete 引擎 | `reasoning/rete_engine.py`（642 LOC） | 可用但有坑 | 0.7.0 重写：alpha `_compiled` 正则、beta token memory、链式 join、action 去重；**仍无 alpha 共享**（§3.3） | 不可用（性能） |
| Datalog（半朴素求值） | `reasoning/` | 可用 | semi-naive fixpoint | 可参考（ODAP 已用 pyDatalog 0.17.4） |
| SPARQL 推理 | `reasoning/` SPARQLReasoner | 可用 | 0.7.0 起对真实三元组库执行查询，不再只做语法包装 | 与 ODAP rdflib 方案重叠 |
| 时序推理（Allen 13 关系） | `reasoning/` | 可用 | 13 种区间关系全实现 | 与 ODAP `temporal_algebra` 重叠 |
| 真值维护 / 信任分层 | `reasoning/` | 可用但有坑 | TMS **仅支持非递归规则**（文档明示限制） | 不可直接用 |
| SHACL 校验 | `ontology/ontology_validator.py` | **可用** | 真实调用 `pyshacl`（`_run_pyshacl`），非自研近似 | 与 ODAP `design/engine/shacl` 重叠 |
| OWL 生成 | `ontology/owl_generator.py` | 可用但有坑 | rdflib 序列化 OWL，**不是推理机**；不做 OWL RL/EL 蕴含 | 仅参考 |
| PROV-O 导出 | `provenance/manager.py` | 可用 | 实测导出 **1,270 字节 Turtle**，结构合法 | 可参考导出层 |
| PROV 完整性校验 | `provenance/integrity.py` | **可用但有坑（有正确性缺陷）** | checksum 非单射（#2136），`verify_chain()` 假通过 | **不可用**（审计红线） |
| 图分析 | `graph_store` / 分析模块 | 原型 | 中心性/社区类算法存在；影响分析需 gensim；无大规模基准 | 不可用（ODAP 有 GDS + NetworkX 双后端） |
| 冲突检测（7 策略） | `conflicts/` | 可用 | 7 种消解策略 + 冲突分析器 + 调查指南 | 可参考（ODAP 3 策略） |
| SourceTracker 可信度 | `conflicts/source_tracker.py` | 可用 | 来源可信度累积与 Wilson 式平滑 | 与 ODAP 实现同类 |
| 两阶段 ER / 去重 | `deduplication/` | 可用但有坑 | blocking → clustering → merge 三段落齐；**无 P/R 基准**，参数靠经验 | 仅参考 |
| Chunker | `chunkers/` | 可用 | **22 种**（非前序报告口径的 13） | 可借鉴清单 |
| Ingest 连接器 | `ingestors/` | 可用（质量未核实） | **30 种**；无统一重试/限流/增量语义说明 | 最有价值的复用面 |
| Pipeline DSL | `pipeline/pipeline_builder.py` | **桩（会崩）** | `validate_pipeline()` 对 `ValidationResult` 调 `.get('valid')` → `AttributeError`（0.6.5 同样存在） | 不可用 |
| LPG 存储 | `graph_store/neo4j_store.py` | 可用但有坑 | `CREATE (n:{label} $props)`；`query_sanitize` **只允许 ASCII 标识符**（§4.1） | 不可用（中文标签被拒） |
| RDF 存储 | `triplet_store/` | 可用 | Oxigraph/Blazegraph/Jena/RDF4J 四后端 | 与 ODAP rdflib/Oxigraph 重叠 |
| Polyglot 统一 API | — | **不存在** | LPG 与 RDF 是两套独立 Store 接口，无跨模型查询/事务 | 宣传点不成立 |
| MCP Server | `semantica_mcp/` | 可用 | **15 个工具** | 可参考工具切分 |
| REST 服务 | `server.py` | **桩** | `/build` 调用被注释掉仍返回 accepted；`/health` 无条件 200 | 不可用 |

### 3.2 决策智能：领域模型强，运行时弱

领域模型是 Semantica 最值得抄的部分：`Decision` / `DecisionContext` / `Policy` / `PolicyException` / `Precedent` / `ApprovalChain`，把"决策"提为一等公民，并配 `DecisionRecorder` / `DecisionQuery`。

但运行时三个问题使其无法承接 ODAP 的 P0：

1. **无隔离维度**：`CREATE (d:Decision {...})` 无 tenant/workspace 属性，多租户部署下决策图会混在一起。
2. **非幂等**：重复提交同一决策会产生重复节点，没有 MERGE 或业务键唯一约束。
3. **影响分析是可选件**：缺 gensim 时返回 `{"error": ...}` 而不是抛异常——这是"看起来成功"的失败，与 ODAP fail-explicit 规则正面冲突。

对比 ODAP `biz/decision/decision_record/`：`record_decision` / `trace_chain` / `find_similar_by_text` / `analyze_impact` / `add_causal_link` 全异步、带 `workspace_id`、走 `neo4j_decision_store` + `neo4j_decision_query`，并有专门的隔离测试。**这一项 ODAP 已经领先，没有引入动机。**

### 3.3 确定性推理：Rete 被重写，但算法没变（修正 2026-08 结论的一半）

前序报告写"其官方自认 `match_patterns()` 不成熟"。2026-10 复核结论：**这个表述已经过时，但结论仍然成立，理由换了。**

- **已改进**：`rete_engine.py` 已从"正则扫一遍"升级为 alpha/beta 网络，有 `_compiled` 正则、`left_tokens`/`right_tokens` 双 token memory、`_propagate_to_beta` 链式 join、`execute_matches` 的动作去重、`get_network_stats` 可观测。它不再是玩具。
- **未改进**：**没有 alpha 节点共享**。实测 100 条完全相同的规则生成 **100 个 alpha 节点**，复杂度仍是 O(规则数 × 事实数)。基准：1,000 事实 × 100 规则 = **0.41 s**，规则数线性放大延迟。
- **仍是正则做 unification**：`_build_condition_regex` 把 `?var` 编译成命名组、用 `.+?` 匹配，跨字段类型/转义边界未做防护。

> 结论：**"不参考 Semantica Rete 实现"这条 ADR 决策无需修改**，但理由应从"对方自认不成熟"改为"无 alpha 共享导致 O(R×F)，且 unification 基于正则"。ODAP 用 pyDatalog 0.17.4 的路线正确。

### 3.4 SHACL / OWL / SKOS

SHACL 是**真实现**（`_run_pyshacl` 直接依赖 pyshacl），比自研校验器可信。`OntologyEngine.to_shacl / export_shacl / validate_graph` 三段式接口清晰，值得借鉴其"生成-导出-校验"分层。OWL 侧只是 rdflib 序列化 + 少量一致性检查，**没有 DL 推理**，不要误读为推理机。SKOS 是词表工具，与 ODAP 的 USL/OL 六层体系不在一个抽象层。

ODAP 已有 `biz/core/ontology/design/engine/{shacl,owl}`（ADR-075/076），**重合度高，无引入价值**；唯一可借鉴的是"ontology quality gate + bootstrap_schema"这种把校验前置到建模期的编排方式。

### 3.5 PROV-O

导出层可用（实测 1,270 字节合法 Turtle），模型覆盖 Entity/Activity/Agent。但**完整性层不可用**：#2136 证明 checksum 存在碰撞且 `verify_chain()` 会假通过，同时 docstring 声称满足 21 CFR Part 11 / SOX / HIPAA。对 ODAP 而言这不是"待修 bug"，而是**供应商对合规语义的理解不可靠**的信号。

ODAP 的 `infra/security/provenance/{prov_o_mapper,audit_exporter,provenance_routes}` 已交付（ADR-077），可借鉴的只有"checksum + 链式 verify"这个**设计意图**，实现必须自建。

### 3.6 图分析

存在中心性/社区检测类算法，但影响分析路径绑 gensim/Node2Vec（可选 extra），无公开基准。ODAP 的 `infra/graph/analytics/{service,gds_backend,networkx_backend}` 已是双后端（GDS 生产 + NetworkX 兜底），能力面更完整。**不采用。**

### 3.7 冲突与 SourceTracker

Semantica 的 **7 种消解策略 + 冲突分析器 + 调查指南**是它的强项，比 ODAP 现有 3 策略更宽。ODAP 的 `biz/core/ontology/construction/conflicts/{detector,resolution,source_tracker,models}` 已有 3 策略 + Wilson 平滑 `(hits+1)/(total+2)`。

> 结论：**策略清单可抄（borrow-only），代码不引入**——因为冲突消解必须与 ODAP 的本体/审批/审计链耦合，跨库调用会把"为什么这样消解"的因果链切断。

### 3.8 两阶段 ER / 去重

blocking → clustering → merge 结构完整，但**没有任何 precision/recall 基准**，阈值靠经验值。ODAP 若需要，应按自己的领域语料做标定，而不是继承别人的魔数。**仅参考结构。**

### 3.9 Chunker / Ingestor

- **22 个 chunker**（前序报告按 README 口径记为 13，实际目录更多），覆盖语义/结构/代码/表格等切分。
- **30 个 ingestor**，是整个项目**复用价值最高**的部分：纯 I/O 适配层，无状态、无 schema 侵入，最适合"抄而不是依赖"；缺陷是无统一的重试/限流/增量水位语义，质量未核实。

### 3.10 Pipeline DSL

设计是对的（`PipelineBuilder` + `ExecutionEngine`：ThreadPoolExecutor、按依赖分层、`parallel_safe` 标记、ProcessPool 并行管理器）。但 `validate_pipeline()` 直接崩溃（`'ValidationResult' object has no attribute 'get'`），且 0.6.5 就有——**说明这个入口没有测试覆盖**。测试目录 81 个文件、2,117 个 `def test_`，其中 `test_pipeline_orchestration.py` 是直接调 `PipelineValidator`，绕过了 builder 包装层，因此漏掉了这个 bug。

### 3.11 Polyglot（RDF + LPG）

**不存在统一抽象**。`graph_store`（Neo4j/FalkorDB/AGE/Neptune）与 `triplet_store`（Oxigraph/Blazegraph/Jena/RDF4J）是两套独立客户端、两套查询语言、两套事务语义。官网"polyglot"应理解为"两种都支持"，而非"两种能联合查询"。这一点必须在任何选型材料里写清楚，否则会被误当作"统一图底座"。

### 3.12 服务面（MCP / REST / Explorer）

- **MCP：15 个工具**，切分合理，是可借鉴的"工具粒度"样本。
- **REST：桩。** `server.py` 的 `/build` 里真正调用被注释掉，接口仍返回 accepted；`/health` 无条件 200。`core/orchestrator.py` 在 ImportError/OSError/ProcessingError 分支返回 `{"status": "placeholder", "results": results}`。
- **Explorer：约 83 条 FastAPI 路由**，可用，但鉴权与多租户未核实。

> 这三条合起来否决了"作为独立服务旁挂"的选项：**健康检查会说谎、构建会说谎、失败会变成 placeholder**。ODAP AGENTS.md 第 14 条明确禁止静默降级与假成功。

## 4. 嵌入可行性

### 4.1 可行性矩阵

| 维度 | 结论 | 证据 | 处置 |
|---|---|---|---|
| pip 安装体积 | 可接受但偏重 | 118.3 MB 下载 / **512 MB 安装**（实测） | 只在独立镜像层引入 |
| Python 版本 | **兼容** | `>=3.10,<3.14` vs ODAP `>=3.10` | 无冲突 |
| 与 FastAPI 共存 | **技术上可行，工程上别扭** | 全同步 API、无 async 入口 | 必须 `run_in_threadpool` 包裹，且线程池会成为瓶颈 |
| 仅用子模块 | **可行但脆** | `__init__` 白名单不含 context/reasoning/provenance/conflicts/deduplication → 只能 `from semantica.context.decision_recorder import ...` | 升级即断，必须锁死版本并写导入契约测试 |
| 稳定公开 API/契约 | **不成立** | `__all__ = []`、无 `.pyi`、无 Protocol 层、季度 MAJOR | 不把它当 API，当"vendored 参考实现" |
| 版本兼容策略 | 需自建 | 25 releases / 10 个月，0.7.0 已有 4 项破坏性变更 | 引入即需 pin + 每季度回归 |
| 与 Graphiti/Neo4j 共存 | **冲突** | 见 §4.2 | 不共享库/实例 |
| 作为第二事实源风险 | **高** | 见 §4.2 | 禁止写同一图 |

### 4.2 四个硬阻断

1. **中文标签被拒（数据层）**。`graph_store/query_sanitize.py` 的 `sanitize_identifier` 只接受 ASCII 标识符；实测把标签 `人物` 传入直接抛 `ValidationError`。ODAP 的领域本体以中文业务词为主，这一条单独就否决了 LPG 侧的复用。（该限制的由来是 Cypher 注入修复 GHSA-482h-hw99-h62p，属于"修安全时牺牲了 i18n"，短期不会改。）
2. **零租户/工作区隔离（安全层）**。全仓库没有 workspace/tenant 概念，`Decision`、`Entity` 节点无隔离属性。ODAP 的 ADR-023/041/063 把工作区隔离作为硬约束，Semantica 无法承载。
3. **零 async（性能层）**。ODAP 后端是异步 FastAPI；把 963 ms 导入 + 同步图查询塞进事件循环，只能靠线程池，P95 会退化，且无法做请求级取消。
4. **REST 与编排是桩（可信层）**。`/build` 假 accepted、`/health` 无条件 200、orchestrator 返回 placeholder——直接违反 fail-explicit。

### 4.3 与 Graphiti 并存 = 第二事实源

Graphiti 的模型是**双时态**：`valid_at` / `invalid_at` / `created_at`，边会被失效而不是删除，实体用 uuid 主键。Semantica 的 `graph_store` 是**无时态的 LPG 写入**：`CREATE (n:Label $props)`、用 `id(n)` 做身份、无 `valid_at` 概念、不感知失效。

两者写同一个 Neo4j 的后果：同一实体在两套标签下各存一份（`Entity` vs Graphiti 的 `Entity` 节点但属性/主键语义不同），时间旅行查询会看到"Semantica 写入的永久有效事实"和"Graphiti 已失效的事实"并存，**无法判定哪个是真相**。这不是可以靠命名空间规避的问题，而是**两套时间语义不可调和**。

> 因此：若引入，必须**独立 Neo4j database 或独立实例**，并明确"Semantica 侧数据是派生视图，不是事实源"。任何双向同步方案都应否决。

## 5. v0.6.5 → 0.7.0 变更

| 类别 | 变更 | 影响 | 来源 |
|---|---|---|---|
| 版本 | 0.6.5 → **0.7.0**（2026-09-22） | MINOR 位却含破坏性变更 | [v0.7.0](https://github.com/semantica-agi/semantica/releases/tag/v0.7.0) |
| **破坏性** | `Entity.confidence` 改为 `Optional` | 下游若假设非空会 NPE/校验失败 | release notes |
| **破坏性** | `PolicyEngine.check_compliance` 改为抛异常（原为返回结果对象） | 调用方 try/except 需重写；这是"变严格"，方向正确但破坏兼容 | release notes |
| **破坏性** | 移除 `dev` extra | CI 脚本 `pip install semantica[dev]` 失效 | release notes |
| **破坏性** | 移除 `crewai` extra | 集成方需自行安装 | release notes |
| 依赖 | 核心依赖 42 → **22** | 真实改善；但能力更多挪进 62 个 extras，用户需明确选装 | [pyproject.toml](https://github.com/semantica-agi/semantica/blob/main/pyproject.toml) |
| Python | 放弃 3.8/3.9，改为 `>=3.10,<3.14` | 与 ODAP 一致 | 同上（注释引用 #1506） |
| 推理 | Rete 重写（alpha/beta、token memory、链式 join、动作去重） | 从"玩具"到"可用但有性能墙" | [rete_engine.py](https://github.com/semantica-agi/semantica/blob/main/semantica/reasoning/rete_engine.py) |
| 推理 | SPARQLReasoner 执行真实查询 | 从"语法包装"到"可执行" | release notes |
| 结构 | **+44 模块，0 删除** | 没有清理，只有堆叠；包体积继续增长 | wheel diff |
| 未修 | `PipelineBuilder.validate_pipeline` 崩溃 | 跨两版未修，说明无测试覆盖 | [pipeline_builder.py](https://github.com/semantica-agi/semantica/blob/main/semantica/pipeline/pipeline_builder.py) |
| 未修 | REST `/build` 桩、orchestrator placeholder | 跨版本仍是桩 | [server.py](https://github.com/semantica-agi/semantica/blob/main/semantica/server.py)、[orchestrator.py](https://github.com/semantica-agi/semantica/blob/main/semantica/core/orchestrator.py) |
| 新增风险 | #2135 安全扫描红灯、#2136 checksum 非单射 | 合规叙事与实现脱节 | 见 §1.5 |

**关于"社区成熟度是否支撑底座"**：14k stars / 134 contributors / 150 commits 月 的数字看起来够，但反证更硬——**81 个测试文件、2,117 个测试里没有 `test_rete`、`test_reasoning`、`test_decision`、`test_ontology`**；最核心的四块能力零专项测试。这不是"测试少"，而是**测试覆盖与功能宣称不匹配**，属于典型的"广度优先、深度欠账"阶段。**不支持底座定位。**

## 6. 与 ODAP 的重合与差距（2026-10 复核）

### 6.1 已重合（ODAP 已交付，Semantica 无增量）

| 能力 | ODAP 现状 | Semantica 对照 | 结论 |
|---|---|---|---|
| 决策记录/追溯/影响/相似 | `biz/decision/decision_record/`，异步 + `workspace_id` + 类型化因果边 + OPA 门禁 | 同步、无隔离、非幂等、影响分析依赖 gensim | **ODAP 领先** |
| 确定性推理 | pyDatalog 0.17.4 + Allen 时序 + `state_at`（ADR-078/079） | Rete 无 alpha 共享、TMS 仅非递归 | **ODAP 领先** |
| SHACL/OWL 治理 | `design/engine/{shacl,owl}`（ADR-075/076） | 真 pyshacl，但 OWL 无 DL 推理 | **持平** |
| PROV-O | `infra/security/provenance/`（ADR-077） | 导出可用，校验有正确性缺陷 | **ODAP 领先**（正确性维度） |
| 图分析 | GDS + NetworkX 双后端（ADR-085） | 算法存在，影响分析绑 gensim | **ODAP 领先** |
| 冲突/来源可信度 | 3 策略 + Wilson 平滑 | **7 策略** + 分析器 + 调查指南 | **Semantica 策略更宽** |
| 语义管理（USL/OL/质量门/审批/漂移） | `semantic_admin` 完整 6 层 | **无对应物** | **ODAP 独有** |
| OPA 策略门禁 / HITL / AG-UI | 已集成 | 无 | **ODAP 独有** |

### 6.2 Semantica 仍然领先的部分（可借鉴清单）

1. **Ingest 连接器广度：30 个**，覆盖的源类型比 ODAP 多；纯适配层，最值得抄。
2. **Chunking 广度：22 个**，含代码/表格/结构感知切分。
3. **PROV 存证的"链式校验"设计意图**（实现不可用，但"每步 checksum + verify_chain"的思路值得内化）。
4. **冲突消解 7 策略**与"冲突调查指南"这一产物形态。
5. **MCP 15 工具**的粒度切分（对 ODAP 暴露 Agent 工具有参考价值）。
6. **evals 框架**的存在本身（ODAP 目前缺统一评测入口）。

### 6.3 对 2026-08 结论的修正

| 2026-08 判断 | 2026-10 复核 | 说明 |
|---|---|---|
| "Rete `match_patterns()` 不成熟" | **半修正**：已重写为 alpha/beta 网络，但无 alpha 共享、仍 O(R×F) | 结论（不用）不变，理由更新 |
| "13 个 chunker" | **修正为 22** | README 口径落后于目录 |
| "polyglot 图存储" | **修正**：两套独立 Store，无统一 API | 宣传误读风险高 |
| "可谨慎作为依赖引入" | **收紧**：仅 3 个接触面可局部依赖 | 因隔离/中文/async/桩四项硬阻断 |
| "6 项能力缺口" | **收窄为 2 项**（ingest 广度、chunking 广度） | ODAP 已补完决策/推理/SHACL/PROV/图分析/冲突 |

## 7. 判定与触发条件

### 7.1 最终判定：**不整体替代 + 不整体依赖；仅 3 处"带适配层的局部依赖"，其余 borrow-only**

| 接触面 | 形式 | 强制约束 |
|---|---|---|
| Ingest 连接器 | 逐个人工移植（copy-adapt），不做运行时依赖 | 必须改造成 ODAP 的 `IIngestor` 端口；补重试/限流/增量水位 |
| Chunker | 逐个人工移植 | 统一到 ODAP 分块契约与 metadata schema |
| PROV 校验思路 | borrow-only（不引代码） | 自建单射 checksum（带长度前缀/分隔符）+ 负向测试（碰撞用例必须失败） |

**明确不做**：不引入 `semantica` 作为 `apps/api` 依赖；不部署其 REST/MCP；不与 Graphiti 共享 Neo4j 实例或 database；不采纳其 `Decision` 模型（ODAP 已有更严格的）。

### 7.2 重新评估的触发条件（任一满足即重评）

1. 发布 **1.0** 且 changelog 明确"公共 API 冻结"，`__all__` 非空并有 `.pyi`。
2. `graph_store` 支持**非 ASCII 标识符**（或改为参数化 label 白名单映射），且 `sanitize_identifier` 有 i18n 测试。
3. 出现 **workspace/tenant 一级概念**并落到 all stores（不是文档承诺，是代码里的必填参数）。
4. 提供 **async 公共 API**（至少 ingest/query 两条路径）。
5. `/build` 与 `/health` 变为真实实现，且 orchestrator 的 `placeholder` 分支被删除（fail-explicit）。
6. #2136 修复并附**碰撞回归测试**；#2135 安全扫描转绿。
7. 出现**金融/制药/能源强审计行业**的公开生产案例，且披露规模与 SLA。

> 上述 7 条中 1、2、3、5 是"能不能用"，4、6、7 是"敢不敢用"。当前 **0/7**。

### 7.3 给 ODAP 的行动项（研究结论，不含代码改动）

- ADR-075~079、085、091 的"不参考 Semantica 实现"结论**维持**，但需把 Rete 的理由改写为技术性理由（O(R×F)、正则 unification），避免引用会过期的"官方自认不成熟"。
- 新增一条 borrow-only 清单：30 ingestor / 22 chunker / 7 冲突策略 / MCP 工具粒度 / evals 框架形态。
- 若要补 PROV 合规叙事，**不要**引用 Semantica 的 21 CFR Part 11 说法作为先例。

## 8. 未核实项（显式声明）

| 项 | 原因 |
|---|---|
| 核心团队人数与资助方 | 无公开 team/FUNDING 信息 |
| `Precedent` 混合检索的召回质量 | 无基准、无公开评测 |
| 30 个 ingestor 的实际可用率 | 仅确认文件存在，未逐个跑通（需外部凭证/服务） |
| Explorer 的鉴权与多租户实现 | 未逐路由审计 |
| 2026-10 之后是否有补丁版本 / 商业版（Managed Cloud、Self-Hosted Enterprise）功能边界 | 调研截止 2026-10-28；商业版官网标注 "In Development"，无文档 |

## 9. 来源清单（访问日期 2026-10-28；GitHub 直连受限，仓库内容经 wheel 制品与 REST 交叉核验）

**代码与仓库**
1. https://github.com/semantica-agi/semantica
2. https://github.com/semantica-agi/semantica/blob/main/pyproject.toml
3. https://github.com/semantica-agi/semantica/blob/main/LICENSE
4. https://github.com/semantica-agi/semantica/blob/main/semantica/__init__.py
5. https://github.com/semantica-agi/semantica/blob/main/semantica/reasoning/rete_engine.py
6. https://github.com/semantica-agi/semantica/blob/main/semantica/context/decision_recorder.py
7. https://github.com/semantica-agi/semantica/blob/main/semantica/context/decision_query.py
8. https://github.com/semantica-agi/semantica/blob/main/semantica/provenance/integrity.py
9. https://github.com/semantica-agi/semantica/blob/main/semantica/provenance/manager.py
10. https://github.com/semantica-agi/semantica/blob/main/semantica/ontology/ontology_validator.py
11. https://github.com/semantica-agi/semantica/blob/main/semantica/ontology/owl_generator.py
12. https://github.com/semantica-agi/semantica/blob/main/semantica/graph_store/query_sanitize.py
13. https://github.com/semantica-agi/semantica/blob/main/semantica/graph_store/neo4j_store.py
14. https://github.com/semantica-agi/semantica/blob/main/semantica/pipeline/pipeline_builder.py
15. https://github.com/semantica-agi/semantica/blob/main/semantica/server.py
16. https://github.com/semantica-agi/semantica/blob/main/semantica/core/orchestrator.py
17. https://github.com/semantica-agi/semantica/tree/main/semantica （子包目录）与 `/tree/main/tests`（测试目录）

**发布与 issue**
18. https://github.com/semantica-agi/semantica/releases/tag/v0.7.0
19. https://github.com/semantica-agi/semantica/releases
20. https://github.com/semantica-agi/semantica/issues/2135
21. https://github.com/semantica-agi/semantica/issues/2136
22. https://github.com/semantica-agi/semantica/issues/2137
23. https://github.com/semantica-agi/semantica/issues/2138

**包与制品**
24. https://pypi.org/project/semantica/
25. https://pypi.org/pypi/semantica/json
26. https://pypi.org/project/semantica/#files （`semantica-0.7.0-py3-none-any.whl`、`semantica-0.6.5-py3-none-any.whl` 实解对比）

**官方文档**
27. https://docs.getsemantica.ai/llms.txt （文档索引，用于定位以下页面）
28. https://docs.getsemantica.ai/guides/decision-intelligence
29. https://docs.getsemantica.ai/guides/reasoning
30. https://docs.getsemantica.ai/guides/shacl
31. https://docs.getsemantica.ai/guides/conflict
32. https://docs.getsemantica.ai/reference/pipeline 、`/reference/graph_store` 、`/reference/triplet_store`
33. https://docs.getsemantica.ai/getting-started/installation 、`/concepts` 、`/faq`

**官网**
34. https://getsemantica.ai/
35. https://getsemantica.ai/pricing
36. https://getsemantica.ai/case-studies

**ODAP 侧对照（本地文件）**
37. `e:/demo/ai/ontology-graphiti/docs/02-architecture/reports/RESEARCH_SEMANTICA_COMPARISON_2026-08-14.md`、`docs/02-architecture/ARCHITECTURE_TARGET_PLAN.md`
38. `e:/demo/ai/ontology-graphiti/apps/api/pyproject.toml`
39. `apps/api/odap/biz/decision/decision_record/`、`apps/api/odap/biz/core/ontology/construction/conflicts/`
40. `apps/api/odap/infra/security/provenance/`、`apps/api/odap/infra/graph/analytics/`
41. `e:/demo/ai/ontology-graphiti/AGENTS.md`（第 14 条 fail-explicit）
