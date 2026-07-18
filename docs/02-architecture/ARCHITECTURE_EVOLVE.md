# 本体驱动分析决策平台 (ODAP) - 演进与决策
> **部分**: 技术选型 + ADR + 需求追溯 + 演进路线图 + 文件结构 + 环境变量
> **版本**: 5.0.0 | **日期**: 2026-05-19
> **上级文档**: [ARCHITECTURE.md](ARCHITECTURE.md)
---
## 10. 技术选型与权衡

### 10.1 核心组件选型

| 组件 | 选项A | 选项B | 选项C | 决策 | 权衡 |
|------|-------|-------|-------|------|------|
| **Agent 框架** | LangGraph | OpenHarness | AutoGen | **OpenHarness** | 开源+生产级+多Agent内置，节省90%代码 |
| **知识图谱** | Neo4j | Amazon Neptune | Graphiti | **Graphiti** | 双时态原生支持，支撑历史回溯 |
| **策略引擎** | OPA | Cedar | Casbin | **OPA** | Rego语言灵活+生态丰富+生产验证 |
| **图数据库** | Neo4j | NetworkX | Memgraph | **Neo4j** | 向量检索+时序+ACID，成熟稳定 |
| **Agent LLM** | Claude | GPT-4 | DeepSeek | **混合** | Commander用强推理，Intelligence用快速 |

### 10.2 权衡矩阵

#### 10.2.1 LLM 模型分配

| Agent | 推荐模型 | 理由 |
|-------|---------|------|
| Commander | Claude-3.5 Sonnet / GPT-4 | 复杂推理+风险权衡 |
| Intelligence | DeepSeek-v3 / Kimi | 快速分析+长上下文 |
| Operations | GPT-4o-mini / Qwen | 规划+执行，速度优先 |

#### 10.2.2 Skill 体系策略

**核心策略：Python Skills 原生接入 OpenHarness**

| 策略 | 范围 | 接入方式 | 决策 |
|------|------|----------|------|
| **Python Skills** | 领域特定能力（情报/作战/分析） | OpenHarness 原生 Tool 接口 | ✅ 核心采用 |
| **OpenHarness Markdown Skills** | 通用工具能力 | OpenHarness 原生 Skill 机制 | ✅ 补充采用 |
| **外部 Agent（MCP）** | 第三方系统集成 | MCP/REST/WebSocket | ✅ 按需集成 |

**Skill 分层**：

| 层级 | 类型 | 示例 | 管理者 |
|------|------|------|--------|
| L2-领域 Skills | Python 模块 | radar_search, threat_assess | 平台开发者 |
| L2-通用 Skills | Markdown | 文件操作, 代码执行 | OpenHarness 社区 |
| L3-外部 Skills | MCP 协议 | 第三方 Agent | 外部系统 |

---

### 10.3 文档体系概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           完备文档体系 (Complete Documentation)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   设计文档      │  │   开发文档      │  │   测试文档      │             │
│  │  Design Docs    │  │  Dev Docs       │  │  Test Docs      │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • 架构设计      │  │ • 开发指南      │  │ • 测试策略      │             │
│  │ • 接口设计      │  │ • API 参考      │  │ • 测试用例      │             │
│  │ • 数据字典      │  │ • 代码规范      │  │ • 测试报告      │             │
│  │ • 模块设计      │  │ • 部署手册      │  │ • 自动化测试    │             │
│  │ • 安全设计      │  │ • 运维手册      │  │ • 性能测试      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   使用手册      │  │   运营文档      │  │   质量保证      │             │
│  │  User Docs      │  │  Ops Docs       │  │  QA Docs        │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • 用户指南      │  │ • 运维手册      │  │ • 验收标准      │             │
│  │ • 管理员指南    │  │ • 故障排查      │  │ • 发布检查单    │             │
│  │ • 快速入门      │  │ • 监控告警      │  │ • 质量报告      │             │
│  │ • FAQ           │  │ • 备份恢复      │  │ • 合规文档      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.4 文档清单

#### 10.4.1 设计文档

| 文档名称 | 路径 | 描述 | 更新频率 |
|----------|------|------|----------|
| **架构设计文档** | `docs/ARCHITECTURE.md` | 整体架构、组件设计、ADR | 每季度审查 |
| **接口设计文档** | `docs/API.md` | REST API、WebSocket 协议定义 | 与 API 同版本 |
| **数据字典** | `docs/DATA_DICTIONARY.md` | 数据库表结构、字段说明 | 数据库变更时 |
| **模块设计文档** | `docs/modules/{module}/DESIGN.md` | 各模块详细设计 | 模块重构时 |
| **安全设计文档** | `docs/SECURITY.md` | 安全架构、威胁建模 | 每半年审查 |

#### 10.4.2 开发文档

| 文档名称 | 路径 | 描述 | 更新频率 |
|----------|------|------|----------|
| **开发指南** | `docs/DEVELOPER_GUIDE.md` | 环境搭建、开发流程 | 按需更新 |
| **API 参考** | `docs/openapi.yaml` | OpenAPI 3.0 规范 | API 变更时自动生成 |
| **代码规范** | `docs/CODE_STYLE.md` | 编码规范、命名约定 | 按需更新 |
| **部署手册** | `docs/DEPLOYMENT.md` | Docker、K8s 部署 | 部署变更时 |
| **技能开发指南** | `docs/SKILL_DEVELOPMENT.md` | 如何开发新 Skill | 按需更新 |
| **OPA 策略编写指南** | `docs/OPA_POLICY_GUIDE.md` | Rego 策略编写规范 | 按需更新 |

#### 10.4.3 测试文档

| 文档名称 | 路径 | 描述 | 更新频率 |
|----------|------|------|----------|
| **测试策略** | `docs/TEST_STRATEGY.md` | 测试方法论、覆盖率目标 | 每季度 |
| **单元测试用例** | `tests/unit/` | pytest 用例 | 与代码同步 |
| **集成测试用例** | `tests/integration/` | API、组件集成测试 | 按需更新 |
| **E2E 测试用例** | `tests/e2e/` | Playwright 端到端测试 | 按需更新 |
| **性能测试报告** | `docs/reports/PERF_TEST_{date}.md` | 性能基准测试 | 每次发布前 |
| **安全测试报告** | `docs/reports/SECURITY_TEST_{date}.md` | 安全扫描报告 | 按需更新 |

#### 10.4.4 使用手册

| 文档名称 | 路径 | 描述 | 受众 |
|----------|------|------|------|
| **用户手册** | `docs/user/MANUAL.md` | 功能使用说明 | 指挥官、分析员 |
| **管理员手册** | `docs/admin/ADMIN_GUIDE.md` | 系统配置说明 | 系统管理员 |
| **快速入门** | `docs/user/QUICK_START.md` | 5 分钟上手指南 | 新用户 |
| **常见问题** | `docs/user/FAQ.md` | FAQ 汇总 | 所有用户 |

#### 10.4.5 运营文档

| 文档名称 | 路径 | 描述 |
|----------|------|------|
| **运维手册** | `docs/ops/OPS_MANUAL.md` | 日常运维操作 |
| **故障排查指南** | `docs/ops/TROUBLESHOOTING.md` | 常见问题处理 |
| **监控告警配置** | `docs/ops/MONITORING.md` | Prometheus/Grafana 配置 |
| **备份恢复手册** | `docs/ops/BACKUP_RECOVERY.md` | 数据备份与恢复 |
| **发布检查单** | `docs/ops/RELEASE_CHECKLIST.md` | 发布前检查项 |

### 10.4.1 文档维护流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          文档生命周期 (Documentation Lifecycle)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │  编写   │───▶│  评审   │───▶│  发布   │───▶│  维护   │───▶│  归档   │ │
│  │ Author  │    │ Review  │    │ Publish │    │ Maintain │    │ Archive  │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│       │              │              │              │                    │      │
│       ▼              ▼              ▼              ▼                    ▼      │
│  • 功能开发时    • PR 评审       • 版本发布      • 版本更新时      • 版本 EOL  │
│  • 代码变更时    • Tech Lead     • 自动生成      • 用户反馈时      • 归档存储  │
│  • 需求文档化    • 文档审查      • GitHub Pages  • 错误更正时      • 版本保留  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.4.2 代码提交规范（原子功能提交）

```bash
# 提交格式
<type>(<scope>): <subject>

# type 类型
feat:     新功能
fix:      缺陷修复
docs:     文档更新
style:    代码格式（不影响功能）
refactor: 重构（既不修复也不添加功能）
perf:     性能优化
test:     测试相关
chore:    构建/工具变更

# scope 影响范围
core:       核心模块
skills:     技能模块
ontology:   本体模块
visualization: 可视化模块
admin:      管理后台
docs:       文档

# 示例
feat(skills): 添加评估技能
fix(core): 修复 Graphiti 连接池泄漏
docs(ontology): 更新数据字典
refactor(admin): 重构角色配置模块
test(skills): 添加技能测试用例
```

### 10.4.3 自动化文档生成

```yaml
# .github/workflows/docs.yml
name: Documentation

on:
  push:
    branches: [main]
    paths: ['docs/**', '**.md']
  release:
    types: [published]

jobs:
  generate-api-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate OpenAPI docs
        run: |
          npm run docs:api

      - name: Upload API docs
        uses: actions/upload-artifact@v4
        with:
          name: api-docs
          path: docs/api/

  build-site:
    runs-on: ubuntu-latest
    needs: generate-api-docs
    steps:
      - uses: actions/checkout@v4

      - name: Build documentation
        run: |
          npm run docs:build

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs/_site
```

---


## 17. 架构决策记录（ADR）

> 所有 ADR 已拆分为独立文件，存放在 [`do../07-adr/`](07-adr/) 目录下。

### 17.1 ADR 索引

> **说明**: 以下为关键 ADR 索引，完整列表（54个）请参考 [adr/README.md](../07-adr/README.md)。

| ADR | 决策标题 | 状态 | 文件 |
|-----|---------|------|------|
| ADR-001 | Agent 基础设施（OpenHarness + LangGraph） | 已接受 | [adr/ADR-001_agent_基础设施openharness_langgraph.md](07-adr/ADR-001_agent_基础设施openharness_langgraph.md) |
| ADR-002 | Graphiti 作为双时态知识图谱 | 已接受 | [adr/ADR-002_graphiti_作为双时态知识图谱.md](07-adr/ADR-002_graphiti_作为双时态知识图谱.md) |
| ADR-003 | OPA 策略治理引擎（MVP + 生产化） | 已接受 | [adr/ADR-003_opa_策略治理引擎mvp_生产化.md](../07-adr/ADR-003_opa_策略治理引擎mvp_生产化.md) |
| ADR-004 | 统一 Skill 体系架构 | 已接受 | [adr/ADR-004_统一_skill_体系架构.md](07-adr/ADR-004_统一_skill_体系架构.md) |
| ADR-005 | 分层 Agent 架构（OpenHarness 原生 + 领域扩展） | 已接受 | [adr/ADR-005_分层_agent_架构openharness_原生_领域扩展.md](../07-adr/ADR-005_分层_agent_架构openharness_原生_领域扩展.md) |
| ADR-006 | OpenHarness 复用策略（完全复用 + 适配复用 + 独立扩展） | 已接受 | [adr/ADR-006_openharness_复用策略完全复用_适配复用_独立扩展.md](../07-adr/ADR-006_openharness_复用策略完全复用_适配复用_独立扩展.md) |
| ADR-007 | 前端采用 React + Ant Design 技术栈 | 已接受 | [adr/ADR-007_前端采用_react_ant_design_技术栈.md](07-adr/ADR-007_前端采用_react_ant_design_技术栈.md) |
| ADR-008 | 审计日志完整记录 | 已接受 | [adr/ADR-008_审计日志完整记录.md](../07-adr/ADR-008_审计日志完整记录.md) |
| ADR-009 | Markdown 编写 OPA 策略 | 已接受 | [adr/ADR-009_markdown_编写_opa_策略.md](../07-adr/ADR-009_markdown_编写_opa_策略.md) |
| ADR-010 | 多模态文档处理可配置 | 已接受 | [adr/ADR-010_多模态文档处理可配置.md](07-adr/ADR-010_多模态文档处理可配置.md) |
| ADR-011 | 角色配置热生效 | 已接受 | [adr/ADR-011_角色配置热生效.md](07-adr/ADR-011_角色配置热生效.md) |
| ADR-012 | 配置组合引擎 | 已接受 | [adr/ADR-012_配置组合引擎.md](../07-adr/ADR-012_配置组合引擎.md) |
| ADR-013 | 多数据源统一接入 | 已接受 | [adr/ADR-013_多数据源统一接入.md](../07-adr/ADR-013_多数据源统一接入.md) |
| ADR-014 | 技能热插拔架构 | 已接受 | [adr/ADR-014_技能热插拔架构.md](07-adr/ADR-014_技能热插拔架构.md) |
| ADR-015 | 可扩展图表系统 | 已接受 | [adr/ADR-015_可扩展图表系统.md](../07-adr/ADR-015_可扩展图表系统.md) |
| ADR-016 | 完备文档体系 | 已接受 | [adr/ADR-016_完备文档体系.md](07-adr/ADR-016_完备文档体系.md) |
| ADR-017 | 原子提交规范 | 已接受 | [adr/ADR-017_原子提交规范.md](07-adr/ADR-017_原子提交规范.md) |
| ADR-018 | 模拟领域数据生成引擎 | 已接受 | adr/ADR-018_模拟领域数据生成引擎.md |
| ADR-019 | 多模态文档处理流水线 | 已接受 | [adr/ADR-019_多模态文档处理流水线.md](../07-adr/ADR-019_多模态文档处理流水线.md) |
| ADR-020 | 管理员控制台统一界面 | 已接受 | [adr/ADR-020_管理员控制台统一界面.md](../07-adr/ADR-020_管理员控制台统一界面.md) |
| ADR-036 | 领域实体标准本体库 | 已接受 | [adr/ADR-036_palantir_ontology_reference.md](../07-adr/ADR-036_palantir_ontology_reference.md) |
| ADR-037 | 前端移动优先、响应式设计和国际化策略 | 已接受 | [adr/ADR-037_frontend_mobile_first_i18n.md](07-adr/ADR-037_frontend_mobile_first_i18n.md) |
| ADR-022 | 模拟数仓与统一查询服务 | 提议中 | [adr/ADR-022_模拟数仓与统一查询服务.md](07-adr/ADR-022_模拟数仓与统一查询服务.md) |
| ADR-023 | 多工作空间隔离架构 | 已接受 | [adr/ADR-023_多工作空间隔离架构.md](../07-adr/ADR-023_多工作空间隔离架构.md) |
| ADR-024 | 本体驱动分析核心架构 | 已接受 | [adr/ADR-024_本体驱动分析核心架构.md](07-adr/ADR-024_本体驱动分析核心架构.md) |
| ADR-025 | 基于 OpenHarness 实现多智能体协同 | 已接受 | [adr/ADR-025_openharness_integration.md](../07-adr/ADR-025_openharness_integration.md) |
| ADR-026 | 采用 MCP 协议作为外部系统集成标准 | 已接受 | [adr/ADR-026_mcp_protocol_integration.md](../07-adr/ADR-026_mcp_protocol_integration.md) |
| ADR-027 | Hook 系统作为可扩展性核心架构 | 已接受 | [adr/ADR-027_hook_system_architecture.md](07-adr/ADR-027_hook_system_architecture.md) |
| ADR-028 | OPA 作为统一权限校验引擎 | 已接受 | [adr/ADR-028_permission_checker_opa_integration.md](07-adr/ADR-028_permission_checker_opa_integration.md) |
| ADR-029 | 统一工具注册表架构 | 已接受 | [adr/ADR-029_tool_registry_architecture.md](../07-adr/ADR-029_tool_registry_architecture.md) |
| ADR-050 | OADP 业务语义体系架构 | 已接受 | [adr/ADR-050_OADP业务语义体系架构.md](../07-adr/ADR-050_OADP业务语义体系架构.md) |
| ADR-051 | 闭环反馈机制设计 | 已接受 | [adr/ADR-051_闭环反馈机制设计.md](../07-adr/ADR-051_闭环反馈机制设计.md) |
| ADR-054 | 全链路深度实现设计 v2.3 | 已接受 | adr/ADR-054_full_chain_deep_implementation_v2.3.md |

### 17.2 ADR 分类

**核心基础设施（P0）**：ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006

**前端与交互**：ADR-007, ADR-014, ADR-015, ADR-020

**安全与治理**：ADR-008, ADR-009, ADR-028

**数据与集成**：ADR-012, ADR-013, ADR-018, ADR-036, ADR-022, ADR-026

**平台架构**：ADR-010, ADR-011, ADR-016, ADR-017, ADR-019, ADR-023, ADR-024, ADR-025

**扩展机制**：ADR-027, ADR-029

**业务语义与闭环**：ADR-050, ADR-051, ADR-054

---


## 18. 需求追溯矩阵

### 18.1 硬性需求覆盖表

| # | 硬性需求 | 功能编号 | ADR 决策 | 优先级 |
|---|----------|----------|----------|--------|
| **A** | ⚠️ **通用本体驱动平台（核心定位）** | F-100 | **ADR-024, ADR-023** | P0 |
| **B** | ⚠️ **多工作空间隔离管理** | F-101, F-102 | **ADR-023** | P0 |
| 1 | 角色前端了解领域情况，询问领域信息，skill 可扩展 | F-001, F-030 | ADR-001, ADR-004 | P0 |
| 2 | **模拟领域数据生成功能** | F-060 | **ADR-018** | P0 |
| 3 | **上传外部情报文档（多模态处理）** | F-061 | **ADR-019** | P0 |
| 4 | **管理员管理界面（模拟数据、本体图谱、日志溯源）** | F-070, F-071, F-072, F-073 | **ADR-020** | P0 |
| 5 | 配置界面分组和可视化配置 | F-080 | ADR-010, ADR-011 | P0 |
| 6 | **领域实体本体库（中英文说明）** | F-090 | **ADR-036** | P0 |
| 7 | **模拟数仓与统一查询服务** | F-091 | **ADR-022** | P1 |
| 8 | OPA 策略 Markdown 自动转化 | F-012 | ADR-008 | P0 |
| 9 | 角色管理界面（skill、OPA 策略绑定） | F-010, F-011 | ADR-010, ADR-013 | P0 |
| 10 | Web 前端实时查看领域变化 | F-031 | ADR-006 | P0 |
| 11 | 快速添加信息到问答 | F-033 | ADR-004 | P1 |
| 12 | 审计日志功能（所有操作记录） | F-007, F-072 | ADR-007 | P0 |

### 18.2 功能需求与 ADR 对照

| 功能需求 | 功能编号 | 对应章节 | ADR |
|----------|----------|----------|-----|
| 多 Agent 调度系统 | F-001 | 第8章 | ADR-005 |
| Graphiti 知识图谱 | F-002 | 第5章 | ADR-002 |
| OPA 策略治理 | F-003 | 第7章 | ADR-003 |
| Skill 体系 | F-004 | 第6章 | ADR-004 |
| 角色配置组合 | F-010 | 第14章 | ADR-010, ADR-011 |
| 技能热插拔 | F-011 | 第14章 | ADR-013 |
| 策略 Markdown 编写 | F-012 | 第7章 | ADR-008 |
| 规则引擎 | F-013 | 第14章 | ADR-011 |
| 多数据源接入 | F-020 | 第13章 | ADR-012 |
| 本体构建 | F-021 | 第13章 | ADR-036 |
| 技能绑定 | F-022 | 第13章 | ADR-013 |
| 多 Agent 问答 | F-030 | 第11章 | ADR-005 |
| 图表展示 | F-031 | 第11章 | ADR-015 |
| 图表扩展 | F-032 | 第11章 | ADR-015 |
| 过程可视化 | F-033 | 第11章 | ADR-006 |
| 完备文档体系 | F-040 | 第19章 | ADR-016 |
| 原子提交规范 | F-050 | 第16章 | ADR-017 |
| 模拟领域数据 | F-060 | 第12章 | ADR-018 |
| 多模态文档处理 | F-061 | 第13章 | ADR-019 |
| 管理员控制台 | F-070 | 第12章 | ADR-020 |
| 本体图谱可视化 | F-071 | 第13章 | ADR-020 |
| 日志溯源 | F-072 | 第15章 | ADR-007 |
| 本体手动编辑 | F-073 | 第13章 | ADR-020 |
| 平台配置中心 | F-080 | 第16章 | ADR-011 |
| 领域实体本体库 | F-090 | 第13章 | ADR-036 |
| 模拟数仓 | F-091 | 第13章 | ADR-022 |
| **工作空间管理** | **F-100** | **第13章** | **ADR-023** |
| **工作空间隔离** | **F-101** | **第13章** | **ADR-023** |
| **本体驱动核心** | **F-102** | **第13章** | **ADR-024** |

### 18.3 ADR 与功能需求反向追溯

| ADR | 决策标题 | 支持的功能需求 |
|-----|----------|----------------|
| ADR-001 | OpenHarness 作为 Agent 基础设施 | F-001 |
| ADR-002 | Graphiti 作为双时态知识图谱 | F-002, F-021 |
| ADR-003 | OPA 作为策略治理引擎 | F-003, F-012 |
| ADR-004 | Skill 双层并行策略 | F-004, F-011, F-033 |
| ADR-005 | 三 Agent 角色分工 | F-001, F-030 |
| ADR-006 | OpenHarness 复用策略 | 架构设计 |
| ADR-007 | 前端 React + Ant Design | F-033 |
| ADR-008 | 审计日志完整记录 | F-007, F-072 |
| ADR-009 | Markdown 编写 OPA 策略 | F-012 |
| ADR-010 | 多模态文档处理可配置 | F-061 |
| ADR-011 | 角色配置热生效 | F-010 |
| ADR-012 | 配置组合引擎 | F-010, F-013, F-080 |
| ADR-013 | 多数据源统一接入 | F-020 |
| ADR-014 | 技能热插拔架构 | F-011, F-022 |
| ADR-015 | 可扩展图表系统 | F-031, F-032 |
| ADR-016 | 完备文档体系 | F-040 |
| ADR-017 | 原子提交规范 | F-050 |
| ADR-018 | 模拟领域数据生成引擎 | F-060 |
| ADR-019 | 多模态文档处理流水线 | F-061 |
| ADR-020 | 管理员控制台统一界面 | F-070, F-071, F-073 |
| ADR-036 | 领域实体标准本体库 | F-021, F-090 |
| ADR-022 | 模拟数仓与统一查询服务 | F-091 |
| ADR-023 | 多工作空间隔离架构 | F-100, F-101, F-102 |
| ADR-024 | 本体驱动分析核心架构 | F-100, F-102 |

### 18.4 优先级矩阵

```
                    高业务价值
                         │
     ┌───────────────────┼───────────────────┐
     │                   │                   │
     │   紧急且重要       │   重要不紧急       │
     │   (P0)           │   (P1)           │
     │                   │                   │
低───┼───────────────────┼───────────────────┼────高
技───┤                   │                   │    术
术───┤   应急补丁         │   技术债务         │    风
复───┤   (临时方案)       │   (规划解决)       │    险
杂────┴───────────────────┴───────────────────┘
度
                         │
                    低业务价值
```

| 象限 | 需求 | 策略 |
|------|------|------|
| P0 (紧急+重要) | F-001~F-005, F-007, F-010~F-012, F-030~F-031, F-060~F-061, F-070~F-073, F-090 | 立即实施 |
| P1 (重要不紧急) | F-013, F-020~F-022, F-032~F-033, F-091 | 规划迭代 |
| P2 (技术债务) | F-040, F-050, F-080 | 持续改进 |

### 18.5 需求状态跟踪

| 功能编号 | 需求描述 | 状态 | 迭代 |
|----------|----------|------|------|
| F-001 | 多 Agent 调度系统 | ✅ 已实现 | Phase 1 |
| F-002 | Graphiti 知识图谱 | ✅ 已实现 | Phase 0 |
| F-003 | OPA 策略治理 | ✅ 已实现 | Phase 0 |
| F-004 | Skill 体系 | ✅ 已实现 | Phase 1 |
| F-007 | 审计日志功能 | ✅ 已实现 | Phase 1 |
| F-010 | 角色配置组合 | ✅ 已实现 | Phase 2 |
| F-011 | 技能热插拔 | ✅ 已实现 | Phase 2 |
| F-012 | 策略 Markdown 编写 | ✅ 已实现 | Phase 1 |
| F-013 | 规则引擎 | ✅ 已实现 | Phase 2 |
| F-020 | 多数据源接入 | ✅ 已实现 | Phase 2 |
| F-021 | 本体构建 | ✅ 已实现 | Phase 0 |
| F-022 | 技能绑定 | ✅ 已实现 | Phase 2 |
| F-030 | 多 Agent 问答 | ✅ 已实现 | Phase 1 |
| F-031 | 图表展示 | ✅ 已实现 | Phase 1 |
| F-032 | 图表扩展 | ✅ 已实现 | Phase 2 |
| F-033 | 过程可视化 | ✅ 已实现 | Phase 2 |
| F-040 | 完备文档体系 | ✅ 已实现 | Phase 3 |
| F-050 | 原子提交规范 | ✅ 已建立 | Phase 0 |
| F-060 | 模拟领域数据 | ✅ 已实现 | Phase 1 |
| F-061 | 多模态文档处理 | ✅ 已实现 | Phase 2 |
| F-070 | 管理员控制台 | ✅ 已实现 | Phase 2 |
| F-071 | 本体图谱可视化 | ✅ 已实现 | Phase 2 |
| F-072 | 日志溯源 | ✅ 已实现 | Phase 2 |
| F-073 | 本体手动编辑 | ✅ 已实现 | Phase 2 |
| F-080 | 平台配置中心 | ✅ 已实现 | Phase 1 |
| F-090 | 领域实体本体库 | ✅ 已实现 | Phase 0 |
| F-091 | 模拟数仓 | ✅ 已实现 | Phase 2 |

---


## 19. 演进路线图

### Phase 0: 基础设施搭建（2-4 周）✅ 已完成

```
完成: 搭建开发环境，验证核心组件集成
```

| 任务 | 时间 | 负责人 |
|------|------|--------|
| OpenHarness 安装配置 | Week 1 | 架构师 |
| Graphiti + Neo4j 集成 | Week 1 | 开发者A |
| OPA 服务部署 + 基础策略 | Week 2 | 开发者B |
| Skills 原生 Tool 接入 | Week 2 | 开发者A |
| Python Skills → Tool 桥接 | Week 3 | 开发者B |
| 单元测试覆盖 (>80%) | Week 4 | 全员 |

**验收标准**:
- `oh` CLI 可正常运行
- Graphiti 可写入/查询 Episode
- OPA 可执行基础策略检查
- 至少 3 个 Python Skills 可通过 OpenHarness 调用

---

### Phase 1: 单 Agent 闭环（1-2 月）✅ 已完成

```
完成: Intelligence Agent 独立完成 Observe + Orient
```

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Phase 1: 单 Agent 闭环                             │
└────────────────────────────────────────────────────────────────────────┘

Week 5-6   Intelligence Agent 开发
            ├─ radar_search Skill
            ├─ drone_surveillance Skill
            ├─ threat_assessment Skill
            └─ 单 Agent 测试

Week 7-8   Graphiti RAG 增强
            ├─ 情报文本向量化
            ├─ 历史模式匹配
            └─ RAG 增强推理

Week 9-10  工具链完善
            ├─ MCP 接入领域仿真器
            ├─ 可视化组件
            └─ 日志/追踪集成

Week 11-12 Demo: "分析 B 区威胁"
            └─ Intelligence Agent 独立输出威胁报告
```

**验收标准**:
- 用户输入 "分析 B 区威胁" → Intelligence Agent 输出结构化威胁报告
- 响应时间 < 10 秒
- 威胁识别准确率 > 85%（基于测试集）

---

### Phase 2: 三 Agent 协同（2-3 月）✅ 已完成

```
完成: Commander + Operations Agent 加入，完成 OODA 闭环
```

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Phase 2: 三 Agent 协同                             │
└────────────────────────────────────────────────────────────────────────┘

Week 13-14 Commander Agent 开发
            ├─ 方案生成 + 排序
            ├─ OPA 集成
            └─ 人工确认机制

Week 15-16 Operations Agent 开发
            ├─ attack_target Skill
            ├─ command_unit Skill
            └─ 执行状态监控

Week 17-18 Swarm 协调集成
            ├─ OpenHarness Swarm 配置
            ├─ Agent 间通信协议
            └─ 错误处理 + 回滚

Week 19-20 完整 OODA 闭环测试
            ├─ 感知→理解→决策→行动
            ├─ Graphiti 回写验证
            └─ 人工介入点测试

Week 21-24 性能优化 + 文档
            ├─ 并发优化
            ├─ 可观测性完善
            └─ 用户文档 + API 文档
```

**验收标准**:
- 完整 OODA 流程端到端 < 30 秒
- OPA 策略覆盖率 > 90%
- 三 Agent 协作成功率 > 95%

---

### Phase 3: 生产化（3-6 月）✅ 已完成

```
完成: 生产级部署，高可用，可观测
```

| 里程碑 | 内容 |
|--------|------|
| M1 (Month 3) | Docker Compose 部署，监控告警 |
| M2 (Month 4) | 多租户支持，权限细化 |
| M3 (Month 5) | 高可用架构（主备切换） |
| M4-M6 (Month 6) | 性能调优，容量规划 |

---

### Phase 4: 高级特性（6-12 月）🔄 进行中

```
目标: 地理空间层、多模态情报、领域数字孪生 + Palantir 架构对齐
```

| 功能 | 描述 | 状态 |
|------|------|------|
| 地理空间层 | 领域态势地图，实时位置追踪 | ✅ 已实现 (Leaflet) |
| 多模态情报 | 图像识别、语音指令 | ⬜ 待实现 |
| 领域数字孪生 | 3D 领域仿真 | ⬜ 待实现 |
| **OMS 本体元数据服务** | 对象类型/动作类型/链接关系运行时管理 (ADR-036) | ✅ 已实现 |
| **OSv2 对象虚拟化层** | 逻辑统一、物理解耦的对象访问层 | ✅ 已实现 |
| **Action Service 动势层** | OADP 闭环 Perform 阶段，动作生命周期管理 | ✅ 已实现 |
| **Feedback Loop 反馈闭环** | 三层反馈架构 (ADR-051)，执行结果自动回流 | ✅ 已实现 |
| **Semantic Retriever** | 从"找文本"到"找对象"的语义检索升级 | ✅ 已实现 |
| **Pipeline 增强** | ActionType 感知抽取 + 实体类型自动注册 OMS | ✅ 已实现 |
| **前端 Action 面板** | 动作管理 UI + OMS/Action API 集成 | ✅ 已实现 |

---


## A. 文件结构

> **注意**: 本文档描述实际项目结构（2026-05-19更新）。

```
apps/api/odap/                                  # Python 主包
│
├── __init__.py
├── celery_app.py                      # Celery 应用配置
├── tasks.py                           # 异步任务定义
│
├── infra/                            # 【L1 基础设施层】— 无业务逻辑
│   ├── graph/                        #   图谱服务（Neo4j + Graphiti）
│   ├── llm/                          #   LLM 服务（ZhipuAI 等）
│   ├── opa/                          #   OPA 策略引擎 (v1 + v2 ABAC)
│   ├── events/                       #   事件/Hook 系统
│   ├── object_service/               #   【v5.0新增】对象虚拟化层 (OSv2)
│   │   ├── schemas.py                #     ObjectQuery/SemanticQuery 数据模型
│   │   ├── object_service.py         #     多源联邦查询 + 链接遍历
│   │   └── routes.py                 #     FastAPI 路由
│   ├── resilience/                   #   韧性（容错 + 健康监控）
│   ├── config/                       #   全局配置
│   ├── security/                     #   安全工具
│   └── monitoring/                   #   监控和指标
│
├── tools/                            # 【L2 领域工具层】— 可插拔 Skill
│   ├── base.py                       #   BaseSkill / SkillInput / SkillOutput
│   ├── registry.py                   #   SkillRegistry / register_skill
│   ├── intelligence/                 #   情报工具
│   ├── operations/                   #   操作工具
│   ├── analysis/                     #   分析工具
│   ├── planning/                     #   规划工具
│   ├── recommendation/               #   决策推荐工具
│   ├── policy/                       #   策略工具
│   ├── computation/                  #   计算工具
│   ├── task_management/              #   任务管理工具
│   └── visualization/                #   可视化工具
│
├── biz/                              # 【L3-L4 业务领域层】— 核心业务模块
│   ├── ontology/                     #   本体管理（图谱 CRUD + 版本 + 热写入）
│   │   ├── schema/                   #     OntologyDocument + 领域模型
│   │   ├── oms/                      #     【v5.0新增】本体元数据服务 (OMS)
│   │   │   ├── schemas.py            #       ObjectTypeDefinition/ActionTypeDefinition
│   │   │   ├── storage/              #       SQLite OMS 存储 + ADR-036 种子数据
│   │   │   └── routes.py             #       OMS API 路由
│   │   ├── service.py                #     OntologyManager（对外 API）
│   │   ├── hot_write.py              #     热写入管道
│   │   ├── version_manager.py        #     版本管理
│   │   └── ingestion.py              #     数据采集
│   │
│   ├── workspace/                    #   工作空间管理
│   │   ├── manager.py                #     WorkspaceManager
│   │   ├── api/                     #     API路由
│   │   ├── impl/                    #     实现
│   │   ├── interfaces/              #     接口定义
│   │   ├── models/                  #     数据模型
│   │   ├── services/                #     业务服务
│   │   └── storage/                 #     存储层
│   │
│   ├── agent/                        #   Agent 协同（OADP 三角色）
│   │   ├── swarm_orchestrator.py     #     DomainSwarm 编排器
│   │   ├── intelligence_agent.py     #     Intelligence Agent
│   │   ├── commander.py              #     Commander Agent
│   │   ├── operations_agent.py       #     Operations Agent
│   │   ├── collector.py              #     情报采集器
│   │   └── recommender.py            #     决策推荐器
│   │
│   ├── action_service/               #   【v5.0新增】动作服务层 (Kinetic Layer)
│   │   ├── schemas.py                #     ActionRequest/ActionRecord/ActionExecutionResult
│   │   ├── executor.py               #     核心执行引擎（校验→OPA→执行→写回→反馈）
│   │   ├── feedback_loop.py          #     三层反馈回路 (ADR-051)
│   │   ├── storage/                  #     SQLite 动作记录存储
│   │   └── routes.py                 #     Action API 路由
│   │
│   ├── event_simulator/              #   事件模拟器（Phase 4新实现）
│   │   ├── api/                     #     模拟器API
│   │   ├── impl/                    #     模拟器实现
│   │   ├── interfaces/              #     接口定义
│   │   ├── models/                  #     领域模型
│   │   └── services/                #     模拟服务
│   │
│   ├── simulator/                    #   模拟器（遗留/兼容）
│   │   └── api/                     #     模拟器API
│   │
│   ├── mcp_adapter/                  #   MCP 协议适配
│   │   ├── api/                     #     API路由
│   │   ├── impl/                    #     MCP实现
│   │   ├── interfaces/              #     接口定义
│   │   ├── models/                  #     数据模型
│   │   └── services/                #     业务服务
│   │
│   ├── roles/                        #   角色管理
│   │   ├── api/                     #     API路由
│   │   └── storage/                 #     角色存储
│   │
│   ├── cognition/                    #   用户认知引擎（Phase 4-5规划）
│   │   └── user_cognition_engine.py  #     认知推理引擎
│   │
│   ├── decision_recommendation/      #   决策推荐引擎
│   │   ├── engine.py                #     推荐引擎
│   │   ├── models.py                #     推荐模型
│   │   └── tests/                  #     单元测试
│   │
│   ├── frontend_compat/              #   前端兼容层
│   │   └── api/                    #     前端兼容API
│   │
│   ├── hook_system/                  #   Hook系统
│   │   ├── hook_manager_v2.py       #     Hook管理器
│   │   ├── api/                     #     API路由
│   │   ├── impl/                    #     Hook实现
│   │   ├── interfaces/              #     接口定义
│   │   ├── models/                  #     数据模型
│   │   └── services/                #     Hook服务
│   │
│   ├── openharness_agent/            #   OpenHarness Agent适配
│   │   └── api/                    #     Agent API
│   │
│   ├── qa/                          #   问答系统
│   │   └── qa_engine_v2.py          #     QA引擎
│   │
│   ├── skill_system/                 #   Skill系统管理
│   │   ├── api/                     #     API路由
│   │   ├── impl/                    #     Skill实现
│   │   ├── interfaces/              #     接口定义
│   │   ├── models/                  #     数据模型
│   │   ├── registry/                #     Skill注册表
│   │   └── services/                #     Skill服务
│   │
│   ├── tool_registry/                #   工具注册表
│   │   ├── registry.py              #     工具注册表
│   │   └── api/                    #     API路由
│   │
│   └── visualization/                #   可视化业务层
│       └── visualization_engine_v2.py  #   可视化引擎
│
├── web/                              # 【Web 服务层】
│   ├── api/                          #   REST 路由
│   │   ├── app.py                    #     FastAPI 应用
│   │   ├── router_ontology.py        #     /api/v1/ontology/*
│   │   ├── router_simulator.py       #     /api/v1/simulator/*
│   │   ├── router_agent.py           #     /api/v1/agent/*
│   │   ├── router_workspace.py      #     /api/v1/workspace/*
│   │   └── router_system.py          #     /api/v1/system/*
│   ├── ws/                           #   WebSocket
│   └── static/                       #   前端 SPA
│
├── storage/                          # 【数据存储层】
│   ├── scenarios/                    #   场景数据
│   ├── versions/                     #   本体版本
│   ├── states/                       #   Agent 状态
│   └── exports/                      #   导出文件
│
├── utils/                            # 工具函数
└── gateway/                          # API 网关

openharness/                          # OpenHarness 子模块（Agent 基础设施）

apps/web/                             # 前端（React + TypeScript + Vite）
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   └── utils/
├── public/
└── dist/

docs/                                 # 文档
├── architecture/                      #   架构文档
├── adr/                              #   架构决策记录（48个ADR）
├── modules/                          #   模块设计文档
└── ...

assets/                               # 静态资源
docker/                               # 容器化配置
scripts/                              # 运维脚本
tests/                                # 测试套件
├── unit/
├── integration/
└── manual/
```

**依赖方向**:
```
web/    → biz/ → tools/ → infra/
           biz/ → infra/
           gateway/ → biz/, infra/
```


## B. 环境变量

```bash
# OpenAI / Anthropic
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# OPA
OPA_URL=http://localhost:8181

# OpenHarness
OH_MODEL=claude-3-5-sonnet
OH_PERMISSION_MODE=default

# LLM（扩展）
ZHIPU_API_KEY=...
SILICONFLOW_API_KEY=...
TAVILY_API_KEY=...
```
