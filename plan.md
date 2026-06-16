# Plan: 本体驱动的检索门控 (Ontology-Driven Retrieval Gating)

## Objective
- **核心目标**: 将 RAG 检索从"浅层感知本体"升级为"本体驱动的检索门控"，使本体 schema 成为检索的验证门控和约束条件
- **成功标准**:
  1. 查询进入时先验证是否在 ontology schema 范围内（输入门控）
  2. 图谱搜索基于 ontology 定义抽取 DAG 子图，缩小搜索范围（约束检索）
  3. 检索结果验证是否符合本体定义（输出门控）
  4. SQLite 检索的 `ontology_ids` 参数真正生效
  5. `GraphRetriever` 集成到主 RAG 流程
  6. `MultiHopPlanner` 查询分解感知本体 schema
  7. 所有变更向后兼容，不破坏现有功能
- **范围**: 后端 `odap/biz/data/qa/` 和 `odap/infra/graph/` 模块，不涉及前端

## Current State

### 代码现状

| 组件 | 文件 | 现状 | 问题 |
|------|------|------|------|
| RAGPipeline | `odap/biz/data/qa/qa_engine.py` L245-743 | 4个数据源并行检索，后过滤 | `ontology_ids` 仅在 `_retrieve_from_graphiti` 中做后过滤，SQLite/语义地图/模型存储完全忽略 |
| GraphManager.search_hybrid | `odap/infra/graph/search_ops.py` L158-235 | 向量+关键词混合，Cypher 仅 CONTAINS | 无本体约束，搜索范围是全图 |
| GraphRetriever | `odap/biz/data/qa/retrieval/graph_retriever.py` L94-243 | 唯一利用本体 schema 的组件 | **未集成到 RAGPipeline**，独立存在 |
| MultiHopPlanner | `odap/biz/data/qa/impl/multihop_planner.py` L105-567 | 关键词+LLM 复杂度检测和分解 | 查询分解完全不知道本体 schema |
| QAEngineV2.ask | `odap/biz/data/qa/qa_engine.py` L988-1311 | 获取 ontology_ids 后仅透传给 RAG | 无输入门控、无输出验证 |
| SchemaSourceImpl | `odap/infra/query/sources/schema_source.py` | 可查询 object_types/link_definitions | 仅被 QueryService 使用，RAG 流程未利用 |
| OntologyService | `odap/biz/core/ontology/ontology_api/services/ontology_service.py` | 完整的 CRUD + schema snapshot | RAG 流程未引用 |

### 数据流现状

```
用户查询 → QAEngineV2.ask()
  ├─ _get_ontology_ids_for_scenario() → ontology_ids (仅从场景绑定获取)
  ├─ _execute_multihop_retrieval()
  │   ├─ MultiHopPlanner.detect_complexity() (无本体感知)
  │   └─ RAGPipeline.retrieve()
  │       ├─ _retrieve_from_graphiti() (ontology_ids 后过滤)
  │       ├─ _retrieve_from_sqlite() (ontology_ids 未使用!)
  │       ├─ _retrieve_from_semantic_map() (无本体约束)
  │       └─ _retrieve_from_model_storage() (无本体约束)
  └─ _generate_answer() (无输出验证)
```

### 缺失组件

1. **OntologyGate** - 本体门控服务：输入验证 + 输出验证
2. **OntologyAwareSearchOps** - 基于本体约束的图谱搜索
3. **GraphRetriever → RAGPipeline 集成** - 将已有的本体感知检索器接入主流程
4. **SchemaAwarePlanner** - 本体感知的查询分解

## Solution

### 架构概览

```
用户查询 → QAEngineV2.ask()
  ├─ OntologyGate.validate_input(query, ontology_ids) ← 新增：输入门控
  │   ├─ 提取查询中的实体类型/关系类型
  │   ├─ 与 ontology schema 交叉验证
  │   └─ 返回: {valid, matched_types, suggested_scope, rewritten_query}
  ├─ _execute_multihop_retrieval() (增强)
  │   ├─ SchemaAwarePlanner.plan(query, ontology_schema) ← 增强：本体感知分解
  │   └─ RAGPipeline.retrieve() (增强)
  │       ├─ _retrieve_from_graphiti() (增强：本体约束 Cypher)
  │       ├─ _retrieve_from_sqlite() (修复：ontology_ids 生效)
  │       ├─ _retrieve_from_semantic_map() (增强：本体约束)
  │       ├─ _retrieve_from_model_storage() (增强：本体约束)
  │       └─ _retrieve_from_graph_retriever() ← 新增：集成 GraphRetriever
  ├─ OntologyGate.validate_output(rag_results, ontology_ids) ← 新增：输出门控
  └─ _generate_answer() (不变)
```

### 关键决策

1. **门控策略**: "先验证后检索"而非"先检索后过滤"——输入门控拒绝明显不在 schema 内的查询，输出门控降级不符合本体的结果
2. **向后兼容**: 所有新增参数均有默认值，`ontology_ids=None` 时行为与当前完全一致
3. **渐进式集成**: GraphRetriever 作为第5个数据源加入 RAGPipeline，不替换现有逻辑
4. **性能优先**: 本体 schema 缓存（TTL 5分钟），避免每次查询都读 DB

## Phases

### Phase 1: 修复 ontology_ids 透传 + 输入门控 (P0, 预计 2 天)

**目标**: 让已有的 `ontology_ids` 参数真正在所有检索路径中生效，并增加输入门控

#### Task 1.1: 修复 `_retrieve_from_sqlite` 中 ontology_ids 未使用的问题

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py) L461-548
- **修改**: 在 `_retrieve_from_sqlite()` 方法中，当 `ontology_ids` 非空时，过滤 `entity_type` 是否在本体定义的对象类型列表中
- **具体步骤**:
  1. 在方法开头，若 `ontology_ids` 非空，从 `OntologyService` 获取每个 ontology 的 object_type 名称列表
  2. 遍历 entities 时，检查 `entity.get("entity_type")` 是否在允许的类型列表中
  3. 若不在列表中，跳过该实体或降低其分数
- **向后兼容**: `ontology_ids=None` 时行为不变
- **验证**: 单元测试 `_retrieve_from_sqlite` 传入 `ontology_ids` 时正确过滤

#### Task 1.2: 修复 `_retrieve_from_semantic_map` 中无本体约束的问题

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py) L550-632
- **修改**: 增加 `ontology_ids` 参数，过滤 `type_definition_id` 属于指定本体的对象
- **具体步骤**:
  1. 方法签名增加 `ontology_ids: Optional[List[str]] = None`
  2. 遍历 `sm.objects` 时，若 `ontology_ids` 非空，检查 `obj.type_definition_id` 是否属于指定本体
  3. 不匹配的对象降低分数（不直接排除，因为语义地图对象可能跨本体复用）
- **向后兼容**: `ontology_ids=None` 时行为不变
- **验证**: 单元测试传入 `ontology_ids` 时语义地图结果正确加权

#### Task 1.3: 修复 `_retrieve_from_model_storage` 中无本体约束的问题

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py) L634-742
- **修改**: 增加 `ontology_ids` 参数，优先检索属于指定本体的实体类型实例
- **具体步骤**:
  1. 方法签名增加 `ontology_ids: Optional[List[str]] = None`
  2. 若 `ontology_ids` 非空，从 `OntologyService` 获取本体下的 type_id 列表
  3. 遍历 `entity_types` 时，优先处理属于指定本体的类型
  4. 不属于指定本体的类型实例降低分数
- **向后兼容**: `ontology_ids=None` 时行为不变
- **验证**: 单元测试传入 `ontology_ids` 时模型存储结果正确加权

#### Task 1.4: 修复 `RAGPipeline.retrieve()` 中 `ontology_ids` 未透传的问题

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py) L256-340
- **修改**: 将 `ontology_ids` 透传到 `_retrieve_from_semantic_map` 和 `_retrieve_from_model_storage`
- **具体步骤**:
  1. 调用 `_retrieve_from_semantic_map` 时传入 `ontology_ids`
  2. 调用 `_retrieve_from_model_storage` 时传入 `ontology_ids`
- **验证**: 集成测试验证 `ontology_ids` 在所有4个检索路径中生效

#### Task 1.5: 创建 `OntologyGate` 输入门控服务

- **新文件**: `odap/biz/data/qa/ontology_gate.py`
- **功能**:
  - `validate_input(query, ontology_ids) -> OntologyGateResult`: 验证查询是否在 ontology schema 范围内
  - `validate_output(rag_results, ontology_ids) -> List[RAGResult]`: 验证检索结果是否符合本体定义
- **输入门控逻辑**:
  1. 从查询中提取实体类型关键词（利用现有 `_extract_search_terms`）
  2. 加载 ontology schema（object_types + link_types），缓存5分钟
  3. 匹配查询关键词与 schema 中的类型名/显示名/别名
  4. 返回: `{valid, matched_types, confidence, suggested_scope}`
  5. 若 `matched_types` 为空且查询非泛化查询（如"有哪些类型"），标记 `valid=False`
- **输出门控逻辑**:
  1. 遍历 RAG 结果，检查 `metadata.entity_type` 是否在本体定义的类型列表中
  2. 不匹配的结果分数乘以 0.3（降级但不排除）
  3. 匹配的结果分数乘以 1.2（提升）
- **向后兼容**: `ontology_ids=None` 时 `validate_input` 返回 `{valid=True}`，`validate_output` 不修改分数
- **验证**: 单元测试覆盖输入门控的匹配/不匹配/空本体场景

#### Task 1.6: 在 `QAEngineV2.ask()` 中集成输入门控

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py) L988-1311
- **修改**: 在获取 `ontology_ids` 之后、执行检索之前，调用 `OntologyGate.validate_input()`
- **具体步骤**:
  1. 在 `__init__` 中初始化 `self._ontology_gate = OntologyGate()`
  2. 在 `ask()` 中，获取 `ontology_ids` 后调用 `gate_result = self._ontology_gate.validate_input(query, ontology_ids)`
  3. 若 `gate_result.valid == False`，在日志中记录警告，但不阻止检索（降级而非拒绝）
  4. 将 `gate_result.matched_types` 注入到 RAG 检索的上下文中
- **向后兼容**: 门控结果仅影响日志和分数，不改变流程
- **验证**: 集成测试验证门控在 `ontology_ids` 存在时生效

#### Task 1.7: 在 `QAEngineV2.ask()` 中集成输出门控

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py)
- **修改**: 在 RAG 检索结果返回后，调用 `OntologyGate.validate_output()`
- **具体步骤**:
  1. 在 `rag_results` 获取后，调用 `rag_results = self._ontology_gate.validate_output(rag_results, ontology_ids)`
  2. 重新排序结果
- **验证**: 集成测试验证输出门控正确调整分数

**Phase 1 交付物**:
- `ontology_ids` 在所有4个检索路径中生效
- `OntologyGate` 输入/输出门控服务
- 完整的单元测试覆盖

---

### Phase 2: GraphRetriever 集成 + 本体约束图谱搜索 (P0, 预计 3 天)

**目标**: 将已有的 GraphRetriever 集成到主 RAG 流程，并增强图谱搜索的本体约束

#### Task 2.1: 在 RAGPipeline 中集成 GraphRetriever 作为第5个数据源

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py) L245-340
- **修改**:
  1. `RAGPipeline.__init__` 增加 `graph_retriever=None` 参数
  2. 新增 `_retrieve_from_graph_retriever()` 方法
  3. 在 `retrieve()` 中，在所有数据源检索之后，增加 GraphRetriever 检索
  4. 将 `RetrievalResult` 转换为 `RAGResult`
- **具体实现**:
  ```python
  def _retrieve_from_graph_retriever(self, query, top_k, workspace_id, scenario_id, ontology_ids):
      if not self.graph_retriever:
          return []
      try:
          results = self.graph_retriever.search(
              query, top_k=top_k,
              workspace_id=workspace_id or "",
              scenario_id=scenario_id,
              mode="auto"
          )
          rag_results = []
          for r in results:
              rag_results.append(RAGResult(
                  content=r.content,
                  source=f"graph:{r.source}",
                  score=r.score,
                  metadata={**r.metadata, "pillar": r.pillar}
              ))
          return rag_results
      except Exception as e:
          logger.warning(f"RAG GraphRetriever search failed: {e}")
          return []
  ```
- **向后兼容**: `graph_retriever=None` 时完全不影响现有逻辑
- **验证**: 单元测试 GraphRetriever 集成路径

#### Task 2.2: 在 QAEngineV2 中初始化并注入 GraphRetriever

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py) L881-911
- **修改**: 在 `QAEngineV2.__init__` 中创建 `GraphRetriever` 实例并注入 `RAGPipeline`
- **具体步骤**:
  1. `from odap.biz.data.qa.retrieval.graph_retriever import GraphRetriever, CypherGenerator`
  2. 创建 `cypher_gen = CypherGenerator(llm_client=None)`
  3. 创建 `graph_retriever = GraphRetriever(graph_manager=graphiti_client, cypher_generator=cypher_gen)`
  4. 传入 `RAGPipeline(graph_retriever=graph_retriever)`
- **验证**: 集成测试验证 GraphRetriever 在 QAEngineV2 中正确初始化

#### Task 2.3: 增强 GraphRetriever 的本体感知能力

- **文件**: [graph_retriever.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/retrieval/graph_retriever.py) L94-243
- **修改**: `search()` 方法增加 `ontology_ids` 参数，在 Cypher 生成和模板选择时注入本体约束
- **具体步骤**:
  1. `search()` 签名增加 `ontology_ids: Optional[List[str]] = None`
  2. 当 `ontology_ids` 非空时，调用 `_get_schema()` 获取类型定义
  3. 将类型定义注入 `CypherGenerator.generate()` 的 schema 参数
  4. 在 `_search_neighbors` 中，Cypher 增加 `WHERE n.ontology_id IN $oids` 过滤
  5. 在 `_search_traverse` 中，同理增加本体过滤
- **向后兼容**: `ontology_ids=None` 时行为不变
- **验证**: 单元测试 GraphRetriever 传入 `ontology_ids` 时正确约束搜索范围

#### Task 2.4: 增强 GraphManager.search_hybrid 的本体约束

- **文件**: [search_ops.py](file:///e:/DEMO/AI/ontology-graphiti/odap/infra/graph/search_ops.py) L158-235
- **修改**: `search_hybrid()` 增加 `ontology_ids` 参数，在 Cypher 查询中注入本体约束
- **具体步骤**:
  1. `search_hybrid()` 签名增加 `ontology_ids: Optional[List[str]] = None`
  2. 在关键词检索的 Cypher 中，若 `ontology_ids` 非空，增加 `AND n.ontology_id IN $oids` 条件
  3. 向量检索结果也按 `ontology_id` 后过滤
- **向后兼容**: `ontology_ids=None` 时行为不变
- **验证**: 单元测试验证本体约束 Cypher 正确生成

#### Task 2.5: 增强 `_retrieve_from_graphiti` 使用本体约束搜索

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py) L358-431
- **修改**: 将 `ontology_ids` 传入 `search_hybrid()`，从"后过滤"升级为"约束检索"
- **具体步骤**:
  1. 调用 `self.graphiti.search_hybrid(query, top_k, ontology_ids=ontology_ids)` （若方法支持）
  2. 保留现有的后过滤逻辑作为双重保障
- **验证**: 集成测试验证图谱搜索从"后过滤"升级为"约束检索"

**Phase 2 交付物**:
- GraphRetriever 作为第5个数据源集成到 RAGPipeline
- GraphManager.search_hybrid 支持本体约束
- 图谱搜索从"先检索后过滤"升级为"按本体约束检索"

---

### Phase 3: 本体感知的 MultiHopPlanner (P1, 预计 2 天)

**目标**: 让查询分解感知本体 schema，生成更精确的子查询

#### Task 3.1: 创建 `SchemaContext` 数据类

- **文件**: `odap/biz/data/qa/impl/multihop_planner.py`
- **修改**: 在文件顶部新增 `SchemaContext` 数据类
- **具体实现**:
  ```python
  @dataclass
  class SchemaContext:
      """本体 schema 上下文，供 MultiHopPlanner 使用"""
      entity_types: List[str] = field(default_factory=list)    # 对象类型名称列表
      relation_types: List[str] = field(default_factory=list)  # 关系类型名称列表
      action_types: List[str] = field(default_factory=list)    # 动作类型名称列表
      type_aliases: Dict[str, List[str]] = field(default_factory=dict)  # 类型名→别名列表
      type_properties: Dict[str, List[str]] = field(default_factory=dict)  # 类型名→属性名列表
  ```
- **验证**: 无需单独测试，作为后续任务的基础

#### Task 3.2: 增强 `MultiHopPlanner.plan()` 接受 SchemaContext

- **文件**: [multihop_planner.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/impl/multihop_planner.py) L238-284
- **修改**: `plan()` 方法增加 `schema_context: Optional[SchemaContext] = None` 参数
- **具体步骤**:
  1. 当 `schema_context` 非空时，在 LLM 分解的 prompt 中注入 schema 信息
  2. 在规则分解中，利用 `schema_context.entity_types` 识别查询中的实体类型引用
  3. 在 `_plan_relational()` 中，利用 `schema_context.relation_types` 识别关系型查询的具体关系
- **向后兼容**: `schema_context=None` 时行为不变
- **验证**: 单元测试验证 schema 感知的查询分解

#### Task 3.3: 增强 `_plan_with_llm()` 注入本体 schema

- **文件**: [multihop_planner.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/impl/multihop_planner.py) L360-416
- **修改**: 在 LLM prompt 中注入本体 schema 信息
- **具体步骤**:
  1. 在 `system_prompt` 中增加 schema 描述段落
  2. 格式: "已知本体定义了以下实体类型: {entity_types}，关系类型: {relation_types}。请基于这些类型分解查询。"
  3. 要求 LLM 返回的子查询中引用具体的类型名
- **验证**: 单元测试验证 LLM prompt 包含 schema 信息

#### Task 3.4: 增强 `detect_complexity()` 利用 schema 上下文

- **文件**: [multihop_planner.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/impl/multihop_planner.py) L286-354
- **修改**: 当查询涉及多个本体类型时，自动提升复杂度
- **具体步骤**:
  1. 在 `detect_complexity()` 中增加 `schema_context` 参数
  2. 检查查询中是否引用了多个 `entity_types` 中的类型名
  3. 若引用了 2+ 个类型，且查询含关系型关键词，提升为 COMPLEX
- **验证**: 单元测试验证跨类型查询的复杂度提升

#### Task 3.5: 在 QAEngineV2 中构建 SchemaContext 并传入 Planner

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py)
- **修改**: 在 `_execute_multihop_retrieval()` 中，当 `ontology_ids` 非空时，构建 `SchemaContext` 并传入 planner
- **具体步骤**:
  1. 从 `OntologyService` 获取本体类型定义
  2. 构建 `SchemaContext` 实例
  3. 传入 `self._multihop_planner.plan(query, schema_context=schema_context)`
- **验证**: 集成测试验证 schema 感知的多跳检索

**Phase 3 交付物**:
- `SchemaContext` 数据类
- `MultiHopPlanner` 支持本体感知的查询分解
- 复杂度检测利用 schema 上下文

---

### Phase 4: 本体 Schema 缓存 + 性能优化 (P1, 预计 1.5 天)

**目标**: 避免每次查询都读取本体定义，增加缓存层

#### Task 4.1: 创建 `OntologySchemaCache`

- **新文件**: `odap/biz/data/qa/ontology_schema_cache.py`
- **功能**: 缓存本体 schema，TTL 5分钟，按 ontology_id 索引
- **具体实现**:
  ```python
  class OntologySchemaCache:
      def __init__(self, ttl_seconds: int = 300):
          self._cache: Dict[str, Tuple[float, SchemaContext]] = {}
          self._ttl = ttl_seconds

      def get(self, ontology_ids: List[str]) -> Optional[SchemaContext]:
          """获取合并的 SchemaContext，若缓存过期返回 None"""

      def put(self, ontology_ids: List[str], schema: SchemaContext) -> None:
          """写入缓存"""

      def invalidate(self, ontology_id: str) -> None:
          """使某个本体的缓存失效"""
  ```
- **验证**: 单元测试覆盖缓存命中/过期/失效

#### Task 4.2: 在 OntologyGate 和 QAEngineV2 中使用缓存

- **文件**: `odap/biz/data/qa/ontology_gate.py`, `odap/biz/data/qa/qa_engine.py`
- **修改**: 所有读取本体 schema 的地方改为从缓存读取
- **验证**: 性能测试验证缓存命中后查询耗时降低

#### Task 4.3: 检索策略选择优化

- **文件**: [qa_engine.py](file:///e:/DEMO/AI/ontology-graphiti/odap/biz/data/qa/qa_engine.py)
- **修改**: 根据门控结果和复杂度，选择不同的检索策略
- **策略矩阵**:
  | 门控结果 | 复杂度 | 策略 |
  |---------|--------|------|
  | valid=True, matched_types>=1 | SIMPLE | 仅 SQLite + ModelStorage（快速路径） |
  | valid=True, matched_types>=1 | MEDIUM/COMPLEX | 全数据源 + GraphRetriever |
  | valid=False | any | 全数据源 + 日志警告 |
  | ontology_ids=None | any | 全数据源（当前行为） |
- **验证**: 集成测试验证不同策略路径

**Phase 4 交付物**:
- `OntologySchemaCache` 缓存服务
- 检索策略选择优化
- 性能测试报告

---

### Phase 5: 测试完善 + 文档更新 (P2, 预计 1.5 天)

**目标**: 完善测试覆盖，更新相关文档

#### Task 5.1: 新增 `test_ontology_gate.py` 单元测试

- **文件**: `tests/unit/test_ontology_gate.py`
- **覆盖场景**:
  - `validate_input`: 匹配/不匹配/空本体/泛化查询
  - `validate_output`: 分数调整/空结果/ontology_ids=None
  - 缓存命中/过期

#### Task 5.2: 新增 `test_ontology_schema_cache.py` 单元测试

- **文件**: `tests/unit/test_ontology_schema_cache.py`
- **覆盖场景**: CRUD/过期/失效/并发安全

#### Task 5.3: 增强 `test_qa_engine.py` 覆盖本体门控路径

- **文件**: `tests/unit/test_qa_engine.py`（如已存在则增强）
- **覆盖场景**:
  - `ontology_ids` 在所有检索路径中生效
  - GraphRetriever 集成路径
  - SchemaContext 传入 Planner 路径
  - 检索策略选择

#### Task 5.4: 增强 `test_multihop_planner.py` 覆盖 schema 感知路径

- **文件**: `tests/unit/test_multihop_planner.py`（如已存在则增强）
- **覆盖场景**:
  - `SchemaContext` 注入 LLM prompt
  - 跨类型查询复杂度提升
  - 规则分解利用 schema

**Phase 5 交付物**:
- 完整的单元测试覆盖
- 所有测试通过

## Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| 本体 schema 读取增加查询延迟 | Medium | Medium | Phase 4 的缓存机制，TTL 5分钟；首次查询后缓存命中 |
| GraphRetriever 的 Cypher 生成可能失败 | Low | Medium | 降级到模板 Cypher；GraphRetriever 已有 fallback 机制 |
| 本体门控误拒绝合法查询 | High | Low | 输入门控仅降级不拒绝；泛化查询（"有哪些类型"）始终放行 |
| `ontology_ids` 过滤导致零结果 | Medium | Medium | 输出门控不排除结果仅降级分数；日志记录零结果情况供调试 |
| MultiHopPlanner LLM 分解不稳定 | Low | Medium | 保留规则回退；schema 注入为增强而非替代 |
| 向后兼容性破坏 | High | Low | 所有新参数均有默认值；`ontology_ids=None` 时行为与当前完全一致 |
| OntologyService 与 OMS Service 的数据不一致 | Medium | Medium | 优先使用 OMS Service（全局注册表），OntologyService 作为补充 |

## Validation

### 单元测试要求

| 模块 | 必测场景 |
|------|---------|
| `OntologyGate` | 输入验证匹配/不匹配/空本体/泛化查询；输出验证分数调整/ontology_ids=None |
| `OntologySchemaCache` | 缓存命中/过期/失效/合并多个 ontology |
| `RAGPipeline._retrieve_from_sqlite` | ontology_ids 过滤/ontology_ids=None |
| `RAGPipeline._retrieve_from_semantic_map` | ontology_ids 加权/ontology_ids=None |
| `RAGPipeline._retrieve_from_model_storage` | ontology_ids 优先/ontology_ids=None |
| `RAGPipeline._retrieve_from_graph_retriever` | 正常检索/graph_retriever=None |
| `GraphRetriever.search` | ontology_ids 约束/ontology_ids=None |
| `GraphManager.search_hybrid` | ontology_ids Cypher 约束/ontology_ids=None |
| `MultiHopPlanner.plan` | schema_context 注入/schema_context=None |
| `MultiHopPlanner.detect_complexity` | 跨类型提升/schema_context=None |

### 集成测试要求

- 端到端 QA 流程：查询 → 门控 → 检索 → 输出验证 → 回答
- `ontology_ids` 在完整流程中生效
- GraphRetriever 集成后结果质量不降级

### 手动 QA 步骤

1. 启动服务 `python bootstep.py dev`
2. 创建工作空间 + 场景 + 本体（使用西游记示例）
3. 绑定本体到场景
4. 摄入知识数据
5. 测试查询:
   - "孙悟空的师傅是谁？" — 应命中本体类型"人物"，门控通过
   - "有哪些雷达？" — 若本体无"雷达"类型，门控降级但不拒绝
   - "孙悟空和猪八戒的关系" — 多类型查询，复杂度提升
6. 验证日志中包含门控结果和检索策略选择信息
7. 运行 `pytest tests/unit/ -v` 确认所有测试通过
