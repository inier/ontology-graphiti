# Feature Specification: Semantic Admin & Ontology Learning Suite

**Feature Branch**: `007-semantic-admin-suite`
**Created**: 2026-07-11
**Status**: Draft
**Sub-project**: SP2 of end-to-end platform vision (SP1→SP2→SP3→SP4→SP6→SP5→SP7)
**Input**: (原需求中文) 用户要求将本体 Schema 的硬编码实现调整为独立服务模块 + 可视化配置 + Hyper-Extract 概念抽取 + 管理员审核闭环，结合 4 个迭代。

---

## 关联设计文档（含架构图/DDL/UI 原型可视化稿）

> 以下为可直接在浏览器打开的可视化设计稿（含 Mermaid 实时渲染、卡片 UI、雷达图/时间线原型），内容与本 spec.md 的文字版用户故事 + plan.md 的实现计划 + data-model.md 的 DDL 保持一致，冲突时以 HTML 设计稿为准。

| # | 文档 | 核心内容 |
|---|------|---------|
| 1 | [📐 整体架构（方案 B）+ 4 迭代交付矩阵](./design/01-architecture-planB.html) | 6 子服务松耦合 Mermaid 架构图 · 4 Iter × 6 子服务交付矩阵 · 清理/迁移/保留图例 |
| 2 | [🔧 Iter 1 · USL 服务化 + 深度清理](./design/02-iter1-usl-design.html) | USL 6 张核心表完整 DDL · 清理迁移动作 Mermaid · 9 个 API 路由清单 · 前端 5 Tab USL 配置页原型 · 50 小步任务矩阵 |
| 3 | [🧪 Iter 2 · L1-L2 OL 流水线 + Candidate 双写](./design/03-iter2-ol-pipeline-design.html) | L1/L2 编排 Mermaid · ExtractService mode=schema_learning 改造 · 3 Pipeline/Candidate 表 DDL + Neo4j USL__Candidate 双写 Cypher · 前端 3 栏 Pipeline 监控页 Steps 示意 · 45 小步任务矩阵 |
| 4 | [🛡️ Iter 3 · 三关质量闸 + 二级审批 + 审核台 UI](./design/04-iter3-quality-approval-design.html) | 3 关 × 16 子指标公式 + 阈值 + 失败动作表 · 10 状态状态机 stateDiagram · usl_approval_records / usl_quality_reports DDL · semantic_admin.rego OPA 策略完整代码 · 前端审核台卡片/抽屉/雷达图原型 · 55 小步任务矩阵 |
| 5 | [♻️ Iter 4 · HITL 写回 + L3-L6 + 清理 + 质量面板](./design/05-iter4-writeback-cleanup-design.html) | HITL 飞轮写回 Mermaid · L3/L4/L5/L6 四层算法核心表 · OLPipelineConfig Pydantic 配置 · semantic_layer 目录 8 文件深度清理清单 · 前端质量面板 4 卡 + 4 图规格 · 电商脚本 --from-doc/--diff CLI + 差异报告格式 · 60 小步任务矩阵 |

---

## 背景与现状诊断

### 已有资产（可复用）

- `semantic_config.py` 三大硬编码语义配置字典：SANGUO_SEMANTIC（7 类对象 + 11 类关系 + 6 类动作 + 20 属性）、XIYOU_SEMANTIC（6 类对象 + 9 类关系 + 6 类动作 + 9 属性）、SHARED_SEMANTIC（5 类共享术语 + 4 类共享关系）
- `semantic_layer/api/routes.py` 现有 4 个 REST 端点：`POST /parse-intent`、`POST /plan-tasks`、`GET/POST /synonyms`、`GET/POST /expansion-rules`
- `IntentParser` / `QueryPlanner` / `Disambiguator` 三组件类实现，全局单例懒加载
- `ExtractionService` 3 入口编排骨架（NL/Document/KB）+ session 管理 + `_detect_conflicts` + `confirm_extraction` 双通道写入
- `Goal` 领域状态机：proposed → approved/rejected → in-progress → achieved/abandoned，可复用为审批流骨架
- `ProcessingStatus` / `AuditLog` / `DataIngestRecord` 审计与管道数据模型
- `QAOntologyBuilder` 异步任务进度跟踪骨架（task_id + progress 百分比 + SSE 订阅）
- `data/he_templates/` 模板沉淀目录结构 + SQLite he_templates 表（SP1 已建）
- `he_templates` 表字段：id, ontology_id, name, description, source, yaml_path, preset_name, score, coverage, usage_count, created_at, updated_at, UNIQUE(ontology_id, name)
- `UnifiedAudit.log_action()` 统一审计接口（`odap.infra.security.unified_audit`，可选导入）
- `get_current_user` JWT 认证依赖（`odap.infra.security.jwt_auth`）
- `get_config()` 统一配置读取（`odap.infra.config_composer`，优先级 DB > USER > WORKSPACE > FILE > ENV > SYSTEM）

### 硬编码 / 伪实现清单（必须解除）

| # | 位置 | 问题 | 影响 |
|---|---|---|---|
| 1 | `semantic_config.py:17-295` 三大 dict 全部硬编码 | 新增领域、修改术语、调整同义词必须改代码 + 重部署 | 无法动态运营，任何术语变更走开发流程 |
| 2 | `semantic_layer/api/routes.py:102-111` POST /synonyms | 仅 `disambiguator.add_synonym()` 内存态修改，进程重启丢失 | 同义词配置不持久化，生产不可用 |
| 3 | `semantic_layer/api/routes.py:120-129` POST /expansion-rules | 同上，内存态修改不落地 | 扩展规则配置不持久化 |
| 4 | `semantic_layer/disambiguator.py` | 未接入持久化层，全部基于硬编码 dict 初始化 | 无独立 USL 模块边界 |
| 5 | `semantic_layer/intent_parser.py` | 未接入持久化层，术语变更需重启 | 无法热加载语义配置 |
| 6 | `semantic_layer/query_planner.py` | 未接入持久化层，同上 | 同上 |
| 7 | 全局无审核流 | 任何语义变更（新增术语/同义词/扩展规则）即时生效，无闸口 | 生产环境误操作直接污染线上 |
| 8 | 无 Candidate 阶段 | 抽取结果无 "待审核候选" 中间态，直接 confirm 写图谱 | HITL 闭环缺失 |
| 9 | `ExtractionService` 无 `mode=schema_learning` | 只有抽取实例的模式，无反向学习本体 TBox 的模式 | 本体 Schema 增长只能靠人工建模 |
| 10 | L1-L6 层级体系缺失 | 硬编码 dict 无层级概念，无 Concept → SubConcept → Instance 抽象链路 | 无法支撑推理与泛化 |

### 架构问题

- USL（Unified Semantic Layer）不是独立服务模块：与 ontology/design/schema 紧耦合，无独立 storage / services / api 分层
- 无可视化配置后台：语义配置的增删改查必须通过 API 调用或改代码，管理员无 UI
- 无质量闸（Quality Gate）：抽取→候选→写回全链路无自动化质量阻断
- 无 OPA（Open Policy Agent）策略引擎：审批规则硬编码，无法按角色/领域/风险等级动态配置策略
- Ontology TBox 双写缺失：语义配置修改不自动同步到 ObjectType / RelationType 等 Schema 实体
- 老目录清理缺失：`semantic_config.py` 等硬编码文件在迁移完成后应删除，未规划删除路径
- 电商领域脚本缺失：仅支持三国/西游两个领域，电商领域 seed 未规划

---

## User Scenarios & Testing *(mandatory)*

### 迭代规划总览

| 迭代 | 包含 US | 交付物 |
|------|---------|--------|
| Iter 1 | US1 (P0) + US2 (P0) | USL 独立服务化 + 三国/西游 seed 迁移 + API 回归 |
| Iter 2 | US3 (P1) + US4 (P1) | L1-L2 概念抽取 + Candidate 双写 + ExtractService schema_learning 模式 |
| Iter 3 | US5 (P0) | 3 关质量闸 + 2 级审批流 + OPA 策略引擎 |
| Iter 4 | US6 (P1) + US7 (P2) | HITL 飞轮写回 USL + TBox 双写 + L3-L6 + 老目录清理 + 电商 seed + 质量面板 |

---

### User Story 1 - USL 服务化 + 深度清理 QA 三文件 (Priority: P0, Iter 1)

将语义层从 `design/schema/semantic_layer/` 的混合目录中剥离为独立 biz 模块 `biz/core/semantic/`，按 AGENTS.md 6 层结构（api/services/impl/interfaces/models/storage）落地。原硬编码 `SANGUO_SEMANTIC` / `XIYOU_SEMANTIC` / `SHARED_SEMANTIC` 三大 dict 通过 seed migration 脚本写入 SQLite `usl_*` 表。现有 `/api/semantic/*` 4 个端点保留路由前缀不变，内部委托新 USL 服务。深度清理 QA：确保 100% 行覆盖单元测试、同义词/扩展规则持久化后重启不丢失、热加载生效。

**Why this priority**: USL 服务化是后续所有迭代的地基——不独立出模块，质量闸、审批流、HITL 写回均无法挂载；seed 迁移保证线上存量不丢失。

**Independent Test**: 启动应用后调用 `POST /api/semantic/synonyms` 新增同义词 → 重启进程 → `GET /api/semantic/synonyms` 返回值包含新增项；原 `semantic_config.py` 三 dict 可被删除且全部测试通过。

**Acceptance Scenarios**:

1. **Given** 新模块 `biz/core/semantic/` 6 层结构就位，**When** 应用启动，**Then** USL 服务从 SQLite `usl_domains` / `usl_canonical_terms` / `usl_synonyms` / `usl_en_mapping` / `usl_expansion_rules` 5 张表加载，不再 import `semantic_config.py`
2. **Given** seed migration 脚本 `python -m odap.biz.core.semantic.storage.seed_migrate`，**When** 对空库执行，**Then** 三国/西游/共享三大领域数据完整写入 5 张表，count 校验：三国对象类型 7 + 关系 11 + 动作 6 + 属性 20；西游对象 6 + 关系 9 + 动作 6 + 属性 9；共享对象 5 + 关系 4
3. **Given** 运行中进程，**When** 通过 API 新增同义词并持久化成功，**Then** 无需重启，IntentParser/Disambiguator 下一次调用立即识别新词（热加载，`USLCache.invalidate(domain)` 广播）
4. **Given** 深度清理 QA，**When** 执行 `pytest tests/unit/biz/core/semantic/ -v --cov=odap.biz.core.semantic`，**Then** 行覆盖率 ≥ 95%，所有 CRUD + 热加载 + 种子迁移用例通过
5. **Given** 新服务就位，**When** 调用原 `/api/semantic/parse-intent`、`/plan-tasks`、`/synonyms`、`/expansion-rules`，**Then** 响应结构与 SP2 前 100% 二进制兼容（契约测试通过），响应时间 P95 < 100ms

---

### User Story 2 - 三国/西游 USL 初始化 seed 迁移 (Priority: P0, Iter 1)

将 `semantic_config.py` 中硬编码的三国、西游、共享三大语义配置，通过幂等迁移脚本写入 USL 持久化层。迁移脚本支持 `--check` 预演模式（dry-run，只 count 不写入）、`--apply` 实际写入、`--rollback` 删除本次写入。迁移完成后 `semantic_config.py` 标记 deprecated，但保留 2 个迭代（Iter3 后删除），期间导入触发 DeprecationWarning。

**Why this priority**: seed 迁移是 USL 服务化的必要数据保障，不迁移则 USL 空库启动导致 IntentParser 全部分词失败。

**Independent Test**: 在空 tmp_path SQLite 上执行 seed migrate → apply → check count 与硬编码一致 → rollback → count 归零。再 apply 一次 → 第二次 apply 为幂等（UNIQUE 冲突被 ignore，不报错，count 不变）。

**Acceptance Scenarios**:

1. **Given** 空库 + `SANGUO_SEMANTIC` 7 对象 + 11 关系 + 6 动作 + 20 属性 + 5 扩展规则，**When** `seed_migrate --apply`，**Then** `usl_domains` 插入 sanguo 行，`usl_canonical_terms` 插入 7+11+6+20=44 条术语（按 term_type=object/relation/action/property 区分），`usl_synonyms` 插入每个 canonical 的 synonyms+near_synonyms+aliases 总条数，`usl_en_mapping` 插入中英文映射，`usl_expansion_rules` 插入 5 条，SQLite 外键关联正确
2. **Given** 已 apply 的库，**When** 第二次执行 `seed_migrate --apply`，**Then** 无异常，各表 count 与第一次后完全相同（幂等）
3. **Given** 已 apply 的库，**When** `seed_migrate --rollback --domain sanguo`，**Then** `usl_domains` sanguo 行及级联子表（canonical/synonym/en_mapping/expansion）全部删除，其他领域不受影响
4. **Given** `seed_migrate --check`（dry-run），**When** 执行，**Then** 只输出"将写入 N1 行 domain / N2 行 canonical / ..." 报告，DB 中 row_count 不变
5. **Given** 迁移完成，**When** import `semantic_config.py`，**Then** 触发 `DeprecationWarning: semantic_config.py will be removed in Iter3. Use SemanticService.get_domain() instead.`，但返回值仍与迁移前一致（向后兼容 2 迭代）

---

### User Story 3 - L1-L2 概念抽取 + Candidate 双写 (Priority: P1, Iter 2)

在 Hyper-Extract 抽取结果上叠加 L1（领域概念层）与 L2（规范术语层）两级概念泛化。L1 用 BGE embedding + HDBSCAN 对抽取到的实体名称做语义聚类，聚类标签作为 L1 概念候选；L2 用 FCA（形式概念分析）对 L1 聚类做属性闭包，生成 is-a / part-of 层级关系，作为规范术语层级候选。L1-L2 候选写入 `usl_candidates` 表（双写：同时写 SQLite + Neo4j 的 Candidate 标签节点，SQLite 为权威源，Neo4j 供可视化），状态机 = `proposed → qg_passed → approved → merged`。

**Why this priority**: L1-L2 是 L3-L6 的地基，Candidate 双写是 Iter3 质量闸和 Iter4 HITL 的前置条件。P1 因为不阻断 USL 基础服务可用。

**Independent Test**: 给定 50 条抽取实体（如 "刘备"、"关羽"、"张飞"、"赵云"、"诸葛亮"、"曹操"、"司马懿"、"夏侯惇"…），验证 HDBSCAN 聚出 ≥3 个簇（蜀汉人物 / 曹魏人物 / 东吴人物），FCA 生成 "三国人物" is-a "人物"、"蜀汉人物" is-a "三国人物" 层级，candidate 双写到 SQLite 表与 Neo4j 节点一致。

**Acceptance Scenarios**:

1. **Given** ExtractService 返回 50+ 实体对象，**When** `ConceptExtractor.run_l1(entities, domain_id)`，**Then** 对每个实体名称取 BGE embedding → 维度 1024 → UMAP 降维到 64 → HDBSCAN(min_cluster_size=3, min_samples=2) 聚类，输出 `l1_clusters: List[{cluster_id, label, member_ids, centroid_emb, confidence}]`，confidence = 簇内平均余弦相似度，confidence < 0.6 的簇标记为 `noise` 丢弃
2. **Given** L1 聚类结果，**When** `ConceptExtractor.run_l2(l1_clusters, domain_id)`，**Then** 构造形式上下文 `(G, M, I)` 其中 G = 簇成员实体，M = 实体属性集合，I = 实体是否具有该属性，调用 FCA `compute_concepts()` 生成概念格，概念节点作为 L2 规范术语，概念间的 superconcept-subconcept 边映射为 `is_a` 层级关系，属性共享阈值 ≥ 0.75 的概念才输出
3. **Given** L1-L2 概念候选，**When** `CandidateWriter.dual_write(candidates)`，**Then** SQLite `usl_candidates` 表插入（字段：id, domain_id, level=L1/L2, label, parent_id, member_refs, confidence, status=proposed, source=he_extraction, created_at, created_by）；Neo4j 写入 `(:ConceptCandidate {id, level, label, confidence, status})` 节点 + `[:IS_A]` 边；两写入在同一事务中，任一失败全部回滚（2PC 模拟：先写 SQLite，写 Neo4j 失败则删 SQLite 对应行）
4. **Given** 双写完成，**When** 查询 `GET /api/semantic/candidates?domain_id=sanguo&level=L1`，**Then** 返回候选列表含 id/label/confidence/status/member_count，分页 page/size，支持 status 过滤
5. **Given** 100 条包含同义词的实体（如"丞相曹操"、"曹孟德"、"曹公"），**When** run_l1，**Then** HDBSCAN 按 embedding 语义把同义词聚为同一簇，label 取簇内出现频次最高的实体名 + 标记 `disambiguation_needed=true`

---

### User Story 4 - ExtractService mode=schema_learning 改造 (Priority: P1, Iter 2)

为 `ExtractionService` 三大入口（NL/Document/KB）新增枚举参数 `mode: Literal["instance_extraction", "schema_learning"] = "instance_extraction"`。当 `mode=schema_learning` 时，抽取结果不是直接写 Instance，而是走 US3 的 L1-L2 概念抽取 → Candidate 双写路径，生成 ObjectType / RelationType / Property 三类 Schema 候选（而非实例）。具体映射：L2 规范术语 → ObjectType 候选；术语间 is-a 层级 → inheritance 候选；术语间语义关联 → RelationType 候选；FCA 共享属性 → Property 候选。

**Why this priority**: 打通 "数据 → 自动学习 Schema" 的反向链路，解决本体 Schema 只能人工建模的痛点。P1 因为 Iter1 已有实例抽取可用。

**Independent Test**: 提交 `mode=schema_learning` 的 NL 抽取请求（输入：三国演义原文 5000 字），验证 session.result_data 含 `schema_candidates` 字段，其中 ObjectType ≥ 5，RelationType ≥ 3，Property ≥ 8，且全部 candidate 可在 `usl_candidates` 表查到 `status=proposed` 记录。

**Acceptance Scenarios**:

1. **Given** 用户请求 `POST /api/extract/nl`，**When** body 带 `mode="schema_learning"` + text + ontology_id，**Then** ExtractionService 创建 session（type=schema_learning）→ 走 HE 多模板抽取 → ConceptExtractor L1-L2 → CandidateWriter 双写，session 最终 status = `reviewing_schema`，不触发 confirm_extraction 的实例写入
2. **Given** schema_learning session，**When** 结果映射，**Then** L2 概念 `{label, attributes}` → ObjectType 候选（name=label, properties=attributes, category=L2, source=he_schema_learning）；L2 概念 A is-a L2 概念 B → inheritance 候选（child=A, parent=B, type=is_a）；FCA 概念格中的非层级关联（共同事件/共同地点）→ RelationType 候选（name=infer_{sourceLabel}_{targetLabel}, domain=sourceL2, range=targetL2）；FCA 共享属性 → Property 候选（name={attr}, type=string/number/date，required=false）
3. **Given** 同一份文本，**When** 分别用 mode=instance_extraction 和 mode=schema_learning 调用，**Then** 前者写 Instance 节点，后者写 usl_candidates Schema 候选，二者互不干扰（session.type 不同，Neo4j label 分别为 `Instance` vs `ConceptCandidate`）
4. **Given** ExtractService 原有调用方（不传 mode 或显式 mode=instance_extraction），**When** 执行，**Then** 行为与 SP2 前完全一致（零回归）
5. **Given** schema_learning 抽取结果，**When** confidence ≥ 0.85，**Then** 自动标为 `qg_preapproved=true`（进入 Iter3 质量闸时跳过低置信度筛选），<0.6 的候选直接丢弃（不写 candidate 表，仅记录日志）

---

### User Story 5 - 3 关质量闸 + 2 级审批流 + OPA (Priority: P0, Iter 3)

建立 Candidate → Approved → Merged 的 3 级自动化质量闸 + 2 级人工审批流。3 关：QG-1（置信度与去重闸：confidence ≥ 阈值 + 与已合并术语 Jaccard < 0.7）→ QG-2（结构一致性闸：新 ObjectType 属性与父类型属性无冲突 + RelationType domain/range 指向已存在类型）→ QG-3（语义一致性闸：LLM 评审 prompt "候选 {label} 是否符合 {domain} 本体 Schema 规范？给出 reason + pass/reject"，通过率 ≥ 80%）。2 级审批：L1（领域管理员，角色 semantic_dom_admin，可 approve/reject 单条候选，批量 ≤50 条/次）→ L2（全局管理员，角色 semantic_global_admin，可批量 approve/reject 51+ 条、可修改质量闸阈值、可执行 merge 写回 USL）。审批规则、角色权限、阈值全部通过 OPA 策略 `.rego` 文件定义，不硬编码。

**Why this priority**: P0，生产环境必备闸口。无质量闸则 Candidate 直接合并等于没有审核，和硬编码时代没有本质区别；审批流是组织协作的基础，OPA 保证策略变更不需要重部署。

**Independent Test**: 提交 10 条候选（3 条低 confidence / 3 条重名 / 2 条结构冲突 / 2 条高质量），验证 QG-1 淘汰 3+3=6，QG-2 淘汰 2，QG-3 对剩余 2 条 LLM 评审都通过；领域管理员 approve 后，全局管理员 merge，最终 USL 表中新增 2 条术语，审批日志完整。

**Acceptance Scenarios**:

1. **Given** status=proposed 的候选，**When** `QualityGateService.run_all(candidate_id)`，**Then** 依次执行 QG-1 / QG-2 / QG-3。QG-1 计算：`confidence >= get_config("semantic.qg1_confidence_threshold", 0.65)` AND `max_jaccard_with_existing(candidate.label, domain) < get_config("semantic.qg1_jaccard_threshold", 0.7)`。QG-2 计算：若候选为 ObjectType 且有 parent_id，则 `new_properties ∩ parent.mandatory_properties = ∅`（无冲突覆盖）；若为 RelationType，则 `ObjectType.exists(domain) AND ObjectType.exists(range)`。QG-3 调用 LLM（温度 0，模型 gpt-4o-mini），prompt 模板："你是本体 Schema 审核专家。领域={domain_display_name}。候选术语：label={label}，level={level}，属性={attributes}，confidence={confidence}。请判断该候选术语是否符合领域本体 Schema 规范。返回严格 JSON：{\"pass\": bool, \"reason\": \"≤200字理由\", \"risk_level\": \"low|medium|high\"}"，3 次采样 majority vote，pass 率 ≥ 2/3 视为通过
2. **Given** 三关全通过，**When** candidate.status，**Then** 更新为 `qg_passed`，`quality_gate_report` JSON 字段写入三关结果（每关 pass/fail + 数值 + reason）。任一关失败 → status = `qg_failed`，失败原因写入 `reject_reason` 字段，可通过 GET 查看
3. **Given** status=qg_passed，**When** 领域管理员（role=semantic_dom_admin，domain 匹配）调用 `POST /api/semantic/approvals/approve`（body: candidate_ids, comment），**Then** candidate.status = `l1_approved`，`approvals` 表插入 `{level=1, approver_id, candidate_id, action=approve, comment, created_at}`。若角色不匹配或 domain 不匹配 → OPA 返回 deny，接口返回 403 `{"status":"denied","policy":"semantic_l1_approve.rego","reason":"不具备该领域管理权限"}`
4. **Given** status=l1_approved，**When** 全局管理员（role=semantic_global_admin）调用 `POST /api/semantic/approvals/merge`（body: candidate_ids ≤ 100），**Then** OPA 校验角色 + 批量数量限制 → 通过后执行 `SemanticService.merge_candidates(ids)`：将 candidate.label / synonyms / en_mapping / expansion 写入 USL 5 张正式表；删除 Neo4j ConceptCandidate 节点，创建正式 `(:Concept)` 节点；candidate.status = `merged`，写入 audit_log（UnifiedAudit.log_action）。若 100 条中第 60 条出错，前 59 条回滚，第 60 条记录 error，merge 整体事务
5. **Given** OPA 策略文件 `config/opa/semantic/` 下 `qg_thresholds.rego`、`l1_approve.rego`、`l2_merge.rego`、`batch_limits.rego`，**When** 管理员更新 `qg_thresholds.rego` 将 qg1_confidence 从 0.65 改为 0.7，**Then** 下一次 run_all 立即生效（OPA 策略热加载，watch 文件系统 mtime），无需重启进程，接口响应中 `policy_version` 字段更新

---

### User Story 6 - HITL 飞轮写回 USL + Ontology TBox 双写 (Priority: P1, Iter 4)

构建人在回路（Human-in-the-Loop）闭环：用户在 ExtractionPreview 页对抽取结果的 "修正操作"（修改实体类型、改关系类型、合并同义词、标记误抽取）自动转为 Candidate 建议，通过审批流后写回 USL 正式表。同时，USL 正式表发生新增 / 修改 / 删除时，Ontology TBox（ObjectType / RelationType / Property 三张 Schema 表）自动同步双写——即术语管理后台的修改也直接影响 Ontology Schema，不再需要去 Ontology Designer 再建一遍。

**Why this priority**: P1，构建 "抽取→人工修正→写回语义层→下次抽取更准" 的质量飞轮；TBox 双写消除语义配置与本体 Schema 的双重维护痛点。

**Independent Test**: 打开 ExtractionPreview，把抽取到的实体 "司马懿" 从类型 "人物" 改为 "谋士"（已存在的 L2 术语），同时新增同义词 "仲达"，保存修正 → 验证 usl_candidates 出现 2 条修正候选（1 条 retype + 1 条 synonym）→ 走审批流 merge → 验证第二次抽取同一文本时 "司马懿" 被正确识别为 "谋士" 类型，同义词 "仲达" 也被消歧到同一实体。

**Acceptance Scenarios**:

1. **Given** ExtractionPreview 前端（已有组件，参考 `frontend/src/modules/ontology/components/ExtractionPreview.tsx`），**When** 用户对抽取结果执行修正操作：(a) 改实体类型 retype、(b) 合并同义词 merge_entity、(c) 新增同义词 add_synonym、(d) 改关系类型 retype_relation、(e) 标误抽取 mark_incorrect，**Then** 前端调 `POST /api/semantic/hitl/submit`（body: extraction_session_id, corrections: List[{op, entity_id, before, after, comment}]），后端 `HITLService` 将每条 correction 转换为 candidate：op=retype → ObjectType 重映射候选；op=add_synonym → synonym 候选；op=mark_incorrect → 反候选（写入 blacklist，下次抽取时排除该标签）
2. **Given** HITL candidate 走完审批 merge，**When** SemanticService.merge_candidates(candidate_ids) 执行，**Then** 同时写入 USL 5 张表 + 更新 Ontology TBox：新增 ObjectType → `ontology_api.services.OntologyService.create_object_type()` 同步调用；新增 RelationType → `create_relation_type()` 同步调用；新增 Property → `add_property()` 同步调用；新增同义词 → ObjectType.aliases 数组追加。双写采用 Outbox 模式：USL 写入 + outbox 消息表入同一 DB 事务，后台 worker 消费 outbox 调用 OntologyService，失败重试 3 次后告警，保证最终一致
3. **Given** 管理员在语义配置后台直接调用 `POST /api/semantic/terms` 手动新增术语，**When** 审批 merge 完成，**Then** 同样触发 TBox 双写（与 HITL 写回同一条代码路径，不分支）
4. **Given** 术语从 USL 被删除（status=deprecated），**When** 删除传播，**Then** Ontology TBox 对应 ObjectType/RelationType 也标 deprecated（而非物理删除，因可能有实例引用），删除操作同样走审批流（不可直接删）
5. **Given** 飞轮运行 N 轮，**When** 对同一领域新文本抽取，**Then** 抽取准确率（按 LLM 评审 score）应显示持续提升趋势：`GET /api/semantic/metrics/flywheel` 返回 `{per_epoch_accuracy: [0.62, 0.68, 0.74, 0.79], epoch_window: "30天", total_human_corrections: 183, merged_corrections: 157}`，数据来源于 audit_log 聚合

---

### User Story 7 - L3-L6 全量 + 老目录清理 + 电商脚本 + 质量面板 (Priority: P2, Iter 4)

完成 L3（属性层：属性值域约束/单位/数据类型推断）、L4（规则层：关联规则 Apriori + SWRL 规则候选）、L5（模式层：Ontology Design Pattern 识别与复用）、L6（公理层：OWL DL 表达的全域公理）四级抽象，与 L1-L2 连通形成完整 6 层概念塔。清理老目录：删除 `design/schema/semantic_layer/` 原目录，删除 `semantic_config.py`，所有 import 路径已在 Iter1 中迁移。新增电商领域 seed 迁移脚本（`seed_migrate --domain ecommerce`）覆盖商品/用户/订单/支付/物流 5 大核心实体 + 关联关系。最后上线语义管理质量面板：3 关通过率趋势、审批流 SLA 达标率、HITL 飞轮提升曲线、术语密度、概念塔完整度 6 大核心 KPI。

**Why this priority**: P2，锦上添花。L3-L6 是高级推理能力的基础但非 P0/P1 阻断项；老目录清理降低维护成本；电商 seed 扩展领域覆盖；质量面板是运营可视化需要。

**Independent Test**: 电商 seed migrate apply 后，质量面板 6 大 KPI 全部有数值（非空）；L3 属性值域推断对商品 price 属性给出 `type=number, min=0, unit=CNY`；L4 Apriori 对订单实例挖掘出 `{买手机 → 买手机壳}` support=0.15, confidence=0.72 关联规则；老目录删除后 `pytest tests/ -v` 全绿。

**Acceptance Scenarios**:

1. **Given** L1-L2 概念塔 + 抽取实例属性数据，**When** `ConceptExtractor.run_l3_l4_l5_l6(domain_id)`，**Then**：
   - L3 属性层：对每个 ObjectType 的每个 Property，统计值分布，推断 type（string/number/integer/boolean/date/enum）、enum 值域（唯一值<20 视为枚举）、min/max（数值型）、format 正则（字符串，如手机正则 /^1[3-9]\d{9}$/）、单位（基于中文单位词匹配：元/件/kg/天），写入 `usl_l3_properties` 表（`property_id, object_type_id, inferred_type, value_constraint_json, confidence, status`）
   - L4 规则层：对实例事务表（订单/事件）跑 Apriori（min_support=0.05, min_confidence=0.6, max_len=3），输出关联规则 → 映射为 SWRL rule 候选，写入 `usl_l4_rules`（`id, antecedent, consequent, support, confidence, lift, status`）
   - L5 模式层：对 L2-L3 结构做子图同构匹配，识别 ODP（Ontology Design Pattern）：如 `{Item -has_part→ Part}` 识别为 PartOf 模式、`{Person -member_of→ Organization -has_role→ Role}` 识别为 RolePattern，复用模式时输出 `pattern_suggestion: {name, description, example_concept_ids}`
   - L6 公理层：将 L4 规则 + L5 模式 + 人工审核规则编译为 OWL DL 公理（disjointWith / subClassOf / domain / range / inverseOf / transitive），写入 `usl_l6_axioms`（`id, axiom_type, subject, object, owl_expression, inferred_by, status`）
2. **Given** Iter4 启动时点，**When** 执行 cleanup 脚本 `python -m odap.biz.core.semantic.storage.cleanup_old_code --apply`，**Then** 删除：(a) `design/schema/semantic_layer/` 原目录（所有文件）；(b) `semantic_config.py`；(c) 所有 `from ...semantic_config import` 通过 sed 替换为 `from odap.biz.core.semantic import SemanticService`；(d) 运行全量测试确保无 import 断裂。cleanup 支持 `--dry-run` 只报告要删除的文件列表，不落盘
3. **Given** 电商领域 seed 脚本，**When** `seed_migrate --apply --domain ecommerce`，**Then** 写入：ObjectType = 商品/用户/订单/支付/物流/店铺/优惠券/评价（≥8），RelationType = 下单/支付/发货/收货/评价/收藏/推荐（≥7），Property = 商品 SKU/价格/库存/分类/品牌 + 订单号/金额/状态/时间 + 物流单号/状态/地址 + 支付方式/金额/时间，同义词库 = 电商常用词（"购买"="下单"="拍下"、"退款"="退货"="售后"… ≥30 组），扩展规则 = 商品→按分类扩展/按品牌扩展…（≥5）
4. **Given** 质量面板后端接口 `GET /api/semantic/dashboard/metrics`，**When** 调用，**Then** 返回 JSON 含 6 大 KPI：`{qg_pass_rate_trend: [{date, rate}], approval_sla: {l1_avg_hours, l2_avg_hours, sla_95th_percentile_hours}, flywheel_accuracy: [{epoch, accuracy, sample_size}], term_density: {domain_id, terms_per_object_type, synonyms_per_canonical, expansion_count}, concept_tower_completeness: {l1_count, l2_count, l3_count, l4_count, l5_count, l6_count, completeness_score=1 - sum(empty_levels)/6}, top_10_pending_candidates: [...]}`，所有数值实时聚合（SQLite 视图 + 定时缓存，缓存 TTL 60s）
5. **Given** Iter4 结束时点，**When** 运行 `pytest tests/ -v` 全量测试，**Then** semantic 模块测试 ≥ 300 条（每 FR 至少 1 条），行覆盖率 ≥ 90%，原 import `semantic_config` 全部触发 ImportError（已删除）

---

## Requirements *(mandatory)*

### Functional Requirements

#### 子域 A: USL 独立服务化（6 层结构 + 持久化）

- **FR-001**: 必须在 `odap/biz/core/semantic/` 下按 AGENTS.md 6 层规范新建目录结构：`api/`（routes.py, schemas.py, __init__.py）、`services/`（semantic_service.py, candidate_service.py, quality_gate_service.py, approval_service.py, hitl_service.py, concept_extractor.py, dashboard_service.py, __init__.py）、`impl/`（*_impl.py 系列）、`interfaces/`（*_repository.py, *_engine.py + __init__.py）、`models/`（domain.py, canonical_term.py, synonym.py, en_mapping.py, expansion_rule.py, candidate.py, approval.py, quality_gate.py, l3_property.py, l4_rule.py, l5_pattern.py, l6_axiom.py, audit_log_entry.py + __init__.py）、`storage/`（sqlite_usl_storage.py, seed_migrate.py, cleanup_old_code.py, neo4j_candidate_writer.py, opa_policy_engine.py, outbox_worker.py + __init__.py）
- **FR-002**: SQLite 必须新建 11 张 USL 表：`usl_domains(id, name, display_name, description, lang[zh/en/both], status, created_at, updated_at, UNIQUE(name))`、`usl_canonical_terms(id, domain_id FK, term_type[object/relation/action/property/l1_concept/l2_concept], name, definition, parent_id, level, status, created_at, updated_at, UNIQUE(domain_id, term_type, name))`、`usl_synonyms(id, canonical_term_id FK, synonym_text, synonym_type[synonym/near_synonym/alias], confidence, status, created_at, UNIQUE(canonical_term_id, synonym_text, synonym_type))`、`usl_en_mapping(id, canonical_term_id FK, en_name, status, UNIQUE(canonical_term_id))`、`usl_expansion_rules(id, domain_id FK, pattern_text, expansion_json[list], status, created_at, UNIQUE(domain_id, pattern_text))`、`usl_candidates(id, domain_id FK, level[L1/L2/L3/L4/L5/L6], candidate_type[object_type/relation_type/property/synonym/inheritance/axiom/rule], label_or_text, parent_candidate_id, member_refs_json, confidence, quality_gate_report_json, status[proposed/qg_passed/qg_failed/l1_approved/l2_approved/merged/rejected/deprecated], source[he_extraction/fca/hitl_correction/manual/seed/l3_inference/l4_mining/l5_odp/l6_owl_compile], reject_reason, created_by, created_at, updated_at, merged_at, approver_l1_id, approver_l2_id)`、`usl_approvals(id, candidate_id FK, approval_level[1/2], approver_id, action[approve/reject/defer], comment, created_at)`、`usl_outbox(id, event_type[semantic_changed/tbox_sync/flywheel_metric], payload_json, status[pending/sent/failed], retry_count, next_retry_at, created_at, processed_at)`、`usl_l3_properties(id, candidate_id FK nullable, canonical_term_id FK nullable, property_name, inferred_type[string/number/integer/boolean/date/enum], value_constraint_json{min,max,pattern,enum_values,unit}, confidence, status)`、`usl_l4_rules(id, candidate_id FK nullable, domain_id, antecedent_json, consequent_json, support REAL, confidence REAL, lift REAL, rule_type[association/swrl], status)`、`usl_l6_axioms(id, candidate_id FK nullable, domain_id, axiom_type[subClassOf/disjointWith/domain/range/inverseOf/transitive/reflexive], subject_term, object_term, owl_expression_turtle, inferred_by, status)`
- **FR-003**: 必须实现 `SemanticService` 接口：`get_domain(name) → Domain`、`list_domains() → List[Domain]`、`create_domain(name, display_name, description, lang) → Domain`、`get_canonical_terms(domain_id, term_type?, page, size) → Page[CanonicalTerm]`、`get_term_with_all_synonyms(canonical_term_id) → TermDetail{canonical, synonyms[], en_mapping, expansion_rules[]}`、`add_synonym(canonical_term_id, text, type, confidence=1.0) → Synonym`（写 DB + 广播 invalidate cache）、`add_expansion_rule(domain_id, pattern, expansion_list) → ExpansionRule`、`update_term(canonical_term_id, **fields) → CanonicalTerm`、`delete_term(canonical_term_id) → status=deprecated`、`hot_reload(domain_id?) → None`（清除本地 + 进程间 USLCache，下一次查询时从 DB 重加载）
- **FR-004**: 必须实现 `USLCache` 内存缓存层：key 为 `{domain_id}:{entity}`，TTL 默认 300s（可通过 `semantic.cache_ttl_seconds` 配置）；任何写操作（add_synonym/update_term/merge_candidate）后必须调用 `invalidate(domain_id)` 广播（多进程场景通过 SQLite `usl_cache_invalidations` 表 + 轮询实现，每 2s check 一次 last_invalidation_id > 本进程 processed_id）；缓存命中率指标必须暴露（通过 `/metrics/semantic` Prometheus 格式）
- **FR-005**: 原 `design/schema/semantic_layer/` 下的 IntentParser / QueryPlanner / Disambiguator 三个类必须迁移到 `biz/core/semantic/impl/` 下，改为依赖注入 `SemanticService`（而非硬编码 dict），保留原公共方法签名；路由 `/api/semantic/parse-intent` `/plan-tasks` `/synonyms` `/expansion-rules` 路径不变，处理函数改为 `semantic/api/routes.py` 中的新 handler
- **FR-006**: 兼容性：原 `from odap.biz.core.ontology.design.schema.semantic_layer import IntentParser` 路径必须通过 `__init__.py` alias 再保留 2 个迭代（Iter1-Iter2），同时触发 DeprecationWarning，Iter3 中由 cleanup 脚本删除

#### 子域 B: Seed 迁移 + 幂等/回滚

- **FR-007**: seed_migrate.py 必须支持 CLI 参数 `--mode check|apply|rollback`（默认 check）、`--domain all|sanguo|xiyou|shared|ecommerce`（默认 all）、`--db-path`（默认取 `get_config("db.path")`）
- **FR-008**: seed_migrate apply 必须幂等：所有 INSERT 使用 `INSERT OR IGNORE`（基于 UNIQUE 约束），对 shared → sanguo/xiyou → ecommerce 的顺序写入避免 FK 级联问题
- **FR-009**: seed_migrate rollback 必须级联删除：给定 domain，先删子表（synonym/canonical/en_mapping/expansion/l3/l4/l6/candidate），再删 domain 本身；`--domain all` 回滚必须走反向顺序 ecommerce → xiyou → sanguo → shared 避免 FK 锁
- **FR-010**: check 模式必须输出结构化报告：`{domain: {name, will_insert_domain:1, will_insert_canonical:N, will_insert_synonyms:M, will_insert_en_mapping:K, will_insert_expansion:E, already_present_count:P, conflicts:[]}}`，conflict 列出 UNIQUE 冲突的已存在行
- **FR-011**: 迁移后必须写入 `usl_migrations` 元数据表：`id, domain, direction[apply/rollback], started_at, finished_at, status, row_counts_json, operator_user`，便于审计
- **FR-012**: `semantic_config.py` 改为 proxy 模式：导入时检查是否已迁移（查 `usl_migrations` 表），若已迁移则实际从 SemanticService 读数据并发出 DeprecationWarning，若未迁移则 fallback 原 dict（保障迭代间无停机）

#### 子域 C: L1-L2 概念抽取 + Candidate 双写

- **FR-013**: L1 聚类算法固定为 BGE-large-zh embedding（1024 维，通过 `sentence-transformers` 加载本地模型文件 `data/models/bge-large-zh-v1.5/`，不存在时自动从 HuggingFace 镜像拉取）→ UMAP 降维到 64 维（n_neighbors=15, min_dist=0.1, metric=cosine）→ HDBSCAN 聚类（min_cluster_size=3, min_samples=2, cluster_selection_epsilon=0.35, metric=euclidean）
- **FR-014**: L1 聚类 confidence 计算公式：`cluster_confidence = (1 / |C|) * Σ_{i∈C} Σ_{j∈C, j>i} cos(emb_i, emb_j) * 2/(|C|(|C|-1))`，即簇内平均两两余弦相似度；`confidence < 0.6` 的簇全部丢弃（label=noise，不写 candidate）
- **FR-015**: L2 FCA 形式上下文构造：对象集 G = 簇内实体；属性集 M = 每个实体的抽取属性键（属性值去停用词后哈希）；二元关系 I(g, m) = True 当且仅当实体 g 拥有属性 m；概念计算使用标准 NextClosure 算法（从 concepts 库 `from concepts import Context`），仅保留 extent 大小 ≥ 2 且 intent 大小 ≥ 1 的概念
- **FR-016**: L2 层级关系抽取：概念格偏序序对 (A, B) 满足 `A.intent ⊃ B.intent`（B 是 A 的超概念）映射为 `is_a` 层级，`B` 为父概念；同时 `A.intent \ B.intent` 作为子概念的独有属性集合，存 candidate.differential_attrs_json
- **FR-017**: CandidateWriter dual_write 事务协议：(1) 开 SQLite 事务写入 usl_candidates + 子表 → (2) 开 Neo4j 事务写 ConceptCandidate 节点 + IS_A 边 → (3) 两者都成功才 commit 两边，任一异常 → (4) Neo4j rollback → (5) SQLite rollback → (6) raise 异常；幂等保证：candidate 唯一键为 `(domain_id, level, candidate_type, label_or_text, parent_candidate_id)`，INSERT OR IGNORE 时 Neo4j 也 MERGE（非 CREATE）
- **FR-018**: 必须实现 Candidate CRUD API：`GET /api/semantic/candidates?domain_id&level&candidate_type&status&page&size&sort_by=confidence|created_at`（支持多组合过滤 + 分页）、`GET /api/semantic/candidates/{id}`（含 quality_gate_report、approvals 历史、member_refs 详情）、`DELETE /api/semantic/candidates/{id}`（软删 status=rejected，非物理删，需权限 L1+）
- **FR-019**: Candidate 批量操作 API：`POST /api/semantic/candidates/batch-delete`（body: ids: int[], 最大 50 条/次）、`POST /api/semantic/candidates/export`（按当前 filter 导出 JSON，≤ 10000 条/次）
- **FR-020**: Neo4j Candidate 节点属性必须与 SQLite 字段对齐：`id, domain_id, level, candidate_type, label, confidence, status, source, created_at, updated_at`；IS_A 边属性：`from_candidate_id, to_candidate_id, inferred_by, confidence`；Neo4j 索引：`CREATE INDEX idx_candidate_domain IF NOT EXISTS FOR (n:ConceptCandidate) ON (n.domain_id, n.status, n.level)`

#### 子域 D: ExtractService mode=schema_learning 改造

- **FR-021**: ExtractionService.extract_from_nl / extract_from_document / extract_from_kb 三个方法签名必须新增 `mode: Literal["instance_extraction", "schema_learning"] = "instance_extraction"` 参数，以及 `schema_learning_config: Optional[Dict] = None`（可选覆盖：l1_min_cluster_size、l2_attr_share_threshold、auto_drop_confidence）
- **FR-022**: mode=schema_learning 时创建 ExtractionSession 的 type 必须 = `schema_learning`，最终 session.status 流程 = `created → extracting → concept_l1 → concept_l2 → candidate_written → reviewing_schema`，任何中间失败 → status = `failed` 并记录 error_message
- **FR-023**: schema_learning 结果映射到 candidate_type 规则：(L2 概念, candidate_type="object_type", label_or_text=concept_label, parent_candidate_id=parent_concept_id if is_a else NULL)、(L2 is_a 边, candidate_type="inheritance", label_or_text=f"{child_label}_is_a_{parent_label}", parent_candidate_id=NULL)、(FCA 非层级关联概念对, candidate_type="relation_type", label_or_text=infer_{src}_{dst})、(FCA 共享属性, candidate_type="property", label_or_text=attr_name, parent_candidate_id=所属 ObjectType candidate_id)
- **FR-024**: schema_learning_config 默认值：`{l1_min_cluster_size: 3, l2_attr_share_threshold: 0.75, auto_drop_confidence: 0.6, run_l3: false, run_l4: false}`（P2 L3-L4 单独跑，默认关闭减少耗时）；用户传入的配置会覆盖默认值
- **FR-025**: ExtractionSession.result_data schema_learning 模式下必须额外包含：`schema_candidates: {object_type_count, relation_type_count, property_count, inheritance_count, all_candidate_ids[]}`、`l1_clusters_report: {noise_count, cluster_count, avg_cluster_size, cluster_confidence_distribution}`、`l2_fca_report: {concept_count, lattice_edge_count, dropped_small_concepts}`
- **FR-026**: 原 mode=instance_extraction（默认）的所有行为必须 100% 回归：session.type=natural_language/document/knowledge_base，confirm_extraction 双通道写入不变；集成测试中对同一文本分别用两种 mode 抽取，断言 Neo4j 中 label Instance 和 ConceptCandidate 数量与期望一致且互不重叠

#### 子域 E: 3 关质量闸（Quality Gate）

- **FR-027**: QG-1（置信度与去重闸）公式：`pass_qg1 = (candidate.confidence >= qg1_conf) AND (max_jaccard_existing < qg1_jaccard)`。其中 `qg1_conf = get_config("semantic.qg1_confidence_threshold", 0.65)`、`qg1_jaccard = get_config("semantic.qg1_jaccard_threshold", 0.7)`。Jaccard 计算：`J(A, B) = |A ∩ B| / |A ∪ B|`，分词（jieba）后 token 集合，max_jaccard_existing = 当前 domain 中与 candidate.label Jaccard 最大的已存在 canonical_term name
- **FR-028**: QG-2（结构一致性闸）：
  - object_type candidate：若 parent_candidate_id 非空 → `new_candidate.differential_attrs_json ∩ parent_candidate.mandatory_attrs_json = ∅`（子类型不得覆盖父类型必填属性，否则破坏 LSP）；若 parent 为空 → 检查与所有同级（同 level、无父）术语的重名率（Jaccard < qg1_jaccard，复用 QG-1）
  - relation_type candidate：`domain` ObjectType 必须存在（status=merged/deprecated OK，deprecated 需 warn）、`range` ObjectType 必须存在；若已有同 name 的 RelationType，检查 domain/range 是否一致（不一致 fail，一致且属性无扩展 → 标记 duplicate，qg2 特殊状态 pass_but_duplicate，审批流中高亮但不自动 reject）
  - property candidate：若绑定 ObjectType，检查属性名不与继承链上同名属性冲突（同 type 允许，冲突类型 fail + reason "属性类型冲突：父类{name}为{old_type}，新属性为{new_type}"）
- **FR-029**: QG-3（语义一致性闸）：
  - LLM 固定模型：`get_config("semantic.qg3_model", "gpt-4o-mini")`、temperature=0，max_tokens=512
  - Prompt 模板（严格）："你是资深本体 Schema 审核专家，仅输出 JSON。领域：{domain_display_name}（{domain_description}）。候选信息：level={level}, candidate_type={candidate_type}, label={label}, parent={parent_label or '无'}, 预期属性/关联={member_refs_summary_str}, confidence={confidence:.2f}。任务：判断该候选是否符合 {domain_display_name} 本体 Schema 规范，是否与已有术语语义一致，无过宽/过窄/歧义。输出：{\"pass\": true/false, \"reason\": \"≤100字中文理由\", \"risk_level\": \"low/medium/high\", \"suggested_edits\": [\"可选修改建议\"]}"
  - 采样 3 次（self-consistency），pass 票数 ≥ 2 视为 QG-3 pass；risk_level=high 即使 pass 也标为 `qg3_high_risk_flag=true`，审批流强制人工过
  - LLM 调用超时 30s、限流、失败时默认行为：`retry 2 次 → 仍失败则 qg3_status=deferred，不阻断也不通过，需人工介入，写入 quality_gate_report`
- **FR-030**: QualityGateService.run_all() 必须写入结构化 `quality_gate_report_json`：`{qg1: {pass, confidence, jaccard_score, threshold_conf, threshold_jac, reason}, qg2: {pass, checks: [{name, pass, detail}], reason}, qg3: {pass, votes: [pass/fail x3], llm_reasons: [str x3], majority_risk, deferred_flag}, overall: {pass, first_failed_gate or "none", running_time_ms}}`
- **FR-031**: 质量闸批量执行：`POST /api/semantic/quality-gates/run`（body: candidate_ids[]，最大 100 条/次，LLM 调用并发控制 `semantic.qg3_concurrency=4`，用 asyncio.Semaphore）；返回 per-candidate 报告 + 总体统计（passed/failed/deferred count）
- **FR-032**: 质量闸阈值必须可通过 OPA 策略覆盖：OPA rego `qg_thresholds.rego` 输出 `{qg1_conf, qg1_jac, qg3_model, qg3_concurrency}`，优先级高于 get_config；OPA deny 时 quality_gate 立即中止返回 403

#### 子域 F: 2 级审批流 + OPA 策略引擎

- **FR-033**: OPA 策略引擎封装：`OPAService.evaluate(package: str, input: Dict) → {allowed: bool, reason: str, metrics: Dict}`。OPA 用本地进程内执行（`pip install opa-python=0.6.2`，非 HTTP sidecar，减少运维）；策略目录 `config/opa/semantic/**/*.rego` 递归 watch（watchdog），文件 mtime 变化后 5s 内自动 reload；所有策略的 package 前缀 `data.semantic.*`
- **FR-034**: 审批流状态机（严格，非法转换抛 ValueError）：`proposed →(run QG)→ qg_passed / qg_failed`；`qg_passed →(L1 approve)→ l1_approved；qg_passed →(L1 reject)→ rejected`；`l1_approved →(L2 approve/merge)→ merged；l1_approved →(L2 reject)→ rejected`；`rejected →(L2 reopen)→ proposed`；`merged → 终态`；每一次转换必须写 `usl_approvals` 表 + `UnifiedAudit.log_action`（action="semantic_approval_transition", resource_id=candidate_id）
- **FR-035**: L1 审批 OPA 策略（`semantic.l1_approve.rego`）：allow 当且仅当 `input.user.roles contains "semantic_dom_admin" AND input.user.managed_domains contains input.candidate.domain_id AND len(input.candidate_ids) <= get_config("semantic.l1_batch_limit", 50)`；reject 需提供 comment ≥ 10 字（前端+后端双重校验）
- **FR-036**: L2 审批 + merge OPA 策略（`semantic.l2_merge.rego`）：allow 当且仅当 `input.user.roles contains "semantic_global_admin"`；merge 操作额外限制 `len(input.candidate_ids) between 1 and 100`、`input.candidate.status must all be "l1_approved"`；merge 事务隔离级别 = SERIALIZABLE（SQLite `PRAGMA journal_mode=WAL; BEGIN IMMEDIATE`）防并发写入 USL 表
- **FR-037**: 审批 API：`POST /api/semantic/approvals`（body: candidate_ids[], approval_level, action, comment）、`GET /api/semantic/approvals?candidate_id=&approver_id=&approval_level=&page&size`（查询审批历史）、`POST /api/semantic/approvals/defer`（L1 可 defer 候选到 "待补充材料"，status=deferred，需 comment ≥ 20 字，7 天未补自动 reject）
- **FR-038**: 合并写回 `SemanticService.merge_candidates(ids)` 事务步骤：(1) 校验全部 l1_approved → (2) 开 SQLite SERIALIZABLE 事务 → (3) 逐个 candidate：写入 usl_canonical_terms / usl_synonyms / usl_en_mapping / usl_expansion_rules / usl_l3 / usl_l4 / usl_l6（按 candidate_type 路由）→ (4) 更新 candidate.status=merged, merged_at=NOW(), approver_l2_id=current_user → (5) 写 usl_outbox 事件（type=tbox_sync，payload={candidate_id, new_term_ids[]}）→ (6) 写 usl_outbox 事件（type=flywheel_metric 若是 HITL 来源）→ (7) commit；全部成功后返回 {merged_count, new_term_ids[]}，任何步骤失败整个事务 rollback
- **FR-039**: outbox worker：单独线程（`threading.Thread(daemon=True)`，非 asyncio 避免事件循环耦合）每 5s 轮询 `usl_outbox WHERE status=pending ORDER BY id LIMIT 10`；tbox_sync 事件 → 调用 `OntologyService.create_object_type()` / `create_relation_type()` / `add_property()`；失败：retry_count 递增（0→1→2→3），next_retry_at = NOW + 2^retry 分钟，>3 次 → status=failed + 告警（`logger.error` + 若配置 `semantic.alert_webhook` 则 POST webhook）；processed_at 写入完成时间

#### 子域 G: HITL 飞轮 + Ontology TBox 双写

- **FR-040**: HITL correction op 枚举（严格 5 种）：`retype_entity`（body: entity_id, from_type, to_type, canonical_term_id?）、`merge_entities`（body: surviving_entity_id, merged_entity_ids[], merged_label）、`add_synonym`（body: entity_id, synonym_text, canonical_term_id?）、`retype_relation`（body: relation_id, from_type, to_type）、`mark_incorrect`（body: entity_id or relation_id, reason）
- **FR-041**: `HITLService.submit_corrections(session_id, corrections[])`：(1) 校验 session.status 必须 = reviewing / reviewing_schema / confirmed（rejected session 不接受修正）→ (2) 每条 correction 映射为 candidate：retype_entity → object_type candidate（to_type 若已存在则 candidate_type=inheritance 挂到 existing 下）；add_synonym → synonym candidate（关联 existing canonical_term_id）；merge_entities → 先写 synonym candidate 两两之间，再标 1 条 merge 建议型 candidate；mark_incorrect → 写 `usl_blacklist`（id, domain_id, blocked_label, reason, created_by），下次 QG-1 时与 blacklist Jaccard ≥ 0.9 直接 fail
- **FR-042**: 飞轮效果度量：每次 merge HITL 来源的 candidate 后，`DashboardService.update_flywheel_metric(domain_id)` 重新计算 `per_epoch_accuracy`（滑动窗口 30 天 = 1 epoch，epoch 内所有 schema_learning 模式抽取的 QG-3 pass_rate 作为 accuracy proxy）；`GET /api/semantic/metrics/flywheel` 返回 6 个 epoch 的趋势数组
- **FR-043**: TBox 双写最终一致保障：outbox worker 成功后，必须回写 `usl_candidates.tbox_synced_object_type_id / tbox_synced_relation_type_id` 到 OntologyService 返回的 id；下次重启应用时启动时扫描 `usl_outbox WHERE status != sent AND processed_at IS NULL AND created_at < NOW - 6h`，重新投递避免永久挂起
- **FR-044**: 删除术语（status=deprecated）传播：`delete_term(canonical_term_id)` 只能由 L2 调用；行为 = (1) canonical.status = deprecated → (2) outbox 事件 semantic_changed + tbox_sync（调用 OntologyService.deprecate_object_type() / deprecate_relation_type()：status=deprecated，不物理删）→ (3) 级联：所有 synonym.status = deprecated、en_mapping.status = deprecated、候选中 child.status = deprecated（递归）；任何术语若仍有 Instance 引用（Neo4j 查询），OPA deny 删除，返回 `{"status":"denied","reason":"术语仍有 N 个实例引用，请先迁移实例"}`

#### 子域 H: L3-L6 全量 + 电商 seed + 质量面板 + 老目录清理

- **FR-045**: L3 属性值域推断（`ConceptExtractor.run_l3`）：
  - type 推断规则：数值型（≥ 90% 值可转为 float/int）→ number/integer；"是/否/true/false"占比 ≥ 90% → boolean；日期格式（YYYY-MM-DD / YYYY/MM/DD / 时间戳）≥ 80% → date；唯一值数 ≤ 20 且总样本 ≥ 100 → enum，枚举值取 top-20 value；其余 → string
  - value_constraint 计算：数值型 → min/max = 数据中 p0.5 / p99.5 分位数（防离群）；string 型 → 若匹配正则库（手机号/邮箱/身份证/URL/邮编）则填入 pattern 字段；枚举型 → enum_values 数组 + 频次 map
  - 置信度公式：`conf_l3 = type_match_ratio * 0.6 + (1 - null_ratio) * 0.4`，conf_l3 < 0.7 → status=proposed 需审批，≥ 0.7 → qg_preapproved（QG-1 自动通过）
- **FR-046**: L4 关联规则挖掘（`ConceptExtractor.run_l4`）：
  - 事务集构造：订单/事件类实体的属性 + 关联实体组合为"购物篮"，每个 ObjectType 实例 = 1 条 transaction
  - Apriori 算法参数默认：min_support=0.05, min_confidence=0.6, max_length=3（可通过 `semantic.l4_apriori` 配置覆盖）
  - 输出规则质量指标：support = P(A ∪ C), confidence = P(C|A) = support/support(A), lift = confidence / P(C)；lift < 1.0 的规则丢弃（负相关无意义）
  - 映射 SWRL 模板：antecedent → 规则前件 body，consequent → 规则头 head，例：`Item(?i), has_category(?i,"手机") → RecommendItem(?i, Item_with_category("手机壳"))`
- **FR-047**: L5 ODP 识别：内置 6 个经典 ODP 模板（PartOf / Role / Classification / Membership / NaryRelation / TemporalEntity），每个模板为固定子图结构（节点-边-label 正则）；用子图同构（VF2 算法，`networkx.is_isomorphic` with node_match）在 L2-L3 概念塔上匹配，匹配度 ≥ 0.8（结构相同 + 语义标签余弦相似度）输出 candidate_type="pattern_suggestion"，suggested_edits 中给出 refactor 方案
- **FR-048**: L6 OWL 公理编译：将 L4 SWRL + L5 pattern + inheritance 层级 编译为 OWL 2 DL 公理，Turtle 语法（`prefix owl: <http://www.w3.org/2002/07/owl#>. prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>. prefix odap: <http://odap.io/semantic#>`）。axiom_type 枚举严格 = subClassOf / disjointWith / domain / range / inverseOf / transitive / reflexive；保存到 `usl_l6_axioms.owl_expression_turtle` 字段，后续可被 HermiT reasoner 消费（见 research.md RQ-4）
- **FR-049**: 电商领域 seed 数据量要求（硬性 count）：ObjectType ≥ 8（商品/用户/订单/支付/物流/店铺/优惠券/评价）、RelationType ≥ 7（下单/支付/发货/收货/评价/收藏/推荐）、Property ≥ 25（商品: SKU/名称/价格/原价/库存/分类/品牌/规格/重量/产地/上架时间/状态 12；用户: ID/昵称/手机号/注册时间/等级/收货地址 6；订单: 号/金额/状态/创建时间/支付时间/发货时间 6；物流: 单号/状态/地址/更新时间 4 → 12+6+6+4=28 ≥ 25 OK）、Synonyms ≥ 30 组、Expansion_rules ≥ 5 条
- **FR-050**: 质量面板 DashboardService 指标 SQL 语句（SQLite 视图，性能保障）：
  - qg_pass_rate_trend：`SELECT date(created_at) as d, AVG(CASE WHEN status='qg_passed' THEN 1 ELSE 0 END) as rate FROM usl_candidates WHERE created_at >= date('now','-30 day') GROUP BY d ORDER BY d`
  - approval_sla：l1_avg_hours = `AVG(julianday(a1.created_at)-julianday(c.updated_at))*24 WHERE a1.level=1 AND c.status='qg_passed'→'l1_approved'`，l2_avg_hours 同理，95th percentile = `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY hours)`（SQLite 用 `approx_percentile` UDF 或排序取 95% 位置）
  - term_density：terms_per_object_type = `COUNT(CASE WHEN term_type='object' THEN 1 END) / COUNT(DISTINCT CASE WHEN term_type='object' THEN name END)`，synonyms_per_canonical = `AVG(syn_count_per_term)`（GROUP BY canonical_term_id 后二次 AVG）
  - concept_tower_completeness：6 级 count 统计，空级数量/6，completeness = 1 - empty_ratio
- **FR-051**: 老目录清理脚本 `cleanup_old_code.py --apply` 必须执行：(a) `shutil.rmtree("odap/biz/core/ontology/design/schema/semantic_layer")`（先备份到 `data/backup/semantic_layer_YYYYMMDDHHmm.tar.gz`）、(b) `os.remove("odap/biz/core/ontology/design/schema/semantic_config.py")`（同备份）、(c) 对所有 `*.py` grep `from.*semantic_config import` / `from.*semantic_layer.* import IntentParser` 等 → 替换为新路径；dry-run 模式下只输出替换 diff 与备份计划，不修改文件系统
- **FR-052**: 质量面板前端 API：`GET /api/semantic/dashboard/overview` 返回上面 6 大 KPI + `last_updated_epoch_ms`；`GET /api/semantic/dashboard/top-pending` 返回 top N=10 待审批候选（按 confidence desc 排序，L1/L2 分两组）；`GET /api/semantic/dashboard/export-csv?metric=qg_trend/flywheel_accuracy/approval_sla` 导出 CSV（UTF-8 BOM + 中文列名 Excel 兼容）

### 补全 FR-053 到 FR-060（补足到 60 条硬性 FR）

#### 子域 I: 运营与可观测

- **FR-053**: 必须为 SemanticService 的每个公共方法添加结构化日志（python-json-logger）：`{"ts": ISO8601, "level": "INFO", "module": "semantic", "method": "SemanticService.add_synonym", "args_summary": {"canonical_term_id": 123, "synonym_len": 4}, "result_status": "ok/error", "duration_ms": N, "trace_id": str}`；trace_id 通过 FastAPI middleware 注入（request header X-Trace-ID 或 auto-gen）并传递到所有下游调用
- **FR-054**: 必须暴露 Prometheus 指标（通过 `/metrics/semantic`，Prometheus FastAPI Instrumentator）：`semantic_cache_hit_total{domain}` / `semantic_cache_miss_total{domain}` / `semantic_qg_duration_seconds{gate="1/2/3"} histogram` / `semantic_approval_duration_seconds{level="1/2"} histogram` / `semantic_candidate_status_total{status}` / `semantic_outbox_retry_total` / `semantic_llm_call_total{model, success="true/false"} counter`
- **FR-055**: 必须支持多语言（i18n）：canonical_term.name 支持多语言字典 `{zh: "...", en: "..."}` 存储；新增 API 头部 `Accept-Language: zh-CN / en-US`，自动返回对应语言字段，缺失 fallback 到 `lang` 首选语言，再 fallback zh-CN；OPQ 策略 + 质量闸 prompt 语言与 Accept-Language 对齐
- **FR-056**: 并发与限流：写操作（approve/merge/add_term/delete_term/HITL submit）按 user_id + domain_id 粒度令牌桶限流（`semantic.write_rps_per_user=2`，`slowapi` Limiter 基于内存），返回 HTTP 429 Retry-After；读操作限流 `semantic.read_rps_per_ip=100`
- **FR-057**: 必须提供数据备份与恢复：`POST /api/semantic/admin/backup`（L2 权限，SQLite `.dump` 输出 + tar 相关 Neo4j ConceptCandidate 节点导出 Cypher → 存到 `data/backups/semantic_{ts}.tar.gz`，保留最近 30 份，自动清理）；`POST /api/semantic/admin/restore`（上传备份文件 → 校验 checksum → dry-run 报告冲突 → apply 覆盖）
- **FR-058**: 术语去重建议工具：`GET /api/semantic/tools/duplicate-suggestions?domain_id=&threshold=0.85`（阈值默认 0.85，embedding 余弦相似度），对同 domain 同 term_type 的所有 canonical 两两计算 embedding 余弦，≥ 阈值的输出 `[{term_a_id, term_b_id, similarity, suggested_merge_label}]` → 转为 merge candidate 一键提交审批流
- **FR-059**: 版本化术语（不可变历史）：任何 canonical_term / synonym / en_mapping / expansion_rule 更新前必须把旧值写入 `usl_term_versions` 表（id, table_name, row_id, old_value_json, new_value_json, changed_by, changed_at）；`GET /api/semantic/terms/{id}/versions` 可查询变更历史；支持 L2 `POST /api/semantic/terms/{id}/rollback?version_id=X` 回滚（rollback 本身走审批流，不直接改）
- **FR-060**: 开放数据导入导出：`GET /api/semantic/domains/{name}/export?format=json|yaml|owl`（JSON 同内部 schema、YAML 同 HE 模板兼容格式、OWL 2 DL Turtle）；`POST /api/semantic/domains/import?format=json|owl` 导入新领域（解析 → 校验结构 → 全量 QG-1/QG-2 → 全部 proposed status 待审批，不自动 merge）

---

### Non-Functional Requirements (NFR-001 到 NFR-020)

- **NFR-001 性能 - 读延迟**：`GET /api/semantic/synonyms`（cache hit）P95 ≤ 50ms；cache miss 触发 DB load P95 ≤ 200ms（单 domain 规模 ≤ 5000 术语）
- **NFR-002 性能 - 写延迟**：单条 synonym add（含 invalidate cache）P95 ≤ 150ms（SQLite WAL 模式 + 同步写入）；批量 merge 100 条（含 TBox 双写 outbox enqueue）P95 ≤ 5s（不含异步消费 outbox）
- **NFR-003 性能 - L1-L2 抽取**：实体数量 N=500 时，端到端（embedding + UMAP + HDBSCAN + FCA）P95 ≤ 30s；embedding 批大小 = 64；HDBSCAN 用 hnsw 近似加速
- **NFR-004 性能 - QG-3 LLM**：单条 QG-3 P95 ≤ 15s（含 3 次 self-consistency 采样 + 重试）；并发 4 路时单条 100 条批量 QG ≤ 10 分钟
- **NFR-005 可用性 - 服务 SLA**：Semantic 模块 月度可用性 ≥ 99.9%（停机 ≤ 43 分）；质量闸 LLM 不可用时自动降级为 QG-3 deferred（不阻塞其他链路），NFR-001/NFR-002 仍满足
- **NFR-006 可用性 - 数据持久性**：SQLite USL 表必须启用 WAL 模式 + 每日 `VACUUM INTO 'data/backups/usl_{date}.db'` 物理备份 + 每分钟 Binlog 风格（SQLite session 钩子写 `usl_wal_log` 追加表），RPO ≤ 1 分钟，RTO ≤ 10 分钟
- **NFR-007 可扩展性 - 水平加域**：新增 1 个领域（如法律/医疗），步骤仅需：准备 seed JSON → `seed_migrate --apply --domain xxx` → 在 OPA 中给管理员配置 managed_domains → 前端新增领域标签页，不需改代码/重部署；新领域 30 分钟内可上线
- **NFR-008 可扩展性 - 术语规模**：单 domain 术语规模 10 万、同义词 50 万 时，NFR-001 读 P95 仍 ≤ 500ms（USLCache + SQLite GIN 索引 + `CREATE VIRTUAL TABLE usl_terms_fts USING fts5(name, synonyms)` 全文索引）
- **NFR-009 安全 - 认证鉴权**：所有 `/api/semantic/*` 接口必须走 `get_current_user` JWT 依赖；写接口强制 OPA 策略鉴权，拒绝裸 token（非登录态）访问；审计日志 UnifiedAudit 必写（即使 `_audit_available=False` 也要 logger.warning 结构化输出）
- **NFR-010 安全 - 输入校验**：所有入参（term name ≤ 200 字、comment ≤ 2000 字、LLM prompt 注入过滤 `ignore_all_previous_instructions` 类关键词、同义词 XSS 过滤 `<script>`）严格 Pydantic Field + constr 校验，返回 422 + 详细路径
- **NFR-011 安全 - OPA 策略文件权限**：`config/opa/semantic/*.rego` 必须文件权限 0644，禁止世界可写；启动时做 SHA-256 校验 + 和内置 baseline hash 比对，不一致则拒绝启动（防策略篡改），管理员更新策略需 L2 API `POST /api/semantic/admin/opa/reload` 带签名
- **NFR-012 一致性 - 双写一致性**：Candidate Writer 双写 SQLite/Neo4j 不一致率（月内巡检 count 差异）≤ 0.01%；每日 3:00 AM cron 跑 `semantic-dual-write-consistency-checker`，diff 超过阈值自动发邮件/钉钉告警并列出修复脚本
- **NFR-013 一致性 - TBox 最终一致**：USL → Ontology TBox 双写 outbox 最大延迟 P95 ≤ 30s（生产观测），超过阈值告警；72h 未 processed outbox 必须人工介入处理（后台任务面板突出显示）
- **NFR-014 可观测性 - 指标覆盖**：所有公共 API 必须有 RED 指标（Rate/Errors/Duration）；错误率 ≥ 5% 触发告警（logger.error + webhook）；慢查询（>1s）日志 `slow_query_ms` 字段必打
- **NFR-015 可维护性 - 测试**：单元测试行覆盖率 semantic 模块 ≥ 90%（Iter 4 验收门槛），集成测试 ≥ 40 条（含 4 迭代全部 Happy Path + Top 3 Unhappy Path per iteration）
- **NFR-016 可维护性 - 代码规范**：严格遵守 AGENTS.md 10 条规则（返回 Dict、HTTPException 仅 routes、单一方法 ≤ 250 LOC、单一职责、强类型 Pydantic、无 any/except Exception 裸捕获等）
- **NFR-017 兼容性 - 迭代迁移零停机**：Iter1→Iter2→Iter3→Iter4 逐步升级，任何迭代无 DB schema 破坏性变更（新增列/表用 ALTER TABLE ADD COLUMN，字段加 nullable 默认值；清理仅发生在 Iter4 cleanup_old_code 且有备份）；旧 API 路径保留 alias 至下下个迭代
- **NFR-018 部署与配置 - 12-Factor**：所有阈值、开关、模型路径、并发数通过 get_config() 读取（支持 env 覆盖 + 管理后台 DB 级覆盖），无代码中硬编码 magic number；Dockerfile 重建后 USL 服务正常启动（seed 迁移为独立 step，失败不阻断镜像 build）
- **NFR-019 国际化 - 中英文双语**：所有 API 错误信息、质量闸 reason、审批通知、前端 UI 文本，必须有 zh/en 双语文案（gettext `*.po` 文件 + FastAPI i18n middleware），默认语言 Accept-Language
- **NFR-020 伦理与合规 - PII 与内容安全**：所有 LLM 调用（QG-3 / L2 retype_suggestion / OWL 编译）必须对输入过 PII 过滤器（脱敏手机号/身份证/邮箱 → `[PHONE]`/`[ID]`/`[EMAIL]`）；HITL 用户修正内容自动过内容安全 API（阿里绿网或自部署），命中违规 → 拒绝提交 + 告警

---

## Out of Scope

以下内容**明确不在本 Feature（SP2）范围**，后续 SP 处理：

1. **推理引擎实装**：虽然 L6 编译 OWL 公理，但本阶段仅存储 turtle 表达式，不实际运行 HermiT/Pellet reasoner 做一致性推理（research.md RQ-4 选型，后续 SP4 实装）
2. **端到端多租户硬隔离**：OPA managed_domains 提供软隔离，本阶段不做 SQLite 多 schema / Neo4j 多 database 的物理隔离，后续 SP5 企业级多租户
3. **自然语言自动生成 ODP**：L5 仅做子图结构匹配，不涉及 LLM 自动总结新概念模式到设计文档
4. **UI 前端开发**：质量面板 + 语义管理后台的 UI 组件不在本 SP 范围内，仅提供 REST API + 数据契约（后续前端 SP 实现）
5. **移动端适配**：后台不考虑 H5 / 小程序 / App
6. **实时流式抽取**：schema_learning 模式基于批量抽取，不接入 Kafka / Flink 流式 topic
7. **知识蒸馏 Student Model**：飞轮积累的高质量数据暂不蒸馏为小模型
8. **跨语言术语对齐**：仅中英双语，不涉及中英日韩多语言跨域对齐
9. **Neo4j 图嵌入与向量检索融合**：L1 embedding 仅用于聚类，不做图神经网络 GNN 训练
10. **联邦学习跨组织协同学习**：所有训练/推理在单组织内发生

---

## Dependencies

### 内部依赖（本项目内模块）

| # | 依赖模块 | 版本 / Commit | 用途 |
|---|---------|--------------|------|
| 1 | `biz/data/hyper_extract`（SP1） | 006-he-extraction-chain 合并后 | ExtractService / HEAdapter / TemplateEngine / ValidationEngine |
| 2 | `biz/core/ontology/ontology_api` | existing | OntologyService.create_object_type / relation_type / property / deprecate_* （TBox 双写） |
| 3 | `biz/core/ontology/extraction` | existing + SP1 改造 | ExtractionService mode 参数扩展（调用方不改签名会 fallback 默认） |
| 4 | `infra/config_composer:get_config` | existing | 所有阈值/开关/路径读取 |
| 5 | `infra.security.jwt_auth:get_current_user` | existing | 认证依赖（全部 /api/semantic/* 路由） |
| 6 | `infra.security.unified_audit:UnifiedAudit` | existing（可选） | 审批/合并/删除审计日志 |
| 7 | `frontend/src/modules/ontology/components/ExtractionPreview.tsx` | existing（需扩展） | HITL 修正入口，新增 5 个 correction op 的 UI 交互 |

### 外部依赖（需新增 pip 包 / 版本升级）

| # | 包名 | 版本 | 用途 | 对应 FR/RQ |
|---|------|------|------|-----------|
| 1 | `sentence-transformers` | 3.0.1 | BGE/Jina/M3E embedding 加载（L1） | FR-013 / RQ-3 |
| 2 | `umap-learn` | 0.5.6 | UMAP 降维（L1，1024→64） | FR-013 |
| 3 | `hdbscan` | 0.8.38 | HDBSCAN 聚类（L1） | FR-013 / RQ-1 |
| 4 | `concepts` | 0.9.2 | FCA 形式概念分析（L2 NextClosure） | FR-015 / RQ-2 |
| 5 | `networkx` | 3.3 | VF2 子图同构（L5 ODP） | FR-047 |
| 6 | `opa-python` | 0.6.2 | OPA 进程内 rego 执行 | FR-033 / RQ 选型 |
| 7 | `mlxtend` | 0.23.1 | Apriori 关联规则（L4） | FR-046 / RQ-5 |
| 8 | `watchdog` | 4.0.1 | OPA 策略文件 watch 热 reload | FR-033 |
| 9 | `slowapi` | 0.1.9 | API 限流令牌桶 | FR-056 |
| 10 | `prometheus-fastapi-instrumentator` | 7.0.0 | /metrics/semantic RED 指标 | FR-054 |
| 11 | `python-json-logger` | 2.0.7 | 结构化 JSON 日志 | FR-053 |
| 12 | `jieba` | 0.42.1 | QG-1 Jaccard 分词 | FR-027 |
| 13 | `rdflib` | 7.0.0 | OWL 2 DL Turtle 解析/导出（L6 / import-export） | FR-048 / FR-060 |

### 数据依赖

| # | 数据/模型文件 | 大小 | 来源 | 存放位置 | 自动获取方式 |
|---|--------------|------|------|----------|-------------|
| 1 | `bge-large-zh-v1.5` 模型 | 1.3GB | HuggingFace（镜像：hf-mirror.com） | `data/models/bge-large-zh-v1.5/` | 首次运行时 sentence-transformers 自动从 hf-mirror.com 拉取 + 本地缓存 |
| 2 | `jina-embeddings-v3`（备选，RQ-3 对比） | 680MB | HuggingFace | `data/models/jina-embeddings-v3/` | 手动下载（RQ-3 验证用，非默认） |
| 3 | `m3e-large`（备选，RQ-3 对比） | 1.3GB | HuggingFace | `data/models/m3e-large/` | 手动下载（RQ-3 验证用，非默认） |
| 4 | 电商领域 seed JSON | <1MB | 本 SP2 编写 | `odap/biz/core/semantic/data/seeds/ecommerce_seed.json` | Git 仓库内 |

### 前置条件（Pre-flight Checklist）

- [ ] SP1 006-he-extraction-chain 已合并到 main，HE 真实启用（`HEAdapter.is_available() == True`，`Template.list()` 返回 35 预设）
- [ ] SQLite 库启用 WAL 模式（`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`）
- [ ] LLM 服务 OPENAI_API_KEY / BASE 在 `.env.docker` 正常可访问，QG-3 所用模型有额度
- [ ] Neo4j Aura / 自建实例密码正确，`CREATE INDEX idx_candidate_domain` 可成功执行
- [ ] Python 版本 ≥ 3.11（Dockerfile 已满足），`pip install` 新增 13 个包在 `requirements.txt` 声明成功
- [ ] `/data/models/`、`/data/backups/semantic/`、`/data/he_templates/` 目录存在且可写（非只读挂载）
- [ ] 统一审计 `UnifiedAudit` 类正确配置（无则 logger fallback）

---

## Architecture

### 组件架构图（6 层分层 + 依赖方向）

```
odap/biz/core/semantic/          (SP2 新建唯一模块)
├── api/
│   ├── routes.py                 FastAPI 路由（4 旧 + 30 新端点：/candidates*, /quality-gates*, /approvals*, /hitl*, /dashboard*, /admin/*, /tools/*, /domains/{import-export}）
│   ├── schemas.py                Pydantic Request/Response 模型（≈ 40 个）
│   └── __init__.py
├── services/                     业务编排层（依赖 interfaces / models）
│   ├── semantic_service.py       SemanticService (FR-003 公共 API)
│   ├── candidate_service.py      Candidate CRUD / 批量 / 过滤分页
│   ├── quality_gate_service.py   3 关 QG 执行 + 报告生成
│   ├── approval_service.py       2 级审批流状态机 + OPA 调用
│   ├── hitl_service.py           5 种 correction op → candidate 映射
│   ├── concept_extractor.py      L1→L2→L3→L4→L5→L6 6 层抽取
│   └── dashboard_service.py      质量面板 6 大 KPI 聚合 + 导出
├── impl/                         具体实现（依赖 interfaces 存储）
│   ├── semantic_repository_impl.py
│   ├── candidate_repository_impl.py
│   ├── quality_gate_engine_impl.py (QG-1/QG-2 纯逻辑)
│   ├── llm_qg3_reviewer_impl.py  (调用 LLM client)
│   ├── opa_policy_engine_impl.py (opa-python 封装 + watchdog)
│   ├── concept_cluster_impl.py   (BGE + UMAP + HDBSCAN)
│   ├── fca_lattice_impl.py       (concepts.Context)
│   ├── l4_apriori_miner_impl.py  (mlxtend apriori)
│   ├── odp_vf2_matcher_impl.py   (networkx.is_isomorphic)
│   ├── owl_compiler_impl.py      (rdflib 生成 OWL Turtle)
│   ├── neo4j_candidate_writer_impl.py （Py2neo/Neo4j driver）
│   └── outbox_worker_impl.py     (线程 + 指数退避重试)
├── interfaces/                   抽象接口（Repository / Engine 协议）
│   ├── semantic_repository.py
│   ├── candidate_repository.py
│   ├── quality_gate_engine.py
│   ├── llm_reviewer.py
│   ├── policy_engine.py
│   ├── concept_cluster_engine.py
│   ├── fca_engine.py
│   ├── rule_miner.py
│   ├── pattern_matcher.py
│   ├── owl_compiler.py
│   ├── graph_writer.py
│   └── __init__.py
├── models/                       Pydantic 领域模型（无方法、纯数据）
│   ├── domain.py
│   ├── canonical_term.py
│   ├── synonym.py
│   ├── en_mapping.py
│   ├── expansion_rule.py
│   ├── candidate.py
│   ├── approval.py
│   ├── quality_gate.py
│   ├── hitl_correction.py
│   ├── outbox_event.py
│   ├── l3_property.py
│   ├── l4_rule.py
│   ├── l5_pattern.py
│   ├── l6_axiom.py
│   ├── dashboard_metrics.py
│   ├── audit_log_entry.py
│   └── __init__.py
└── storage/                      持久化访问层（SQLite + Neo4j + 文件）
    ├── sqlite_usl_storage.py     11 张表 CRUD（实现 interfaces 契约）
    ├── neo4j_writer_storage.py   Neo4j ConceptCandidate MERGE + VF2 结构
    ├── opa_file_storage.py       rego 文件 + 基线 hash + watchdog watch
    ├── seed_migrate.py           CLI（check/apply/rollback，三国/西游/共享/电商）
    ├── cleanup_old_code.py       Iter4 老目录/文件删除 + 备份 + import 替换
    ├── backup_manager.py         备份/恢复/30 份轮转
    ├── cache_invalidation_poller.py 多进程 cache 失效轮询
    └── __init__.py
```

### 端到端数据流（Schema Learning HITL 闭环示例）

```
用户 NL 文本 (mode="schema_learning")
       │
       ▼
ExtractionService (SP1 已存在，扩展 mode 参数)
       │ parse(text, multi-template) → entities/relations
       ▼
ConceptExtractor.run_all()
       ├── run_l1: BGE embed 1024D → UMAP → HDBSCAN → 簇 + confidence
       ├── run_l2: 形式上下文 → FCA concepts → is_a 层级
       ├── run_l3: 属性值域推断 ← (默认关闭，config 开启)
       ├── run_l4: Apriori 关联规则 ← (默认关闭)
       ├── run_l5: VF2 ODP 识别 ← (P2 Iter4 独立跑)
       └── run_l6: OWL 编译 ← (P2 Iter4 独立跑)
       │
       ▼
CandidateWriter.dual_write()
  ├── SQLite: INSERT usl_candidates (+子表)  [BEGIN事务1]
  └── Neo4j: MERGE (:ConceptCandidate) + [:IS_A]  [事务2]
       │ 双写 2PC 模拟；任一失败全回滚
       ▼
QualityGateService.run_all(ids)  ← 批量异步任务(asyncio.create_task)
  ├── QG-1: confidence ≥ 0.65 + Jaccard < 0.7
  ├── QG-2: 结构一致性 (LSP + domain/range 存在)
  └── QG-3: LLM 3 次 majority vote
       │ 写入 quality_gate_report_json
       ▼
前端 审批台 UI（未在此 SP 范围内，仅提供 API）
  ├── L1 领域管理员：approve/reject 最多 50 条 → status l1_approved / rejected
  └── L2 全局管理员：merge 最多 100 条 → status merged
       │
       ▼
SemanticService.merge_candidates(ids)  [SQLite SERIALIZABLE 事务]
  ├── 写入 usl_canonical_terms / usl_synonyms / ... / usl_l6（USL 正式表）
  ├── 更新 candidate.status = merged + approver_l2_id + merged_at
  ├── enqueue usl_outbox: event_type=tbox_sync → OntologyService 双写 TBox
  ├── enqueue usl_outbox: event_type=semantic_changed → 广播 USLCache.invalidate()
  └── enqueue usl_outbox: event_type=flywheel_metric（若 source=HITL）
       │
       ▼
Outbox Worker (后台线程每 5s)
  ├── tbox_sync: OntologyService.create_*() / deprecate_*() → 最终一致
  ├── semantic_changed: USLCache.invalidate(domain) → 多进程同步
  └── flywheel_metric: DashboardService.update_flywheel_metric()
       │
       ▼
后续用户 HITL 修正 → submit_corrections → 新 candidate → 重新走 QG + 审批
       └──────────────── 形成飞轮闭环 ──────────────────────┘
```

### 关键接口契约（Python 类型签名，实现必须严格匹配）

```python
# services/semantic_service.py
class SemanticService:
    def __init__(self, repo: SemanticRepository, cache: "USLCache"): ...
    def get_domain(self, name: str) -> Optional[Domain]: ...
    def list_domains(self) -> List[Domain]: ...
    def create_domain(self, name: str, display_name: str, description: str = "", lang: str = "zh") -> Domain: ...
    def get_canonical_terms(self, domain_id: str, term_type: Optional[str] = None, page: int = 1, size: int = 50) -> PageResult[CanonicalTerm]: ...
    def get_term_detail(self, canonical_term_id: str) -> TermDetail: ...
    def add_synonym(self, canonical_term_id: str, text: str, synonym_type: str = "synonym", confidence: float = 1.0) -> Synonym: ...
    def add_expansion_rule(self, domain_id: str, pattern: str, expansion: List[str]) -> ExpansionRule: ...
    def update_term(self, canonical_term_id: str, **fields) -> CanonicalTerm: ...
    def deprecate_term(self, canonical_term_id: str, operator_user_id: str) -> Dict[str, Any]: ...
    def merge_candidates(self, candidate_ids: List[int], operator_user_id: str) -> MergeResult: ...
    def hot_reload(self, domain_id: Optional[str] = None) -> None: ...

# services/quality_gate_service.py
class QualityGateService:
    def __init__(self, qg_engine: QualityGateEngine, llm_reviewer: LLMReviewer, policy: PolicyEngine): ...
    def run_all(self, candidate_ids: List[int], concurrency: int = 4) -> QGBatchResult: ...
    def get_report(self, candidate_id: int) -> Optional[QualityGateReport]: ...

# services/approval_service.py
class ApprovalService:
    def __init__(self, repo: ApprovalRepository, policy: PolicyEngine): ...
    def transition(self, candidate_ids: List[int], action: ApprovalAction, level: int, operator_user_id: str, comment: str = "") -> ApprovalBatchResult: ...
    def list_history(self, candidate_id: Optional[int] = None, approver_id: Optional[str] = None, level: Optional[int] = None, page: int = 1, size: int = 20) -> PageResult[ApprovalLog]: ...

# services/concept_extractor.py
class ConceptExtractor:
    def __init__(self, cluster: ConceptClusterEngine, fca: FCAEngine, miner: RuleMiner, matcher: PatternMatcher, owlc: OWLCompiler): ...
    def run_l1(self, entities: List[Dict], domain_id: str, config: Dict = {}) -> L1Result: ...
    def run_l2(self, l1_result: L1Result, domain_id: str, config: Dict = {}) -> L2Result: ...
    def run_l3(self, instances: List[Dict], domain_id: str) -> List[L3Property]: ...
    def run_l4(self, instances: List[Dict], domain_id: str, config: Dict = {}) -> List[L4Rule]: ...
    def run_l5(self, l2_l3_graph: "nx.DiGraph", domain_id: str) -> List[L5Pattern]: ...
    def run_l6(self, l2: L2Result, l4: List[L4Rule], l5: List[L5Pattern], domain_id: str) -> List[L6Axiom]: ...
    def run_all_l1_l2(self, entities: List[Dict], domain_id: str) -> Tuple[L1Result, L2Result]: ...
```

---

## Error Handling & Degradation

| 场景 | 处理策略 | 降级标记 / 告警 |
|---|---|---|
| SQLite 锁定 (SQLITE_BUSY) | 指数退避重试 3 次（50ms/200ms/800ms）→ 失败返回 503 Retry-After: 2 | degradation=sqlite_busy_retry |
| Neo4j 连接丢失（Session 过期） | driver.verify_connectivity() 探活 + 重连；双写期间失败则 rollback SQLite，candidate 仍 proposed，status += `neo4j_write_failed_manual_retry` 标记 + 告警 | degradation=neo4j_down；webhook 通知 |
| LLM 不可用 / 限流 (QG-3) | retry 2 次（指数退避）→ 仍失败：qg3_status=deferred（quality_gate_report 标记），不阻断整体流程（候选进入审批但 QG-3 状态为待人工），指标 `semantic_llm_call_total{success=false}` +1 | degradation=llm_down_qg3_deferred |
| Embedding 模型文件缺失 | 首次启动自动从 hf-mirror.com 下载（BGE）；下载失败：启动报错 + 明确说明；运行时损坏：删除损坏目录 + 自动重试下载 | 启动时 fail-fast；运行时重启 |
| OPA rego 文件被篡改（hash 不一致） | 启动时 fail-fast（exit 2），错误信息包含 "opa_baseline_hash_mismatch, expected: HASH, actual: HASH"；运行时策略 reload 前 hash check，失败保留旧策略 + 告警 | NFR-011 强制 |
| Outbox 重试超 3 次 | status=failed；告警 webhook + admin dashboard red banner；人工 API `POST /admin/outbox/{id}/retry` 手动触发 | outbox_failed_permanent |
| HITL 提交的 correction 引用不存在 session/entity | 400 + 详细字段错误列表（JSON Pointer），不创建任何 candidate | 无降级 |
| merge_candidates 中间某条违反 FK/UNIQUE | 整批 SERIALIZABLE 事务整体 ROLLBACK，返回 `{"status":"error","failed_at_candidate_id":N,"reason":"...conflict UNIQUE(canonical)"}`，已执行步骤 0 回滚 | 无部分成功 |
| FR-007 seed_migrate apply 时磁盘满 | SQLite rollback + 报明确错误 + 清理临时文件，库恢复至 apply 前状态 | 无脏数据 |
| FR-051 cleanup_old_code 删除前备份失败 | 立即中止（不删任何文件），返回 `backup_failed_abort`，需人工检查磁盘空间 / 权限 | 零风险 |

---

## Testing Strategy

### 单元测试（tests/unit/biz/core/semantic/，必须通过）

| 测试文件 | 覆盖内容 | Mock 策略 | 数量 ≥ |
|---|---|---|---|
| `test_semantic_service_crud.py` | Domain/Term/Synonym/Expansion CRUD + hot_reload + cache 失效 | tmp_path 真实 SQLite，不 mock | 45 条 |
| `test_seed_migrate.py` | check/apply/rollback/幂等/回滚 sanguo/xiyou/shared/ecommerce 四领域 count 校验 | tmp_path 空 DB；真实 seed JSON | 28 条 |
| `test_usl_cache.py` | TTL 失效 / 多进程轮询 / 命中率 / 广播 invalidate | time-machine 冻结时间 | 12 条 |
| `test_concept_l1_cluster.py` | BGE embed（mock embedder 返回固定向量）+ UMAP + HDBSCAN 聚类边界（noise / cluster < min_size / confidence 阈值） | Mock sentence-transformers → 返回 numpy.random | 18 条 |
| `test_fca_l2_lattice.py` | 构造 5 个形式上下文用例（含空/全同概念/概念链/概念格）→ NextClosure 输出期望概念 + 层级 | 纯逻辑，无外部依赖 | 15 条 |
| `test_quality_gate_1_2.py` | QG-1 公式（边界 0.649/0.65）+ QG-2 LSP 冲突覆盖测试 4 例 + Jaccard 计算边界 0.699/0.701 | 纯逻辑 | 30 条 |
| `test_llm_qg3_reviewer.py` | 3 次 majority vote（2 pass / 1 pass / 0 pass 三种情况）+ 超时重试 + 错误降级 | Mock LLM client 返回预定义 JSON，TimeoutError 场景 | 14 条 |
| `test_approval_state_machine.py` | 所有合法/非法转换（含 reopen/merge 101 条越界 OPA deny）+ 审计日志必写 | OPA evaluate mock 返回 allow/deny 组合 | 26 条 |
| `test_candidate_dual_write.py` | SQLite success/Neo4j fail → SQLite 回滚验证；幂等 MERGE；批量 | pytest neo4j 测试容器（若无则 mock driver） | 12 条 |
| `test_outbox_worker.py` | tbox_sync 成功 / 3 次退避 / webhook 告警 / 重启重投递未完成 | OntologyService mock 返回 success + 异常 | 16 条 |
| `test_hitl_service.py` | 5 种 correction op → candidate 映射边界（unknown op / missing canonical / blacklist 重复） | 纯逻辑 | 22 条 |
| `test_l3_l4_l5_l6.py` | 属性值域 5 种类型推断 + Apriori support/confidence/lift 计算 + VF2 同构 + OWL Turtle 语法合法 | rdflib parse 验证语法 | 25 条 |
| `test_dashboard_metrics.py` | 构造 30 天历史数据 → 6 大 KPI SQL 值与手算一致（Jaccard 误差 < 1e-6） | tmp_path 预置历史 SQL 数据 | 18 条 |
| `test_cleanup_old_code.py` | dry-run 报告 + apply 备份验证 + import 替换 sed 正确性 | 临时目录构造假 semantic_config.py / old semantic_layer | 9 条 |
| `test_nfr_perf_baseline.py` | 基准 5000 术语场景下所有 P95 延迟断言（mock 计时） | 纯逻辑时间模拟 | 7 条 |
| 其他 (opa/backup/versioning/tools) | FR-053~FR-060 覆盖 | - | ≈ 30 条 |
| **合计** | - | - | **≥ 307 条** |

### 集成测试（tests/integration/semantic/，@pytest.mark.integration，需 Neo4j）

| 测试 | 场景 | 前置 |
|---|---|---|
| `test_end_to_end_schema_learning.py` | NL schema_learning → L1/L2 → candidate 双写 → QG 三关 → L1 approve → L2 merge → USL 表 + TBox 双写 全链路 | 需 Neo4j + OPENAI_API_KEY |
| `test_hitl_flywheel_iteration.py` | 3 轮 HITL 修正 → merge → 下一轮抽取 accuracy 提升趋势 ≥ 3% 每轮 | 同上 |
| `test_neo4j_consistency_daily.py` | 模拟 1000 candidate 双写 → 随机 kill Neo4j 3 次 → 一致性巡检 diff < 0.01% | Neo4j 测试容器 + chaos |
| `test_seed_import_export_ecommerce.py` | ecommerce seed apply → export OWL → import 回新 domain → 结构等价（node/edge count 相等） | tmp_path 真实 DB |
| `test_opa_policy_reload.py` | 后台修改 rego 文件（qg1_conf 0.65→0.9）→ watchdog 触发 reload → 下一次 QG 立即使用新阈值 | watchdog real fs event |
| **合计** | - | - | **≥ 5 条 E2E** |

---

## Migration Path

### 4 迭代部署顺序（可回滚，每步零停机）

| 步骤 | 操作 | 回滚方式 | 风险级别 |
|---|---|---|---|
| I1.1 | 新增 `biz/core/semantic/` 模块 + 11 张表 SQL schema（`CREATE TABLE IF NOT EXISTS`，纯新增列） | 删除新表（不影响老流程） | 低 |
| I1.2 | 部署 seed_migrate `--mode check` → 人工核对报告 → `--mode apply` 三国/西游/共享 | `seed_migrate --rollback --domain all` | 中（UNIQUE 冲突需排查） |
| I1.3 | 修改 API route 指向 semantic 新 handler（原 handler 保留 alias） | 路由回滚 + 恢复老 import | 低 |
| I1.4 | 跑 Iter1 单测 + 集成 + 回归（原 endpoint 契约不变） | 代码 revert 到 I1.1 | 低 |
| I2.1 | 安装 sentence-transformers / hdbscan / concepts / mlxtend 新依赖 | 回滚 requirements.txt + 重建镜像 | 中 |
| I2.2 | 部署 ConceptExtractor + CandidateWriter + mode=schema_learning 扩展 | feature flag `semantic.enable_schema_learning=false` 关闭 | 低 |
| I2.3 | 人工用三国原文 5000 字走 schema_learning，核验 L1/L2 概念质量 | 清 candidate 表即可 | 低 |
| I3.1 | 部署 OPA 策略目录 + 策略基线 hash | 回退旧 approval_service（无 OPA 分支 revert） | 高（策略错误=审批全 Deny） |
| I3.2 | 跑 QG + 审批流 E2E 测试（独立环境 + 真实 LLM） | feature flag `semantic.enable_quality_gate=false` 临时降级 | 中 |
| I3.3 | 灰度 L1 领域管理员（先 1 个 sanguo 域）→ 观察 3 天 → 全局铺开 | 手动 rollback candidate 到 proposed（SQL UPDATE + 工具脚本） | 中 |
| I4.1 | 跑 L3/L4/L5/L6 离线批处理（先三国域，不自动 merge，全人工 review） | 清 l3/l4/l5/l6 表即可 | 低 |
| I4.2 | 部署电商 seed migrate apply → 验证 count | rollback 电商域 | 低 |
| I4.3 | 部署 dashboard 指标 API → 监控验证非空 | 关 dashboard endpoint | 低 |
| I4.4 | cleanup_old_code --dry-run 审核 → 备份 + --apply 删老目录 + import 替换 | 恢复备份 tar.gz（一键脚本 restore_backup.py） | 中（import 路径断裂风险） |
| I4.5 | 全量测试 + 验收 | 回滚到 I4.3 状态 | 低 |

### 破坏性变更管理（唯一一次 I4.4 删除）

- `semantic_config.py`：从 I1.2 开始 import 触发 DeprecationWarning → I3 结束已 2 迭代 → I4.4 删除
- 老路径 `design/schema/semantic_layer/*`：I1.3 起 alias 保留 → I2 结束 1 迭代 → I4.4 时已超 2 迭代 → 删除
- 所有旧 import 路径：I1.3 时代码替换 + CI grep 检查，0 命中才允许 I4.4 删除

---

## Success Criteria *(mandatory)*

### 量化验收标准（逐项必过，不接受 "近似通过"）

- **SC-001 (Iter1)**: seed migrate --apply 四领域后，usl_canonical_terms 行数 ≥ 三国(7+11+6+20=44) + 西游(6+9+6+9=30) + 共享(5+4=9) + 电商(≥8+≥7+≥25=40) → 总计 ≥ 123；四领域 count 与 seed JSON 中 count 100% 相等（缺 1 行 = 失败）
- **SC-002 (Iter1)**: 进程重启同义词不丢失测试：POST /synonyms 新增 50 条 → 重启 pod → GET /synonyms 返回包含全部 50 条，且 created_at 时间戳与重启前完全相等（非重建）
- **SC-003 (Iter1)**: `pytest tests/unit/biz/core/semantic -v --cov` 行覆盖率 ≥ 95%（Iter1 子域 A+B 部分）
- **SC-004 (Iter2)**: 三国原文 5000 字 schema_learning → usl_candidates 中 L1 candidate ≥ 5 个，L2 ≥ 3 个，object_type ≥ 5，confidence ≥ 0.70 比例 ≥ 60%
- **SC-005 (Iter2)**: 双写一致性：SQLite usl_candidates count 与 Neo4j `MATCH (n:ConceptCandidate) RETURN count(n)` 100% 相等（diff = 0，允许 ±0% 容差）
- **SC-006 (Iter3)**: 10 条 mixed 候选独立测试：QG 淘汰 8 条（3 low conf + 3 dup + 2 struct conflict）→ QG-3 对剩余 2 条 3 次投票均 pass → L1 approve → L2 merge → usl_canonical_terms 精确新增 2 条（审计日志链完整，缺一步 = 失败）
- **SC-007 (Iter3)**: OPA 策略变更：修改 rego qg1_conf 0.65→0.9 → 下一次 QG 10 条候选中 9 条 confidence ∈ [0.65, 0.9) 的原本通过 0.65 现在全 fail，行为与新阈值严格一致（热加载无重启，≤ 10s 内生效）
- **SC-008 (Iter4)**: HITL 飞轮测试：3 轮修正 merge 后，`flywheel_accuracy[3] - flywheel_accuracy[0] ≥ 0.05`（5 pp 提升）且单调不减
- **SC-009 (Iter4)**: L3-L4：电商订单 1000 条实例 → L3 推断出 price 为 type=number, min ≥ 0，枚举 category 枚举值 count ≥ 5；L4 挖掘出 {手机→壳} 类规则 support≥0.05, lift>1.0 至少 3 条
- **SC-010 (Iter4)**: 老目录清理后：`os.path.exists("design/schema/semantic_layer/") == False`；`python -c "from odap.biz.core.ontology.design.schema.semantic_config import SANGUO_SEMANTIC"` 触发 ImportError（已删）；全量 pytest 测试用例 100% 通过（0 失败）
- **SC-011 (All Iter)**: 全流程端到端测试：`pytest tests/integration/semantic/test_end_to_end_schema_learning.py -v` 通过（需 Neo4j + LLM Key，CI 环境可选 skip 标记，生产环境必跑）
- **SC-012 (NFR)**: NFR-001~NFR-004 延迟指标在生产环境压测报告中 P95 全部达标（压测工具 Locust，脚本 50 vu 持续 10 分钟，每 1 分钟 sample 一次，n≥10）

---

## Assumptions

1. BGE 模型可从 hf-mirror.com 自动下载成功；如失败（企业网络限制），需手动拷贝到 data/models，本 SP 不做离线 wheel 分发
2. Neo4j 版本 ≥ 5.13（支持 `CREATE INDEX ... IF NOT EXISTS` 语法），4.x 不兼容需升级
3. LLM QG-3 使用模型 gpt-4o-mini 有足够额度（每 1000 candidate ≈ $0.2 费用）；若额度耗尽，业务允许人工审核跳过 QG-3（L2 管理员 special override OPA 策略配置允许）
4. SP1 (006) ExtractService mode 参数扩展不会破坏现有调用方签名（Python 默认参数值保证向后兼容）
5. `UnifiedAudit.log_action` 写入不会阻塞主流程（异步队列 + 丢 data 容忍，NFR-009 要求）
6. 术语名纯中文 / 英文混合无 emoji / RTL 文字（不考虑阿拉伯语、emoji 嵌入的分词正确性）
7. 质量面板前端由独立前端 SP 完成，本 SP 仅提供 REST API + 字段契约；前端延迟/渲染 NFR 不在 SP2 范围
8. OPA 策略文件仅 L2 管理员通过 API 提交变更，不接受直接在服务器上编辑（否则 baseline hash 校验失败，NFR-011）
9. 所有数据库 SQLite 路径、Neo4j 连接、.env 配置与现有 ODAP 架构保持一致，不需要多 DB / 多 Neo4j 实例
10. 审计日志保留期 180 天（业务需求），过期自动清理（后台 cron），不纳入本 SP 功能

---

## Edge Cases

### 边界条件

- **EC-001**: L1 聚类实体数 N=0 或 1（不满足 min_cluster_size=3）→ run_l1 返回空 clusters，L2 也空，写日志 "too few entities for L1 clustering"，不报错
- **EC-002**: QG-1 Jaccard 分词后为空（全是停用词，如"的/了/是"）→ max_jaccard = 0.0，通过 Jaccard 判定；但 candidate.label 空字符直接 fail
- **EC-003**: OPA evaluate 超时（≥ 5s）→ 默认 deny（fail-close 原则），返回 403 "policy_engine_timeout"，绝不静默 allow
- **EC-004**: HITL merge_entities 合并跨 domain 的实体 → 直接拒绝 400 "cannot merge across domains"
- **EC-005**: 质量面板 30 天内无数据（冷启动）→ 返回空 trend 数组 + `cold_start_warning=true`，前端展示占位 "暂无数据"

### 错误场景

- **EC-006**: Apriori 挖掘事务数 < 10（不满足统计意义）→ run_l4 立即返回空 + warn，不浪费算力
- **EC-007**: FCA 概念数爆炸（> 10,000 个概念，典型无属性离散上下文）→ 自动截断 + confidence 加权取前 500 个 concept，写入 `l2_fca_report.truncated=true, truncated_count=...`
- **EC-008**: Candidate dual_write 时 Neo4j 写入成功但 commit 消息丢失 → 巡检脚本 daily consistency check 自动修复（SQLite 数据为权威源，Neo4j 重建）
- **EC-009**: Import OWL 文件语法错误（rdflib parse 失败）→ 返回 400 `parse_error`，附第 N 行字符位置 + 片段，不写入任何 DB 行
- **EC-010**: OPA rego 语法错误（运行时引入）→ watchdog reload 失败 → 自动回滚到上次已知 good 版本 + webhook 告警，服务不中断

### 规模与性能

- **EC-011**: 单批 merge 100 条，每条需调用 OntologyService 3 次（outbox）→ outbox worker 异步串行消费，不阻塞同步 API 返回；预期 30 秒内消费完毕，超过 NFR-013 阈值告警
- **EC-012**: 1000 并发读 synonyms（cache miss 风暴）→ USLCache singleflight：同 domain 并发 miss 只打 1 次 DB，其他协程等待结果（缓存击穿防护）
- **EC-013**: L1 embedding 批处理 10 万实体 → 自动分块 1024 条/块 + tqdm 进度条（日志），总耗时上限 30 分钟，超时 kill 进程 + 告警

### 一致性与并发

- **EC-014**: 两 L2 管理员同时 merge 同一 candidate（并发）→ SQLite SERIALIZABLE 后到事务 SQLITE_BUSY → 按 FR 错误处理重试 3 次，仍冲突返回 409 Conflict + "candidate already merged by {user_id}"
- **EC-015**: canonical_term 已被 merge 后再收到同 label 的新 candidate → QG-1 Jaccard=1.0 > 0.7 → fail + reason "duplicate of canonical_term_id=X"，管理员可手动关联（de-dup suggestion）

### 降级场景

- **EC-016**: embedding 模型不可用（L2 schema_learning）→ feature flag 自动 fallback 到 "Jaccard 词汇相似度 + 层次聚类 ward"（精度下降但流程不中断），标记 degradation=l1_fallback_jaccard_ward；L3-L6 各自可独立关闭降级
- **EC-017**: Neo4j 完全不可用 > 1 小时 → Candidate Writer 降级为 "仅写 SQLite"，写入 outbox event_type=neo4j_deferred_replay；恢复后巡检 replay 重放所有待写 Neo4j 的 candidate，最终与 SQLite 对齐
- **EC-018**: LLM QG-3 全不可用 > 4 小时 → OPA 特殊策略 `qg3_emergency_bypass.rego` 激活（默认 disable，需 L2 管理员显式 POST /admin/qg/bypass 启用）：QG-3 直接通过但 risk_level 自动标 high，所有审批强制人工走；事后恢复时所有 bypass 过的 candidate 必须重新补做 QG-3 并重新审批（二次审计）

---

## Brainstorm Log

### 2026-07-11 Session: SP2 架构 + 4 迭代拆解

**参与者**: User + AI

**关键决策清单（影响 FR/NFR）**:

| # | 决策 | 方案 | 理由 |
|---|------|------|------|
| 1 | 模块归属 | biz/core/semantic 独立模块（6 层），不依附 design/schema | 语义层是跨域核心概念，不应作为 ontology design 的子目录；6 层可测性好 |
| 2 | L1 聚类选型 | BGE + UMAP + HDBSCAN（RQ-1 最终选型）见 research.md | HDBSCAN 免调 k，抗噪声；BGE 在中文领域 SOTA |
| 3 | L2 层级推断 | FCA 形式概念分析（RQ-2 最终选型） | 数学严谨，可解释性远好于 LLM few-shot 黑盒 |
| 4 | 质量闸数量 | 3 关 QG（置信度去重/结构/语义LLM）| 2 关太松（容易进噪音），4 关冗余；3 关经典自动化测试金字塔原则 |
| 5 | 审批级数 | L1 + L2 两级（非三级） | 三级会把延迟拉到不可接受；两级 + OPA 批限制在大多数组织够用 |
| 6 | 策略引擎 | OPA rego 进程内 opa-python（非 sidecar）见 research.md RQ-8 引申 | sidecar 运维复杂度陡增；10k QPS 以内进程内执行 CPU 占 < 5% |
| 7 | Candidate 双写 | SQLite 权威 + Neo4j 可视化 + 2PC 模拟（非真正 XA） | Neo4j 不支持 XA，只能模拟 + 巡检修复；最终一致 SLA 可接受 |
| 8 | TBox 同步方式 | Outbox 最终一致（非双写事务） | OntologyService 调用不可靠（外部 API），Outbox + 重试是业界标准 |
| 9 | 老目录清理时机 | Iter4 最后（非 Iter1 激进） | 给迁移留 2-3 迭代缓冲，避免 import 断裂导致事故；备份 + dry-run 保障 |
| 10 | L3-L6 与 L1-L2 关系 | 解耦为独立方法，schema_learning 模式仅 L1-L2，L3-L6 独立批处理 | L3-L6 算力大、场景特定，默认关闭避免过度消耗 |

**约束重申**: 严禁 TODO / 假实现 / 空承诺；所有算法公式接口必须给出可直接落地的定义（已在 FR 中逐条细化到公式/字段/API 签名）。

---
