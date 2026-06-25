# Hyper-Extract 集成设计：本体驱动的智能知识提取引擎

**日期**: 2026-06-16
**状态**: Draft (v2 — Review 修订版)
**关联分支**: `005-data-collection-opt`
**关联仓库**: [yifanfeng97/Hyper-Extract](https://github.com/yifanfeng97/Hyper-Extract)

---

## 1. 概述

### 1.1 背景

ODAP 平台当前的数据摄入管道存在两个核心问题：

1. **提取质量不足**：当前 LLM 提取基于硬编码 Prompt，无 Schema 约束，提取结果不可控、不一致
2. **双重 LLM 浪费**：ODAP 管道 LLM 提取结构化数据 → 转为自然语言 → Graphiti `add_episode` 内部 LLM 再次提取，存在信息损失和语义漂移

[Hyper-Extract](https://github.com/yifanfeng97/Hyper-Extract)（HE）是一个 LLM 驱动的智能知识提取框架，核心能力：
- 80+ YAML 模板（金融/法律/医疗/工业/通用领域）
- 10+ 提取引擎（GraphRAG / LightRAG / Hyper-RAG / KG-Gen 等）
- 8 种知识结构（Graph / Hypergraph / Temporal Graph / Spatial Graph 等）
- 确定性实体 ID + 增量演化

### 1.2 目标

将 Hyper-Extract 作为 Git Submodule 集成到 ODAP，作为**统一的非结构化文本→结构化知识提取引擎**，同时：
- 增强 IngestService 的提取能力
- 注册为 Agent Skill，支持 Agent 按需调用
- 优化"双重 LLM"问题（第二次 LLM 调用降级为轻量级结构化描述提取）
- 保证本体定义的统一性

### 1.3 与 Graphiti 的关系定位

| 组件 | 核心职责 | 不可替代能力 |
|------|---------|-------------|
| **Hyper-Extract** | 文本→结构化数据（提取引擎） | 模板化提取、确定性 ID、增量演化 |
| **Graphiti** | 结构化数据→双时态知识图谱（存储+索引+检索） | 双时态索引、语义搜索、RAG 上下文 |

两者**互补而非冲突**：HE 是 Graphiti 的**上游提取引擎**，Graphiti 是 HE 的**下游存储引擎**。

**关键约束**：Graphiti 的 `search()` 返回 `EntityEdge`（知识三元组），这些 Edge 是 Graphiti 内部从 Episode 中提取并构建的。直接在 Neo4j 创建裸 Episode 节点不会产生 EntityEdge，`search()` 将无法发现这些数据。因此，**必须保留 `graphiti.add_episode()` 调用**以维持 Graphiti 的检索能力。

---

## 2. 架构设计

### 2.1 整体数据流

```
原始文本 (任何长度/复杂度)
    │
    ▼
Hyper-Extract Template.parse(text, template=ontology_template)
    │  模板由本体定义自动生成（通过 OntologyService 获取类型定义）:
    │  list_object_types(ontology_id) → YAML template entities.fields
    │  list_link_types(ontology_id) → YAML template relations.fields
    │  list_action_types(ontology_id) → YAML template events.fields
    │
    ▼
KnowledgeAbstract (符合本体定义的结构化数据)
    │  entities: [{name, type, description, ...}]
    │  relations: [{source, target, type, ...}]
    │  events: [{name, event_type, valid_time, ...}]
    │
    ▼
OntologyMapper (验证 + 映射，确保 100% 符合本体)
    │  1. 类型校验: entity.type 必须在本体 object_types 中
    │  2. 关系校验: relation.type 必须在本体 link_types 中
    │  3. 属性映射: 将提取属性映射到本体定义的属性结构
    │  4. ID 生成: 统一使用 deterministic_entity_id()
    │  5. 未知类型处理: 严格模式丢弃 / 宽松模式标记 "unclassified"
    │
    ▼
双通道互补写入
    │
    ├─→ 通道 A: GraphWriteProxy (确定性写入，完整属性)
    │     write_proxy.add_entity(entity_id, entity_type, properties, workspace_id)
    │     write_proxy.add_relationship(source_id, target_id, rel_type, properties, workspace_id)
    │     → Neo4j Entity 节点 (MERGE 幂等，携带四层属性)
    │     → 审计日志自动记录
    │     → 工作空间隔离自动保证
    │
    └─→ 通道 B: Graphiti add_episode (双时态索引 + 语义搜索)
          graph_manager.add_episode(
              name=entity_id,
              episode_body=结构化摘要文本,
              reference_time=valid_time  ← 来自 HE 事件提取
          )
          → Graphiti 内部提取 EntityEdge (供 search() 发现)
          → 双时态索引 (valid_time + transaction_time)
          → 向量嵌入 (供语义搜索)
```

### 2.2 关键设计决策

#### 决策 1：双通道互补写入

**问题**：如何同时满足"完整属性存储"和"Graphiti 检索能力"两个需求？

**方案**：双通道互补写入：
- **通道 A**（GraphWriteProxy）：写入完整属性（四层属性结构），确定性 ID，幂等 MERGE，审计日志
- **通道 B**（graphiti.add_episode）：写入结构化摘要文本，建立双时态索引和语义搜索能力

**为什么不使用单通道**：直接在 Neo4j 创建裸 Episode 节点不会产生 `EntityEdge`，Graphiti 的 `search()` 无法发现这些数据。`add_episode()` 内部的 LLM 提取是 Graphiti 检索能力的前提条件。

**双重 LLM 优化**：通道 B 的 LLM 调用是轻量级的——输入已是 HE 提取的结构化描述（如"中国是一个 Organization。北斗导航卫星是一个 Satellite"），Graphiti 内部提取的准确度远高于处理原始非结构化文本。相比当前架构（原始文本 → ODAP LLM → 自然语言 → Graphiti LLM），HE 路径的第二次 LLM 调用输入质量更高、提取更准确。

**时间一致性保证**：
- `valid_time`：来自 HE 提取的事件时间，优先级：HE events.valid_time > 文档元数据 > 用户指定 > datetime.now()
- `transaction_time`：通道 A 和通道 B 在同一次 `extract_and_write()` 调用中顺序执行，共享同一 `datetime.now()` 基准时间

**为什么必须通过 GraphWriteProxy**：
- `GraphWriteProxy.get_raw_graph_manager()` 已被显式移除，项目禁止业务模块直接访问 GraphManager
- GraphWriteProxy 提供审计日志（`_log_write()`）、工作空间隔离、标准化返回值
- 绕过代理将违反 AGENTS.md 审计一致性约束

#### 决策 2：本体定义→HE 模板自动生成（通过 OntologyService）

**问题**：HE 需要 YAML 模板指定提取目标，用户不应手动编写。

**方案**：`OntologyTemplateGenerator` 通过 `OntologyService` 获取类型定义，自动生成 HE 兼容的 YAML 模板：
- `OntologyService.list_object_types(ontology_id)` → template `entities.fields`
- `OntologyService.list_link_types(ontology_id)` → template `relations.fields`
- `OntologyService.list_action_types(ontology_id)` → template `events.fields`
- 支持手动模板覆盖（`template_override` 参数）

**注意**：项目中不存在 `OntologyDefinition` 类。本体存储为字典，类型定义通过 `OntologyService` 的独立方法获取。`ObjectTypeDefinition`、`LinkDefinition`、`ActionTypeDefinition` 等模型定义在 `odap/biz/core/ontology/application/oms/schemas.py` 中。

**统一性保证**：无论文本长短，都走同一条提取路径，模板直接来自本体定义，提取结果天然符合本体约束。

#### 决策 3：HE 替代自建 LLM 提取管道

**问题**：ODAP 自建了 `LLMExtractionStageHandler`，与 HE 功能重叠。

**方案**：HE 替代 `LLMExtractionStageHandler`，作为统一提取引擎。IngestService 的各入口方法内部从"LLM Prompt 直接提取"切换为"HE 模板化提取"。对上层调用者透明。

---

## 3. 模块结构

### 3.1 新增文件

```
odap/biz/data/hyper_extract/                    # NEW: Hyper-Extract 集成模块
├── __init__.py
├── api/
│   ├── routes.py                               # POST /api/he/extract, /api/he/templates
│   └── schemas.py                              # ExtractRequest, ExtractResponse
├── services/
│   ├── extract_service.py                      # 编排层: HE 提取 + 映射 + 双通道写入
│   └── template_generator.py                   # 本体定义 → HE YAML 模板生成
├── impl/
│   ├── he_adapter.py                           # Hyper-Extract Python API 适配
│   └── ontology_mapper.py                      # KnowledgeAbstract → OntologyDocument
├── models/
│   ├── __init__.py
│   └── extraction_task.py                      # 提取任务模型
└── storage/
    ├── __init__.py
    └── sqlite_extraction_storage.py             # 提取记录持久化

hyper-extract/                                  # NEW: Git Submodule
├── hyperextract/                               #   HE 核心库
└── hyperextract-skills/                        #   HE Skills 扩展
```

### 3.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `odap/tools/web/web_skills.py` | 新增 `KnowledgeExtractSkill` |
| `odap/biz/core/ontology/design/services/ingest_service.py` | 摄入方法新增可选 `ontology_id` 参数，内部切换为 HE 提取 |
| `odap/web/app.py` | `include_router(he_router)` |
| `odap/infra/opa/policies/data_collection.rego` | 新增 HE 提取权限策略 |
| `requirements.txt` | 新增 `hyperextract>=0.2.0` |
| `.gitmodules` | 新增 Hyper-Extract Submodule |

### 3.3 Skill 注册

```python
class KnowledgeExtractSkill(BaseSkill):
    """知识提取技能 — 基于 Hyper-Extract"""
    metadata = SkillMetadata(
        name="knowledge_extract",
        description="从非结构化文本中提取结构化知识（实体/关系/事件），基于本体定义自动生成提取模板",
        category="ontology",
        danger_level="medium",
        requires_opa_check=True,          # 启用 OPA 权限检查
        opa_action="data_collection:extract",
    )
    input_schema = KnowledgeExtractInput

    async def execute(self, input_data: KnowledgeExtractInput) -> SkillOutput:
        service = ExtractService()
        result = await service.extract_and_write(
            text=input_data.text,
            ontology_id=input_data.ontology_id,
            scenario_id=input_data.scenario_id,
        )
        return SkillOutput(
            success=result.get("status") == "ok",
            data=result,
            execution_time_ms=result.get("execution_time_ms", 0),
            skill_name=self.metadata.name,
            request_id=input_data.request_id,
        )

class KnowledgeExtractInput(SkillInput):
    text: str                                    # 待提取的原始文本
    ontology_id: str                             # 本体定义 ID
    scenario_id: Optional[str] = None            # 场景 ID
    template_override: Optional[str] = None      # 自定义 HE 模板名称
```

---

## 4. 核心组件设计

### 4.1 OntologyTemplateGenerator

```python
class OntologyTemplateGenerator:
    """从 ODAP 本体类型定义自动生成 Hyper-Extract YAML 模板

    注意：项目中不存在 OntologyDefinition 类。
    类型定义通过 OntologyService 的独立方法获取：
    - list_object_types(ontology_id) -> List[ObjectTypeDefinition]
    - list_link_types(ontology_id) -> List[LinkDefinition]
    - list_action_types(ontology_id) -> List[ActionTypeDefinition]
    """

    def __init__(self, ontology_service: OntologyService = None):
        self._service = ontology_service or OntologyService()

    def generate(self, ontology_id: str) -> dict:
        # 通过 OntologyService 获取类型定义
        object_types = self._service.list_object_types(ontology_id)
        link_types = self._service.list_link_types(ontology_id)
        action_types = self._service.list_action_types(ontology_id)

        template = {
            "language": "zh",
            "name": f"ontology_{ontology_id}",
            "type": "graph",
            "description": f"Auto-generated from ontology: {ontology_id}",
            "output": {
                "entities": {"fields": self._build_entity_fields(object_types)},
                "relations": {"fields": self._build_relation_fields(link_types)},
            },
            "identifiers": {
                "entity_id": "name",
                "relation_id": "{source}|{type}|{target}",
            },
        }

        # 如果本体包含 action_types，添加 events 输出
        if action_types:
            template["output"]["events"] = {
                "fields": self._build_event_fields(action_types)
            }
            template["type"] = "temporal_graph"  # 升级为时序图

        return template

    def _build_entity_fields(self, object_types: list) -> list:
        fields = [
            {"name": "name", "type": "str"},
            {"name": "type", "type": "str"},
            {"name": "description", "type": "str"},
        ]
        # 从 ObjectTypeDefinition.properties 生成额外字段
        for obj_type in object_types:
            for prop in obj_type.properties:
                fields.append({"name": prop.name, "type": self._map_type(prop.type)})
        return fields
```

### 4.2 OntologyMapper

```python
class OntologyMapper:
    """KnowledgeAbstract → OntologyDocument 转换，确保符合本体定义"""

    def __init__(self, ontology_id: str, strict: bool = True):
        self.ontology_id = ontology_id
        self.strict = strict
        # 通过 OntologyService 获取类型定义，构建索引
        self._service = OntologyService()
        self._object_type_names = {
            ot.name for ot in self._service.list_object_types(ontology_id)
        }
        self._link_type_names = {
            lt.name for lt in self._service.list_link_types(ontology_id)
        }

    def map(self, ka: KnowledgeAbstract) -> OntologyDocument:
        entities = []
        for entity in ka.entities:
            # 类型校验
            if entity["type"] not in self._object_type_names:
                if self.strict:
                    continue  # 严格模式：丢弃不在本体中的实体
                entity["type"] = "unclassified"  # 宽松模式：标记

            # 属性映射
            mapped_props = self._map_properties(entity)
            entities.append(OntologyEntity(
                entity_id=deterministic_entity_id(entity["type"], entity["name"]),
                entity_type=entity["type"],
                name=entity["name"],
                basic_properties=mapped_props.get("basic", {}),
                statistical_properties=mapped_props.get("statistical", {}),
                capabilities=mapped_props.get("capabilities", {}),
                constraints=mapped_props.get("constraints", {}),
            ))

        # 关系映射（同理，校验 link_type_names）
        relations = self._map_relations(ka.relations)
        # 事件映射（同理）
        events = self._map_events(ka.events)

        return OntologyDocument(
            entities=entities,
            relations=relations,
            events=events,
        )
```

### 4.3 双通道写入（替代原 UnifiedGraphWriter）

```python
class DualChannelWriter:
    """双通道互补写入器

    通道 A: GraphWriteProxy — 完整属性写入（审计日志 + 工作空间隔离）
    通道 B: Graphiti add_episode — 双时态索引 + 语义搜索

    为什么必须保留 add_episode：
    - Graphiti search() 返回 EntityEdge，这些 Edge 是 add_episode 内部 LLM 提取构建的
    - 直接在 Neo4j 创建裸 Episode 节点不会产生 EntityEdge，search() 无法发现
    - add_episode 的 LLM 调用是轻量的：输入已是结构化描述，提取准确度高
    """

    def __init__(self):
        self._write_proxy = None
        self._graph_manager = None

    @property
    def write_proxy(self):
        if self._write_proxy is None:
            from odap.infra.query.graph_write_proxy import get_graph_write_proxy
            self._write_proxy = get_graph_write_proxy()
        return self._write_proxy

    @property
    def graph_manager(self):
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager.get_instance()
        return self._graph_manager

    async def write(self, doc: OntologyDocument,
                    workspace_id: str,
                    scenario_id: str = None) -> Dict[str, Any]:
        # 统一时间基准
        valid_time = self._extract_valid_time(doc)

        # ── 通道 A: GraphWriteProxy 写入完整属性 ──
        for entity in doc.entities:
            self.write_proxy.add_entity(
                entity_id=entity.entity_id,
                entity_type=entity.entity_type,
                properties={
                    "name": entity.name,
                    "basic_properties": entity.basic_properties,
                    "statistical_properties": entity.statistical_properties,
                    "capabilities": entity.capabilities,
                    "constraints": entity.constraints,
                    "valid_time": valid_time.isoformat() if valid_time else None,
                },
                workspace_id=workspace_id,
            )

        for relation in doc.relations:
            self.write_proxy.add_relationship(
                source_id=relation.source_entity,
                target_id=relation.target_entity,
                rel_type=relation.relation_type,
                properties=relation.model_dump(exclude={"source_entity", "target_entity", "relation_type"}),
                workspace_id=workspace_id,
            )

        # ── 通道 B: Graphiti add_episode 建立双时态索引 ──
        episode_body = doc.to_episode_text()  # 结构化摘要文本
        try:
            await self.graph_manager.add_episode(
                name=f"he_extract:{doc.entities[0].entity_id if doc.entities else 'unknown'}",
                content=episode_body,
                source_description="hyper-extract",
                reference_time=valid_time,
            )
        except Exception as e:
            # 通道 B 失败不影响通道 A 的数据完整性，仅记录日志
            logger.warning(f"Graphiti add_episode failed: {e}")

        return {
            "status": "ok",
            "valid_time": valid_time,
            "entities_written": len(doc.entities),
            "relations_written": len(doc.relations),
        }

    def _extract_valid_time(self, doc: OntologyDocument) -> Optional[datetime]:
        """从 HE 提取的事件中获取 valid_time"""
        if doc.events:
            for event in doc.events:
                if hasattr(event, "time") and event.time:
                    return event.time
        return None  # 降级：Graphiti add_episode 将使用当前时间
```

### 4.4 ExtractService (编排层)

```python
class ExtractService:
    """知识提取编排层 — HE 提取 + 映射 + 双通道写入"""

    async def extract_and_write(self, text: str, ontology_id: str,
                                scenario_id: str = None,
                                workspace_id: str = None) -> Dict[str, Any]:
        # 0. 内容安全过滤（复用 web_crawl 的 content_sanitizer）
        from odap.biz.data.web_crawl.impl.content_sanitizer import ContentSanitizer
        sanitizer = ContentSanitizer()
        safe_text = sanitizer.sanitize(text)
        if not safe_text:
            return {"status": "error", "message": "Content filtered by sanitizer"}

        # 1. 生成 HE 模板（通过 OntologyService 获取类型定义）
        generator = OntologyTemplateGenerator()
        template = generator.generate(ontology_id)

        # 2. HE 提取
        adapter = HEAdapter()
        ka = adapter.parse(safe_text, template)

        # 3. 本体映射
        mapper = OntologyMapper(ontology_id)
        doc = mapper.map(ka)

        if not doc.entities and not doc.relations:
            return {"status": "error", "message": "No valid entities/relations extracted"}

        # 4. 双通道写入
        writer = DualChannelWriter()
        result = await writer.write(doc, workspace_id=workspace_id, scenario_id=scenario_id)

        # 5. 记录提取任务
        self._save_extraction_task(text, ontology_id, result)

        return result
```

---

## 5. 与现有系统的集成

### 5.1 与 IngestService 集成

IngestService 的各入口方法新增可选 `ontology_id` 参数，不破坏现有接口：

```python
class IngestService:
    async def ingest_from_natural_language(
        self, text: str, scenario_id: str = None,
        ontology_id: str = None,  # 新增可选参数
    ) -> str:
        # 优先使用 HE 提取路径
        if ontology_id and self.he_extract_service.is_available():
            result = await self.he_extract_service.extract_and_write(
                text=text,
                ontology_id=ontology_id,
                scenario_id=scenario_id,
                workspace_id=self._get_workspace_id(scenario_id),
            )
            if result.get("status") == "ok":
                return self._create_ingest_record(text, "natural_language", scenario_id)

        # 降级到原有 LLM 提取（不变）
        return await self._ingest_with_legacy_llm(text, scenario_id)
```

### 5.2 与 005-data-collection-opt 衔接

```
005-data-collection-opt (已实现):
  Crawl4AI/SearchService → 原始文本
  web_search Skill → Agent 联网搜索
  web_crawl Skill → Agent 网页爬取

Hyper-Extract 集成 (新增):
  knowledge_extract Skill → Agent 知识提取
  ExtractService → 摄入管道增强提取
  OntologyTemplateGenerator → 本体驱动模板生成

完整链路:
  Crawl4AI/SearchService → 原始文本
      → HE Template.parse() → KnowledgeAbstract
      → OntologyMapper → OntologyDocument
      → DualChannelWriter:
          通道 A: GraphWriteProxy → Neo4j (完整属性)
          通道 B: graphiti.add_episode → Neo4j (双时态索引 + 语义搜索)
```

### 5.3 与 Graphiti 检索能力的关系

**通道 B 保留 `graphiti.add_episode()` 的原因**：

| Graphiti 检索方法 | 依赖 | 直接创建 Episode 能否工作 |
|---|---|:---:|
| `search()` | 返回 `EntityEdge`（由 add_episode 内部 LLM 提取构建） | 否 |
| `retrieve_episodes()` | 返回 `EpisodicNode`（由 add_episode 创建，含 uuid/content/embedding） | 否 |
| 图遍历 | 显式过滤 `WHERE NOT b:Episode` | 否 |

因此，**必须保留 `add_episode()` 调用**。通道 B 的 LLM 调用是轻量的——输入已是结构化描述，提取准确度远高于原始文本。

**查询时的双通道互补**：
1. Graphiti `search()` 通过语义搜索找到相关 `EntityEdge`
2. 从 `EntityEdge` 中提取 `source_node_uuid` / `target_node_uuid`
3. 通过 `GraphWriteProxy` / `GraphManager` 获取通道 A 写入的完整属性

---

## 6. 双时态信息流转

### 6.1 valid_time 来源优先级

| 优先级 | 来源 | 示例 |
|:---:|------|------|
| 1 | HE 事件提取的 `valid_time` | "2026年6月16日" → `2026-06-16` |
| 2 | 文档元数据（如新闻发布时间） | RSS feed 的 `pubDate` |
| 3 | 摄入请求中用户指定的时间 | `ingest(valid_time="2026-06-15")` |
| 4 | 降级：`datetime.now()` | 无法确定时间时使用当前时间 |

### 6.2 transaction_time

通道 A（GraphWriteProxy）和通道 B（add_episode）在同一次 `extract_and_write()` 调用中顺序执行，共享同一 `datetime.now()` 基准时间。Graphiti 的 `add_episode` 内部会自动记录 `created_at` 作为 transaction_time。

### 6.3 时态查询

```python
# 查询: "2026年6月发生了什么？"
episodes = await graphiti.retrieve_episodes(reference_time="2026-06-01~2026-06-30")
# 从 Episode 关联的 EntityEdge 中提取 entity_id
# → 通过 GraphManager 获取通道 A 写入的完整属性
```

---

## 7. 安全与合规设计

### 7.1 OPA 权限控制

新增 `odap/infra/opa/policies/data_collection.rego`：

```rego
package data_collection

# 知识提取权限：需要 data_collection:extract action
allow {
    input.action == "extract"
    input.role == "admin"
}

allow {
    input.action == "extract"
    input.role == "analyst"
    input.workspace_id == input.target_workspace_id
}
```

`KnowledgeExtractSkill` 设置 `requires_opa_check=True`，`opa_action="data_collection:extract"`，SkillExecutorV2 在执行前自动检查 OPA 策略。

### 7.2 重试机制

复用 `SkillExecutorV2` 的重试策略（最多 3 次，指数退避），无需自行实现。`ExtractService` 内部的 HE 提取调用由 SkillExecutorV2 包裹，自动获得重试能力。

### 7.3 内容安全过滤

复用 `odap/biz/data/web_crawl/impl/content_sanitizer.py` 的 `ContentSanitizer`：
- 在 HE 提取前对原始文本进行安全过滤
- 移除潜在恶意脚本/iframe
- 标记外部内容可信度

---

## 8. 风险分析

| 风险 | 严重度 | 概率 | 缓解措施 |
|------|:---:|:---:|------|
| HE LLM 调用与 ODAP LLM 配置冲突 | 高 | 中 | HE 支持 OpenAI 兼容 API，复用 ODAP 的 `OPENAI_API_KEY` / `OPENAI_API_BASE` |
| HE 输出格式与 OntologyDocument 映射复杂 | 中 | 高 | OntologyMapper 处理字段名差异、类型转换、缺失字段补全 |
| Submodule 更新导致兼容性破坏 | 中 | 低 | 锁定 HE 版本（tag），定期手动更新 |
| HE 模板自动生成质量不足 | 中 | 中 | 提供手动模板覆盖，自动生成作为默认 |
| 双通道写入数据不一致 | 中 | 低 | 通道 B 失败不影响通道 A；entity_id 统一，可交叉验证 |
| 通道 B LLM 调用成本 | 中 | 中 | 输入已是结构化描述，token 消耗远低于原始文本提取 |
| 批量提取性能瓶颈 | 中 | 中 | HE 逐文档处理，可通过 asyncio 并行化 |

---

## 9. 实施优先级

| 阶段 | 内容 | 优先级 |
|------|------|:---:|
| P1 | Submodule 引入 + HE Adapter + OntologyMapper + 基础提取 | 高 |
| P2 | OntologyTemplateGenerator (通过 OntologyService 获取类型定义) | 高 |
| P3 | DualChannelWriter (GraphWriteProxy + graphiti.add_episode) | 高 |
| P4 | KnowledgeExtractSkill 注册 + OPA 策略 + 重试机制 | 中 |
| P5 | IngestService 集成 (新增可选 ontology_id 参数) | 中 |
| P6 | 前端摄入界面增强 (HE 提取选项) | 低 |
| P7 | HE 增量演化 (evolve) + 批量并行 | 低 |

---

## 10. 可行性评估

| 维度 | 评分 | 说明 |
|------|:---:|------|
| 技术可行性 | 8/10 | HE 是 Python 库，Apache 2.0 许可，API 简洁，与 ODAP 技术栈兼容 |
| 架构合理性 | 8/10 | 双通道互补，GraphWriteProxy 保证架构边界，Graphiti 保证检索能力 |
| 集成复杂度 | 7/10 | Submodule 管理 + OntologyMapper + DualChannelWriter 三层适配 |
| 收益/成本比 | 8/10 | 提升提取质量、80+ 模板复用、本体统一性保证 |
| 维护成本 | 5/10 | Submodule 跟踪 + HE 版本兼容性 + 模板维护 |

---

## 附录 A：Review 修订记录

本节记录 superspec review 发现的问题及修订措施。

| Review 发现 | 严重度 | 修订措施 |
|-------------|:---:|---------|
| C1: 单通道写入假设不成立（Graphiti search 依赖 EntityEdge） | Critical | 改为双通道互补：GraphWriteProxy + graphiti.add_episode |
| C2: 绕过 GraphWriteProxy 违反架构约束 | Critical | 所有实体/关系写入通过 GraphWriteProxy |
| I1: OntologyDefinition 类不存在 | Important | 通过 OntologyService 获取类型定义 |
| I2: IngestService 缺少 ontology_id 参数 | Important | 新增可选 ontology_id 参数 |
| I3: Cypher 注入风险 | Important | 使用 GraphWriteProxy 内部安全模式 |
| I4: 005 Spec 合规缺口（OPA/重试/安全过滤） | Important | 新增 Section 7 安全与合规设计 |
| S1: requires_opa_check 未设置 | Suggestion | 设置 requires_opa_check=True |
| S2: ExtractService 应为 async | Suggestion | extract_and_write 改为 async def |
