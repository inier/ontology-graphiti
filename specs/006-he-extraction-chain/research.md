# Research: Hyper-Extract 启用 + 抽取校验完整链路

**Date**: 2026-07-11
**Feature**: 006-he-extraction-chain

## Research Questions

### RQ-1: HE 真实 API 表面（Template / BaseAutoType / AutoGraph）

**Decision**: 确认 HE API 签名，修正 spec 中的 API 名称错误。

**Findings**:

#### Template API (`hyperextract/utils/template_engine/template.py`)

```python
@staticmethod
def create(source: str, language: Optional[str] = None,
           llm_client: Optional[BaseChatModel] = None,
           embedder: Optional[Embeddings] = None, **kwargs) -> BaseAutoType

@staticmethod
def get(path: str) -> Optional[TemplateCfg]

@staticmethod
def list(filter_by_query=None, filter_by_type=None, filter_by_tag=None,
         filter_by_language=None, include_methods=True) -> Dict[str, TemplateCfg]
```

- `create()` 的 kwarg 名为 `llm_client=` / `embedder=`（确认正确）
- `list()` 返回 `Dict[str, TemplateCfg]`，支持按 type/tag/language/query 过滤
- 若 `llm_client` 或 `embedder` 为 None，HE 从 `~/.he/config.toml` 读取默认值（我们需显式注入避免依赖此文件）

#### BaseAutoType (`hyperextract/types/base.py`)

| 方法 | 签名 | 说明 |
|------|------|------|
| `parse(text)` | `-> BaseAutoType` | 返回**新实例**，不修改当前实例 |
| `feed_text(text)` | `-> BaseAutoType (self)` | **修改当前实例**，合并新数据（链式调用） |
| `dump(folder_path)` | `-> None` | 序列化到目录（data.json + metadata.json + index/） |
| `load(folder_path)` | `-> None` | 从目录反序列化 |
| `build_index()` | `-> None` | 构建 FAISS 向量索引 |
| `search(query, top_k=3)` | `-> List` | 语义搜索 |
| `chat(query, top_k=3)` | `-> AIMessage` | 问答 |

**关键修正**:
- spec 中提到的 `evolve()` **不存在**——HE 的增量抽取 API 是 `feed_text(text)`，修改当前实例并返回 self
- spec 中提到的 `dump_dict()` **不存在**——序列化通过 `dump(folder_path)` 写文件，或直接访问 `.nodes` / `.edges` 属性
- **无原生图合并 API**：`AutoList.extend()` 和 `AutoSet.union()` 存在，但 `AutoGraph` 无 merge/union 方法。`merge_results()` 必须手工实现（按 name + 三元组去重）

#### AutoGraph

构造参数（通过 `Template.create()` 间接创建，或直接实例化）:
```python
AutoGraph(
    node_schema, edge_schema,
    node_key_extractor, edge_key_extractor, nodes_in_edge_extractor,
    llm_client, embedder
)
```

结果访问：`result.nodes` → 节点列表，`result.edges` → 边列表
节点属性：`node.name`, `node.type`, `node.description`, `node.properties`
边属性：`edge.source`, `edge.target`, `edge.relation_type`, `edge.properties`

#### create_llm / create_embedder (`hyperextract/utils/client.py`)

```python
def create_llm(spec: str | dict, *, api_key: str = "", **kwargs) -> BaseChatModel
def create_embedder(spec: str | dict, *, api_key: str = "", **kwargs) -> Embeddings
```

- `spec` 格式：`provider:model@url`（如 `"openai:gpt-4o"`、`"bailian:qwen-plus"`）
- `**kwargs` 转发给 `ChatOpenAI`（如 `base_url`、`temperature`）
- `api_key` fallback 到 `OPENAI_API_KEY` 环境变量

**Rationale**: 直接读源码确认，避免假设 API 名称。

**Alternatives considered**: 无——直接验证是唯一可靠方式。

---

### RQ-2: HE YAML 模板规范

**Decision**: 确认 YAML 模板字段结构，供 `generate_custom()` 的 LLM prompt 使用。

**Findings**:

读取 `hyper-extract/templates/presets/general/base_graph.yaml`，HE 模板 YAML 包含以下顶层字段:

| 字段 | 类型 | 说明 |
|------|------|------|
| `language` | `[str]` | 支持语言列表 (如 `[zh, en]`) |
| `name` | `str` | 模板名称 |
| `type` | `str` | AutoType 类型 (graph/list/model/set/hypergraph/temporal_graph/spatial_graph) |
| `tags` | `[str]` | 标签 (如 `[general, graph]`) |
| `description` | `{zh: str, en: str}` | 多语言描述 |
| `output` | `object` | 输出定义：entities/relations 的 fields (name/type/description/required) |
| `guideline` | `object` | 抽取指南：target, rules_for_entities, rules_for_relations |
| `identifiers` | `object` | ID 生成规则：`entity_id`, `relation_id`, `relation_members` |
| `options` | `object` | 抽取选项 (如 `extraction_mode: two_stage`) |
| `display` | `object` | 显示格式模板 |

**自定义模板生成**: LLM 需按此格式生成 YAML，关键必填字段为 `language`, `name`, `type`, `output`, `identifiers`。

**Rationale**: 读取真实模板文件确认格式，确保 LLM 生成的 YAML 可被 `Template.create(yaml_path)` 加载。

---

### RQ-3: 依赖可用性与 Docker 构建

**Decision**: 确认依赖链可从 PyPI 安装，Dockerfile 已正确配置。

**Findings**:

#### HE 依赖链 (`hyper-extract/pyproject.toml`)

| 依赖 | 版本约束 | 备注 |
|------|----------|------|
| faiss-cpu | >=1.13.2 | 需 gcc/g++ 编译（Dockerfile 已安装） |
| langchain | >=1.2.6 | |
| langchain-community | >=0.4.1 | |
| langchain-openai | >=1.1.7 | |
| structlog | >=25.5.0 | |
| ontomem | >=0.2.3 | 可能需要镜像源 |
| ontosight | >=0.1.8 | 可能需要镜像源 |
| python-dotenv | >=1.2.1 | |
| semhash | >=0.4.1 | |
| typer | >=0.13.0 | CLI 依赖 |
| rich | >=13.7.0 | CLI 依赖 |

#### Dockerfile 配置 (`docker/Dockerfile`)

- 基础镜像: `localhost/python:3.11-slim`（满足 HE >=3.11）
- 第 11-16 行: 已安装 `gcc`, `g++`, `tesseract-ocr`（满足 faiss-cpu 编译需求）
- 第 21-22 行: `COPY hyper-extract ./hyper-extract`
- 第 27-28 行: `pip install --no-cache-dir -r requirements.txt`（含 `-e ./hyper-extract`）
- 第 33 行: `graphiti-core` 单独安装（容错）

#### requirements.txt

第 60 行: `-e ./hyper-extract`（已声明）

#### 重建命令

`python bootstep.py rebuild main` — 重建后端镜像

**风险**: ontomem/ontosight 是小众包，可能不在清华镜像源中。若安装失败，需配置离线 wheel 或 PyPI 直连。

**Rationale**: 直接验证配置文件，确保重建即可启用 HE。

---

### RQ-4: `get_config` 正确 import 路径

**Decision**: 确认 `get_config` 的正确 import 路径为 `from odap.infra.config_composer import get_config`。

**Findings**:

- 定义位置: `odap/infra/config_composer.py:325`
- 函数签名: `get_config(key: str, default: Any = None) -> Any`
- 优先级: DB(管理员界面) > USER > WORKSPACE > FILE > ENV > SYSTEM
- 全项目统一使用 `from odap.infra.config_composer import get_config`（10+ 处引用确认）

**Bug 确认**: `odap/biz/data/hyper_extract/impl/he_adapter.py` 第 114、122 行使用 `get_config()` 但**从未 import**，会导致 `NameError`。修复: 在文件头添加 `from odap.infra.config_composer import get_config`。

**LLM 配置项**:
- `llm.api_key` — OpenAI API 密钥
- `llm.api_base` — API 基础 URL
- `llm.model` — 模型名称（默认 `gpt-4o`）

**Rationale**: 直接验证源码，修正 spec 中的错误路径 `odap.infra.config`。

---

### RQ-5: HE 预设模板数量与分类

**Decision**: 确认 35 个预设模板，6 大分类。

**Findings**:

通过 Glob 扫描 `hyper-extract/hyperextract/templates/presets/**/*.yaml`，共 35 个模板文件:

| 分类 | 数量 | 示例 |
|------|------|------|
| general | 11 | base_graph, concept_graph, biography_graph, base_model, base_list, base_set, base_hypergraph, base_temporal_graph, base_spatial_graph, base_spatio_temporal_graph, workflow_graph, doc_structure |
| finance | 5 | earnings_summary, ownership_graph, event_timeline, risk_factor_set, sentiment_model |
| legal | 5 | contract_obligation, defined_term_set, compliance_list, case_fact_timeline, case_citation |
| medicine | 5 | treatment_map, drug_interaction, anatomy_graph, hospital_timeline, discharge_instruction |
| industry | 5 | equipment_topology, operation_flow, safety_control, failure_case, emergency_response |
| tcm | 4 | herb_property, herb_relation, formula_composition, syndrome_reasoning, meridian_graph |

**Rationale**: 实际文件扫描，非文档引用。

---

### RQ-6: HE 不可用时的降级策略修正

**Decision**: 修正 spec 中 `evolve()` 相关的 FR-007。

**Findings**:

spec FR-007 写道："HEAdapter.evolve() 必须调用真实 `BaseAutoType.evolve(new_text)`"

实际 HE API 中**无 `evolve()` 方法**。增量抽取 API 是 `feed_text(text)`:
- `feed_text(text)` 修改当前实例（合并新数据），返回 self
- `parse(text)` 返回新实例（不修改当前）

**修正**: FR-007 应改为 "HEAdapter.evolve() 必须调用真实 `BaseAutoType.feed_text(new_text)` 实现增量抽取"

**Rationale**: 直接读源码确认，避免实现时发现 API 不存在再返工。

---

## Summary of Spec Corrections Needed

| Spec 位置 | 原文 | 修正为 |
|-----------|------|--------|
| FR-007 | `BaseAutoType.evolve(new_text)` | `BaseAutoType.feed_text(new_text)` |
| FR-008 | "优先使用 HE 原生合并 API" | "HE 无原生图合并 API，直接按 name + 三元组去重合并" |
| 接口契约 HEAdapter | `dump_dict()` | `dump(path)` 或直接访问 `.nodes/.edges` |
| FR-003 | `from odap.infra.config import get_config` | `from odap.infra.config_composer import get_config` |

> 这些修正将在 contracts/ 文件中体现，spec.md 保持原样（已审批），以 contracts 为实施依据。
