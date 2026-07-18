# 规格与架构文档瘦身报告（2026-07-08）

## 结论

在不损失任何**功能描述**（用户故事、验收标准、API 契约、数据模型）的前提下，文档总量下降 **14,222 行（约 −15%）**，其中 `specs/` 下降 **46%**。

## 瘦身前 / 后

| 维度 | 瘦身前 | 瘦身后 | 变化 |
|------|--------|--------|------|
| `specs/` 总行数 | 19,565 | 10,553 | **−9,012 (−46%)** |
| `docs/` 总行数 | 75,571 | 70,361 | **−5,210 (−7%)** |
| 合计 | 95,136 | 80,914 | **−14,222 (−15%)** |

## 删除项（全部 git 追踪，可 `git restore` 恢复）

### 死文档（从未落地 / 已被实现取代）
| 目标 | 行数 | 理由 |
|------|------|------|
| `specs/002-copilotkit-eval/` | 4,922 | CopilotKit 全仓零引用，从未实现 |
| `specs/006-llm-config-management/` | 1,516 | 功能已由 `apps/api/odap/biz/platform/config/`（config.db + 热更新）实现 |
| `specs/004-microservice-split/` | 329 | 微服务拆分未采纳，零引用 |
| `specs/ui-ux-pro-max/` | 245 | 早期碎片 |
| `docs/02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md` | 5,210 | 内联源码，与仓库 100% 重复 |

### 过程产物（非功能描述，派生/重复快照）
- `specs/000-architecture-review/`：7 份评审报告 → 合并为 1 份 `SUMMARY.md`（保留最终结论 + P0/P1 修复清单 + 关键文件）
- `specs/001-odap-platform/tasks-review.md`、`tasks-dependency-diagram.md`（明确"从 tasks.md 派生"）
- `specs/003-ontology-redesign/tasks-us3.md`（US3 子集）

## 保留项（功能真相源，未动）
- `spec.md`：用户故事 + Given/When/Then 验收标准
- `contracts/`：API 契约
- `data-model.md`：存储/数据模型
- `plan.md` / `research.md`：设计依据
- 每个活跃 spec 的主 `tasks.md`
- `docs/` 下全部 `DESIGN.md`、AI 助手系列（统一设计/独立组件化/平台功能本体/操作手册 Schema/升级报告）—— 经核验均为单一职责、内容互不重复

## 后续可选清理（低优先级，未执行）
- `docs/00-requirements/archive/req-alpha.md`（2,893 行）、`req-beta.md`（795 行）：已归档旧需求，由 `req-ok.md` 权威替代。归档即有意保留，本次未删。

## 关联决策
- `docs/07-adr/ADR-049_规格与架构文档瘦身.md`
