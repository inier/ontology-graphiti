# 建模-语义层-抽取体系化设计

> 日期: 2026-06-15
> 状态: Approved
> 关联 ADR: ADR-036, ADR-038, ADR-048

---

## 1. 问题陈述

当前平台存在三套并行的本体类型定义体系（OntologyService / OMSService / ModelService），数据互不联通，导致：

1. **建模→语义断裂**：语义层业务资产（规则/逻辑/指标/过程）的 `schema_type_id` 和 `ontology_id` 是软关联，无验证逻辑
2. **建模→抽取断裂**：非结构化数据抽取不依赖已有模型定义，LLM 抽取时无上下文约束，结果可能命名冲突
3. **建模→摄入断裂**：数据摄入不要求 `ontology_id`，不验证 entity_type 是否已定义
4. **三套体系数据不一致**：同一概念在不同体系中有不同模型（object_type vs entity_type vs ObjectTypeDefinition）

### 根因

- **ModelService**（Design Layer）：Palantir AIP 对齐的蓝图设计器，以 OntologyDocument 为核心
- **OMSService**（Application Layer）：平台内置元数据注册表，为 OPA/Action 引擎提供运行时类型信息
- **OntologyService**（API Layer）：最晚出现的完整 CRUD 层，7 种类型定义 + 版本管理

ADR-036 Amendment 提出 "OntologyDocument JSON serves as the unified atomic format"，但从未在代码层面实现。

---

## 2. 统一架构

### 2.1 三层架构

```
┌─────────────────────────────────────────────────────────┐
│  统一管理界面 (Frontend)                                  │
│  建模管理 | 语义层管理 | 抽取管理 | 摄入管理               │
└──────────────────────┬──────────────────────────────────┘
                       │ 统一 API
┌──────────────────────v──────────────────────────────────┐
│  TypeRegistry (统一读写入口)                              │
│  - 所有类型定义的创建/查询/更新/删除                       │
│  - 两阶段抽取（探索性 + 约束性）                          │
│  - 摄入契约校验                                          │
│  - 语义层一致性验证                                       │
│  - OMS 同步（写入时自动同步用户自定义类型到 OMS）           │
└──────────┬───────────────────────┬──────────────────────┘
           │ 写入                   │ 读取
┌──────────v──────────┐  ┌─────────v─────────────────────┐
│  OntologyService    │  │  OMSService (只读缓存)          │
│  (唯一权威源)        │  │  - 平台核心实体元数据（种子数据）│
│  - 7种类型定义       │  │  - 从 OntologyService 同步     │
│  - OntologyDocument │  │    用户自定义类型               │
│  - 版本管理          │  │  - 下游11个消费者不变           │
│  - 抽取会话          │  └───────────────────────────────┘
└─────────────────────┘
```

### 2.2 关键决策

| 决策 | 说明 |
|------|------|
| OntologyService 为唯一权威源 | 所有用户自定义类型定义的写入必须经过 TypeRegistry → OntologyService |
| OMS 保留为只读缓存 | 平台核心实体（Agent/Workspace 等）的元数据仍由 OMS 种子数据提供；用户自定义类型从 OntologyService 同步 |
| ModelService 逐步合并 | entity_type → OntologyService.object_type，instance → IngestService，document → OntologyService.ontology_version |
| OntologyDocument JSON 为统一格式 | 类型定义的序列化/导出/版本快照统一使用此格式 |

---

## 3. TypeRegistry 统一读写入口

### 3.1 位置

`odap/biz/core/ontology/registry/`

```
registry/
├── __init__.py
├── type_registry.py          # TypeRegistry 主类
├── oms_sync.py               # OMS 同步适配器
├── models.py                 # 注册表专用模型
└── api/
    ├── routes.py             # /api/ontology/registry/*
    └── schemas.py            # 请求/响应模型
```

### 3.2 TypeRegistry 核心接口

```python
class TypeRegistry:
    """统一类型定义读写入口"""

    def __init__(self):
        self._ontology_service = OntologyService()
        self._oms_sync = OMSSyncAdapter()

    # === 类型定义 CRUD ===
    def create_type(self, ontology_id: str, type_category: str, definition: dict) -> dict:
        """创建类型定义，同步到 OMS"""
        result = self._ontology_service.create_object_type(ontology_id, definition)
        self._oms_sync.sync_to_oms(type_category, result)
        return result

    def get_type(self, ontology_id: str, type_category: str, type_id: str) -> dict | None:
        """查询类型定义（优先从 OntologyService）"""
        return self._ontology_service.get_object_type(ontology_id, type_id)

    def list_types(self, ontology_id: str, type_category: str, **filters) -> list[dict]:
        """列出类型定义"""
        return self._ontology_service.list_object_types(ontology_id, **filters)

    def update_type(self, ontology_id: str, type_category: str, type_id: str, updates: dict) -> dict:
        """更新类型定义，同步到 OMS"""
        result = self._ontology_service.update_object_type(ontology_id, type_id, updates)
        self._oms_sync.sync_to_oms(type_category, result)
        return result

    def delete_type(self, ontology_id: str, type_category: str, type_id: str) -> bool:
        """删除类型定义，同步到 OMS"""
        result = self._ontology_service.delete_object_type(ontology_id, type_id)
        self._oms_sync.remove_from_oms(type_category, type_id)
        return result

    # === 跨本体查询 ===
    def search_types(self, query: str, type_category: str | None = None) -> list[dict]:
        """跨本体搜索类型定义"""
        ...

    def get_type_references(self, type_id: str) -> list[dict]:
        """查询类型被哪些语义层资产引用"""
        ...

    # === 一致性检查 ===
    def validate_consistency(self, ontology_id: str, version_id: str | None = None) -> dict:
        """验证本体类型定义与语义层资产的一致性"""
        ...
```

### 3.3 OMS 同步适配器

```python
class OMSSyncAdapter:
    """将 OntologyService 的类型定义同步到 OMS 只读缓存"""

    def sync_to_oms(self, type_category: str, type_def: dict):
        """写入/更新 OMS 缓存"""
        if type_category == "object_types":
            # 将 OntologyService 的 object_type 映射为 OMS 的 ObjectTypeDefinition
            oms_type = self._map_to_oms_object_type(type_def)
            self._oms_storage.save_object_type(oms_type)
        elif type_category == "action_types":
            oms_action = self._map_to_oms_action_type(type_def)
            self._oms_storage.save_action_type(oms_action)

    def remove_from_oms(self, type_category: str, type_id: str):
        """从 OMS 缓存中删除"""
        ...

    def full_sync(self, ontology_id: str):
        """全量同步某个本体的所有类型定义到 OMS"""
        ...
```

### 3.4 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ontology/registry/types` | 创建类型定义 |
| GET | `/api/ontology/registry/types` | 列出类型定义 |
| GET | `/api/ontology/registry/types/{type_id}` | 查询类型定义 |
| PUT | `/api/ontology/registry/types/{type_id}` | 更新类型定义 |
| DELETE | `/api/ontology/registry/types/{type_id}` | 删除类型定义 |
| GET | `/api/ontology/registry/search` | 跨本体搜索 |
| GET | `/api/ontology/registry/types/{type_id}/references` | 查询引用 |
| POST | `/api/ontology/registry/validate` | 一致性验证 |
| POST | `/api/ontology/registry/sync` | 手动触发 OMS 同步 |

---

## 4. 两阶段抽取

### 4.1 问题

用户提到："如果是要从各类杂乱无章的数据里面抽取，如何提前定义这个对象？"

### 4.2 解决方案

```
阶段 1: 探索性抽取 (Exploratory Extraction)
  输入: 原始非结构化数据（文本/文档/网页）
  输出: 候选类型定义（draft 状态）
  特点: 不要求已有模型，LLM 从数据中推断类型结构
  约束: 候选类型必须经过用户审核才能变为 active

阶段 2: 约束性抽取 (Constrained Extraction)
  输入: 原始数据 + 已有模型定义
  输出: 符合类型约束的结构化数据
  特点: LLM 在类型约束下抽取，结果必须通过类型校验
  约束: 抽取结果必须符合已有类型定义的 schema
```

### 4.3 抽取流程

```
用户提交数据
  │
  ├─ 有目标本体？ ── 是 ──→ 约束性抽取
  │                          │
  │                          ├─ LLM Prompt 包含已有类型定义
  │                          ├─ 抽取结果通过类型校验
  │                          └─ 校验失败 → 告警 + 引导修改类型定义
  │
  └─ 无目标本体？ ── 是 ──→ 探索性抽取
                             │
                             ├─ LLM 从数据推断类型结构
                             ├─ 生成候选类型定义（draft）
                             ├─ 用户审核 → 确认/修改/拒绝
                             └─ 确认后创建本体 + 类型定义 → 可进入约束性抽取
```

### 4.4 ExtractionService 改造

```python
class ExtractionService:
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        if request.mode == "exploratory":
            return self._exploratory_extract(request)
        elif request.mode == "constrained":
            return self._constrained_extract(request)

    def _exploratory_extract(self, request):
        """探索性抽取：不要求已有模型"""
        result = self._schema_extractor.extract(request.text)
        # 标记所有候选类型为 draft
        for type_def in result.object_types:
            type_def["status"] = "draft"
        return result

    def _constrained_extract(self, request):
        """约束性抽取：基于已有模型定义"""
        # 加载目标本体的已有类型定义作为上下文
        existing_types = self._type_registry.list_types(
            request.ontology_id, "object_types"
        )
        result = self._schema_extractor.extract(
            request.text, context_types=existing_types
        )
        # 校验抽取结果与已有类型定义的一致性
        validation = self._validate_against_schema(result, existing_types)
        if not validation.valid:
            result.warnings = validation.warnings
        return result
```

---

## 5. 摄入契约

### 5.1 改造

- `UnifiedIngestFacade.ingest()` 新增 `ontology_id` 参数（必填）
- 摄入时验证 `entity_type` 是否在目标本体的类型定义中存在
- 未定义类型触发告警（不阻断），引导用户创建类型定义或选择探索性抽取

### 5.2 告警机制

```python
class IngestContractValidator:
    def validate(self, ontology_id: str, entities: list[dict]) -> ContractValidationResult:
        defined_types = self._type_registry.list_types(ontology_id, "object_types")
        defined_type_names = {t["name"] for t in defined_types}

        undefined_types = set()
        for entity in entities:
            if entity.get("entity_type") not in defined_type_names:
                undefined_types.add(entity["entity_type"])

        if undefined_types:
            return ContractValidationResult(
                valid=False,
                undefined_types=undefined_types,
                suggestion="以下类型未在本体中定义，请先创建类型定义或使用探索性抽取",
            )
        return ContractValidationResult(valid=True)
```

---

## 6. 语义层一致性验证

### 6.1 验证规则

| 规则 | 说明 |
|------|------|
| ontology_id 存在性 | 业务资产关联的 ontology_id 必须存在 |
| schema_type_id 存在性 | 业务资产关联的 schema_type_id 必须在目标本体中存在 |
| 类型引用完整性 | 业务规则中引用的对象类型必须在本体类型定义中存在 |
| 版本一致性 | 业务资产关联的 version_id 必须是本体的有效版本 |

### 6.2 版本提交前验证

`commit_schema_version()` 前自动运行一致性检查，发现问题则阻止提交并返回错误列表。

---

## 7. 前端统一管理界面

### 7.1 建模管理

- 类型定义可视化（7 种类型及其关系图）
- 版本对比（diff 视图）
- 类型引用分析（哪些语义层资产使用了此类型）

### 7.2 语义层管理

- 业务资产与本体类型的关联管理
- 一致性验证结果展示
- 悬挂引用告警

### 7.3 抽取管理

- 抽取会话列表
- 候选类型审核（探索性抽取的 draft 类型）
- 抽取结果与已有类型的冲突解决

### 7.4 摄入管理

- 摄入数据与本体类型的映射状态
- 未定义类型告警
- 一键创建缺失类型定义

---

## 8. 实施阶段

### Phase 1: TypeRegistry + OMS 同步

- 创建 `odap/biz/core/ontology/registry/` 模块
- TypeRegistry 核心类 + OMSSyncAdapter
- API 端点 `/api/ontology/registry/*`
- OMS 写入路由代理到 TypeRegistry
- PerceptionHub 自动注册重定向到 TypeRegistry
- 前端 OMS API 切换到 Registry API

### Phase 2: 两阶段抽取 + 摄入契约

- ExtractionService 新增 exploratory/constrained 模式
- SchemaLevelExtractor 支持上下文类型定义
- IngestContractValidator
- UnifiedIngestFacade 新增 ontology_id 参数
- 前端抽取界面改造

### Phase 3: 语义层一致性验证

- BusinessService CRUD 时验证 schema_type_id
- 版本提交前一致性检查
- 前端验证结果展示

### Phase 4: 前端统一管理界面

- 建模管理页面
- 语义层管理页面
- 抽取管理页面
- 摄入管理页面

### Phase 5: ModelService 合并

- entity_type → OntologyService.object_type
- instance → IngestService 实体数据
- document → OntologyService.ontology_version
- 前端 Model API 切换
- ModelService 标记 deprecated
