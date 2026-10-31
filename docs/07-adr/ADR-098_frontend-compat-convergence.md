---
id: odap.l7.adr-098-frontend-compat-convergence
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

# ADR-098: frontend_compat 兼容层收敛与下线

## Status

**已接受（2026-10-17）**。本轮确立兼容层收敛路径与下线触发条件。

---

## Background

关联需求：模块化/组件化解耦，提升可组合性；用户授权合并/下线重复模块（须附迁移映射 + 溯源证据）。

**现状（文件:行证据）**：

- 兼容层实际位于 `apps/api/odap/biz/integration/frontend_compat/`（**非**任务书所述 `biz/frontend_compat/`，后者系 2026-04 报告旧路径）。
- 规模：`api/routes.py`(17) + `_deps.py`(169) + `agent_routes.py`(235) + `ontology_routes.py`(433) + `simulation_routes.py`(114)，合计 968 行。
- `routes.py:3-4` 自述「仅保留真正做跨服务聚合的端点，1:1 重复原生服务层的端点已删除」——已做过一轮收敛。
- 但兼容层仍承接**已证明为伪实现**的端点：`/graph/generate`、`/graph/progress/{task_id}`（`ontology_routes.py:148,203`），其内核 `tasks.py:108-131` 为 `time.sleep(10)` + 硬编码返回值（评估报告 §1.6）。
- 层级方向正确：挂 `biz/integration` 下，向下依赖 infra，不反向依赖 web（C2 通过）。

---

## Decision

1. **定性**：`frontend_compat` 是过渡层技术债，最终须下线，不作为长期架构的一部分。
2. **收敛路径**（分三步）：
   - 第一步：产出「兼容层端点 → 原生 `/api/v1/*` 端点」映射表 + 前端调用点清单（Phase 2，前后端共同确认）。
   - 第二步：前端全部改指原生端点；对兼容层加**调用计数**；进入观测期。
   - 第三步：观测期零调用后，删除兼容层；删除前打 tag。
3. **伪实现前置修复**：`/graph/generate`、`/graph/progress/{task_id}` 的调用方（`AgentChat` 等前端）在迁移前，须先重做内核为真实实现，或明确降级口径（如「仅校验不入库」并在契约标注），**不得带伪实现迁移**。
4. **回滚策略**：兼容层保留至零调用确认后删除；任一迁移步骤异常，`git revert` 对应提交即可恢复兼容层端点。
5. **新端点归属**：本轮新增端点（LLM Wiki / 本体约束问答 / 溯源 / 文档治理）**不**进兼容层，直接落原生 `/api/v1/*`。

**备份方案**：若前端长期无法完成迁移，则把兼容层显式「升格」为正式适配层（改名 `biz/integration/legacy_adapter`），并纳入正式维护与测试，但须附「保留原因 + 清退时间表」。

---

## Consequences

**正面**：
- 消除过渡层，模块边界清晰，可组合性提升。
- 伪实现在迁移前被强制处理，堵住技术债转移。
- 新端点不污染兼容层，边界干净。

**负面**：
- 需一轮线上观测期，下线周期较长。
- 前端迁移涉及调用点改动，有回归风险。
- 若无前端调用点清单，映射表无法完成（依赖前端协作）。

---

## Related ADRs

- ADR-040（api gateway unified entry）
- ADR-046（modular monolith deployment）
- ADR-067（biz shared relocation）
- ADR-080（ontology 门面封装与分层契约）
