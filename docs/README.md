# ODAP 文档中心

> **项目**: ODAP (Ontology-Driven Analysis Platform) — 本体驱动分析决策平台
> **文档体系**: SDD (Software Design Document) 层次化 | 11层 + 契约层 + 归档层 | 防腐文档
> **版本**: 3.1.0 | **日期**: 2026-07-04 | **更新**: 文档体系治理：消除散落目录、统一归档路径、新增 subsystems 专项架构索引

---

## 快速导航

| 你要做什么？ | 从这里开始 |
|-------------|----------|
| 📖 了解项目需求和目标 | [00-需求](00-requirements) |
| 🎯 了解产品设计方案 | [01-产品设计](01-product-design) |
| 🏗️ 理解系统架构 | [02-架构设计](02-architecture) |
| 🔧 查看某个模块的详细设计 | [03-模块设计](03-modules) |
| 🎨 查看UI/UX设计规范 | [04-UI设计](04-ui) |
| 🔒 了解安全策略 | [05-安全设计](05-security) |
| ⚙️ 查看性能/测试/运维设计 | [06-DFX设计](06-dfx) |
| 📝 查阅架构决策记录 | [07-ADR](07-adr) |
| 📋 查看开发任务分解 | [08-任务分解](08-tasks) |
| ✅ 使用检查清单验收 | [09-检查清单](09-checklists) |
| 🔌 查看API接口规范 | [10-API规范](10-api) |
| 🗄️ 查阅历史归档 | [11-归档](11-archive) |

---

## SDD 层次体系

```
层1: 原始需求    ── 00-requirements/req-ok.md               ← 用户要什么
层2: 开发需求    ── 00-requirements/backlog/                ← 工程解读
层3: 产品设计    ── 01-product-design/                      ← 我们做什么
层4: 架构设计    ── 02-architecture/ARCHITECTURE.md ⭐       ← 怎么组织
层5: 模块设计    ── 03-modules/                             ← 每部分怎么做
层6: UI设计      ── 04-ui/                                  ← 长什么样
层7: 安全设计    ── 05-security/                            ← 怎么保护
层8: DFX设计     ── 06-dfx/                                 ← 非功能属性
层9: 决策记录    ── 07-adr/                                 ← 为什么这样选
层10: 任务分解   ── 08-tasks/                               ← 怎么实施
层11: 检查清单   ── 09-checklists/                          ← 怎么验收
契约层: API规范  ── 10-api/                                 ← 对外契约
归档层: 历史     ── 11-archive/                             ← 演进依据
```

---

## 核心文档（必读）

| 优先级 | 文档 | 位置 |
|:------:|------|------|
| ⭐⭐⭐ | **唯一权威需求来源** | [00-requirements/req-ok.md](00-requirements/req-ok.md) |
| ⭐⭐⭐ | **唯一权威架构文档** | [02-architecture/ARCHITECTURE.md](02-architecture/ARCHITECTURE.md) |
| ⭐⭐ | 全链路深入实现 | [02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md](02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md) |
| ⭐⭐ | 综合优化设计 | [01-product-design/ODAP综合优化设计文档.md](01-product-design/ODAP综合优化设计文档.md) |

---

## 文档维护

- **维护规范**: [DOCUMENT_MANAGEMENT.md](DOCUMENT_MANAGEMENT.md) — 防腐文档体系与维护指南
- **文档基线**: [DOCUMENT_BASELINE_v1.0.0.md](DOCUMENT_BASELINE_v1.0.0.md)
- **文档关系**: [DOCUMENT_RELATIONSHIP.md](DOCUMENT_RELATIONSHIP.md)

### 变更原则

1. 需求变更 → 更新 `req-ok.md` → 同步更新受影响架构文档
2. 架构决策 → 创建新 ADR → 更新 ARCHITECTURE.md 引用
3. 模块变更 → 更新对应 `modules/*/DESIGN.md` → 同步更新 DEEP
4. 废弃文档 → 移至 `11-archive/`，保留演进历史

---

## 目录结构

> **治理原则**：docs/ 根目录仅保留 4 份文档管理文件，其余所有内容必须归入 SDD 编号目录。禁止在根目录新增自由命名目录。

```
docs/
├── README.md                           # ⭐ 本文件 - SDD 文档中心总索引
├── DOCUMENT_MANAGEMENT.md              # 防腐文档体系维护指南
├── DOCUMENT_BASELINE_v1.0.0.md         # 文档基线（首个可信版本）
├── DOCUMENT_RELATIONSHIP.md            # 文档关系完整索引 + 角色阅读路径
│
├── 00-requirements/                    # 层1+2：原始需求 + 开发需求
│   ├── req-ok.md                       # ⭐ 唯一权威需求定稿
│   ├── archive/                        # 早期技术研究归档
│   ├── backlog/                        # 需求待办
│   └── documents/                      # 补充前端文档
│
├── 01-product-design/                  # 层3：产品设计
│
├── 02-architecture/                    # 层4：架构设计（唯一权威 ARCHITECTURE.md）
│   ├── subsystems/                     # ✨ 子系统专项架构（AI 助手/本体隔离等）
│   └── reports/                        # 历史审查报告归档
│
├── 03-modules/                         # 层5：模块设计（25个 DESIGN.md）
│
├── 04-ui/                              # 层6：UI设计（含 v2 Design System）
├── 05-security/                        # 层7：安全设计
├── 06-dfx/                             # 层8：DFX设计（性能/测试/可维护性）
├── 07-adr/                             # 层9：架构决策记录（60+ ADR）
├── 08-tasks/                           # 层10：任务分解
├── 09-checklists/                      # 层11：检查清单（验收/文档同步）
├── 10-api/                             # 契约层：API + 数据库设计规范
│
└── 11-archive/                         # 归档层：演进依据（不删除、只归档）
    ├── legacy_code/                    # 废弃代码保留（Python）
    ├── specs/                          # 早期 Spec-kit 规格（已被根 specs/ 取代）
    ├── audit/                          # 审查报告归档（R1~R5 / 升级 / 测试报告）
    └── feature-specs/                  # 早期超能力专项设计规格归档
```
