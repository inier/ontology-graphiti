# ADR-061: Semantic Admin Suite 架构决策

## 标题
Semantic Admin Suite 独立业务域架构决策

## 状态
Accepted

## 日期
2026-07-12

## 领域
Architecture

## 决策人
User

---

## 上下文（背景）

原 ODAP 语义层实现存在两大结构性问题，制约了 USL（统一语义层）治理能力的扩展：

1. **硬编码耦合严重**：`semantic_config.py` 将分类体系、同义词映射、消歧规则、质量阈值等以 Python 常量形式硬编码在单个文件中，修改任何规则都需要代码变更 + 重新部署 + 重启服务，无法支持运营人员在线配置、灰度发布、审批审计的 HITL（人机协同）治理流程。

2. **目录职责混杂**：原 `odap/biz/core/ontology/semantic_layer/` 目录同时承载了两类正交职责：
   - **USL 管理侧**：分类层级维护、语义候选生成、质量评估、审批工作流、写回本体 TBox 等生产治理能力；
   - **问答认知侧**：`parse-intent`（意图解析）、`plan-tasks`（任务规划）、`disambiguate`（实体消歧）等问答时认知能力。
   两类能力共享同一存储、同一路由前缀 `/api/semantic/*`、同一服务实例，导致测试无法隔离、发布节奏耦合、权限粒度无法区分（schema_auditor 角色无法单独授权 USL 管理权限而不泄露问答认知接口）。

---

## 决策

### A. 新建 biz/semantic_admin 顶级业务域（不挂 ontology/core）

新建 `odap/biz/semantic_admin/` 作为与 `core / decision / integration / platform / data / simulation / management` 并列的**第 8 个顶级业务域**，采用 7 层标准目录结构（api / models / interfaces / impl / services / storage），内部分解为 6 个子服务：

| 子服务 | 职责 |
|--------|------|
| **usl_manager** | USL 元数据 CRUD、分类层级管理、版本快照、发布/回滚 |
| **ol_pipeline** | Ontology Learning 6 层流水线：L1 文本分段 → L2 术语抽取 → L3 候选合并 → L4 分类标注 → L5 关系抽取 → L6 质量评估 |
| **candidate_store** | 语义草稿（Candidate）存储、去重、聚类、增量合并 |
| **quality_gate** | 质量闸 16 子指标公式化计算、O(N) 纯算、P95 ≤ 100ms |
| **approval_workflow** | 审批状态机 10 状态流转、OPA 二级授权、加速通道判定 |
| **usl_writeback** | 审批通过后写回本体 TBox（ObjectType / LinkType / Property 定义）、同步语义地图 |

严格遵循 `routes.py → services/ → impl/ → storage/` 调用链，禁止跨层调用（如路由层不得直接访问 storage、services 层不得直接 import impl 内部私有类）。

接口契约引用 specs 目录文档：
- USL 元数据契约：[contracts/usl_metadata.md](file:///e:/DEMO/AI/ontology-graphiti/specs/007-semantic-admin-suite/contracts/usl_metadata.md)
- 质量闸指标契约：[contracts/quality_gate.md](file:///e:/DEMO/AI/ontology-graphiti/specs/007-semantic-admin-suite/contracts/quality_gate.md)
- 审批工作流契约：[contracts/approval_workflow.md](file:///e:/DEMO/AI/ontology-graphiti/specs/007-semantic-admin-suite/contracts/approval_workflow.md)

### B. 路由前缀独立 + 旧问答路由立即移除

- **新路由前缀**：`/api/semantic-admin/*`，与原 `/api/semantic/*` 完全独立，两者在 FastAPI 路由注册、JWT 权限组、OPA policy 包路径三方面互不重叠。
- **旧路由移除（非 deprecated 标记）**：原 `semantic_layer/api/routes.py` 中 3 个问答认知路由 **立即移除**，不保留 deprecated 标记：
  - `POST /api/semantic/parse-intent`
  - `POST /api/semantic/plan-tasks`
  - `POST /api/semantic/disambiguate`
- 问答认知能力归位至 `odap/biz/data/qa/` 模块下的 cognition 子目录，路由前缀统一归 `/api/qa/cognition/*`。

### C. 双写存储架构（SQLite 主 + Neo4j 从）

#### SQLite 为主存储
- **适用数据**：USL 元数据、分类层级、Candidate 草稿、质量评估记录、审批工作流全量审计、Outbox 消息表。
- **存储规范**：
  - 每次操作 `sqlite3.connect()` → 执行 → `conn.close()`，**不使用连接池**。
  - 复杂字段（Dict / List / 嵌套 Pydantic）→ JSON TEXT 列，存储前 `json.dumps(ensure_ascii=False, sort_keys=True)`，读取后 `json.loads()`。
  - 所有 Enum 字段存 `.value` 字符串（如 `CandidateStatus.DRAFT.value → "draft"`）。
  - datetime 存 ISO 8601 字符串（`datetime.isoformat()`）。
- **表数量**：共 12 张表（详见 [§5 存储设计](file:///e:/DEMO/AI/ontology-graphiti/docs/03-modules/semantic_admin/DESIGN.md#5-存储设计)）。

#### Neo4j 为从存储（只读副本）
- **适用数据**：分类层级树结构、语义草稿间的语义相似度边、USL→Ontology TBox 映射关系。
- **命名空间规范**：
  - 节点标签前缀：`USL__Candidate`、`USL__Category`、`USL__SynonymCluster`
  - 关系类型前缀：`USL__BELONGS_TO`、`USL__SIMILAR_TO`、`USL__MAPS_TO`
  - 所有节点携带 `usl_workspace_id` 属性，确保工作空间隔离。
- **一致性策略**：
  - SQLite 写入成功后，通过 Outbox 表异步双写 Neo4j。
  - **Neo4j 写入失败不回滚 SQLite**：仅在 Outbox 表记录 `error_message`，下次 daemon 扫描自动重试。
  - **日巡检重建副本**：每日 UTC 02:00 触发巡检脚本，对比 SQLite 与 Neo4j 的计数哈希，不一致时以 SQLite 为准重建 Neo4j USL__* 命名空间。

### D. 任务调度架构（零中间件依赖）

不引入 Celery / Dramatiq / RQ 等第三方消息中间件，仅用 Python 标准库 + asyncio 实现两级调度：

#### 短批任务（< 30s）：asyncio.Semaphore(4)
- 适用场景：L1 文本分段、L2 术语抽取、质量闸计算、审批状态流转。
- 路由层 `asyncio.create_task(...)` 触发后立即返回 `task_id`，前端轮询 `/tasks/{task_id}` 获取进度。
- 所有 task 包裹 `try/except Exception as e` 兜底，异常写入 SQLite `sa_task_log` 表，**不中断主事件循环**。
- 全局并发上限 `Semaphore(4)`，防止 LLM 调用打爆下游。

#### 长任务（≥ 30s，如全量重算、Neo4j 重建）：Outbox daemon Thread
- 单例后台线程（`threading.Thread(daemon=True)`），每 5 秒扫描 SQLite `sa_outbox` 表中 `status='pending'` 的行。
- 每条 Outbox 记录最多重试 5 次，指数退避（30s / 1min / 2min / 5min / 15min），最终失败标记 `status='dead'` 并告警。
- 应用启动时在 `lifespan` 中启动 daemon，退出时优雅等待 10s 让运行中任务完成。

### E. 质量闸 + 审批工作流

#### 质量闸（Quality Gate）：三关 16 子指标公式化
| 关卡 | 子指标数 | 核心公式（示意） |
|------|----------|-----------------|
| 第一关：完整性 | 6 项 | coverage = (字段非空率 × 0.4 + 同义词覆盖率 × 0.3 + 上下位关系覆盖率 × 0.3) |
| 第二关：准确性 | 6 项 | accuracy = (LLM 验证通过率 × 0.5 + 本体一致性得分 × 0.3 + 反例冲突率 × 0.2) |
| 第三关：有用性 | 4 项 | usefulness = (候选频率分位数 × 0.4 + 问答历史命中 × 0.3 + 专家反馈分 × 0.3) |

- 所有指标 **O(N) 纯算**，无外部 I/O（LLM 验证结果预取后才入闸）。
- P95 延迟目标 ≤ 100ms，单批次 1000 条候选总耗时 ≤ 2s。
- 综合分 `overall = 完整性×0.35 + 准确性×0.45 + 有用性×0.20`，范围 [0, 1]。

#### 审批工作流：10 状态机 + OPA 二级审批

**状态机 10 状态**：
`DRAFT → PIPELINING → QUALITY_CHECK → REJECTED_QG → PENDING_FIRST → REJECTED_FIRST → PENDING_FINAL → APPROVED_WRITEBACK → WRITTEN → ARCHIVED`

**二级审批 OPA 授权**：
1. **初审（schema_auditor 角色，工作空间级）**：OPA policy `data.semantic_admin.approval.first_review`，要求 JWT payload 中 `ws_role ∈ {schema_auditor, ws_owner}`。
2. **终局（global admin）**：OPA policy `data.semantic_admin.approval.final_review`，要求 `role == "admin"`。

**加速通道（Fast Track）**：当满足以下 4 条同时成立时，`approvals_required = 1`（仅需初审通过即写回，跳过全局 admin）：
```
overall_score ≥ 0.7
  AND 无子指标 < 0.4
  AND L2 术语抽取余弦相似度 mean ≥ 0.3
  AND soft_coverage_score ≥ 0.5
```

---

## 后果

### 正向
1. **职责清晰**：USL 治理能力与问答认知能力彻底解耦，各自独立开发、测试、发布、授权。
2. **测试可追溯**：6 子服务按 7 层分层后，每层都有清晰的接口契约，TDD 可逐层覆盖（storage → models → services → routes）。
3. **零硬编码**：原 `semantic_config.py` 中 1200+ 行常量全部迁移到 SQLite `sa_config` 表，运营人员可在前端语义管理台实时修改并热生效。
4. **HITL 闭环**：10 状态机 + 2 级审批 + 加速通道形成"自动生成 → 质量闸 → 人工审核 → 写回本体"完整飞轮，不依赖工程团队介入。
5. **分类可视化**：Neo4j 从存储使得语义地图模块可直接 Cypher 查询分类层级树，无需在 SQLite 中做递归邻接表查询。

### 负向
1. **12 张表维护成本**：SQLite 新增 12 张表，需配套迁移脚本、日巡检 SQL、备份策略。
2. **Neo4j 巡检脚本**：需编写 `scripts/usl_neo4j_rebuild.py` 重建脚本，以及每周校验哈希的 cron job。
3. **目录重构 7+ 文件迁移**：原 `semantic_layer/` 下问答相关 3 路由 + 2 service 需迁移至 `data/qa/cognition/`，同时修改 `odap/web/app.py` 路由注册 + `router_registry.py`。
4. **双写一致性运维**：Outbox 死信队列需有运营告警通道（邮件 + 钉钉），否则 USL 与本体 TBox 不一致会被 QA 误判为 bug。
5. **权限模型升级**：OPA policy 需新增 `semantic_admin` 包，RBAC 菜单需新增语义管理台一级菜单，`menu_config` 表需 seed 4 条子菜单。

---

## 替代方案评估

| 替代方案 | 否决原因 |
|---------|---------|
| **挂在 ontology/core 下、单 `semantic_admin.py` 文件实现** | 伪实现风险：单文件无法支撑 6 子服务 + 12 表 + 10 状态机的复杂度，3 个月后必然演变为 2000+ 行"上帝类"，违反分层调用链规则，可测试性归零。 |
| **单 SQLite 不双写 Neo4j** | 分类可视化差：SQLite 递归查询 N 层分类树性能指数级下降（5 层分类需 5 次 self-join），G6 语义地图前端体验严重卡顿；且无法利用现有 Neo4j 图谱可视化能力。 |
| **引入 Celery 做任务调度** | 过度设计：当前峰值 QPS < 10，Outbox daemon Thread 完全足够；Celery 需额外 Redis/Broker 运维成本，且 Podman Compose 需新增 1 个服务，违反"最小依赖"原则。 |

---

## 可逆性

**中等**。
- 路由层面：`/api/semantic-admin/*` 前缀独立，回滚时只需从 `odap/web/app.py` 移除 `include_router(semantic_admin_router)` 即可。
- 数据层面：SQLite 12 张表均以 `sa_` 前缀命名，Neo4j 命名空间均以 `USL__` 前缀，回滚时可一次性 DROP / DELETE 而不影响其他业务数据。
- 代码层面：`odap/biz/semantic_admin/` 为独立目录，无反向依赖（其他 7 大业务域不 import semantic_admin 内部类），回滚时可整体删除目录 + 路由注册。
- 不可逆点：旧问答路由 `parse-intent / plan-tasks / disambiguate` 已移除，若需回退需从 Git 历史恢复并重新注册。
