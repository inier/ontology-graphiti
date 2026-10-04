# 架构评审：ODAP 对照 Talisman《The Ontology Pipeline》六阶段/九工序框架

- **日期**：2026-10-03
- **评审方法**：`architecture-visualization:risk-quality-reviewer`（证据模型与置信度规则遵循 `architecture-contract.md` / `architecture-evidence-model.md`）；风险关系图用 `graphviz`（见同目录 `review_ontology_pipeline_risk_map.dot`）
- **受众**：平台架构师、语义治理模块负责人、技术决策者
- **范围**：后端 `apps/api/odap/` 的语义相关链路（semantic_admin、core/ontology、data/ingest、data/perception、data/knowledge_base、data/qa、infra/graph、infra/query、infra/observability），辅以 docs/ADR/specs 与测试
- **参照框架**：Jessica Talisman《The Ontology Pipeline® — A Semantic Knowledge Management Framework》(2025-05)。六阶段：①受控词表 ②元数据标准 ③分类法 ④叙词表 ⑤本体 知识图谱；九工序：清洗、准备、协调、建模、测试、富化、强制、报告、度量
- **阅读顺序**：执行摘要 → 六阶段映射 → 九工序映射 → 发现表 → 优势 → 整改计划 → 未知与假设
- **证据约定**：所有结论标注 `file:line`；置信度 high=代码/配置直接证据，medium=多信号一致，low=命名/结构推断；"仅文档声称" 单列，不与代码事实混排

---

## 1. 执行摘要

ODAP 不是"跳级盖楼"的项目，而是少数真正把 Talisman 第一、二阶段当作一等公民来实现的平台：它有一个带同义词/近义/别名/定义/停用词标记的受控词表（USL），有一条从术语抽取到公理推导的六层流水线（OL Pipeline），以及把"强制/报告/度量"做成产品功能的质量闸、两级审批与仪表盘。这在同类"直接画知识图谱"的项目中是显著优势，也正面回应了文章"不要跳级""语义工程要可估算可度量"的核心主张。

但评审发现三个高优先级架构风险，均与"框架主张"和"实际执行面"之间的缝隙有关：

1. **双车道强制不一致（F1，high）**：治理车道（OL 管线→质量闸→审批→写回）有真实强制；而高吞吐的摄入车道（知识库建图、感知事件）绕过本体强制自由写图（中文类型降级为 `zh_type`、GraphWriteProxy 无 schema 校验、SHACL 未挂写图路径）。用框架语言说：这条车道事实上跳过①–④级直接落到⑥级，图谱会持续积累未经词表/本体批准的节点——正是文章警告的"概念对不上"，但发生在平台内部。
2. **度量完整性失真（F2，high）**：质量闸 G2.2（基数）、G2.3（is_a 无环）为占位恒 1.0，G2.4（LLM Judge）默认关闭；而仪表盘把三门均分作为 KPI 上报。度量层是文章框架的落脚点，占位分数进入 KPI 会使审批与汇报依据系统性偏高。
3. **词表归一未接入写入链（F3，medium-high）**：USL 术语归一器（同义词→canonical 确定性查表）只服务于 QA 检索改写与候选去重，未接入抽取/写图主链。写入侧保留原始名、检索侧靠查询改写补救，属于"治标不治本"的对齐策略。

另有中优先级：元数据标准阶段偏薄（F4）、semantic_admin 设计文档与代码漂移（F5，违反仓库自身规则 12）、叙词表关系载体不完整（F6）、SHACL 形状不持久化（F7，与 F1 同根）、审批权限硬编码角色（F8，low）。

**总体判断**：以六阶段成熟度看，ODAP 在①⑤两阶段强、③⑥中等偏强、④部分、②弱；以九工序看，"协调"与"测试"最弱、"强制"呈双车道分裂。平台具备文章所说的"语义基础设施"雏形，当前最该投资的不是新增阶段，而是**把治理车道的强制与度量一致性扩展到摄入车道**。

---

## 2. 六阶段映射（当前态）

| 阶段 | ODAP 对应实现 | 关键证据 | 成熟度(0-5) | 置信度 |
|---|---|---|---|---|
| ① 受控词表 | USL 术语库：`UslTerm` 含 canonical、synonyms(UF)、near_synonyms、aliases、definition、stoplist_flag、semantic_type(6 枚举)、en_mapping；L2 概念合并注入 USL 去重；L5 三分类融合(merge/keep_as_new/flag_conflict)；G1.5–G1.7 去重率≥0.98/互包含/同名冲突；驳回可入停用词 | `biz/semantic_admin/usl_manager/models/usl_term.py:59-75`；`ol_pipeline/services/pipeline_service.py:305-314,739-745`；`quality_gate/services/quality_evaluator.py:180-186`；`usl_writeback/impl/usl_writeback_handler.py:153-165` | 4 | high |
| ② 元数据标准 | 弱。KB 文档有描述性(title/summary/keywords/content_type)与部分管理性(created_by/cleaning_status/graph_built)；抽取血缘表 `extraction_provenance`(source_doc_id/method/template_version/confidence) 是最完整的管理性元数据；**缺**结构性元数据 schema 与资产级 author/version/permission/lineage；data_warehouse 无治理元数据 | `biz/data/knowledge_base/storage/sqlite_kb_storage.py:45-70`；`hyper_extract/impl/provenance_tracker.py:25-60`；`biz/data/data_warehouse/models.py:27-61` | 2 | high |
| ③ 分类法 | `UslHierarchy`(IS_A/PART_OF/INSTANCE_OF+confidence)；OL L3 形式概念分析(FCA)产出层级边；L6 sub_class_of 闭包；OMS `ObjectTypeDefinition.parent_type` 继承 | `usl_manager/models/usl_hierarchy.py:21-29`；`ol_pipeline/impl/l3_formal_concept.py:1-14`；`core/ontology/application/oms/schemas.py:84` | 3.5 | high |
| ④ 叙词表 | 部分。层级+近义(near_synonyms)+不相交对(UslDisjointPair)；L4 关系抽取含 related_to；**缺**等价关系表，related_to 在 USL 侧无持久化关系载体（UslHierarchy rel_type 仅三种） | `usl_manager/models/usl_disjoint_pair.py:21-32`；`pipeline_service.py:679-690`；`usl_hierarchy.py:21-29` | 3 | high |
| ⑤ 本体 | 自定义 Pydantic Schema 为权威源：EntityTypeDefinition(properties/primary_key/links/actions/constraints[unique/not_null/range/regex/enum/custom]/Cardinality/LinkType 含 inheritance)；OMS 七类族(object/link/action/process/rule/function/indicator)；公理在 OL L6 推导(subClassOf/disjointClasses/domain-range-cardinality)，OWL 风格但计算态非存储态；OWL/SHACL 为派生互操作层(ADR-077 双轨) | `core/ontology/design/model/models/entity_type.py:7-63`；`design/model/models/constraint.py:9-24`；`semantic_admin/ol_pipeline/impl/l6_axiom_deriver.py:1-20`；`design/engine/owl/owl_exporter.py:33-79`；`design/engine/shacl/validator.py:30-74` | 4 | high |
| ⑥ 知识图谱 | Graphiti/Neo4j **双时态属性图(LPG)**：valid/transaction time、episodes；SemanticMap 为绑定 ontology_version_id 的实例快照(objects/relations/clusters/coverage_score/temporal)；查询层为 ADR-055 统一查询自定义前缀 DSL(.schema/.entity/.topo/.temporal/.unstructured)落 Cypher/向量；前端 G6 可视化。**非 RDF 三元组库、无 SPARQL 端点**；SHACL 校验经临时 rdflib 图完成 | `infra/graph/graph_service.py:114,205-262`；`infra/graph/temporal_ops.py:4,81,117-137`；`biz/data/semantic_map/models/semantic_map.py:38-77`；`infra/query/parser.py:24-49`；`infra/query/sources/entity_source.py:74-84` | 3.5 | high |

**与框架主张的对照判断**：

- "不要跳级"：OL 管线 L1→L6 的顺序执行（`advance_run(target_step)` 状态机，`pipeline_service.py:862-873`）是"不跳级"的工程化体现；但**摄入车道事实上跳级**（见 F1），框架主张在平台内只被部分遵守。
- "知识图谱是前五阶段的集合体"：ODAP 的写回链（candidate→USL 术语→Graphiti/OMS 类型→Neo4j，`candidate_service.py:527-579`、`graphiti_writeback_adapter.py:41-105`）确实让图谱承载治理产物；但摄入车道的自由写入使图谱同时承载未治理产物，集合体被污染。
- "SPARQL/SHACL 精确查询与约束验证"：SHACL 有真实实现（pySHACL 实例校验 + 质量门 G2.8，`quality_calculator.py:322-351`）但只挂设计引擎 API（`public_routers.py:162`）；SPARQL 仅注释提及（`shape_generator.py:12`）。以 LPG+双时态换取时序查询能力是合理取舍（框架未覆盖双时态需求），但"约束验证不在写图路径"是实质缺口（F7）。
- "用 SKOS/ISO 25964/NISO Z39.19 做验证矩阵"：SKOS 在仓内仅研究文档提及且自评缺口（`docs/02-architecture/reports/RESEARCH_SEMANTICA_COMPARISON_2026-08-14.md:91,237`）；等价物是质量闸 G1/G2/G3 自建矩阵——方向一致，未采用标准编码。

---

## 3. 九工序映射（当前态）

| 工序 | 状态 | 证据 | 置信度 |
|---|---|---|---|
| 清洗 | 有 | 实体名清洗(剥中文介词/连词/动词前缀、碎片过滤) `hyper_extract/impl/ontology_mapper.py:51-125`；KB cleaning_status/level `sqlite_kb_storage.py:45-70` | high |
| 准备 | 有但契约校验不阻塞 | `/api/ingest/unified` 11 种 source_type 归一 `biz/data/ingest/api/routes.py:130-136`、`unified_ingest_facade.py:21-28`；契约校验失败返回 ok/valid `unified_ingest_facade.py:135-137,153-155` | high |
| 协调(实体对齐) | **最弱** | 确定性 entity_id=sha256(type:name) `ontology_mapper.py:582-584`；KB 按 name 匹配已有实体 `knowledge_base_service.py:312-325`；USL 归一器仅用于 QA 检索 `qa/retrieval/vector_retriever.py:24-27` 与候选去重 `candidate_store/services/entity_resolution.py:19-30`，**未接入写图主链**；无跨源 embedding/规则对齐；无缩写展开步骤（仅 prompt 层要求，`hyper_extract/templates/chinese_ontology_graph.yaml:137`） | high |
| 建模 | 有 | OL L3/L4/L5/L6；OMS schema；版本 commit 锁定 `core/ontology/design/services/version_service.py:235` | high |
| 测试(一致性验证) | **弱/占位** | G2.2 基数、G2.3 is_a 无环恒 1.0 占位 `quality_gate/services/quality_evaluator.py:341-342,389-405`（OPA 镜像同占位 `policies/quality_gate.rego:171-175`）；G2.4 LLM Judge 默认关 `quality_evaluator.py:57-58`；SHACL 实例校验存在但未入写图路径 | high |
| 富化 | 部分 | LLM 抽取、en_mapping、semantic_hints、KB keywords/summary、Graphiti episode 时序上下文 `knowledge_base_service.py:628-666` | high |
| 强制 | **双车道分裂** | 治理车道：质量闸阈值分档(PASS≥0.8/REVIEW≥0.5/FAIL) `quality_gate_service.py:28-38` + 两级审批 `approval_workflow/impl/approval_service.py:826-832` + 停用词 + HE strict 跳过未定义类型 `ontology_mapper.py:509-523`；摄入车道：KB 中文类型降级 `zh_type` 自由写 `knowledge_base_service.py:337-339`、GraphWriteProxy 无 schema 校验 `infra/query/graph_write_proxy.py:66-96` | high |
| 报告 | 有 | 质量报告/risk_tags/suggestions `pipeline_service.py:454-464`；统一审计 `infra/security/unified_audit.py`；approval_log `approval_service.py:850-871`；抽取血缘 provenance | high |
| 度量 | 部分且完整性存疑 | 仪表盘 3 视图：summary(候选数/分 tier/分闸/门均分/审批时长)、terms_trend(日新增/批准/拒绝+累计)、approvals_breakdown(分角色/分决策/平均秒) `quality_gate/services/dashboard_query_service.py:75-106,358-458,464-567`；**但**门均分含占位子项（F2）；语义指标未进 Prometheus `infra/observability/metrics.py:43-123` | high |

---

## 4. 发现表

| ID | 发现 | 严重度 | 可能性 | 影响 | 置信度 | 证据 | 验证/整改路径 |
|---|---|---|---|---|---|---|---|
| F1 | 摄入车道绕过本体强制自由写图（zh_type 降级、无 schema 校验、SHACL 不在写图路径、契约校验失败不阻塞），图谱积累未治理节点 | high | high（每次 KB/感知摄入） | 语义一致性被侵蚀；USL/本体批准集与图谱实际集持续背离；检索与推演建立在混合语料上 | high | `knowledge_base_service.py:337-339`；`graph_write_proxy.py:66-96`；`design/engine/shacl/validator.py:68` 仅挂 `public_routers.py:162`；`unified_ingest_facade.py:135-155` | 写图前过 ontology 类型校验+SHACL；未定义类型转候选队列进治理车道而非 zh_type 落图。验收：摄入含新类型文档后 Neo4j 无新增 `zh_type` 节点且 candidate_store 出现对应候选 |
| F2 | 度量完整性：G2.2/G2.3 占位 1.0、G2.4 默认关，但仪表盘把门均分当 KPI 上报 | high | certain | 审批与汇报依据系统性偏高；"度量"工序产出不可信，违背框架"可度量"承诺 | high | `quality_evaluator.py:341-342,389-405`；`quality_gate.rego:171-175`；`dashboard_query_service.py:75-106` | 占位子项标 `not_evaluated` 并从均分分母剔除，或实现 L3 拓扑排序/L5 基数复核填充真值。验收：dashboard 响应含占位标记且均分不含占位项；或 G2.2/G2.3 有真实计算与单测 |
| F3 | USL 词表归一未接入写入链，仅检索侧查询改写补救 | medium-high | high | 写入侧同名异写、异名同写并存；对齐成本后移到每次查询；词表投资回报被稀释 | high | `vector_retriever.py:24-27`；`semantic_retrieval/impl/nl_engine.py:38`；`entity_resolution.py:19-30`；`ontology_mapper.py`/`knowledge_base_service.py` 无 resolver 引用 | OntologyMapper/KB 写图前调用 UslTermResolver 归一 canonical，未命中落原名并打 `unresolved_term` 标记供 L2 合并消费。验收：同义异名文档摄入后图谱实体名归一且标记可查 |
| F4 | 元数据标准阶段薄：无结构性元数据 schema，缺资产级 author/version/permission/lineage | medium | high | 框架②阶段缺位削弱实体对齐与 schema 验证矩阵的地基；血缘追溯仅覆盖抽取环节 | high | `sqlite_kb_storage.py:45-70`；`data_warehouse/models.py:27-61`；对照 `provenance_tracker.py:25-60`（亮点） | 定义 AssetMetadata 基线(结构/描述/管理三组)并入 KB 与 data_warehouse 模型+迁移+单测。验收：三类元数据字段可查询且写入路径覆盖 |
| F5 | semantic_admin 设计文档与代码漂移：状态机(文档 10 态 vs 代码 12 态)、表清单(文档 12 张 sa_* vs 实际 usl_*)、不存在文件名、Fast Track 公式未实现、outbox daemon 缺失；README 声称 MinHash 去重无实现 | medium | certain | 设计文档失去证据价值；违反仓库规则 12；后续开发者按文档施工会踩空 | high | `docs/03-modules/semantic_admin/DESIGN.md:142-155,215-230,182-183,161-167` vs `sqlite_candidate_storage.py:53-65`、`sqlite_usl_storage.py:91-195`；`docs/03-modules/README.md:99` | 按 `docs/09-checklists/DOC_SYNC_CHECKLIST.md` 刷新 DESIGN.md 与 README；删除或实现 Fast Track/outbox/MinHash 声明。验收：文档状态机/表清单/文件清单与代码逐项一致 |
| F6 | 叙词表关系载体不完整：无等价关系表；L4 related_to 候选在 USL 侧无持久化关系类型 | low-medium | medium | ④阶段停留"层级+近义"，关联关系(RT)在治理产物中断链 | high | `usl_hierarchy.py:21-29`；`pipeline_service.py:679-690` | UslHierarchy rel_type 扩展 RELATED_TO/EQUIVALENT 或新增 UslRelation 模型+写回适配。验收：L4 related_to 候选审批后可写回 USL 并可查询 |
| F7 | SHACL 形状实时生成不持久化、校验未入写图路径（ADR-077 部分落地） | medium | high | 无常设约束注册表；约束验证只在设计态可用，运行态写图不受约束（与 F1 同根） | high | `design/engine/shacl/shape_generator.py:22`；`validator.py:68-74`；`public_routers.py:162` | 形状随 ontology version 持久化；写图路径接入 validator（与 F1 合并整改）。验收：版本提交生成并存储形状；越界写入被拒且有审计 |
| F8 | 审批权限为硬编码 JWT 角色，OPA 仅"Iter 3 计划" | low | medium | 治理权限与平台 OPA 策略体系脱节；角色变更需发版 | high | `approval_workflow/impl/permissions.py:9-11,24,45-52`；`usl_manager/api/routes.py:114` | Iter3 将审批权限迁入 rego 策略。验收：rego 驱动审批判定且有策略单测 |

**已排除的疑似风险**：分层契约无 CI 门禁（2026-09-11 记忆）——复核发现 `.github/workflows/ci.yml:53-71` 与 `quality-gate.yml:41-49` 已执行 `lint-imports`，该风险已消除，不列入。

---

## 5. 优势：与框架主张一致甚至超越之处

1. **双向治理，回应框架自认的局限**。文章承认"先有分类法后有词表"的逆向治理缺乏操作指南；ODAP 同时具备自上而下（设计引擎建本体）与自下而上（OL L1 术语抽取→L2 合并→L5 融合→审批→写回 USL/本体/图谱；`semantic_asset_pipeline` 从 database/BI 结构化源归集候选；seed 脚本从既有 semantic_config 反推 USL 六表 `usl_manager/migrations/seed_sanguo_xiyou.py`）两条路径，逆向治理是已实现能力而非论文方向。
2. **LLM 半自动构建+本体约束**（文章"未来研究方向"之一）已产品化：L1 三实现(LLM/N-gram/BGE-HDBSCAN)、幻觉软校验(`he_adapter.py:434-508`)、质量闸约束兜底。
3. **度量产品化**：dashboard 三视图把"清洗了多少术语、批准/拒绝多少、审批耗时"变成可汇报指标——正是文章所说"语义工程从成本中心变风险控制中心"的前提，在同类项目中罕见。
4. **未盲从公共分类法**：领域词表自建（sanguo/xiyou/shared 内置域），符合文章对 Google Product Taxonomy 式套用的警告。
5. **双时态图谱+版本快照**：SemanticMap 绑定 ontology_version_id、Graphiti valid/transaction time，使"知识作为基础设施"具备版本化与时间旅行能力，超出框架⑥阶段的静态 RDF 设想。
6. **存储层测试纪律**：`test_semantic_admin_usl_manager.py` 文件头明示"严禁 MagicMock 替 storage"、全 tmp_path 真 SQLite，符合仓库规则 9/14。

---

## 6. 整改计划（按爆炸半径/业务影响/可逆性/工作量排序）

| 优先级 | 动作 | 关联发现 | 验收标准 |
|---|---|---|---|
| P0 | 摄入车道接入强制：写图前类型校验+SHACL，未定义类型转候选队列 | F1, F7 | 摄入含新类型文档后无新增 `zh_type` 节点；候选出现；越界写入被拒且审计可查 |
| P0 | 度量完整性：占位子项显式标记并剔出均分，或实现 G2.2/G2.3 真值 | F2 | dashboard 含 `not_evaluated` 标记；或占位代码删除且有真实计算单测 |
| P1 | USL 归一器接入写入链（写前归一+未命中打标记） | F3 | 同义异名摄入后实体名归一；标记可查询 |
| P1 | 刷新 semantic_admin DESIGN.md 与 03-modules README，清除漂移声明 | F5 | 文档状态机/表/文件/公式与代码逐项一致（过 DOC_SYNC_CHECKLIST） |
| P2 | AssetMetadata 基线（结构/描述/管理）入 KB 与 data_warehouse | F4 | 字段+迁移+单测齐备 |
| P2 | UslHierarchy 扩展 RELATED_TO/EQUIVALENT 或新增 UslRelation | F6 | related_to 候选可写回可查询 |
| P2 | 审批权限迁入 OPA rego | F8 | rego 驱动判定+策略单测 |
| P3 | 语义 KPI 进 Prometheus（术语数/候选数/审批数/门分分布） | F2 延伸 | metrics.py 有对应 counter/gauge 且 grafana 可见 |

---

## 7. 未知与假设（不作结论）

- **U1**：L4 抽取的 `related_to` 候选审批后的最终落点（是否仅进 Neo4j 镜像 `USL__Candidate` 而无 USL 关系载体）未逐行确认，F6 的影响面按 medium 估计。验证：跟踪一条 related_to 候选走完 final_approve→writeback 的存储写入。
- **U2**：感知车道（webhook/sensor/mcp）写图是否同样绕过强制，仅由 `hub.py:109-115` 调用链推断（与 KB 车道共用 GraphWriteProxy，medium 置信）。验证：对 sensor 事件做一次端到端摄入观察 Neo4j label。
- **U3**：`recommend_auto_skip: total>=0.9`（`quality_gate_service.py:96`）与文档 Fast Track 公式的关系为"替代实现"还是"残次实现"未定，仅计入 F5 文档漂移，不单独定级。
- **A1（假设）**：评审未运行运行时验证（容器/Neo4j 未启动），所有"行为"结论来自代码静态证据与单测存在性；涉及运行时降级（graph mode fallback）的行为未实测。

---

## 8. 下一步检查

1. 按 P0 两项整改后，重跑 `tests/e2e/test_semantic_admin_chain.py` 与 `tests/extraction/` 观察摄入车道行为变化。
2. 对 F1 整改做一次反向探针：构造含未定义类型的文档，断言写图被拒且候选入队。
3. 将本评审的六阶段成熟度表纳入季度复评，跟踪②阶段与"协调/测试"工序的收敛。

*评审人：Qoder（risk-quality-reviewer + graphviz）。证据采集：3 个只读调研代理 + 主代理复核 grep；关键结论（F1/F2/F3）经主代理亲自验证 file:line。*
