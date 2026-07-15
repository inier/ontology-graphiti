# Feature Specification: Hyper-Extract 启用 + 抽取校验完整链路

**Feature Branch**: `006-he-extraction-chain`

**Created**: 2026-07-11

**Status**: Draft

**Sub-project**: SP1 of the end-to-end platform vision (Approach C 缺口优先序列: SP1 → SP3 → SP2 → SP4 → SP6 → SP5 → SP7)

**Input**: 用户描述端到端平台愿景中"基于数据进行抽取（使用 Hyper-Extract，先评估现有模板是否满足，如果不满足，需要先自定义模板），抽取（对象及属性/关系/规则/动作）抽取完成后的校验和评估"阶段。要求生产级实现，不偷懒、不伪实现、不简化。

## 背景与现状诊断

### 已有资产（可复用）

- `ExtractionService` 3 个抽取入口编排骨架（NL/Document/KB）
- 3 级模板回退骨架（ontology-generated → preset → web-search）
- `confirm_extraction` 双通道写入（Channel A: GraphWriteProxy→Neo4j, Channel B: GraphManager.add_episode→Graphiti）
- `_detect_conflicts` 冲突检测（重名 + Levenshtein 相似度）
- `ProvenanceTracker` 溯源记录
- `OntologyMapper` 的 `map_to_schema` / `map_to_instances`
- `requirements.txt:60` 已声明 `-e ./hyper-extract`
- `Dockerfile:21-22` 已 `COPY hyper-extract ./hyper-extract`
- Docker 镜像基于 `python:3.11-slim`（满足 HE `>=3.11` 要求）

### 伪实现/桩代码清单（必须修复）

| # | 位置 | 问题 |
|---|---|---|
| 1 | `ontology/extraction/impl/he_adapter.py:36-40` | `extract_incremental()` 是空桩，返回 `{"nodes": [], "edges": []}` |
| 2 | `ontology/extraction/impl/he_adapter.py:42-62` | `merge_results()` naive 手工去重，未用 HE 真实合并 API |
| 3 | `ontology/extraction/impl/template_generator.py:75-84` | `generate_with_web_search()` 伪生成——搜索后只选预设，未真正动态生成模板 |
| 4 | `ontology/extraction/impl/template_generator.py:115-127` | `list_all_presets()` 硬编码 10 个，HE 实际有 30+ 预设 |
| 5 | `ontology/extraction/impl/he_adapter.py:27-34` | `extract_from_text()` 只用 `name` 调 `Template.create(name)`，忽略 `node_schema/edge_schema`——本体自定义模板实际未生效；且 kwarg 名错误（`llm=`/`emb=` 应为 `llm_client=`/`embedder=`） |
| 6 | `data/hyper_extract/impl/he_adapter.py:114,122` | `get_config` 未 import，即使 HE 装好也会 NameError |

### 架构问题

- 两套 he_adapter 重复实现（`biz/data/hyper_extract/impl/` 和 `biz/core/ontology/extraction/impl/`），接口不同，实际只有后者被 `ExtractionService` 使用，前者是死代码。
- HE 包未实际安装到运行镜像（镜像未重建），`_HE_AVAILABLE=False`，所有抽取走 `SchemaLevelExtractor` fallback。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 模板评估: 试抽评分 (Priority: P0)

用户提交自然语言文本进行抽取时，系统首先评估现有模板（已沉淀模板、本体生成模板、30+ 预设模板）是否满足抽取需求。评估方式为质量试抽评分：取文本前 ~1500 字符作为样本，对每个候选模板调用 HE 试抽，根据实体数、关系数、字段覆盖率、类型多样性打分排序。评分低于阈值时触发自定义模板生成。

**Why this priority**: 模板评估是整个抽取链路的入口，决定后续抽取质量。当前为伪实现（硬编码选预设），必须最先修复。

**Independent Test**: 给定一段电商业务描述文本，验证系统对 30+ 预设模板试抽后返回带评分的排序列表，且评分逻辑可追溯（每个候选的实体数/关系数/覆盖率可查）。

**Acceptance Scenarios**:

1. **Given** 用户提交抽取请求，**When** 系统进入模板评估阶段，**Then** 系统动态枚举 HE 全部预设模板（非硬编码），返回候选列表含 name/description/domain
2. **Given** 候选模板列表，**When** 系统对每个候选试抽样本文本，**Then** 返回每个候选的评分（实体数 + 关系数 + 字段覆盖率 + 类型多样性加权），结果可追溯
3. **Given** 已有为本体沉淀的模板，**When** 系统评估时，**Then** 沉淀模板优先参与评估且只做轻量验证（不重复全量试抽），usage_count 递增
4. **Given** 所有候选评分低于阈值，**When** 系统判定预设不满足，**Then** 触发自定义模板生成流程

### User Story 2 - 多模板互补抽取 (Priority: P0)

系统根据试抽评分结果，选择多个互补模板组合抽取，覆盖 ODAP 5 类产出（对象及属性/关系/规则/动作/过程）。采用贪心集合覆盖算法：从最高分模板开始，逐步加入覆盖缺失类别且分数最高的模板。信息不足的类别由 LLM 补充抽取。抽取完成后合并多模板结果，经 OntologyMapper 映射到 ODAP 5 类 Schema + Instance。

**Why this priority**: 多模板互补抽取是覆盖 5 类产出的核心机制，单模板无法全覆盖。

**Independent Test**: 给定一段含对象、关系、规则、动作的业务描述，验证系统选择多个模板分别抽取，合并后 5 类产出均有结果，且无重复实体。

**Acceptance Scenarios**:

1. **Given** 评分排序的候选模板 + 本体 Schema，**When** 系统执行互补选择，**Then** 选出的模板组合覆盖 5 类产出，选择过程基于贪心集合覆盖可追溯
2. **Given** 选中的多模板组合，**When** 系统对每个模板执行 `he_adapter.parse(text, template)`，**Then** 各模板结果收集为结果集列表，单模板失败不阻断其他
3. **Given** 多模板结果集，**When** 某些类别（如规则/动作）结果为空或不足，**Then** 系统调用 LLM 从同文本补充抽取缺失类别
4. **Given** 多模板结果 + LLM 补充结果，**When** 系统合并映射，**Then** OntologyMapper 产出 ODAP 5 类 Schema + Instance，无重复实体（按 name 去重）

### User Story 3 - 自定义模板生成与沉淀复用 (Priority: P0)

当预设模板试抽评分不满足时，系统调用 LLM 根据输入文本 + 本体 Schema + 缺失类别生成符合 HE YAML 规范的自定义模板。生成后试抽验证质量，达标则沉淀保存（YAML 文件 + SQLite 元数据），后续对同一本体的抽取优先复用沉淀模板。

**Why this priority**: 沉淀复用机制避免重复评估和生成成本，是生产级抽取的必要能力。

**Independent Test**: 触发自定义生成后，验证 YAML 文件落盘到 `data/he_templates/{ontology_id}/`，SQLite he_templates 表有记录；二次抽取同一本体时复用沉淀模板（usage_count 递增，跳过全量试抽）。

**Acceptance Scenarios**:

1. **Given** 预设不满足 + 输入文本 + 本体 Schema + 缺失类别，**When** 系统调用 LLM 生成 HE YAML 模板，**Then** 生成的 YAML 符合 HE 模板规范（含 node_schema/edge_schema/identifiers）
2. **Given** 生成的 YAML 模板，**When** 系统试抽验证质量，**Then** 评分达标才沉淀；不达标则 LLM 重新生成（最多 2 次），仍失败降级用最佳预设 + 标记 warning
3. **Given** 质量达标的自定义模板，**When** 系统沉淀保存，**Then** YAML 写入 `data/he_templates/{ontology_id}/{name}.yaml`，元数据存入 SQLite he_templates 表
4. **Given** 已沉淀模板，**When** 同一本体再次抽取，**Then** 系统优先复用沉淀模板（get_settled_template），跳过全量试抽，usage_count 递增
5. **Given** 沉淀模板复用时，**When** 系统做轻量验证，**Then** 若沉淀模板评分下降（输入语义变化），重新触发评估

### User Story 4 - 抽取后 4 维校验评估 (Priority: P0)

抽取完成后，系统对结果执行 4 维校验：(1) Schema 一致性——实体字段 vs ObjectType 定义（类型匹配、必填字段已填、无未定义字段）；(2) 完整性——必填字段缺失率、空值率、孤立节点（无关系的实体）；(3) 置信度评分——每个实体/关系打 0-1 分（字段填充率 0.4 + 模板匹配度 0.3 + LLM 一致性 0.3）；(4) 引用一致性——关系引用实体是否存在、动作目标类型是否已定义、规则引用对象是否已定义。校验报告写入 ExtractionSession，低于阈值的实体标记 needs_review，用户须确认/修正后才允许 confirm。

**Why this priority**: 校验评估是抽取质量的保障，当前仅有冲突检测，4 维校验是生产级必备。

**Independent Test**: 给定抽取结果含字段缺失、孤立节点、悬空关系，验证 4 维校验报告正确标识所有问题项，且 needs_review 列表包含低置信度实体。

**Acceptance Scenarios**:

1. **Given** 抽取结果 + 本体 Schema，**When** 系统执行 Schema 一致性校验，**Then** 返回每个实体的字段违规列表（类型不匹配/必填缺失/未定义字段）
2. **Given** 抽取结果，**When** 系统执行完整性评估，**Then** 返回 fill_rate/empty_rate/orphan_count 及孤立实体列表
3. **Given** 抽取结果 + 模板评分，**When** 系统执行置信度评分，**Then** 每个实体/关系有 0-1 置信度分，低于阈值的列入 needs_review
4. **Given** 抽取结果 + 本体 Schema，**When** 系统执行引用一致性检查，**Then** 返回 dangling_relations（悬空关系）和 invalid_action_targets（无效动作目标）
5. **Given** 4 维校验报告，**When** 报告含 needs_review 项，**Then** confirm_extraction 阶段要求用户逐项确认/修正后才允许写入

### User Story 5 - HE 包安装与真实 API 对齐 (Priority: P0)

重建 Docker 镜像安装 HE 包及依赖（faiss-cpu, langchain>=1.2.6, ontomem, ontosight 等），验证 HE 真实 API 与 adapter 调用对齐。HE 不可用时返回明确错误，不再静默走 SchemaLevelExtractor fallback。

**Why this priority**: HE 包未安装是当前所有抽取走 fallback 的根因，必须最先解除阻塞。

**Independent Test**: 重建镜像后 `podman exec graphiti-main-app python -c "from hyperextract import Template; print(len(Template.list()))"` 返回 30+，且 `HEAdapter.is_available()` 返回 True。

**Acceptance Scenarios**:

1. **Given** requirements.txt 已声明 `-e ./hyper-extract`，**When** 执行 `python bootstep.py rebuild main`，**Then** 镜像构建成功，HE 及全部依赖装入
2. **Given** 重建后的镜像，**When** 验证 HE 导入，**Then** `from hyperextract import Template, AutoGraph, create_llm, create_embedder` 全部成功
3. **Given** HE 已安装，**When** HEAdapter 初始化，**Then** `is_available()` 返回 True，不再走 fallback
4. **Given** HE 未安装/导入失败，**When** 用户发起抽取，**Then** 系统返回明确错误 `{"status":"error","message":"HE未安装，请重建镜像"}`，不静默 fallback
5. **Given** HEAdapter 调用 Template.create，**When** 传入 llm_client/embedder kwarg，**Then** 调用成功（kwarg 名与真实 API 一致）

---

## Requirements *(mandatory)*

### Functional Requirements

**HE 安装与 API 对齐**

- **FR-001**: 系统必须通过重建 Docker 镜像安装 HE 包及全部依赖（faiss-cpu, langchain>=1.2.6, langchain-community, langchain-openai, structlog, ontomem>=0.2.3, ontosight>=0.1.8, python-dotenv, semhash）
- **FR-002**: HEAdapter 必须使用真实 HE API kwarg 名（`llm_client=`/`embedder=`，非 `llm=`/`emb=`）
- **FR-003**: HEAdapter 必须从 ODAP 环境变量（`get_config("llm.api_key")` 等）注入 LLM/Embedder 配置，不另建 `~/.he/config.toml`
- **FR-004**: HE 不可用时系统必须返回明确错误，禁止静默走 SchemaLevelExtractor fallback

**统一 HEAdapter**

- **FR-005**: 系统必须合并两套 he_adapter 为唯一规范实现，位于 `biz/data/hyper_extract/impl/he_adapter.py`
- **FR-006**: HEAdapter.parse() 必须调用 `Template.create(source, language, llm_client=, embedder=)` → `ka.parse(text)` → 标准化结果
- **FR-007**: HEAdapter.evolve() 必须调用真实 `BaseAutoType.evolve(new_text)`，禁止空桩返回
- **FR-008**: HEAdapter.merge_results() 必须优先使用 HE 原生合并 API，无原生 API 时按实体 name + 关系三元组去重合并
- **FR-009**: HEAdapter.trial_extract() 必须取文本前 N 字符试抽，返回实体数/关系数/字段覆盖率供评分
- **FR-010**: 必须删除 `ontology/extraction/impl/he_adapter.py`（死代码）和 `ontology/extraction/impl/template_generator.py`（硬编码伪实现）

**TemplateEngine（试抽评分 + 多模板选择 + 自定义生成 + 沉淀）**

- **FR-011**: TemplateEngine.list_presets() 必须调用 HE 原生 `Template.list()` 动态枚举全部预设（30+），禁止硬编码
- **FR-012**: TemplateEngine.assess() 必须收集候选模板（已沉淀 + 本体生成 + 语义匹配预设），对每个候选调用 trial_extract 试抽，按加权评分排序。候选预筛选：对 30+ 预设先用 embedder 计算文本与模板 description 的余弦相似度取 top-k=5（避免全量试抽成本爆炸），再对 top-k 试抽
- **FR-013**: 评分公式 = 0.3*entity_count + 0.3*relation_count + 0.2*field_coverage + 0.2*type_diversity（归一化到 0-1，阈值默认 0.5，可通过 `he.template_score_threshold` 配置）
- **FR-014**: TemplateEngine.select_complementary() 必须用贪心集合覆盖算法选择多模板组合，覆盖 ODAP 5 类产出
- **FR-015**: TemplateEngine.generate_custom() 必须调用 LLM 生成符合 HE YAML 规范的自定义模板，生成后试抽验证质量
- **FR-016**: 自定义模板生成失败时 LLM 重试最多 2 次，仍失败降级用最佳预设 + 标记 warning
- **FR-017**: TemplateEngine.settle_template() 必须将 YAML 写入 `data/he_templates/{ontology_id}/{name}.yaml` + 元数据存入 SQLite he_templates 表
- **FR-018**: TemplateEngine.get_settled_template() 必须优先返回已沉淀模板，assess() 对已沉淀模板只做轻量验证（仅对样本前 500 字符试抽确认评分≥阈值的 80%，不重复全量试抽）
- **FR-019**: 沉淀模板复用时若轻量验证评分下降到阈值 80% 以下（输入语义漂移），必须重新触发全量评估

**多模板互补抽取 + LLM 补充**

- **FR-020**: ExtractService 必须对选中的多模板组合分别执行 parse()，单模板失败不阻断其他
- **FR-021**: 某些类别（规则/动作等）结果为空或实体数 < 2（不足）时，系统必须调用 LLM 从同文本补充抽取缺失类别
- **FR-022**: OntologyMapper 必须合并多模板结果 + LLM 补充结果，映射到 ODAP 5 类 Schema + Instance，按 name 去重
- **FR-023**: OntologyMapper 必须保留全链路溯源信息（来源模板 + 切片 ID + 提取方法 + 模板版本）

**ValidationEngine（4 维校验）**

- **FR-024**: ValidationEngine 必须执行 Schema 一致性校验：实体字段 vs ObjectType 定义（类型匹配、必填字段已填、无未定义字段）
- **FR-025**: ValidationEngine 必须执行完整性评估：必填字段缺失率、空值率、孤立节点（无关系的实体）
- **FR-026**: ValidationEngine 必须执行置信度评分：每个实体/关系 0-1 分（字段填充率 0.4 + 模板匹配度 0.3 + LLM 一致性 0.3），低于阈值（默认 0.6，可通过 `he.confidence_threshold` 配置）列入 needs_review
- **FR-027**: ValidationEngine 必须执行引用一致性检查：关系引用实体存在、动作目标类型已定义、规则引用对象已定义
- **FR-028**: 校验报告必须写入 ExtractionSession.result_data.validation_report
- **FR-029**: confirm_extraction 阶段必须要求 needs_review 项逐项确认/修正后才允许写入

**模板持久化**

- **FR-030**: 系统必须在 SQLite 新建 he_templates 表（id, ontology_id, name, description, source, yaml_path, preset_name, score, coverage, usage_count, created_at, updated_at, UNIQUE(ontology_id, name)）
- **FR-031**: 自定义/本体生成模板的 YAML 必须落盘到 `data/he_templates/{ontology_id}/{name}.yaml`，可通过 `Template.create(yaml_path, language, llm, emb)` 直接加载

**抽取编排（保留 + 改写）**

- **FR-032**: ExtractService 必须保留 3 个抽取入口（NL/Document/KB）的 session 管理逻辑
- **FR-033**: ExtractService 必须保留 confirm_extraction 的双通道写入（Channel A: GraphWriteProxy→Neo4j, Channel B: GraphManager.add_episode→Graphiti）
- **FR-034**: ExtractService 必须保留 _detect_conflicts 冲突检测
- **FR-035**: `ontology/extraction/services/extraction_service.py` 必须改为委托 `data/hyper_extract.ExtractService`，保留 session/conflict/confirm 薄编排
- **FR-036**: 现有 API 路径与响应结构必须保持不变，前端无需改动

### Key Entities

- **HETemplate**: Hyper-Extract 模板元数据，含 source(preset/ontology_generated/custom)、yaml_path、score、coverage、usage_count，关联到 ontology_id
- **TemplateAssessment**: 模板评估结果，含候选列表 + 评分 + 试抽结果，关联到抽取 session
- **ValidationReport**: 4 维校验报告，含 schema_conformance/completeness/confidence/referential_consistency + needs_review 列表
- **ExtractionSession** (现有,增强): 新增 validation_report 字段、template_assessment 字段、degradation_flags 字段
- **ExtractionProvenance** (现有,增强): 新增 source_template 字段记录来源模板

## Architecture

### 组件架构

```
biz/data/hyper_extract/  (SP1 规范位置 — 唯一抽取实现)
├── api/routes.py                    # 现有, 保留
├── impl/
│   ├── he_adapter.py                # 统一 adapter（修复 API 对齐 + 桩实现补全）
│   ├── ontology_mapper.py           # 迁移+增强: 多模板结果合并映射到 ODAP 5 类
│   ├── dual_channel_writer.py       # 复用现有
│   └── provenance_tracker.py        # 迁移+增强: 新增 source_template
├── services/
│   ├── extract_service.py           # 重写编排: 模板评估→多模板抽取→LLM补充→校验→写入
│   ├── template_engine.py           # 新: 试抽评分 + 30+预设动态枚举 + 自定义生成 + 沉淀复用
│   └── validation_engine.py         # 新: 4 维校验
└── storage/
    └── sqlite_template_storage.py   # 新: 模板持久化

biz/core/ontology/extraction/  (降级为薄编排层)
├── services/extraction_service.py   # 改为委托 data/hyper_extract.ExtractService
│                                    # 保留: _detect_conflicts, confirm_extraction, session 管理
└── impl/                            # 删除 he_adapter.py, template_generator.py
                                     # 迁移 ontology_mapper.py, provenance_tracker.py 到 data 域
                                     # 保留 document_parser.py
```

### 端到端数据流（NL 抽取为例）

1. 输入: text + ontology_id
2. 创建 ExtractionSession (type=natural_language)
3. TemplateEngine.assess(): 取样本 → 收集候选（已沉淀/本体生成/语义匹配预设）→ trial_extract 试抽 → 打分排序
4. 判定: 最高分≥阈值 → select_complementary() 选多模板组合；否则 generate_custom() LLM 生成 → 试抽验证 → 沉淀
5. 多模板互补抽取: 各模板 parse(text) → 结果集列表
6. LLM 补充: 缺失类别（规则/动作等）从同文本补充
7. OntologyMapper.merge_and_map(): 合并多模板结果 → 映射 ODAP 5 类 (object/link/action/rule/process)
8. ValidationEngine.validate(): 4 维校验（Schema 一致性/完整性/置信度/引用一致性）
9. _detect_conflicts: 重名 + 相似度检测（现有）
10. confirm_extraction: 双通道写入 Neo4j + Graphiti（现有, 复用）+ ProvenanceTracker 溯源

### 统一 HEAdapter 接口契约

```python
class HEAdapter:
    def is_available(self) -> bool: ...
    def parse(self, text: str, template_config: Dict) -> Dict[str, Any]: ...
    def parse_batch(self, texts: List[str], template_config: Dict) -> List[Dict]: ...
    def evolve(self, ka_instance, new_text: str) -> Dict: ...
    def merge_results(self, results: List[Dict]) -> Dict: ...
    def trial_extract(self, text: str, template_config: Dict, sample_size: int = 1500) -> Dict: ...
```

关键修复: Template.create() 用 `llm_client=`/`embedder=`；get_config 正确 import；evolve 调真实 BaseAutoType.evolve()；merge_results 优先用 HE 原生合并。

### TemplateEngine 接口契约

```python
class TemplateEngine:
    def list_presets(self) -> List[Dict]: ...           # 动态枚举 30+
    def assess(self, text: str, ontology_id: str) -> Dict: ...  # 试抽评分
    def select_complementary(self, scored: List[Dict], schema: Dict) -> List[Dict]: ...  # 贪心覆盖
    def generate_custom(self, text: str, schema: Dict, gaps: List[str]) -> Optional[Dict]: ...  # LLM 生成
    def settle_template(self, ontology_id: str, config: Dict, yaml: str, score: float) -> str: ...  # 沉淀
    def get_settled_template(self, ontology_id: str) -> Optional[Dict]: ...  # 复用
```

### ValidationEngine 接口契约

```python
class ValidationEngine:
    def validate(self, result: Dict, ontology_schema: Dict, template_scores: Dict) -> Dict: ...
    def _validate_schema(self, result, schema) -> Dict: ...       # Schema 一致性
    def _validate_completeness(self, result) -> Dict: ...          # 完整性
    def _score_confidence(self, result, template_scores) -> Dict:  # 置信度
    def _validate_references(self, result, schema) -> Dict: ...    # 引用一致性
```

## Error Handling & Degradation

| 场景 | 处理 | 对应 EC |
|---|---|---|
| HE 包未安装/导入失败 | 返回明确错误，禁止静默 fallback | EC-008 |
| LLM 超时/不可用 | 试抽阶段该候选评分 0；正式抽取保留已成功部分，session 标记 partial | EC-007 |
| 试抽全部低于阈值 | 触发 generate_custom()；也失败则返回最佳结果 + 低置信度标记 | EC-015 |
| 自定义 YAML 生成失败 | LLM 重试 2 次；仍失败降级用最佳预设 + warning | EC-016 |
| 单模板 parse 抛异常 | 捕获，该模板结果记空，继续其他；至少 1 个成功才继续 | EC-006 |
| merge_results 失败 | 降级手工去重合并 + 降级标记 | EC-017 |
| ValidationEngine 异常 | 校验失败不阻断，返回 status="error"，结果可 confirm 但标记"未校验" | EC-018 |
| ontomem/ontosight 缺失 | HE 导入失败同"HE 未安装"；Dockerfile fail-fast 暴露 | EC-008 |

**关键原则**: 所有降级显式标记（session.degradation_flags），不静默掩盖。前端展示"降级模式"提示。

## Testing Strategy

### 单元测试（tests/unit/）

| 测试文件 | 覆盖 | Mock 策略 |
|---|---|---|
| test_he_adapter.py | is_available, parse, trial_extract, evolve, merge_results | Mock Template.create/ka.parse；不真实调 LLM |
| test_template_engine.py | list_presets(动态), assess(评分逻辑), select_complementary(贪心), generate_custom(YAML), settle/get_settled | Mock trial_extract 返回固定评分；Mock LLM 返回 YAML |
| test_validation_engine.py | 4 维校验全路径 + 边界（空结果/全违规/全通过） | 纯逻辑，无外部依赖 |
| test_sqlite_template_storage.py | CRUD + 去重 + usage_count 递增 | tmp_path 真实 DB |
| test_ontology_mapper.py | 多模板结果合并 → 5 类映射 | 纯逻辑 |
| test_extract_service.py | 3 入口编排 + 降级路径 + session 更新 | Mock adapter/engine/writer |

### 集成测试（tests/integration/，@pytest.mark.integration）

| 测试 | 验证 | 前置 |
|---|---|---|
| test_he_real_extraction.py | 真实 HE + LLM 端到端 | 需 Neo4j + OPENAI_API_KEY |
| test_template_settle_reuse.py | 沉淀复用（usage_count 递增，跳过全量试抽） | 同上 |
| test_dual_channel_write.py | confirm_extraction 双通道写入 | 需 Neo4j |

**关键**: extract_incremental 和 merge_results 必须有非桩测试——验证真实 HE API 调用（mock 层验证调用参数）。

## Docker Install & Dependency Verification

1. 重建后端镜像: `python bootstep.py rebuild main`
2. 验证 HE 导入: `podman exec graphiti-main-app python -c "from hyperextract import Template; print(len(Template.list()))"`
3. 验证重依赖: 确认 ontomem/ontosight/faiss-cpu/langchain 装入镜像
4. 若 ontomem/ontosight 装失败: Dockerfile 加清华源或离线 wheel
5. LLM 配置注入: HE 的 create_llm/create_embedder 从 ODAP env 读取（get_config），不另建 ~/.he/config.toml

## Migration Path

### 迁移顺序（保证可回滚）

1. 先建新组件（TemplateEngine/ValidationEngine/sqlite_template_storage）+ 单元测试
2. 修复 HEAdapter（API 对齐 + 桩实现补全）+ 单元测试
3. 新 ExtractService 编排 + 单元测试
4. ontology/extraction 改为委托新服务 + 测试
5. 删除死代码（ontology/extraction/impl/he_adapter.py, template_generator.py）
6. 重建镜像，端到端集成测试

### API 契约不变

现有路由 `POST /api/extract/nl` 等路径与响应结构保持不变，前端无需改动。

### 删除/迁移清单

| 操作 | 文件 |
|---|---|
| 删除 | ontology/extraction/impl/he_adapter.py |
| 删除 | ontology/extraction/impl/template_generator.py |
| 迁移 | ontology/extraction/impl/ontology_mapper.py → data/hyper_extract/impl/ |
| 迁移 | ontology/extraction/impl/provenance_tracker.py → data/hyper_extract/impl/ |
| 保留 | ontology/extraction/impl/document_parser.py |
| 改写 | ontology/extraction/services/extraction_service.py（委托 + 保留 conflict/confirm/session） |
| 修复 | data/hyper_extract/impl/he_adapter.py（get_config import + API 对齐） |
| 删除 | data/hyper_extract/services/template_generator.py（被 TemplateEngine 替代） |
| 删除 | data/hyper_extract/services/extract_service.py 旧版（被新编排替代） |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 重建镜像后 `HEAdapter.is_available()` 返回 True，`Template.list()` 返回 30+ 预设
- **SC-002**: 模板评估对 5 个候选模板试抽并在 30 秒内返回带评分的排序列表
- **SC-003**: 多模板互补抽取后 5 类产出（object/relation/action/rule/process）均有结果（给定覆盖 5 类的输入文本）
- **SC-004**: 自定义模板生成后 YAML 文件落盘 + SQLite 记录存在，二次抽取复用（usage_count 递增）
- **SC-005**: 4 维校验报告正确标识字段缺失/孤立节点/悬空关系/低置信度实体
- **SC-006**: 抽取结果中无任何 `template_used: "schema_level_fallback"` 标记（HE 真实启用）
- **SC-007**: 单元测试全部通过（pytest tests/unit/ -v 零失败），集成测试在 Neo4j 可用时通过
- **SC-008**: extract_incremental 和 merge_results 不再返回空桩/手工去重（除非 HE 原生 API 不可用且已标记降级）

## Assumptions

- Docker 镜像基于 python:3.11-slim（满足 HE >=3.11 要求），无需升级 Python
- HE 及依赖（ontomem/ontosight/faiss-cpu）可从 PyPI 安装；若网络受限需配置镜像源
- LLM 服务可用（OPENAI_API_KEY/OPENAI_API_BASE 已在 .env.docker 配置）
- 现有 GraphWriteProxy 和 GraphManager.add_episode 双通道写入逻辑正常工作
- 前端 ExtractionPreview 组件可扩展展示校验报告（4 维 + needs_review）
- Neo4j 与 Graphiti 服务在集成测试环境可用

## Edge Cases

### 边界条件

- **EC-001**: 试抽样本过短（< 100 字符）→ 扩大样本到全文本或返回低评分标记
- **EC-002**: 输入文本为空/仅空白 → 返回 `{"status":"error","message":"文本不能为空"}`（现有）
- **EC-003**: 本体无任何类型定义 → generate_from_ontology 返回 None，依赖预设 + 自定义生成

### 错误场景

- **EC-004**: LLM 生成 YAML 格式错误 → 重试 2 次，仍失败降级用最佳预设
- **EC-005**: 自定义模板试抽验证无实体产出 → 视为不达标，触发重试
- **EC-006**: 单模板 parse 抛异常 → 捕获，继续其他模板
- **EC-007**: LLM 超时 → 试抽阶段评分 0；正式抽取保留已成功部分
- **EC-008**: HE 未安装/导入失败 → 明确错误，禁止静默 fallback

### 规模与性能

- **EC-009**: 30+ 预设全量试抽成本过高 → 语义匹配预筛选 top-k=5 再试抽
- **EC-010**: 多模板抽取串行耗时 → 可并行 parse（asyncio.gather），控制并发≤3
- **EC-011**: 大文档分块后多模板抽取块数爆炸 → 每块用已选定的模板组合（不重复评估）

### 一致性

- **EC-012**: merge_results 时实体 name 冲突但属性不同 → 保留首次 + 标记冲突到校验报告
- **EC-013**: 沉淀模板 YAML 文件被删除但 SQLite 记录存在 → get_settled_template 检测文件不存在时跳过
- **EC-014**: 并发抽取对同一本体同时生成自定义模板 → SQLite UNIQUE 约束防重，后到的复用

### 降级场景

- **EC-015**: 试抽全部低于阈值 → 触发 generate_custom()；也失败则返回最佳结果 + 低置信度标记，session.degradation_flags 记录 "template_below_threshold"
- **EC-016**: 自定义 YAML 生成失败 → LLM 重试 2 次；仍失败降级用最佳预设 + warning，degradation_flags 记录 "custom_generation_failed"
- **EC-017**: merge_results 失败 → 降级手工去重合并 + 降级标记，degradation_flags 记录 "merge_fallback"
- **EC-018**: ValidationEngine 异常 → 校验失败不阻断，返回 status="error"，结果可 confirm 但标记"未校验"，degradation_flags 记录 "validation_skipped"

## Brainstorm Log

### 2026-07-11 Session: SP1 设计

**参与者**: User + AI

**关键决策**:

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | 端到端愿景分解 | 7 子项目，Approach C 缺口优先序列 | 大部分模块已存在，集中精力于缺口 |
| 2 | 模板评估语义 | 质量试抽评分 | 最严谨，符合生产级要求 |
| 3 | 抽取策略 | 多模板互补抽取 + LLM 补充 + 沉淀复用 | 单模板无法覆盖 5 类产出 |
| 4 | 校验评估范围 | 4 维全选（Schema/完整性/置信度/引用一致性） | 用户明确要求不简化 |
| 5 | 架构方案 | Approach 2 统一重构 | 合并两套 adapter，保留已正常代码 |
| 6 | adapter 规范位置 | biz/data/hyper_extract/ | API kwarg 已正确，data 域负责数据加工 |
| 7 | HE 不可用处理 | 明确错误，禁止静默 fallback | 静默 fallback 等于伪实现 |
| 8 | 模板持久化 | SQLite 元数据 + YAML 文件落盘 | YAML 可被 Template.create(path) 直接加载 |
| 9 | LLM 配置注入 | 从 ODAP env 读取，不另建 ~/.he/config.toml | 避免双重配置源 |
| 10 | 迁移策略 | 先建新→修复→改写委托→删死代码→重建镜像 | 保证可回滚 |

**约束**: 生产级实现，不偷懒、不伪实现、不简化，按实际能生产跑的逻辑处理。
