# Spec — 决策主线贯通 v1.0

> 生成日期：2026-10-24
> 基于：`prd.md`（699 行 / EARS 37 条）+ `architecture.md`（13 章）+ `api-spec.yaml`（6 端点 / 18 schema）+ `uiux.md`（1060 行）
> 状态：**已锁定**（项目总监裁定，2026-10-24）
> 编号：ADR-091（仓库现有最大 ADR-090；ADR-087 为语义漂移检测预留号，不复用）

---

## 1. 产品定义

- **一句话**：让同一个 `decision_id` 在四个入口都是同一份数据，并让"人拍板"这件事第一次有地方可写。
- **目标用户**：业务决策者（拍板）、本体工程师（修数据）、审计/合规/分析师（只读复盘）。
- **核心问题**：决策能力已建好，但决策不是产品主线——四条链各自为政，`decision_id` 可能一处有一处无，"采纳了却忘了执行"不在任何人的待办里。

---

## 2. MVP 范围（锁定 —— 不在此表的功能一律不做）

### 批次 A「看得见」（先交付，验收点是"决策不再消失"）

| 编号 | 功能 | 验收摘要 |
|---|---|---|
| A1 | 决策台账 `GET /api/decisions`（分页/筛选/排序/导出） | 10 列、6 筛选器、keyset 分页 |
| A2 | 决策详情页（复用 `GET /{id}/chain`，零改动） | 因果链 + 影响 + 先例 + 推理路径 |
| A3 | 来源入口标注 `entry_source`（7 值） | 台账可见来源，`legacy` 置灰不猜测 |
| A4 | 数据源统一 + 跨空间暴露收口（E26） | Agent Tab 换台账数据源；三接口隔离生效；中间态 Tab 隐藏 |
| T1 | `POST /api/auth/switch-workspace`（**P0 前置**） | 真实登录下 `ws_id` 不再为空 |

### 批次 B「能操作」（验收点是"端到端可演示"）

| 编号 | 功能 | 验收摘要 |
|---|---|---|
| B1 | 仅记录为待决策（`POST /api/decisions` 落库即 `pending`） | 队列有数据来源 |
| B2 | 待决策队列 `GET /api/decisions/pending` | 待办域三态 + 双分组 + 双计数 |
| B3 | 裁决 `POST /{id}/resolve`（accept/reject + 理由） | 写入 `resolution`，409 冲突不覆盖 |
| B4 | 先例留痕（`precedent_decision_ids` 已有能力） | 采纳即建 `PRECEDENT_FOR` 边 |
| B5 | 执行 `POST /{id}/execute`（`decided` 发起、幂等） | 重复发起不产生第二条记录 |
| B6 | 批量裁决（≤50） | 逐条结果、3 类失败码（**CSV 导出已降 P1**） |
| T11 | 演示数据 seed | 幂等、`ENV=production` 硬拒绝、独立 demo 空间 |

### P1（本期不做，但接口/字段需预留不冲突）

台账统计卡 · 状态步骤条 · SLA 阈值可配 · 证据不完整筛选 · 全文索引切换 · `action_records.workspace_id` 列 · **CSV 导出（T8，1.0 人日）** · **`evidence_count` 排序 + M3 回填（0.3 人日）** · **`reasoning-steps` 端点承接（后续批次）**

---

## 3. 明确不做（Out-of-Scope — 锁定）

| 不做的 | 原因 | 何时考虑 |
|---|---|---|
| 裁决时改选备选 | 连锁触发置信度重算 + 证据链失效规则未定；字段能力存在而决策不做时，前端必会误做 | P1 且须先修订 PRD §7 |
| 协作讨论 / 转人工补充信息 | 由"证据不完整标记 + 查看详情先看证据"路径覆盖 | 有多人协作裁决真实需求后 |
| 四条链物理合并代码 | 写入口已收敛，缺的是读侧，物理合并 ROI 为负 | 不做 |
| 决策效果 A/B 实验 | 需流量分桶与统计功效设计 | 有量级后 |
| 移动端适配 | `AdminLayout` 硬写 `minWidth:1200`，是全站议题 | 全站响应式改造时 |
| Agent 决策 Tab 维护态页面 | 过渡窗口不到一个迭代 | 不做 |

---

## 4. 技术架构（版本锚定）

| 层 | 技术 | 版本 | 说明 |
|---|---|---|---|
| 后端 | Python + FastAPI | 3.12 / 仓库锁定 | — |
| 模型 | Pydantic | v2 | `model_validator` 用于状态矩阵 |
| 图库 | Neo4j + graphiti-core | 0.29.2 | 异步单例驱动，不复用同步 driver |
| 前端 | React + TypeScript | 19 | — |
| UI | Ant Design | 6.3.5 | — |
| 图标 | `@ant-design/icons` | **6.1.1（唯一，全仓 187 处）** | 禁止引入第二套 |
| 新增依赖 | **无** | — | 零 `pyproject` 变更、零镜像重建 |

**新增模块**：`odap/biz/decision/decision_hub/`（读侧编排：台账/队列/裁决/执行）。**不重写**既有 pipeline / recommendation / agent 链。

---

## 5. API 端点清单（锁定，以 `api-spec.yaml` 为唯一依据）

| Method | Path | 功能 | 认证 | 备注 |
|---|---|---|---|---|
| POST | `/api/auth/switch-workspace` | 重签 access+refresh | JWT | **T1，P0 前置**；校验成员资格；写审计 |
| GET | `/api/decisions` | 台账列表 | JWT + ws | 分页 `has_more`/`total_is_estimate` |
| GET | `/api/decisions/pending` | 待决策队列 | JWT + ws | 待办域 `pending\|decided\|executing`，按 group 二分 |
| POST | `/api/decisions/{id}/resolve` | 裁决 | JWT + ws | `action=approve\|reject`；**无 `selected_option`** |
| POST | `/api/decisions/{id}/execute` | 发起执行 | JWT + ws | 允许从 `decided`/`failed`；幂等 `idempotent_replay` |
| POST | `/api/decisions/batch-resolve` | 批量裁决 | JWT + ws | ≤50，逐条结果 |
| GET | `/api/decisions/{id}/reasoning-steps` | 推理步骤读取（**承接 agent `/steps` 下线**） | JWT + ws | 能力口径 6 + 承接 2 = **8 path**；本期后端不实现，前端"有数据才渲染" |
| POST | `/api/decisions/{id}/reasoning-steps` | 推理步骤写入 | JWT + ws | 同上 |
| GET | `/api/decisions/export.csv` | 导出 | — | **降 P1，本批不实现、前端不渲染按钮** |

**复用不改造**：`POST /api/decisions`、`GET /{id}/chain`、`GET /{id}/impact`、`GET /similar`、`POST /{id}/causal-links`、`POST /check-rules`、`PATCH /{id}/outcome`。

**状态码语义（全局唯一口径）**：
- 跨空间命中 → **404**（纵深防御，非关键修复；48 位随机 ID 枚举不可行）
- 确认同空间但无权限 → 403
- 非法状态转移（如 `pending` 直跳 `executing`） → **409** + `reason_code: illegal_transition`
- `workspace_id` 缺失 → **422**（不接受"空即不过滤"）

---

## 6. 数据模型（锁定）

`DecisionRecord` **新增 4 字段**，`outcome` 五态**零变更**（ADR-076 §3 契约不动）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | enum(6) | `pending/decided/executing/executed/failed/rejected`，服务端产生、客户端不可写 |
| `entry_source` | enum(7) | `manual/pipeline/recommendation/qa/agent/import/legacy` |
| `recommended_action` | object | `action_type_id / target_object_id / target_object_type / parameters`；`execute` 缺省取此值 |
| `resolution` | object | `action(approve\|reject) / actor_type(user\|system) / by / at / reason` |
| `status_assumed` | bool | `true` = 历史回填的**推导态**，非当时真实写入；新写入恒 `false`。用途：让"历史数据不得默认灌进待裁定队列"可审计，而不是把推断伪装成权威 |

**为什么单独 `resolution` 而不塞 `outcome_details`**：`outcome_details` 会被 pipeline 反馈回填覆写，裁决信息放进去会被冲掉；且 `actor_type=system`（策略门禁自动拒绝）与 `user`（人拍板）结论性质不同，不得共用字段互相覆盖。

**约束（服务端强制，E33/E34）**：
1. `status × outcome` 非法组合必须拒绝写入并返回明确错误。**校验落点在服务层写入侧，不放 `model_validator`** —— 该模型从图节点反序列化，硬校验会让任何一条历史脏数据在**读取**时抛 500，为防漂移把可用性搞挂代价不对等。读取侧只 `logger.warning` 并以 `status` 为准。**必须有测试断言**（E33 要求，不接受"只有代码没有测试"）。
2. 两字段写入必须同事务原子完成（防止"status 已改、outcome 未改"的中间态被读到）
3. 迁移幂等：二次运行 0 行；**历史数据不得默认灌进待裁定队列**（无 `status` 的旧记录按 `outcome` 回填，`outcome` 缺失则 `legacy` 语义，不判 `pending`），回填项 `status_assumed=true`

---

## 7. 页面清单（锁定）

| 页面 | 路由 | 核心组件 | 对应 API |
|---|---|---|---|
| 台账 | `/decisions/ledger` | `DecisionLedgerTable`（`agentId?` / `embedded?`） | `GET /api/decisions` |
| 待决策队列 | `/decisions/queue` | `DecisionQueuePage` + `DecisionStatusTag` | `GET /pending` / `resolve` / `execute` |
| 详情 | `/decisions/detail/:decisionId` | `DecisionChainGraph` / `ImpactPanel` / `PrecedentSearch`（复用）+ 推理路径区块 | `GET /chain` `/impact` `/similar` |
| 旧入口 | `/decisions` → `/decisions/ledger` | 重定向 | — |

**不新增一级菜单**（菜单由后端 `menu_config` seed 驱动，加 3 个一级菜单 = 3 次后端迁移）。

---

## 8. 设计 Token（锁定）

- **新增 token 数 = 0**（brownfield，复用 `global.css` 的 `--odap-*` 与 antd ConfigProvider）
- **图标库**：`@ant-design/icons` 6.1.1，尺寸 16/20/24px
- **状态标签**：界面 5 类 / 4 色系 —— 执行成功、部分成功（success 系）、执行失败（error）、待定（warning）、已驳回（中性）
- **映射函数签名必须是 `toDisplayLabel(status, outcome)`**：`status` 六值不含 `partial_success`，只吃 `status` 会丢掉"部分成功"标签；映射只允许一处实现
- **禁用硬编码色值**（`#fff`/`#000` 除外）；`DecisionChainGraph` 现存 5 个十六进制色值本期顺带清掉

---

## 9. 验收标准（以 PRD 为唯一依据）

> **引用纪律**：PRD 的 EARS 编号仍在演进，本 Spec **不跟随引用编号**，改用自有编号 `AC-xx` + PRD 章节/名称定位。
> 例外：`E26` / `E27` 已成本团队专有名词，保留按编号引。

| 编号 | 验收要求 | 对应 PRD | 优先级 |
|---|---|---|---|
| AC-01 | 跨空间归属不匹配时，系统**必须**返回 404，不得 403 | E26 | P0 |
| AC-02 | 全新空间首次进入为空态、demo 空间有数据，**两者互相不可见** | 历史数据要求 / E32 | P0 |
| AC-03 | `status×outcome` 非法组合**必须**拒绝写入，且有自动化断言 | §5.1.1 / E33 | P0 |
| AC-04 | 两字段**必须**同事务原子写，不得出现中间态 | §5.1.1 / E34 | P0 |
| AC-05 | 从 `decided` 发起执行可流转为 `executing`；重复发起**必须**幂等不产生第二条；并发只允许一个成功且输家得到明确冲突；失败**必须**回写 `failed` | §5.1 / E36 | P0 |
| AC-06 | 真实登录（`login → switch-workspace`）后，台账与队列**必须**可用，不得 422 | §5 / Spec 前置 | P0 |
| AC-07 | 执行载荷缺失（`recommended_action` 三字段任一为空）**必须** 422，不得 500 或静默成功 | §4.2 / E37 | P0 |
| AC-08 | `status_assumed=true` 的记录**不得**出现在队列、顶部计数、导出三者中 | §6 约束 3 / E30 | P0 |
| AC-09 | 以 `outcome=partial_success` 筛选台账，返回行标签**全部**为"部分成功" | §4.1.1 / E35 | P0 |
| AC-10 | `to_execute_count > 0` 时 `group.to_execute` **必须**非空（防次队列恒空复发） | §5.1 裁定块 | P0 |
| AC-11 | `decided` 档等待时长**必须**自 `resolution.at` 起算；无法获得时**整块不显示**，不得用 `created_at` 顶替 | §5.3 / E38 | P0 |
| AC-12 | 残留 `executing` 记录经 `execute` 幂等重放**必须**自愈到终态，且不产生第二条 ActionRecord | Spec 增补（跨库边界） | P0 |
| AC-13 | **未知值不得渲染为 0 / 0h / 空**：证据数不可得显示"证据数未知"，等待时长不可得整块不显示，历史数据裁决人显示 `—`（不显示"未处理"） | §5.2 / R2 判据 | P0 |
| AC-14 | **同步残留的诚实降级（可验收半）**：`status=executing` 且 `updated_at` 超阈值 → 详情页**必须**改为"状态可能未同步，请检查执行记录"+ 执行记录入口，**不得**继续显示"执行中"。只依赖 `status` + `updated_at`，零跨库零新字段 | E41 / §5.1.4 | P0 |
| AC-15 | **合法但长期的"执行中"必须有出口**：`status=executing` 的**任何**分支（含未超阈值、含拿不到 `action_status`）都**必须**渲染「查看执行记录」入口。**「出口」是恒定要求，不是超窗后的补偿**——若挂在时间条件下，删掉 ① 分支时 ② 的出口会一并消失。验收**不需要等待任何窗口**即可判定 | E41 扩写 / §5.1.4 | P0 |
| AC-16 | **跨空间命中必须 404、状态冲突必须 409，且响应体可读**：跨空间 → `404` + `error.code=not_found`；非法迁移 → `409` + `error.code=illegal_transition`。**禁止**用 `ValueError`（会成 400）或裸 `Exception`（会成 500）承载可预期的客户端错误。**错误体形状见下条，形状不对等于本条不成立** | E36 / E42 / ADR-091 §5.1.3 | P0 |
| AC-17 | **决策模块的错误体形状必须唯一**：所有客户端可见错误一律走 `APIError` 家族（`NotFoundError` / `ConflictError`），响应体为 `{"error": {type, code, message, request_id, path, details?}}`。**不得再用 `HTTPException`**——它由 Starlette 直接处理（中间件 `except HTTPException: raise`），输出 `{"detail": ...}`，与上面是两种形状。**两处例外（写进契约的例外，不是遗漏）**：① 共享基础设施依赖产出的 `401` 与"缺 workspace 声明 422"——`jwt_auth.get_current_user` / `workspace_access.get_current_workspace` 在**进入路由体之前**就已生成响应，决策模块改不了；② 框架字段级校验 `422`，体为 `{"detail": [ ... ]}`。**要消灭①得改全仓共用的安全入口，回归面覆盖所有端点**——所以这里要的是承认边界，不是"下期补齐" | E42 / §5 错误语义 | P0 |

> **AC-09 为何优先于"非法组合被拒"**：界面 6 个人话筛选选项要翻译成 `status[]` + `outcome[]` 两个独立参数，这套翻译的正确性**隐含依赖矩阵保证 `failed` 不可能带 `outcome=success`**。矩阵一旦失效，不只是后端脏数据，而是前端会**静默**给出错误筛选结果——用户看到"执行失败"标签只会以为这条决策失败了，不会意识到是筛选逻辑错了。前者漏了还有别的测试能发现，后者漏了没人会发现。

> **AC-16/17 的事故记录（为什么这两条必须一起写）**：契约 `api-spec.yaml` 的 `ErrorDetail` / `ConflictDetail` 声明的是 `{"detail": ...}`；
> 而全局中间件对 `ValueError` / `APIError` / 未捕获异常一律输出 `{"error": {...}}`。前端按契约只读 `data.detail`
> → 拿到 `undefined` → 回落成 `HTTP 409` → 用户看到的仍是泛化文案。
> **两边都是照契约写的，接起来不通**：不是谁写错了，是契约只描述了两种真实形状中的一种。
> 判据可复用：**契约里描述"响应形状"时，必须对着框架的实际产出写，不能对着理想设计写。**

> **AC-14 的不可验收半（明说不测）**：窗口内那句「状态同步中」依赖 `outcome_details.action_status`，而该键在契约中**零结构承诺**（`additionalProperties: true`）。字段缺失时断言会**静默通过**——等于没测。故本期**明确标注不可验收**，架构补声明后升级为可测。
> **降级规则定死**：取不到执行动作状态时**保持"执行中"**，不得显示"状态同步中"，**更不得用 `sla_state` 或任何等待时长档位冒充**（防的是换一个字段犯同一个错）。
> **"取不到"的口径（关键补丁）**：指**缺失、空、或取值不在 `ActionRequestStatus` 8 值枚举内**。后者即"不可解析"，**一律按无法判定处理，不得当终态**——否则后端将来多给一个枚举值时会被误判为终态，把「系统会自动同步」这句承诺说出来，而它恰恰是唯一含承诺的文案。
> **为什么"不可验收"可以被放行**：接受它的理由**不是"影响小"，而是失败时倒向安全的一侧**。按上条口径，字段不可得时 ① 根本渲染不出来 → 承诺永远说不出口 → 最坏结果是**少承诺**，不是**多承诺**。判据可复用：**若某分支失败时会多说一句假话，就不能放行。**
>
> **AC-16 的背景（必读，否则会重复踩）**：`odap/infra/middleware/exception_handler.py` 曾定义
> `APIError` / `NotFoundError`(404) / `ConflictError`(409) 却**从未在 `_handle_exception` 里消费**，
> 导致它们与裸 `Exception` 同路，全部返回 **500**。已补 `isinstance(exc, APIError)` 分支并加行为级测试
> （`test_middleware.py::test_not_found_error_maps_to_404` 等）。原测试只断言对象属性 `err.status_code == 404`，
> 从未发一次真实请求——**测属性不等于测行为**，这类"死代码"只能靠行为断言拦住。

---

## 10. 边界与约束

- 响应式：≥1280 正常；<1200 全站横向滚动（外壳限制，不在本模块修复）
- 性能：台账 keyset 分页，5 万条 / p95 300ms 为全文索引切换阈值
- 权限：只读角色可看队列不可操作（禁用 + Tooltip，**不得整页 403**）；"不适用"与"无权限"必须视觉区分（前者不渲染按钮）
- SLA：后端派生 `sla_state: ok|warning|breached` + `waiting_minutes`，阈值默认 24h/72h（可配为 P1）；**前端不自算**
- **跨库一致性边界（明确不承诺）**：`Decision.status`（Neo4j）与 `ActionRecord.status`（SQLite）**不保证任何时刻严格一致**。允许的最长不一致窗口 = 一次回写往返（调用后立即回写 + `finally` 回写 `failed`/`failure`），**超出即视为缺陷而非"正常最终一致"**；窗口内残留态由 `execute` 幂等重放自愈，前端显示"状态同步中"，**不得显示成"执行中"**。此条须登记进 ADR-091 Consequences，避免被当作强一致使用

---

## 11. 内嵌已知坑

| 坑 | 根因 | 应对 |
|---|---|---|
| `test_function_length` 长期失败 | 快照相对路径 vs collect 绝对路径；router_registry 行数失配 | **既有失败，不修**；但新写函数仍须 ≤40 行、文件 ≤300 行 |
| pytest 汇总行被插件日志覆盖 | safe-delete 插件 | 用 `EXIT=$?` 退出码判定，或输出落文件解析 |
| C3 契约阻断 | `odap.biz.core.ontology.*` 内部禁止直连 | 一律经 `odap/biz/core/ontology/public.py` 门面 |
| `IDecisionStore` 加 abstractmethod | `FakeDecisionStore` 会 TypeError，10 用例全红 | 同 PR 修 Fake（约 35 行） |
| `neo4j_decision_store.py` 已 408 行 | 超 300 硬上限 | 拆 `neo4j_decision_query.py`（Mixin），目标 288/276 |
| `feedback_loop.py` 取错字段 | `decision_id=action_record.get('agent_id')` | 本期修正为 `'decision_id'` |
| **`outcome` 当垃圾桶（存量）** | `pipeline._backfill_decision_outcome` 的 `else → PENDING` 兜底，把 `rolled_back`（已回滚）记成"结果待定" | 新增显式分支：`rolled_back → failed + failure`，明细写 `outcome_details{achieved_items, rolled_back_items}`；单测断言该映射。**这也是"从 outcome 派生队列"当初看起来可行的原因**——`pending` 同时罩住了"待裁定"与"已回滚" |
| T11 种子数据依赖 LLM | 若靠真跑完整 pipeline 造数据，演示可靠性被绑到最不稳定环节 | **种子数据必须由生产代码路径产生，但不必经过网络与模型**：直接调用真实映射函数构造 `rolled_back` 样本 |

---

## 12. 端到端验证步骤（锁定的最后一项）

```bash
# 0. 回归基线（改动前）
cd apps/api && ../../.venv/Scripts/python.exe -m pytest \
  tests/unit/test_decision_pipeline.py tests/unit/test_decision_recommendation.py \
  tests/unit/test_decision_record_isolation.py -q -p no:cacheprovider
# 期望：73 passed；EXIT=0

# 1. 契约层
cd apps/api && ../../.venv/Scripts/lint-imports.exe --config pyproject.toml
# 期望：Contracts: 4 kept, 0 broken

# 2. 真实登录（关键：B-1 修完才可能通过）
curl -X POST /api/auth/login -d '{"username":"demo","password":"***"}'
# 断言：200，token 内含非空 ws_id
curl -X POST /api/auth/switch-workspace -H "Authorization: Bearer $AT" -d '{"workspace_id":"ws_demo"}'
# 断言：200，新 token 的 ws_id == ws_demo

# 3. 主链路
curl -X POST /api/decisions ...                          # 断言 status=pending
curl -X GET  /api/decisions/pending                      # 断言 to_resolve_count ≥ 1
curl -X POST /api/decisions/{id}/resolve -d '{"action":"approve"}'
curl -X POST /api/decisions/{id}/execute                 # 断言 1 条 ActionRecord
curl -X POST /api/decisions/{id}/execute                 # 断言 idempotent_replay=true，仍 1 条
curl -X GET  /api/decisions/ledger?...                   # 断言 status=executed

# 4. 错误流（必须逐条断言）
# 跨空间读 → 404；pending 直跳 execute → 409；重复裁决 → 409 且不覆盖他人；ws 缺失 → 422
```

**专项门禁：契约自相矛盾检查**
> 接口能跑通、字段齐全，但组合起来功能是空的——单测与契约校验都抓不住。
> 检查方式：把「用户要看到什么」与「接口返回什么」逐条对齐，而不是看接口是否 200。
> 已知实例：`/pending` 曾声明"固定 status=pending"而分组为 `decided|executing`（次队列恒空）；SLA 曾单阈值而要求三档。

## 13. 变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-10-24 | 新增 `status` 6 态（原定"派生"） | 派生前置不可求值：`action_record_id` 全仓无写入 |
| 2026-10-24 | 移除 `selected_option` | 能力存在而决策不做 → 前端必误做 |
| 2026-10-24 | `execute` 允许从 `decided` 发起 | 否则次队列成死档 |
| 2026-10-24 | SLA 后端派生（驳 PM"前端自算"） | 阈值 P1 可配 → 前端自算成第二真相源 |
| 2026-10-24 | 端点口径定为 **8 path**（能力 6 + `reasoning-steps` 承接 2） | 按 6 计等于让 agent `/steps` 下线后推理步骤无声消失 |
| 2026-10-24 | 新增第 5 字段 `status_assumed` | 让"历史回填非权威"可被审计，而非伪装成权威状态 |
| 2026-10-24 | 矩阵校验改服务层写入侧（原 `model_validator`） | 模型从图节点反序列化，硬校验会让历史脏数据读取时 500 |
| 2026-10-24 | CSV 导出 + `evidence_count` 排序降 P1 | 估算 13.5 人日超 2.0；砍旁路保主链（导出 1.0 + 排序 0.3），保全 T11 演示数据 |
| 2026-10-24 | `available_actions` → `available_operations` | 与 `RecommendedAction`（命令对象）撞名，实现后改需动前端+契约+文档三处 |
