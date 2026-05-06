# ODAP 文档中心

> **项目**: ODAP (Ontology-Driven Analysis Platform) — 本体驱动分析决策平台
> **文档体系**: SDD (Software Design Document) 层次化 | 11层 | 防腐文档
> **版本**: 3.0.0 | **日期**: 2026-05-07

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

```
docs/
├── README.md                           # 本文件 - 总索引
├── DOCUMENT_MANAGEMENT.md              # 防腐维护指南
├── DOCUMENT_BASELINE_v1.0.0.md         # 文档基线
├── DOCUMENT_RELATIONSHIP.md            # 文档关系图
│
├── 00-requirements/                    # 原始需求 + 开发需求
│   ├── req-ok.md                       # ⭐ 唯一权威需求
│   ├── archive/                        # 早期技术研究
│   ├── backlog/                        # 需求待办
│   └── documents/                      # 补充文档
├── 01-product-design/                  # 产品设计
├── 02-architecture/                    # 架构设计
│   └── reports/                        # 历史审查报告
├── 03-modules/                         # 22个模块设计
├── 04-ui/                              # UI设计
├── 05-security/                        # 安全设计
├── 06-dfx/                             # DFX设计
├── 07-adr/                             # 架构决策记录（54个ADR）
├── 08-tasks/                           # 任务分解
├── 09-checklists/                      # 检查清单
├── 10-api/                             # API规范
└── 11-archive/                         # 归档
    ├── legacy_code/
    └── specs/                          # 早期spec（已取代）
```
