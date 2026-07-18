# 规格文档复查与修复报告（2026-07-08 二次审计）

> 关联决策：[ADR-049 规格与架构文档瘦身](07-adr/ADR-049_规格与架构文档瘦身.md)
> 触发：用户对首轮瘦身结果进行"残缺与冗余"复查

## 1. 复查范围与方法
- 范围：`specs/`（4 个现存目录）与 `docs/`（架构/设计/需求/ADR）
- 方法：
  1. **结构体检**：目录完整性、核心文件（`spec.md` / `contracts` / `data-model`）存在性
  2. **断链扫描**：已删对象（002/004/006/ui-ux-pro-max/FULL_CHAIN_DEEP）在 specs/docs 中的残留引用
  3. **层间重复度**：research/plan/tasks 是否重述 spec.md 的用户故事/验收标准
  4. **冗余识别**：过程产物（review 报告）、雷同 quickstart、膨胀 data-model

## 2. 发现的残缺（Incomplete）
| ID | 问题 | 范围 | 严重度 | 处理 |
|----|------|------|--------|------|
| C1 | `ARCHITECTURE_FULL_CHAIN_DEEP.md` 被 21 个文件悬空引用（删文件未清引用） | 跨 docs/ | 高 | **已修复(P0)** |
| C2 | `000-architecture-review/` 缺 spec.md | 仅该目录 | 低 | **已修复(P2)** |
| C3 | `docs/11-archive/...sanguo...md` 引用已删 `specs/002-copilotkit-eval/` | 仅 archive | 低 | 跳过（归档容忍） |

## 3. 发现的冗余（Redundant）
| ID | 问题 | 处理 |
|----|------|------|
| R1 | `specs/005-data-collection-opt/checklist-review.md`（Superspec Review Report，纯代码修复记录） | **已删除(P1)** |
| R2 | `001/data-model.md` 1,796 行 | 经核实为真实 DB schema，**非冗余**，保留 |

## 4. 复查确认的健康项（首轮未误伤）
- **层间零重述**：`001` 的 research/plan/tasks 对 spec.md 的 8 User Story、39 验收标准 **0 复制**
- **三份 quickstart 内容各异**（平台启动 / 本体提取 / 数据采集），非模板冗余
- **contracts 完整**：001/003/005 的 API 契约齐全
- **除 FULL_CHAIN_DEEP 外无真断链**；spec.md 之间不互引

## 5. 修复动作与验证
- **P0**：21 文件 `ARCHITECTURE_FULL_CHAIN_DEEP.md` → `ARCHITECTURE_FULL_CHAIN.md`（现存，已确认存在）。验证：`docs/` 中除 ADR-049/SLIMMING_REPORT 的删除记录外，无 DEEP 死链残留。
- **P1**：删除 `specs/005-data-collection-opt/checklist-review.md`。
- **P2**：为 `000-architecture-review/` 补 `spec.md`（注明评审记录性质）。
- 全部改动 git 可恢复。

## 6. 经验沉淀
删除文档时必须同步清理引用。建议将"删文件 → 查引用"纳入删除 checklist 或 pre-commit 校验，杜绝"删文件留死链"的系统性残缺复发。
