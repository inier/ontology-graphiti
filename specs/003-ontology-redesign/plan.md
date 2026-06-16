# Implementation Plan: 本体设计器彻底重构

**Branch**: `003-ontology-redesign` | **Date**: 2026-06-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-ontology-redesign/spec.md`

## Summary

彻底重构本体设计能力，统一三套数据模型为两层架构（Schema层+Instance层），支持三种本体设计方式（手工定义、数据库抽取、自然语言提取），实现结构与实例数据统一，增强图谱交互和版本管理。

## Technical Context

**Language/Version**: Python 3.10+ (后端), TypeScript 5.x (前端)
**Primary Dependencies**: FastAPI, Pydantic v2, React 19, Ant Design 6, Zustand 5, AntV G6 5.x, SQLAlchemy 2.0 (新增)
**Storage**: SQLite (本体/版本/业务实体), Neo4j (图谱运行时)
**Testing**: pytest (后端), vitest (前端)
**Target Platform**: Web (Podman 容器化部署)
**Project Type**: Web service + SPA
**Performance Goals**: 图谱 100 节点/200 边流畅渲染, 版本回滚 < 3s, NL 提取 < 30s
**Constraints**: 单用户编辑场景, 数据库连接需网络可达, LLM 服务需可用

## Constitution Check

*GATE: Must pass before proceeding. Re-check after design phase.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. 简单 | PASS | 统一三套模型为一套，消除同名类冲突，降低理解成本 |
| II. 可维护 | PASS | Schema层与Instance层分离，模块间依赖单向，API按领域注册 |
| III. 测试优先 | PASS | 核心逻辑（模型映射、版本管理、冲突检测）需TDD |
| IV. 避免过度设计 | PASS | 复用现有GraphCanvas/VersionManager/IngestService，不重新开发 |
| Security Boundaries | PASS | 数据库连接密码加密存储，抽取使用只读用户，API需认证 |
| G-1 (Given/When/Then) | PASS | Spec中所有Acceptance Scenarios使用G/W/T格式 |
| G-4 (任务1日内完成) | PASS | 任务拆分见tasks.md |
| G-7 (路由异常测试) | NEEDS ATTENTION | 新增路由需配套异常处理测试 |
| G-10 (pytest零失败) | PASS | 实施完成后必须全绿 |

## Project Structure

### Documentation (this feature)

```text
specs/003-ontology-redesign/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Technical research
├── data-model.md        # Data model design
├── quickstart.md        # Quick verification guide
├── contracts/
│   └── api-contracts.md # API endpoint contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
odap/biz/core/ontology/
├── design/
│   ├── model/                          # 现有: 逐步废弃，迁移到统一模型
│   ├── schema/                         # 现有: ADR-032 Instance层，保持不变
│   ├── ingestion_split/
│   │   ├── ingestion.py                # 现有: NewsIngester, ManualInputHandler
│   │   └── db_schema_ingester.py       # 新增: 数据库Schema抽取器
│   ├── services/
│   │   ├── version_service.py          # 现有: 版本管理，增强
│   │   └── ingest_service.py           # 现有: 摄入服务，扩展
│   └── extraction/                     # 新增: 抽取模块
│       ├── api/
│       │   └── routes.py               # 新增: 抽取API路由
│       ├── services/
│       │   └── extraction_service.py   # 新增: 抽取编排服务
│       └── models/
│           └── schemas.py              # 新增: 抽取请求/响应模型
├── application/oms/
│   └── schemas.py                      # 现有: 统一Schema层模型，增强
└── ontology_api/                       # 新增: 统一本体API
    ├── api/
    │   └── routes.py                   # 新增: 本体CRUD+图谱API
    ├── services/
    │   └── ontology_service.py         # 新增: 本体编排服务
    └── storage/
        └── sqlite_ontology_storage.py  # 新增: 本体SQLite存储

odap/biz/management/business/
├── storage/
│   └── sqlite_storage.py               # 现有: 扩展is_schema字段
└── api/
    └── routes.py                       # 现有: 扩展Schema API端点

frontend/src/modules/
├── ontology/
│   ├── pages/
│   │   ├── OntologyDesignerPage.tsx    # 现有: 重构
│   │   └── OntologyGraphPage.tsx       # 新增: 独立图谱页面
│   ├── components/
│   │   ├── OntologySelector.tsx        # 新增: 本体选择器
│   │   ├── DesignMethodSelector.tsx    # 新增: 设计方式选择
│   │   ├── DatabaseExtractor.tsx       # 新增: 数据库抽取UI
│   │   ├── NLExtractor.tsx             # 新增: 自然语言提取UI
│   │   ├── ExtractionPreview.tsx       # 新增: 抽取结果预览
│   │   ├── GraphCanvas.tsx             # 现有: 增强编辑交互
│   │   └── NodeEdgeEditor.tsx          # 新增: 节点/边编辑面板
│   ├── stores/
│   │   └── ontologyStore.ts            # 现有: 重构
│   └── services/
│       └── ontologyApi.ts              # 现有: 扩展API
└── business/
    ├── services/
    │   └── businessApi.ts              # 现有: 扩展Schema查询
    └── types.ts                        # 现有: 补全ontology_id/version_id

tests/unit/
├── test_ontology_service.py            # 新增
├── test_ontology_storage.py            # 新增
├── test_db_schema_ingester.py          # 新增
├── test_extraction_service.py          # 新增
└── test_route_exception_handling.py    # 现有: 扩展
```

**Structure Decision**: 新增 `ontology_api/` 子模块作为统一入口，遵循 AGENTS.md 的 biz 模块分层规范（api/services/impl/storage）。抽取功能独立为 `extraction/` 子模块，与现有 `ingestion_split/` 平级。

## Execution Strategy

### TDD Requirements

- [ ] **ontology_service.py**: 本体CRUD+版本管理的核心业务逻辑，多状态转换和边界条件
- [ ] **db_schema_ingester.py**: 数据库Schema到本体模型的映射逻辑，类型转换和冲突检测
- [ ] **extraction_service.py**: 抽取会话生命周期管理，冲突合并策略
- [ ] **sqlite_ontology_storage.py**: 存储层CRUD，JSON序列化/反序列化

### Parallel Execution Opportunities

- [ ] 后端本体CRUD模块（ontology_api/）与前端本体选择器组件可并行开发
- [ ] 数据库抽取后端（db_schema_ingester.py）与自然语言提取后端可并行开发
- [ ] 前端图谱增强（NodeEdgeEditor）与前端抽取UI（DatabaseExtractor/NLExtractor）可并行开发
- [ ] 业务实体is_schema扩展与本体CRUD模块可并行开发

### Human Checkpoints

1. **数据模型统一后** — 验证三套模型合并到统一Schema层，OMS API与本体设计器API共享数据
2. **本体选择器完成后** — 验证设计器入口流程：选择本体→选择设计方式→进入设计
3. **数据库抽取完成后** — 验证端到端：连接数据库→抽取Schema→预览编辑→确认导入
4. **结构与实例统一后** — 验证设计器定义的结构在子菜单页面可见，子菜单可创建实例
5. **全部故事完成后** — 运行完整测试套件，验证所有Acceptance Scenarios

### Review Gates

- [ ] **API contracts**: 抽取API和本体CRUD API的请求/响应结构，在实现消费者之前审查
- [ ] **数据模型变更**: 类型定义表新增和schema_type_id引用字段，在存储层实现之前审查
- [ ] **数据库连接安全**: 连接字符串处理、密码加密、只读权限验证

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 新增 sqlalchemy 依赖 | 数据库Schema抽取需要统一抽象层 | 每种数据库单独写原生SQL会导致代码重复和维护成本高 |
| 新增7张类型定义表 | 类型定义与实例数据职责不同，天然分离 | `is_schema` 共享表是一行两义的反模式，违反单一职责 |

### 架构反思记录（2026-06-09 修订）

| 方案 | 原决策 | 修订后 | 修订原因 |
|------|--------|--------|---------|
| R1 模型统一 | 两层模型+映射层 | 一套模型+引用 | 映射层是架构负债，引用关系天然消除转换逻辑 |
| R3 NL提取 | 复用 NewsIngester | 复用 LLM 基础设施，新建 Schema 级提取器 | NewsIngester 输出 Instance 级，与 Schema 级需求不匹配 |
| R4 结构/实例 | is_schema 共享表 | 类型系统分表+schema_type_id 引用 | 共享表一行两义，违反单一职责；类型定义和实例数据生命周期/权限/访问模式均不同 |
| R6 版本管理 | 复用 OntologyVersionManager | Schema 版本与数据版本独立版本链 | 两者频率不同（天级 vs 分钟级），混在一起 Schema 变更历史被淹没 |
