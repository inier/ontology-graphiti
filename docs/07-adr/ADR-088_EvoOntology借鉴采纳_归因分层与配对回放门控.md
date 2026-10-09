# ADR-088: EvoOntology 借鉴采纳——归因分层与配对回放门控（attribution + paired replay）

## Status
**已接受（2026-10-09）。落地情况（诚实注记，规则 12/14）：spec [docs/superpowers/specs/2026-10-08-evoontology-adoption-design.md](../superpowers/specs/2026-10-08-evoontology-adoption-design.md) 定稿后，子项目 A/B 已于 2026-10-09 以 TDD 实现完毕——7 个新测试文件（attribution_storage / attribution_emitter / regression_builder / paired_replay / regression_routes / regression_loop_acceptance 含 writeback 侧道）全绿，既有 test_gap_* 6 文件（38 用例）零回归，semantic_admin 全量 310 用例绿；代码 staged 待用户 git commit，dev 容器手验（E-k）待办。本 ADR 记录三项关键决策（D3 门控归人 / D6 信号收集器及线程安全权衡 / D8 cost 记录）。**

> 触发来源：对照外部参照 **EvoOntology**（RUC，arXiv 2609.15779，`ruc-datalab/EvoOntology`，MIT）审视 ADR-086 已落地的概念缺口回路，暴露两个结构性缺口——回路**能"闭"但不能"验证"**：① `source_counts` 只回答"哪条链路失败"，不回答"哪个本体元素缺失"（无归因维度，promote 产出的 candidate `semantic_type` 写死"对象类型"）；② "改完之后系统是否真的变好"无任何度量（resolve-check 是单点静态判定，stats 只有人工 adoption_rate）。
> 借鉴边界：借 EvoOntology 两个机制——**attribution-guided typed edits**（归因到 schema/content/tool 三层具体元素再生成针对性修改）与 **backbone-conditional paired evaluation**（同 backbone 下 held-out 配对评估门控）。**明确不采纳其 auto-accept（自动接受）**——EvoOntology 的本体只装数据语义，改错顶多 SQL 写偏；ODAP 本体挂着 OPA 权限、审计关键路径、分支合并与版本不可变，自动写回爆炸半径完全不同。不引入其任何依赖/栈。
> 关联：ADR-086（概念缺口回路，本 ADR 是其增量演进）、ADR-087 预留（语义漂移检测，"报告即不可变证据"纪律被本 ADR 借用）、spec 008 语义检索 / FR-010、FR-026；AGENTS.md 规则 2/6/8/9/12/14。

---

## Context

### 现状（证据见 spec §1 + §3 代码勘验）

- gap_pool 回路已在跑：`intent_recognizer.py:163-167` 已调 `report_gap_signal(MAPPING_FAILURE, ...)`，promote/dismiss/resolve_check/stats 全在。
- `ConceptGap` 无归因字段；`promote()` 把裸 expression 丢给 `create_candidate_from_gap()`（`candidate_service.py:675`），缺口与变更之间的映射靠人脑补全。
- `resolve_check()`：term 类现场查一次 `canonical_of(emit=False)`；非 term 类如实返回 `resolvable=False`（"不假装能判定"）。BeModel 验收标准"同一个问题下次能答上"只在 promote 单点被检验，从未在问答主路径被检验。
- 仓库**无 agent trajectory/trace store**（仅 `agent_factory.py` 提及）——EvoOntology 那种"从执行轨迹归因"在本项目无素材，归因只能来自信号点自身携带的上下文。
- 评估基础设施现成：`biz/data/qa/evaluation/benchmark.py`（BenchmarkRunner/BenchmarkDataset/EvaluationReport），但其 EM/F1 依赖 reference_answer，缺口场景大多为空，硬套会全零失真。

---

## Decisions

### D1. attribution 双层数据形态：镜像既有 source 双层模式，不引入新模式

`ConceptGap` 增加 gap 级 `attribution_counts: Dict[str, int]`（`{layer: count}` 全量计数），occurrence dict（`sources_json` 内）增加 `attribution` 键（`{"layer", "target_kind", "target_ref"}`，逐条，随 50 条截断）——完全镜像既有 `source_counts_json` / `sources_json` 双层结构。存储加列 `attribution_counts_json TEXT NOT NULL DEFAULT '{}'`；旧库经 `PRAGMA table_info` 探测后 `ALTER TABLE ADD COLUMN` 幂等迁移，旧数据 NULL → 读侧 `_safe_json` 回退 `{}`（既有容错覆盖）。`list_gaps` 加 `layer` 过滤（`json_extract` 同 source 过滤模式）。

### D2. GapLayer 三层枚举 + 最佳努力归因（不造数）

`GapLayer(str, Enum)`：`schema`（TBox 结构）/ `content`（USL 术语·映射）/ `tool`（检索引擎·模板·路由）——对齐 EvoOntology 三层，也是后续类型化编辑提案（spec §4.3 子项目 D）路由 promote 的判据。归因**最佳努力**：信号点上下文不足以判定 layer 时省略（None），绝不造数（规则 14）；归因缺失只影响统计粒度，不影响回路。归因来源 = 信号点自身携带上下文（emitter 参数），**不做**事后轨迹分析（无 trace store 素材）。`chain_engine.py:130` degraded 属基础设施降级，维持 ADR-086 纪律**不接入**。emitter 签名 `report_gap_signal(..., attribution: Optional[Dict] = None)` 默认 None，四类既有接线点零改动也兼容。

### D3. 配对回放门控：**门控归人不归模型**（本 ADR 核心决策）

EvoOntology 的门控是"配对评估通过 → 自动接受"。本 ADR **只借配对评估，不借自动接受**：

- 缺口的 occurrence（query 原文 + scope）固化为**不可变回归集**（缺口天然就是"曾经答不上的问题集"——现成 held-out 验证集，不另造数据；固化后不随 gap 后续变化更新，对齐 ADR-087 预留的"报告即不可变证据"纪律）。
- `PairedReplayRunner` 在**冻结的模型配置**下对回归集回放两轮（变更前/变更后），per-case 判定 answered，产出 `fixed / regressed / unchanged` 计数与 `verdict`。
- **paired 报告只作为证据呈现给人**（挂审批/详情界面："这个变更修复了 N 例、回归了 M 例"），**不做自动接受或驳回**——"采不采永远人决定"（ADR-086 基线）是硬边界。

**D3 附注（实现期澄清，2026-10-09）**：勘验确认 `QueryResponse` 不带 fallback 标记，answered 判定采用信号收集器模式。生产语义定为 **before = 捕获证据**（before_answered=False 由"缺口即当时未答"的集合语义给出，不重放历史、不造时间机器）+ **after = 现场回放**；真·双轮现场配对（regressed 可达）经 `before_executor` / `after_executor` 注入支持。理由：现场连跑两轮是"当前 vs 当前"，恒 fixed=0，无法回答"补上了之后是否真的能答上"。

`verdict = pass` 当且仅当 **回归数 = 0 且 修复数 ≥ 1**（修复是目的，回归是红线，两条件独立可测）。EM/F1 等检索质量指标**明确排除**在 replay 报告外：`BenchmarkCase.reference_answer` 对缺口场景大多为空，硬套会全零失真（记入 spec 非目标，防后续实现"顺手"用上）。

### D4. answered 判定复用既有信号定义，不新造判定标准

per-case `answered` 由 QA/NL 未答信号是否触发来判定——复用 ADR-086 已锁定的 `qa_unanswered` / `nl_query_unanswered` 语义（"答不上"），不脆弱匹配兜底文案，不新造判定标准。

### D5. 回放读侧纪律：绝不写 concept_gaps（M1 只读守卫延伸）

回放期间 heat 不变、REJECTED 不复活——对齐 `usl_term_resolver.py:105-110` `canonical_of(emit=False)` 的读侧绝不写纪律（ADR-086 终审 M1）。否则回放自我污染缺口统计。回归测试以 SQL 断言 heat 不变。

### D6. 信号收集器模式及其线程安全权衡（如实登记）

实现 answered 判定的机制：回放期间以**模块级补丁**把 `gap_emitter.report_gap_signal` 替换为内存收集器（记录 QA/NL 未答信号即 unanswered），两轮结束恢复原函数并**丢弃**收集结果（绝不落库，配合 D5）。

**线程安全权衡（如实登记）**：模块级补丁在并发请求下会把**同进程内其他真实用户请求**的缺口信号也收进收集器（并短暂抑制真实落库）。缓解：① 回放按 case 顺序同步执行，补丁窗口内逐 case 走完 pipeline 即收；② 本期回放为管理端手动触发（集规模 ≤50），非高频路径；③ 实现时**先勘验** pipeline response 是否自带 fallback 标记，有则优先用标记（免补丁、免线程安全顾虑）；④ 若勘验确认无标记且并发风险不可接受，替代方案是给 emitter 加进程内 collector 协议——记为后备，不预先实现（YAGNI）。

### D7. 组件归属与 API 面：gap_pool/regression/ 子包，不新建顶级模块

回归集是缺口回路的验证臂，生命周期与 gap_pool 同域，落 `gap_pool/regression/` 子包（builder/storage/runner/service），SQLite 独立库 `gap_regression.db`（规则 8：每次 connect/close、JSON TEXT、ISO 时间），两表 `gap_regression_sets` / `gap_replay_reports` 均**不可变**。API prefix `/api/semantic-admin/gap-regression`（6 端点：build/list/get set/replay/list reports/get report，全 get_current_user）。`resolve_check` **保持 fast 语义不动**，paired 走独立端点——fast 是便宜只读判定，paired 是贵重操作（跑两轮 pipeline），混端点会诱导前端把贵操作当便宜操作误调。`verdict=error` 时 `error_detail` 必填具体原因（规则 14：不写"回放失败"笼统话）。

### D8. 模型指纹 + cost 记录（补 EvoOntology 论文自认之缺）

- **backbone-conditional 落地形态**：报告强制记录 `model_id` + `prompt_version`；模型/prompt 变更后旧报告标记失效、须重跑——本体价值是 model-dependent 的，本项目经 LM Studio 跑本地 GGUF，换模型是常态，无指纹的报告不可复现。
- **cost 记录**：报告记录两轮耗时（+可得时的 token 数）。EvoOntology 论文自认未做 cost accounting（省下的 token 未与 round-trip/prefix-cache 代价对账），本项目补上——回放成本未实测前，writeback 侧道自动回放开关 `GAP_REGRESSION_AUTO_REPLAY` **默认 off**；侧道接线照 `writeback_service.py:116` 的 `on_candidate_resolved` 范式，异常只 logger.warning，绝不传播 writeback 主路径。

### D9. promote 归因透传（小增强，不触碰审批链）

`GapService.promote()` 把 gap 的 content 层 attribution 的 `target_kind` 透传给 `create_candidate_from_gap` 的 `semantic_type`（payload 已支持，`candidate_service.py:678-679`）；无 attribution 时维持"对象类型"默认，行为不变。质量闸/两级审批/writeback 全部零改动。

---

## 验收口径（Acceptance）

| 编号 | 场景 | 期望 | 状态 |
|------|------|------|------|
| E-a | 旧库（无 attribution 列）启动 | 自动 ALTER 加列、幂等；既有 gap 数据完好；stats 正常 | ✅ test_gap_attribution_storage |
| E-b | emitter 带/不带 attribution 调用 | 带 attribution 时 occurrence 落 attribution 键、gap 级计数累加；不带时（旧签名路径）行为不变 | ✅ test_gap_attribution_emitter |
| E-c | stats `by_layer` | 全部来自真实记录，无推断 | ✅ 同上 |
| E-d | 回归集固化不可变 | 同参数二次 build 生成**新**集不覆盖旧的；scope 隔离；min_heat 过滤 | ✅ test_regression_builder |
| E-e | 配对回放判定 | before unanswered / after answered → fixed；verdict=pass ⇔ regressed=0 ∧ fixed≥1；真实 collector 函数体 | ✅ test_paired_replay |
| E-f | 回放期间 concept_gaps 零写入 | heat 不变、REJECTED 不复活（SQL 断言） | ✅ test_paired_replay |
| E-g | 收集器异常 | verdict=error 且 error_detail 非空具体 | ✅ test_paired_replay |
| E-h | 6 端点 HTTP 行为 | 状态码映射、`except HTTPException: raise` 透传、鉴权 Depends override | ✅ test_regression_routes |
| E-i | 回路验收升级 | signal(带 attribution)→gap→build set→promote→approve→writeback→replay→verdict=pass ∧ fixed≥1 | ✅ test_regression_loop_acceptance |
| E-j | 既有 test_gap_*.py 6 文件 | 零回归（回归红线） | ✅ 38 用例全绿 |
| E-k | dev 容器手验全链路（spec §7 第 2 项） | 制造 MAPPING_FAILURE → list 页可见 attribution → build → promote → 审批 → writeback → replay verdict=pass | ⏳ 待用户手验 |

---

## Alternatives Considered

1. **采纳 EvoOntology auto-accept（配对评估通过即自动写回）**：被否。OPA 权限 / 审计关键路径 / 分支合并与版本不可定的爆炸半径与 EvoOntology（改错顶多 SQL 写偏）不可比；"采不采永远人决定"（ADR-086）是项目基线。paired 报告降格为人工裁决证据。
2. **用 EM/F1/faithfulness 等 benchmark 指标做 replay 判定**：被否。缺口场景 reference_answer 大多为空，指标全零失真；改用 answered 差分（D3/D4），复用既有信号定义。
3. **事后轨迹归因（从 agent 执行 trace 分析 layer）**：被否。仓库无 trajectory/trace store，无素材；归因只能来自信号点自身上下文（D2），设计为 emitter 参数而非事后分析。
4. **paired 挂进 resolve_check 同一端点（加 mode 参数）**：被否。fast 是便宜只读判定、paired 是贵重操作，混端点诱导前端误调；独立端点（D7）。
5. **writeback 侧道自动回放默认 on**：被否。回放成本未实测（EvoOntology 自己也没做 cost accounting），先默认 off 观测手动回放的 cost_json，再决定是否默认开。
6. **新建顶级 regression 模块**：被否。回归集是缺口回路的验证臂，与 gap_pool 同域生命周期，落子包（D7）。
7. **为 answered 判定新造文案匹配器（匹配"未找到相关信息"等兜底话术）**：被否。脆弱；复用 QA/NL 未答信号定义（D4），且实现前先勘验 pipeline response 是否自带 fallback 标记（有则免补丁）。

---

## Consequences

**正面**：缺口回路从"能闭"升级为"能验证"——BeModel"同一个问题下次能答上"从 promote 单点判定升级为问答主路径上的回放判定（E-i）；归因维度使后续类型化编辑提案（子项目 D）有判据可路由；回归集零新造数据（缺口即现成 held-out 集）；模型指纹使报告在 LM Studio 换模型常态下保持可复现性；cost_json 补上 EvoOntology 论文自认空白，为侧道自动化提供决策数据。

**负面/风险（如实登记）**：
- **信号收集器的进程级补丁窗口**（D6）：并发下其他真实请求的信号被短暂收集并抑制落库。缓解与替代方案见 D6；若实测并发风险不可接受，后备方案（emitter 内置 collector 协议）待启。
- **归因最佳努力 = by_layer 统计有空洞**：上下文不足的信号 attribution 为 None，by_layer 之和可能小于 total——这是诚实的取舍（不造数），不是 bug；运维解读时需知晓。
- **回归集不可变 = 集会陈旧**：固化后不随 gap 变化更新，需手动重建新集；不合并入定时巡检（非目标）。
- **`qa_unanswered` 信号发射点（qa_engine fallback 分支）在补丁窗口内被抑制落库**：真实用户请求恰逢回放窗口时该次 heat 不计——登记取舍，频率与回放触发（手动、管理端）正相关，预期极低。
- **replay 同步执行**：集规模 ≤50 时可控，超规模集的异步化未做（非目标）。

---

## 可逆性
**高**。attribution 是 gap_pool 加列 + emitter 可选参数，不填即回退（旧数据 NULL → `{}`）；regression 子包独立 SQLite 库、独立 prefix，删除即回退且不触碰 concept_gaps / candidate / writeback 任何既有表；writeback 侧道默认 off 且异常不传播；promote 透传在无 attribution 时行为不变。子项目 C/D 本期不实现（spec §4.3 仅立项框）。
