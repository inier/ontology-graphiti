# Implementation Plan: Hyper-Extract 启用 + 抽取校验完整链路

**Branch**: `006-he-extraction-chain` | **Date**: 2026-07-11 | **Spec**: [spec.md](file:///e:/DEMO/AI/ontology-graphiti/specs/006-he-extraction-chain/spec.md)
**Input**: Feature specification from `specs/006-he-extraction-chain/spec.md`

## Summary

启用 Hyper-Extract (HE) 包并构建生产级抽取校验完整链路：模板试抽评分 → 多模板互补抽取 → LLM 补充 → 4 维校验 → 双通道写入。合并两套重复的 HEAdapter 为唯一规范实现，删除所有伪实现/桩代码，重建 Docker 镜像安装 HE 及依赖。技术路径为统一重构 (Approach 2)：新建 TemplateEngine + ValidationEngine + SqliteTemplateStorage 三个核心组件，修复 data/hyper_extract/impl/he_adapter.py（API 对齐 + 补全缺失方法），重写 ExtractService 编排逻辑，将 ontology/extraction 降级为薄委托层。

## Technical Context

**Language/Version**: Python 3.11 (Docker `python:3.11-slim`，满足 HE `requires-python >= 3.11`)
**Primary Dependencies**: FastAPI, Pydantic v2, Graphiti, Neo4j Driver, Hyper-Extract (langchain>=1.2.6, faiss-cpu, ontomem>=0.2.3, ontosight>=0.1.8, semhash, structlog)
**Storage**: SQLite (会话/模板元数据/溯源), Neo4j (图数据), MinIO (文档), YAML 文件 (HE 模板落盘)
**Testing**: pytest (单元测试 + @pytest.mark.integration 集成测试)
**Target Platform**: Docker 容器 (Podman 运行)，Linux 服务器部署
**Project Type**: web-service (FastAPI 后端，REST API)
**Performance Goals**: 模板评估 5 候选试抽 ≤ 30 秒；多模板抽取并发 ≤ 3
**Constraints**: 生产级实现，不偷懒、不伪实现、不简化；HE 不可用时明确错误禁止静默 fallback；API 路径与响应结构不变

## Constitution Check

*GATE: Must pass before proceeding. Re-check after design phase.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. 简单 | PASS | 每个新组件单一职责：TemplateEngine 管模板生命周期，ValidationEngine 管校验，HEAdapter 管 HE API 封装。函数拆分到 40 行以内 |
| II. 可维护 | PASS | 合并两套 adapter 为唯一规范实现，消除歧义。模块依赖单向：storage ← impl ← services ← api。配置集中通过 `get_config()` |
| III. 测试优先 | PASS | 6 个单元测试文件 + 3 个集成测试。新组件全部 TDD：先写测试定义接口行为，再实现。Mock 策略明确（Mock Template.create/ka.parse，不真实调 LLM） |
| IV. 避免过度设计 | PASS (post-design) | 设计阶段后确认复杂度必要：4 维校验每维度有独立方法签名（contracts/validation-engine.md）；多模板互补算法明确（贪心集合覆盖，contracts/template-engine.md）；沉淀复用生命周期有状态图（data-model.md）。所有复杂度追溯到具体 FR 和用户需求 |

### Post-Design Re-evaluation

设计产物完成后（research.md + data-model.md + contracts/ + quickstart.md），重新评估宪法合规：
- **I. 简单**: contracts 定义清晰接口，每方法职责单一，无过度抽象 ✓
- **II. 可维护**: 模块边界通过 contracts 明确，依赖方向单向，无循环依赖 ✓
- **III. 测试优先**: TDD 要求 + 测试文件清单已定义，mock 策略明确 ✓
- **IV. 避免过度设计**: 复杂度通过 Complexity Tracking 表证明必要，每项有用户需求支撑 ✓

## Project Structure

### Documentation (this feature)

```text
specs/006-he-extraction-chain/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: 技术调研（HE API、模板规范、依赖验证）
├── data-model.md        # Phase 1: 数据模型（HETemplate、ValidationReport、ExtractionSession 增强）
├── quickstart.md        # Phase 1: 快速验证指南
└── contracts/           # Phase 1: 接口契约
    ├── he-adapter.md     # HEAdapter 完整接口
    ├── template-engine.md # TemplateEngine 完整接口
    └── validation-engine.md # ValidationEngine 完整接口
```

### Source Code (repository root)

```text
odap/biz/data/hyper_extract/  (SP1 规范位置 — 唯一抽取实现)
├── api/
│   └── routes.py                    # 现有, 保留
├── impl/
│   ├── he_adapter.py                # 修复: get_config import + 补全 parse_batch/merge_results/trial_extract
│   ├── ontology_mapper.py           # 迁移自 ontology/extraction + 增强: 多模板结果合并映射
│   ├── dual_channel_writer.py       # 现有, 复用
│   └── provenance_tracker.py        # 迁移自 ontology/extraction + 增强: 新增 source_template 字段
├── services/
│   ├── extract_service.py           # 重写编排: 模板评估→多模板抽取→LLM补充→校验→写入
│   ├── template_engine.py           # 新: 试抽评分 + 30+预设动态枚举 + 自定义生成 + 沉淀复用
│   └── validation_engine.py         # 新: 4 维校验
└── storage/
    └── sqlite_template_storage.py   # 新: HE 模板持久化 (he_templates 表)

odap/biz/core/ontology/extraction/  (降级为薄编排层)
├── api/routes.py                    # 现有, 保留
├── services/extraction_service.py   # 改为委托 data/hyper_extract.ExtractService
│                                    # 保留: _detect_conflicts, confirm_extraction, session 管理
└── impl/
    └── document_parser.py           # 保留 (文档解析功能不变)
    # 删除: he_adapter.py, template_generator.py, ontology_mapper.py, provenance_tracker.py

tests/
├── unit/
│   ├── test_he_adapter.py           # 新: is_available, parse, trial_extract, evolve, merge_results
│   ├── test_template_engine.py      # 新: list_presets, assess, select_complementary, generate_custom, settle
│   ├── test_validation_engine.py    # 新: 4 维校验全路径
│   ├── test_sqlite_template_storage.py # 新: CRUD + 去重 + usage_count
│   ├── test_ontology_mapper.py      # 新: 多模板结果合并 → 5 类映射
│   └── test_extract_service.py      # 新: 3 入口编排 + 降级路径
└── integration/
    ├── test_he_real_extraction.py   # 新: 真实 HE + LLM 端到端
    ├── test_template_settle_reuse.py # 新: 沉淀复用
    └── test_dual_channel_write.py   # 新: confirm_extraction 双通道写入
```

**Structure Decision**: 采用 Approach 2 统一重构。`biz/data/hyper_extract/` 作为唯一抽取实现位置（data 域负责数据加工），`biz/core/ontology/extraction/` 降级为薄编排层（保留 session/conflict/confirm 逻辑，委托抽取给 data 域）。理由：data/hyper_extract/impl/he_adapter.py 的 API kwarg 名已正确（`llm_client=`/`embedder=`），且 data 域语义上负责数据加工。

## Execution Strategy

### TDD Requirements

- [ ] **HEAdapter**: 核心适配器，需 TDD——Mock Template.create/ka.parse 验证调用参数正确性，确保不再有 kwarg 名错误
- [ ] **TemplateEngine.assess()**: 评分逻辑复杂（加权公式 + 语义预筛选 + 试抽），需 TDD——先定义评分公式测试用例
- [ ] **TemplateEngine.select_complementary()**: 贪心集合覆盖算法，需 TDD——边界用例（空候选/单模板全覆盖/无法覆盖）
- [ ] **ValidationEngine**: 4 维校验逻辑密集，需 TDD——每维度独立测试 + 边界（空结果/全违规/全通过）
- [ ] **SqliteTemplateStorage**: 持久化层，需 TDD——tmp_path 真实 DB，验证 CRUD + UNIQUE 约束 + usage_count 递增

### Parallel Execution Opportunities

- [ ] **TemplateEngine** 和 **ValidationEngine** 无共享文件或依赖，可并行开发
- [ ] **SqliteTemplateStorage** 和 **HEAdapter 修复** 可并行（HEAdapter 不依赖 storage）
- [ ] **OntologyMapper 增强** 可在 TemplateEngine 完成后并行（mapper 需要理解多模板结果格式但不需要 engine 实例）

### Human Checkpoints

1. HE 安装验证 — 重建镜像后验证 `Template.list()` 返回 30+ 预设，`HEAdapter.is_available()` 返回 True
2. TemplateEngine + ValidationEngine 完成 — 验证评分逻辑和校验报告正确
3. ExtractService 编排完成 — 验证 3 入口端到端流程
4. 死代码删除前 — 确认无引用残留
5. 集成测试 — 需 Neo4j + OPENAI_API_KEY 环境

### Review Gates

- [ ] **HEAdapter 接口**: Review before implementing TemplateEngine（TemplateEngine 依赖 HEAdapter.trial_extract）
- [ ] **TemplateEngine 接口**: Review before implementing ExtractService（ExtractService 依赖 assess/select_complementary）
- [ ] **数据模型变更**: Review he_templates 表 schema 和 ExtractionSession 增强字段 before migration
- [ ] **删除死代码**: Review 引用扫描结果 before deletion

## Complexity Tracking

> Constitution Check IV (避免过度设计) 标记为 NEEDS ATTENTION，以下说明复杂性必要性

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 4 维校验（而非简化为 1-2 维） | 用户明确要求"不能简化"，且生产级抽取质量保障需要多维度检查 | 单维校验无法捕获字段缺失、悬空关系、低置信度等不同类型问题 |
| 多模板互补抽取（而非单模板） | 单模板无法覆盖 ODAP 5 类产出（对象/关系/规则/动作/过程），HE 预设模板各有侧重 | 单模板抽取在规则/动作类别上结果为空，需 LLM 兜底，质量不可控 |
| 模板沉淀复用机制 | 避免对同一本体重复评估和生成，控制 LLM 调用成本 | 每次抽取都全量试抽 30+ 模板，成本和耗时不可接受 |

## Phase Summary

### Phase 0: Research (research.md)

调研并确认：
1. HE 真实 API 表面（Template.create/list/get 签名、AutoType.parse/evolve/dump_dict 签名、原生合并 API 是否存在）
2. HE YAML 模板规范（node_schema/edge_schema/identifiers 字段格式，供 generate_custom 的 LLM prompt 使用）
3. ontomem/ontosight 依赖的 PyPI 可用性（是否需配置镜像源或离线 wheel）
4. `get_config` 正确 import 路径（`from odap.infra.config_composer import get_config`，非 `odap.infra.config`）
5. HE create_llm/create_embedder 从 ODAP env 注入的配置项映射

### Phase 1: Design & Contracts (data-model.md, contracts/, quickstart.md)

1. **data-model.md**: HETemplate 实体（含 source/yaml_path/score/coverage/usage_count 字段）、ValidationReport 结构（4 维 + needs_review）、ExtractionSession 增强（validation_report/template_assessment/degradation_flags）、ExtractionProvenance 增强（source_template）
2. **contracts/**: 3 个接口契约文档（HEAdapter/TemplateEngine/ValidationEngine），含方法签名、参数、返回值、异常
3. **quickstart.md**: 重建镜像 + 验证 HE 导入 + 端到端抽取示例

### Phase 2: Tasks (tasks.md)

由 `/speckit-tasks` 生成，按迁移顺序（先建新→修复→改写委托→删死代码→重建镜像）拆分为可独立验证的任务。
