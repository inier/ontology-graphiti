# Contract: UslManagerService + SqliteUslStorage — 38+ 方法完整签名（对齐 data-model.md §2 权威 6 张 USL 表）

**Location**:
- `SqliteUslStorage`: `odap/biz/semantic_admin/usl_manager/storage/sqlite_usl_storage.py`
- `UslManagerService`: `odap/biz/semantic_admin/usl_manager/services/usl_manager_service.py`
- `UslRepository` Protocol: `odap/biz/semantic_admin/usl_manager/interfaces/usl_repositories.py`
- `UslQueryEngine` Protocol: `odap/biz/semantic_admin/usl_manager/interfaces/usl_query_engine.py`

**依赖关系链**: `Routes` → `UslManagerService` → `UslRepositoryImpl + UslQueryEngineImpl` → `SqliteUslStorage` → `SQLite (WAL mode, 每次方法独立 connect/close)`

**对应 SQLite 表（6 张 · 对齐 data-model.md §2.1.1 ~ §2.1.6）**:
| 表名 | 中文说明 | Contract 方法分组 |
|------|---------|-----------------|
| `usl_domains` | 语义域（顶级命名空间） | Domain 组（10 方法） |
| `usl_terms` | 规范术语主表 | Term 组（12 方法） |
| `usl_term_synonyms` | 同义词/别名/停用词/歧义词 | Synonym 组（7 方法，原 term 内字段拆独立表） |
| `usl_term_hierarchies` | 层级边（is_a/part_of/has_role/member_of/located_in） | Hierarchy 组（8 方法，含环检测） |
| `usl_term_properties` | 术语属性规范（RDFS/Dublin-Core 扩展） | Property 组（8 方法，含按域批量） |
| `usl_cross_domain_mappings` | 跨域映射（SKOS exactMatch/closeMatch...） | CrossMapping 组（6 方法，原 disjoint+cardinality 合并此表用 mapping_type 区分） |
| **合计** | | **51 方法（含 storage + query + service 分层，plan.md Phase 0 #3 要求的 38 法指 service 层 38 公开法）** |

---

## Section 0: 通用数据类型（所有方法共享 — 对齐 §2.1 DDL CHECK 约束）

```python
from typing import Any, Protocol, runtime_checkable, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

# ============= 枚举（严格对齐 §2.1 CHECK 约束值） =============
class HierarchyType(str, Enum):
    """对齐 usl_term_hierarchies.hierarchy_type CHECK"""
    IS_A        = "is_a"
    PART_OF     = "part_of"
    HAS_ROLE    = "has_role"
    MEMBER_OF   = "member_of"
    LOCATED_IN  = "located_in"

class TermType(str, Enum):
    """对齐 usl_terms.term_type CHECK"""
    CLASS      = "class"
    RELATION   = "relation"
    EVENT      = "event"
    ATTRIBUTE  = "attribute"
    METRIC     = "metric"
    PROCESS    = "process"
    RULE       = "rule"

class SynonymType(str, Enum):
    """对齐 usl_term_synonyms.synonym_type CHECK"""
    ALIAS          = "alias"
    ABBREVIATION   = "abbreviation"
    ACRONYM        = "acronym"
    COLLOQUIAL     = "colloquial"
    TYPO           = "typo"
    STOPWORD       = "stopword"
    AMBIGUOUS      = "ambiguous"

class PropertyDatatype(str, Enum):
    """对齐 usl_term_properties.datatype CHECK"""
    STRING    = "string"
    INT       = "int"
    FLOAT     = "float"
    BOOL      = "bool"
    DATE      = "date"
    DATETIME  = "datetime"
    ENUM      = "enum"
    JSON      = "json"
    REF_TERM  = "ref_term"

class MappingType(str, Enum):
    """对齐 usl_cross_domain_mappings.mapping_type CHECK"""
    EXACT_MATCH    = "exact_match"
    CLOSE_MATCH    = "close_match"
    BROAD_MATCH    = "broad_match"
    NARROW_MATCH   = "narrow_match"
    RELATED_MATCH  = "related_match"

class MappingDirectionality(str, Enum):
    UNIDIRECTIONAL_SRC2TGT  = "unidirectional_src2tgt"
    BIDIRECTIONAL           = "bidirectional"

class SemanticRoleEnum(str, Enum):
    ONTOLOGY_ADMIN  = "ontology_admin"
    SCHEMA_AUDITOR  = "schema_auditor"
    DOMAIN_EDITOR   = "domain_editor"
    TERM_EDITOR     = "term_editor"
    REVIEWER        = "reviewer"
    VIEWER          = "viewer"

# ============= Pydantic 域模型（严格对齐 §2.1 表列） =============
class UslDomain(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    code: str
    display_name: str
    description: Optional[str] = None
    is_active: bool = True
    owner_role: SemanticRoleEnum = SemanticRoleEnum.ONTOLOGY_ADMIN
    config: dict[str, Any] = Field(default_factory=dict)   # → config_json JSON TEXT
    term_count: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime
    updated_by: str
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[str] = None

class UslTerm(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    domain_id: str
    canonical_name: str
    normalized_name: str
    display_name: Optional[str] = None
    term_type: TermType
    description: Optional[str] = None
    short_definition: Optional[str] = None
    is_deprecated: bool = False
    preferred_term_id: Optional[str] = None
    semantic_tags: list[str] = Field(default_factory=list)      # → semantic_tags_json
    examples: list[str] = Field(default_factory=list)          # → examples_json
    source_refs: dict[str, Any] = Field(default_factory=dict)  # → source_refs_json
    version: int = 1
    created_by: str
    created_at: datetime
    updated_at: datetime
    updated_by: str

class UslTermSynonym(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    term_id: str
    synonym_text: str
    normalized_synonym: str
    synonym_type: SynonymType = SynonymType.ALIAS
    ambiguity_targets: list[str] = Field(default_factory=list)   # → ambiguity_targets_json
    language_code: str = "zh-CN"
    frequency: int = 0
    is_blacklisted: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    created_by: str

class UslTermHierarchy(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    domain_id: str
    parent_term_id: str
    child_term_id: str
    hierarchy_type: HierarchyType = HierarchyType.IS_A
    depth_from_parent: int = 1
    is_inferred: bool = False
    inference_source: dict[str, Any] = Field(default_factory=dict)  # → inference_source_json
    sort_order: int = 0
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    version: int = 1
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str

class UslTermProperty(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    term_id: str
    property_code: str
    property_name: str
    datatype: PropertyDatatype
    is_required: bool = False
    is_unique: bool = False
    allow_multiple: bool = False
    enum_values: list[str] = Field(default_factory=list)          # → enum_values_json
    ref_domain_id: Optional[str] = None
    description: Optional[str] = None
    default_value: Any = None                                     # → default_value_json
    validation_rules: dict[str, Any] = Field(default_factory=dict)  # → validation_rules_json
    sort_order: int = 0
    version: int = 1
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str

class UslCrossDomainMapping(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    source_term_id: str
    target_term_id: str
    mapping_type: MappingType
    directionality: MappingDirectionality = MappingDirectionality.BIDIRECTIONAL
    confidence_score: float = Field(ge=0.0, le=1.0, default=1.0)
    mapping_reason: Optional[str] = None
    mapping_source: dict[str, Any] = Field(default_factory=dict)  # → mapping_source_json
    is_validated: bool = False
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str

# ============= 自定义异常（细粒度便于 HTTP 层翻译） =============
class UslException(Exception): ...
class DomainNotFoundError(UslException): ...
class DomainExistsError(UslException): ...
class DomainDeactivatedError(UslException): ...
class TermNotFoundError(UslException): ...
class TermDuplicateError(UslException): ...
class TermDeprecatedError(UslException): ...
class TermInUseError(UslException): ...
class SynonymNotFoundError(UslException): ...
class SynonymBlacklistedError(UslException): ...
class HierarchyCycleError(UslException): ...
class HierarchyEdgeDuplicateError(UslException): ...
class HierarchySelfReferenceError(UslException): ...
class PropertySpecInvalidError(UslException): ...
class PropertyDatatypeMismatchError(UslException): ...
class CrossMappingSameTermError(UslException): ...
class CrossMappingDuplicateError(UslException): ...
class RoleAssignmentError(UslException): ...
class SeedValidationError(UslException): ...
```

---

## Section 1: SqliteUslStorage — 21 个低阶 CRUD 方法（全部带幂等 ON CONFLICT DO UPDATE）

```python
class SqliteUslStorage:
    """SQLite USL 6 张核心表 DAO（WAL mode）。
    所有写入方法均幂等：UNIQUE 冲突走 ON CONFLICT DO UPDATE，而非抛 IntegrityError。
    **硬约束（AGENTS.md SQLite 存储规则）**：每个方法独立 `connect()` → 执行 → `close()`，禁止 self.conn 长连接单例。
    """

    def __init__(self, db_path: str): ...

    # ============= Group 1: Domain（4 方法）—— 表 usl_domains =============
    def upsert_domain(self, domain: UslDomain) -> UslDomain: ...
    def get_domain(self, domain_id: str) -> Optional[UslDomain]: ...
    def list_domains(self, q: Optional[str] = None, *,
                     is_active: Optional[bool] = None,
                     owner_role: Optional[SemanticRoleEnum] = None,
                     page: int = 1, page_size: int = 50) -> tuple[int, list[UslDomain]]: ...
    def delete_domain(self, domain_id: str, force: bool = False) -> None: ...

    # ============= Group 2: Term（4 方法）—— 表 usl_terms =============
    def upsert_term(self, term: UslTerm) -> UslTerm: ...
    def get_term(self, term_id: str) -> Optional[UslTerm]: ...
    def list_terms(self, *, domain_id: Optional[str] = None,
                   q: Optional[str] = None,
                   term_type: Optional[TermType | list[TermType]] = None,
                   is_deprecated: Optional[bool] = None,
                   parent_term_id: Optional[str] = None,   # JOIN usl_term_hierarchies 过滤
                   page: int = 1, page_size: int = 50) -> tuple[int, list[UslTerm]]: ...
    def delete_term(self, term_id: str, force: bool = False) -> None: ...

    # ============= Group 3: Synonym（3 方法）—— 表 usl_term_synonyms =============
    def upsert_synonym(self, syn: UslTermSynonym) -> UslTermSynonym: ...
    def list_synonyms(self, *, term_id: Optional[str] = None,
                      synonym_text_like: Optional[str] = None,
                      synonym_type: Optional[SynonymType | list[SynonymType]] = None,
                      is_blacklisted: Optional[bool] = None,
                      language_code: Optional[str] = None,
                      page: int = 1, page_size: int = 100) -> tuple[int, list[UslTermSynonym]]: ...
    def delete_synonym(self, synonym_id: str) -> None: ...

    # ============= Group 4: Hierarchy（3 方法 + 1 辅助）—— 表 usl_term_hierarchies =============
    def insert_hierarchy_edge(self, edge: UslTermHierarchy) -> UslTermHierarchy: ...
    def list_hierarchy_edges(self, *, domain_id: Optional[str] = None,
                             parent_term_id: Optional[str] = None,
                             child_term_id: Optional[str] = None,
                             root_id: Optional[str] = None, depth: int = 5,
                             hierarchy_type: Optional[HierarchyType] = None) -> list[UslTermHierarchy]: ...
    def delete_hierarchy_edge(self, edge_id: str) -> None: ...
    def detect_hierarchy_cycle(self, domain_id: str, parent_id: str, child_id: str,
                               hierarchy_type: HierarchyType = HierarchyType.IS_A
                               ) -> Optional[list[str]]:
        """检测若插入 parent→child 边是否会引入环。无环返回 None；有环返回环路径 [term_id, ...]。
        递归 CTE 从 child 出发沿 parent 向上，若命中 parent_id → 有环。"""

    # ============= Group 5: PropertySpec（3 方法）—— 表 usl_term_properties =============
    def upsert_property_spec(self, spec: UslTermProperty) -> UslTermProperty: ...
    def list_property_specs(self, *, term_id: Optional[str] = None,
                            property_code: Optional[str] = None,
                            datatype: Optional[PropertyDatatype] = None,
                            ref_domain_id: Optional[str] = None) -> list[UslTermProperty]: ...
    def delete_property_spec(self, spec_id: str) -> None: ...

    # ============= Group 6: CrossDomainMapping（3 方法）—— 表 usl_cross_domain_mappings =============
    def upsert_cross_mapping(self, mapping: UslCrossDomainMapping) -> UslCrossDomainMapping: ...
    def list_cross_mappings(self, *, source_term_id: Optional[str] = None,
                            target_term_id: Optional[str] = None,
                            mapping_type: Optional[MappingType] = None,
                            is_validated: Optional[bool] = None,
                            domain_id: Optional[str] = None) -> list[UslCrossDomainMapping]: ...
    def delete_cross_mapping(self, mapping_id: str) -> None: ...
```

---

## Section 2: UslRepository + UslQueryEngine Protocol（接口抽象 — 便于替换存储后端 / Mock）

```python
@runtime_checkable
class UslRepository(Protocol):
    """SqliteUslStorage 21 方法的协议定义。"""
    # Domain 4
    def upsert_domain(self, domain: UslDomain) -> UslDomain: ...
    def get_domain(self, domain_id: str) -> Optional[UslDomain]: ...
    def list_domains(self, q: Optional[str] = None, *, is_active: Optional[bool] = None,
                     owner_role: Optional[SemanticRoleEnum] = None,
                     page: int = 1, page_size: int = 50) -> tuple[int, list[UslDomain]]: ...
    def delete_domain(self, domain_id: str, force: bool = False) -> None: ...
    # Term 4
    def upsert_term(self, term: UslTerm) -> UslTerm: ...
    def get_term(self, term_id: str) -> Optional[UslTerm]: ...
    def list_terms(self, *, domain_id: Optional[str] = None, q: Optional[str] = None,
                   term_type: Optional[TermType | list[TermType]] = None,
                   is_deprecated: Optional[bool] = None,
                   parent_term_id: Optional[str] = None,
                   page: int = 1, page_size: int = 50) -> tuple[int, list[UslTerm]]: ...
    def delete_term(self, term_id: str, force: bool = False) -> None: ...
    # Synonym 3
    def upsert_synonym(self, syn: UslTermSynonym) -> UslTermSynonym: ...
    def list_synonyms(self, *, term_id: Optional[str] = None,
                      synonym_text_like: Optional[str] = None,
                      synonym_type: Optional[SynonymType | list[SynonymType]] = None,
                      is_blacklisted: Optional[bool] = None,
                      language_code: Optional[str] = None,
                      page: int = 1, page_size: int = 100) -> tuple[int, list[UslTermSynonym]]: ...
    def delete_synonym(self, synonym_id: str) -> None: ...
    # Hierarchy 4
    def insert_hierarchy_edge(self, edge: UslTermHierarchy) -> UslTermHierarchy: ...
    def list_hierarchy_edges(self, *, domain_id: Optional[str] = None,
                             parent_term_id: Optional[str] = None,
                             child_term_id: Optional[str] = None,
                             root_id: Optional[str] = None, depth: int = 5,
                             hierarchy_type: Optional[HierarchyType] = None) -> list[UslTermHierarchy]: ...
    def delete_hierarchy_edge(self, edge_id: str) -> None: ...
    def detect_hierarchy_cycle(self, domain_id: str, parent_id: str, child_id: str,
                               hierarchy_type: HierarchyType = HierarchyType.IS_A) -> Optional[list[str]]: ...
    # PropertySpec 3
    def upsert_property_spec(self, spec: UslTermProperty) -> UslTermProperty: ...
    def list_property_specs(self, *, term_id: Optional[str] = None,
                            property_code: Optional[str] = None,
                            datatype: Optional[PropertyDatatype] = None,
                            ref_domain_id: Optional[str] = None) -> list[UslTermProperty]: ...
    def delete_property_spec(self, spec_id: str) -> None: ...
    # CrossMapping 3
    def upsert_cross_mapping(self, mapping: UslCrossDomainMapping) -> UslCrossDomainMapping: ...
    def list_cross_mappings(self, *, source_term_id: Optional[str] = None,
                            target_term_id: Optional[str] = None,
                            mapping_type: Optional[MappingType] = None,
                            is_validated: Optional[bool] = None,
                            domain_id: Optional[str] = None) -> list[UslCrossDomainMapping]: ...
    def delete_cross_mapping(self, mapping_id: str) -> None: ...

@runtime_checkable
class UslQueryEngine(Protocol):
    """查询增强：同义词回查 + 层级双向展开 + domain 内去重合并。"""

    def lookup_terms_by_synonym(self, domain_id: str, text: str, *,
                                fuzziness: float = 0.7,
                                include_blacklisted: bool = False,
                                top_k: int = 50) -> list[tuple[UslTerm, list[UslTermSynonym]]]:
        """text 与 usl_term_synonyms.normalized_synonym 做 LIKE + 编辑距离 ≥ fuzziness 匹配，
        返回 (term, hit_synonyms 列表) 元组列表（按 term_id 去重）。
        主要用于 OL L1-1 USL 对齐阶段。"""

    def expand_hierarchy_up(self, domain_id: str, start_term_id: str, *,
                            hierarchy_type: Optional[HierarchyType] = None,
                            max_depth: int = 10) -> list[UslTermHierarchy]:
        """层级上溯：从 start_term_id 沿 parent 方向 → domain 根。返回完整路径边列表（按深度升序）。"""

    def expand_hierarchy_down(self, domain_id: str, start_term_id: str, *,
                              hierarchy_type: Optional[HierarchyType] = None,
                              max_depth: int = 10) -> list[UslTermHierarchy]:
        """层级下钻：从 start_term_id 沿 child 方向 → 子树。返回完整路径边列表（BFS 顺序）。"""

    def merge_term_by_normalized_name(self, domain_id: str, normalized_name: str) -> Optional[UslTerm]:
        """domain 内精确匹配 normalized_name → 返回合并后的目标 term（用于 OL 去重）。"""
```

---

## Section 3: UslManagerService — **38 法**（plan.md Phase 0 #3 要求：Domain 10 + Term 12 + Hierarchy 8 + Property 8 = 38；Synonym + CrossMapping 实际为 Service 层额外扩展，合计 49 公开法）

```python
from uuid import uuid4
from datetime import datetime, timezone

class UslManagerService:
    """USL 业务门面。依赖注入 UslRepository + UslQueryEngine。
    所有 public 方法保证：
    (1) 先 validate 域规则，再 delegate 到 repo
    (2) DB/Repo 错误封装为 UslException 子类（不抛 IntegrityError / sqlite3.Error）
    (3) 写操作自动刷新 updated_at = utc_now()、updated_by = 当前操作人
    (4) 幂等（通过 repo 层的 ON CONFLICT）
    (5) 不抛 HTTPException（对齐 AGENTS.md 规则 2：services 层只返回 Dict 或抛业务异常）
    """

    def __init__(self, repo: UslRepository, query_engine: UslQueryEngine, *,
                 utc_now_factory: Any = lambda: datetime.now(timezone.utc)):
        self._repo = repo
        self._qe = query_engine
        self._now = utc_now_factory

    # =====================================================================
    # Group A: Domain 管理（10 方法 · 对应 plan.md Phase 0 #3 Domain 10）
    # =====================================================================

    def create_domain(self, *, code: str, display_name: str,
                      description: Optional[str] = None,
                      owner_role: SemanticRoleEnum = SemanticRoleEnum.ONTOLOGY_ADMIN,
                      config: Optional[dict[str, Any]] = None,
                      created_by: str,
                      id: Optional[str] = None) -> UslDomain: ...
    def get_domain(self, domain_id: str) -> UslDomain: ...
    def update_domain(self, domain_id: str, *, updated_by: str,
                      display_name: Optional[str] = None,
                      description: Optional[str] = None,
                      config: Optional[dict[str, Any]] = None,
                      owner_role: Optional[SemanticRoleEnum] = None
                      ) -> UslDomain: ...
    def list_domains(self, q: Optional[str] = None, *,
                     is_active: Optional[bool] = None,
                     owner_role: Optional[SemanticRoleEnum] = None,
                     page: int = 1, page_size: int = 50
                     ) -> tuple[int, list[UslDomain]]: ...
    def deactivate_domain(self, domain_id: str, *, deactivated_by: str,
                          reason: Optional[str] = None) -> UslDomain: ...
    def reactivate_domain(self, domain_id: str, *, reactivated_by: str) -> UslDomain: ...
    def delete_domain(self, domain_id: str, *, deleted_by: str, force: bool = False) -> None: ...
    def get_domain_stats(self, domain_id: str) -> dict[str, Any]:
        """返回 {term_count, active_term_count, deprecated_count, hierarchy_count,
                  property_count, cross_mapping_count, last_updated_at}。"""
    def update_domain_term_count(self, domain_id: str) -> int:
        """刷新 usl_domains.term_count = COUNT(usl_terms WHERE domain_id=? AND is_deprecated=0) → 返回新 count。"""
    def assign_owner_role(self, domain_id: str, *, owner_role: SemanticRoleEnum,
                          updated_by: str) -> UslDomain: ...

    # =====================================================================
    # Group B: Term 管理（12 方法 · 对应 plan.md Phase 0 #3 Term 12）
    # =====================================================================

    def create_term(self, domain_id: str, *, canonical_name: str,
                    term_type: TermType, created_by: str,
                    display_name: Optional[str] = None,
                    description: Optional[str] = None,
                    short_definition: Optional[str] = None,
                    semantic_tags: Optional[list[str]] = None,
                    examples: Optional[list[str]] = None,
                    source_refs: Optional[dict[str, Any]] = None,
                    preferred_term_id: Optional[str] = None
                    ) -> UslTerm: ...
    def get_term(self, term_id: str) -> UslTerm: ...
    def get_term_by_canonical(self, domain_id: str, canonical_name: str) -> UslTerm: ...
    def update_term(self, term_id: str, *, updated_by: str,
                    canonical_name: Optional[str] = None,
                    display_name: Optional[str] = None,
                    description: Optional[str] = None,
                    short_definition: Optional[str] = None,
                    term_type: Optional[TermType] = None,
                    semantic_tags: Optional[list[str]] = None,
                    examples: Optional[list[str]] = None,
                    source_refs: Optional[dict[str, Any]] = None,
                    preferred_term_id: Optional[str] = None
                    ) -> UslTerm: ...
    def list_terms(self, *, domain_id: Optional[str] = None, q: Optional[str] = None,
                   term_type: Optional[TermType | list[TermType]] = None,
                   is_deprecated: Optional[bool] = None,
                   parent_term_id: Optional[str] = None,
                   page: int = 1, page_size: int = 50
                   ) -> tuple[int, list[UslTerm]]: ...
    def deprecate_term(self, term_id: str, *, deprecated_by: str,
                       preferred_term_id: Optional[str] = None) -> UslTerm: ...
    def undeprecate_term(self, term_id: str, *, restored_by: str) -> UslTerm: ...
    def delete_term(self, term_id: str, *, deleted_by: str, force: bool = False) -> None: ...
    def search_terms_by_synonym(self, domain_id: str, text: str, *,
                                fuzziness: float = 0.7, top_k: int = 50
                                ) -> list[dict[str, Any]]:
        """封装 QueryEngine.lookup_terms_by_synonym → 返回 [{term, matched_synonyms, score}]。"""
    def merge_terms(self, target_term_id: str, source_term_ids: list[str], *,
                    merged_by: str,
                    move_synonyms: bool = True,
                    move_hierarchy: bool = True,
                    move_properties: bool = True,
                    move_cross_mappings: bool = True
                    ) -> UslTerm:
        """合并 source → target。source 被置为 is_deprecated=1，preferred_term_id=target。"""
    def clone_term(self, source_term_id: str, *, new_domain_id: Optional[str] = None,
                   new_canonical_name: Optional[str] = None,
                   cloned_by: str
                   ) -> UslTerm:
        """浅拷贝：term 基本信息 + property_specs；不拷贝 synonym/hierarchy/cross_mapping。"""
    def get_term_full_graph(self, term_id: str, *, depth: int = 2
                            ) -> dict[str, Any]:
        """返回 {term, synonyms, parents[], children[], properties[], cross_mappings[]} 单术语视图（前端详情页用）。"""

    # =====================================================================
    # Group C: Hierarchy（8 方法 · 对应 plan.md Phase 0 #3 Hierarchy 8）
    # =====================================================================

    def add_hierarchy_edge(self, *, domain_id: str,
                           parent_term_id: str, child_term_id: str,
                           hierarchy_type: HierarchyType = HierarchyType.IS_A,
                           created_by: str,
                           sort_order: int = 0,
                           confidence_score: Optional[float] = None,
                           is_inferred: bool = False,
                           inference_source: Optional[dict[str, Any]] = None
                           ) -> UslTermHierarchy: ...
    def get_hierarchy_edge(self, edge_id: str) -> UslTermHierarchy: ...
    def list_hierarchy_tree(self, domain_id: str, *, root_id: Optional[str] = None,
                            depth: int = 5,
                            hierarchy_type: Optional[HierarchyType] = None
                            ) -> dict[str, Any]:
        """返回 {edges: [...], tree: nested_dict, level_terms: {depth: [terms]}}（前端树状展示）。"""
    def list_parent_edges(self, child_term_id: str, *,
                          hierarchy_type: Optional[HierarchyType] = None
                          ) -> list[UslTermHierarchy]: ...
    def list_child_edges(self, parent_term_id: str, *,
                         hierarchy_type: Optional[HierarchyType] = None
                         ) -> list[UslTermHierarchy]: ...
    def delete_hierarchy_edge(self, edge_id: str, *, deleted_by: str) -> None: ...
    def update_hierarchy_edge(self, edge_id: str, *, updated_by: str,
                              sort_order: Optional[int] = None,
                              confidence_score: Optional[float] = None
                              ) -> UslTermHierarchy: ...
    def detect_hierarchy_cycle(self, domain_id: str, parent_id: str, child_id: str,
                               hierarchy_type: HierarchyType = HierarchyType.IS_A
                               ) -> Optional[list[str]]: ...

    # =====================================================================
    # Group D: PropertySpec（8 方法 · 对应 plan.md Phase 0 #3 Property 8，含按域批量）
    # =====================================================================

    def add_property_spec(self, term_id: str, *, property_code: str,
                          property_name: str, datatype: PropertyDatatype,
                          created_by: str,
                          is_required: bool = False,
                          is_unique: bool = False,
                          allow_multiple: bool = False,
                          enum_values: Optional[list[str]] = None,
                          ref_domain_id: Optional[str] = None,
                          description: Optional[str] = None,
                          default_value: Any = None,
                          validation_rules: Optional[dict[str, Any]] = None,
                          sort_order: int = 0
                          ) -> UslTermProperty: ...
    def get_property_spec(self, spec_id: str) -> UslTermProperty: ...
    def list_property_specs(self, *, term_id: Optional[str] = None,
                            property_code: Optional[str] = None,
                            datatype: Optional[PropertyDatatype] = None,
                            ref_domain_id: Optional[str] = None
                            ) -> list[UslTermProperty]: ...
    def batch_add_property_specs(self, term_ids: list[str], base_spec: dict[str, Any], *,
                                 created_by: str
                                 ) -> list[UslTermProperty]:
        """按域批量：对 term_ids 每一项应用 base_spec（{property_code, name, datatype, ...}）UPSERT。"""
    def update_property_spec(self, spec_id: str, *, updated_by: str,
                             property_name: Optional[str] = None,
                             datatype: Optional[PropertyDatatype] = None,
                             is_required: Optional[bool] = None,
                             enum_values: Optional[list[str]] = None,
                             description: Optional[str] = None,
                             sort_order: Optional[int] = None
                             ) -> UslTermProperty: ...
    def delete_property_spec(self, spec_id: str, *, deleted_by: str) -> None: ...
    def validate_term_value(self, spec: UslTermProperty, raw_value: Any
                            ) -> tuple[bool, Optional[str]]:
        """校验 raw_value 是否符合 spec.datatype + enum_values + min/max 约束。
        Returns (is_valid, error_message_or_none)。写回与 QA 阶段复用。"""
    def list_domain_global_specs(self, domain_id: str) -> list[UslTermProperty]:
        """ref_domain_id=domain_id 且 term_id 暂不绑的属性定义（域级模板；写回时批量应用）。"""

    # =====================================================================
    # Group E: Synonym（7 方法 · Service 层扩展，承接原 synonyms_json 拆表后的独立管理）
    # =====================================================================

    def add_synonym(self, term_id: str, *, synonym_text: str,
                    synonym_type: SynonymType = SynonymType.ALIAS,
                    created_by: str,
                    language_code: str = "zh-CN",
                    is_blacklisted: bool = False
                    ) -> UslTermSynonym: ...
    def batch_add_synonyms(self, term_id: str, texts: list[str], *,
                           synonym_type: SynonymType, created_by: str
                           ) -> list[UslTermSynonym]: ...
    def list_synonyms(self, *, term_id: Optional[str] = None,
                      text_like: Optional[str] = None,
                      synonym_type: Optional[SynonymType | list[SynonymType]] = None,
                      is_blacklisted: Optional[bool] = None,
                      page: int = 1, page_size: int = 100
                      ) -> tuple[int, list[UslTermSynonym]]: ...
    def mark_synonym_blacklisted(self, synonym_id: str, *, blacklisted: bool,
                                 updated_by: str
                                 ) -> UslTermSynonym: ...
    def review_synonym(self, synonym_id: str, *, reviewed_by: str,
                       approved: bool, final_type: Optional[SynonymType] = None
                       ) -> UslTermSynonym: ...
    def delete_synonym(self, synonym_id: str, *, deleted_by: str) -> None: ...
    def merge_term_synonyms(self, target_term_id: str, source_term_id: str, *,
                            merged_by: str,
                            disposition: str = "merge"   # "merge"|"overwrite"|"skip"
                            ) -> int:
        """返回合并新增/更新的 synonym 行数量。"""

    # =====================================================================
    # Group F: CrossDomainMapping（6 方法 · Service 层扩展，承接原 disjoint_pair + cardinality 合并）
    # =====================================================================

    def add_cross_mapping(self, *, source_term_id: str, target_term_id: str,
                          mapping_type: MappingType, created_by: str,
                          directionality: MappingDirectionality = MappingDirectionality.BIDIRECTIONAL,
                          confidence_score: float = 1.0,
                          mapping_reason: Optional[str] = None
                          ) -> UslCrossDomainMapping: ...
    def list_cross_mappings(self, *, source_term_id: Optional[str] = None,
                            target_term_id: Optional[str] = None,
                            mapping_type: Optional[MappingType] = None,
                            is_validated: Optional[bool] = None,
                            domain_id: Optional[str] = None
                            ) -> list[UslCrossDomainMapping]: ...
    def validate_cross_mapping(self, mapping: UslCrossDomainMapping
                               ) -> tuple[bool, Optional[str]]:
        """校验：(1) source != target；(2) directionality='unidirectional' → 反向不建；(3) confidence ∈ [0,1]。"""
    def approve_cross_mapping(self, mapping_id: str, *, validated_by: str
                              ) -> UslCrossDomainMapping: ...
    def update_mapping_confidence(self, mapping_id: str, score: float, *,
                                  updated_by: str
                                  ) -> UslCrossDomainMapping: ...
    def delete_cross_mapping(self, mapping_id: str, *, deleted_by: str) -> None: ...
```

---

## Section 4: ON CONFLICT DO UPDATE 幂等规则（对齐 data-model.md §2 UNIQUE/FK）

**原则**：所有 `INSERT` 语句带唯一键冲突时，**更新可更新字段而非抛错**。`created_at/created_by` 永不改；`updated_at/updated_by` 一律置新。

### 4.1 usl_domains（UNIQUE(code)，主键 id）

```sql
INSERT INTO usl_domains (id, code, display_name, description, is_active, owner_role,
                         config_json, term_count, created_by, created_at, updated_at, updated_by)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
  code          = excluded.code,
  display_name  = excluded.display_name,
  description   = excluded.description,
  owner_role    = excluded.owner_role,
  config_json   = excluded.config_json,
  updated_at    = excluded.updated_at,
  updated_by    = excluded.updated_by
WHERE usl_domains.is_active = 1 OR excluded.is_active = 1;
```

### 4.2 usl_terms（UNIQUE(domain_id, canonical_name)）

```sql
INSERT INTO usl_terms (id, domain_id, canonical_name, normalized_name, display_name,
  term_type, description, short_definition, is_deprecated, preferred_term_id,
  semantic_tags_json, examples_json, source_refs_json, version,
  created_by, created_at, updated_at, updated_by)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(domain_id, canonical_name) DO UPDATE SET
  normalized_name   = excluded.normalized_name,
  display_name      = COALESCE(excluded.display_name, usl_terms.display_name),
  description       = excluded.description,
  short_definition  = excluded.short_definition,
  semantic_tags_json= excluded.semantic_tags_json,
  examples_json     = excluded.examples_json,
  source_refs_json  = excluded.source_refs_json,
  version           = usl_terms.version + 1,
  updated_at        = excluded.updated_at,
  updated_by        = excluded.updated_by
WHERE usl_terms.is_deprecated = 0;  -- deprecated 的同 canonical 允许新的 INSERT，不 UPDATE 旧 deprecated
```

### 4.3 usl_term_synonyms（UNIQUE(term_id, normalized_synonym, synonym_type, language_code)）

```sql
INSERT INTO usl_term_synonyms (id, term_id, synonym_text, normalized_synonym,
  synonym_type, ambiguity_targets_json, language_code, frequency, is_blacklisted,
  reviewed_by, reviewed_at, created_at, created_by)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(term_id, normalized_synonym, synonym_type, language_code) DO UPDATE SET
  synonym_text            = excluded.synonym_text,
  ambiguity_targets_json  = excluded.ambiguity_targets_json,
  frequency               = usl_term_synonyms.frequency + 1,
  is_blacklisted          = excluded.is_blacklisted;
```

### 4.4 usl_term_hierarchies（UNIQUE(parent_term_id, child_term_id, hierarchy_type)）

```sql
INSERT INTO usl_term_hierarchies (...) VALUES (...)
ON CONFLICT(parent_term_id, child_term_id, hierarchy_type) DO UPDATE SET
  sort_order           = excluded.sort_order,
  confidence_score     = excluded.confidence_score,
  is_inferred          = excluded.is_inferred,
  inference_source_json= excluded.inference_source_json,
  updated_at           = excluded.updated_at,
  updated_by           = excluded.updated_by;
```

### 4.5 usl_term_properties（UNIQUE(term_id, property_code)）

```sql
INSERT INTO usl_term_properties (...) VALUES (...)
ON CONFLICT(term_id, property_code) DO UPDATE SET
  property_name       = excluded.property_name,
  datatype            = excluded.datatype,
  is_required         = excluded.is_required,
  enum_values_json    = excluded.enum_values_json,
  description         = excluded.description,
  validation_rules_json= excluded.validation_rules_json,
  sort_order          = excluded.sort_order,
  updated_at          = excluded.updated_at,
  updated_by          = excluded.updated_by;
```

### 4.6 usl_cross_domain_mappings（UNIQUE(source_term_id, target_term_id, mapping_type)）

```sql
INSERT INTO usl_cross_domain_mappings (...) VALUES (...)
ON CONFLICT(source_term_id, target_term_id, mapping_type) DO UPDATE SET
  directionality      = excluded.directionality,
  confidence_score    = excluded.confidence_score,
  mapping_reason      = excluded.mapping_reason,
  mapping_source_json = excluded.mapping_source_json,
  updated_at          = excluded.updated_at,
  updated_by          = excluded.updated_by;
```

### 4.7 幂等性的行为预期（Contract Guarantee）

| Method | 重复调用 N 次的效果 |
|--------|--------------------|
| `create_domain(same_code)` | N 次 = 1 行；N-1 次 updated_at 更新；最后一次 display_name/description 获胜 |
| `create_term(same_domain, same_canonical)` | 同 canonical 未 deprecated → 1 行，UPDATE synonym/tags；已 deprecated → INSERT 新行（version=1） |
| `add_hierarchy_edge(A→B, score=0.5)` 后同 A→B, score=0.9 | 最终 confidence_score=0.9；created_by/created_at 仍为首次 |
| `add_synonym(term, "诸葛亮", alias)` 重复 N 次 | 1 行；frequency = N |
| `seed_from_dict(相同 dict)` | created=0, updated=0（完全一致时 storage 触发 0 行变更） |

---

## Section 5: 38 法快速索引表（plan.md Phase 0 #3 要求的主 38 法）

### Domain 10 法

| # | 方法签名 | 核心 | 主异常 |
|---|---------|------|--------|
| D1 | `create_domain(code, display_name, created_by, ...)` | 新建 domain（UUID 或指定 id） | DomainExistsError / ValueError |
| D2 | `get_domain(domain_id)` | 单查（含 deactivated） | DomainNotFoundError |
| D3 | `update_domain(id, updated_by, ...)` | 改 domain | DomainNotFoundError |
| D4 | `list_domains(q?, is_active?, ...)` | 分页+搜索 | - |
| D5 | `deactivate_domain(id, deactivated_by)` | 软停用（is_active=0） | DomainNotFoundError |
| D6 | `reactivate_domain(id, reactivated_by)` | 恢复（is_active=1） | DomainNotFoundError |
| D7 | `delete_domain(id, deleted_by, force?)` | 彻底删除（force=False 且子 term>0 → TermInUseError） | TermInUseError |
| D8 | `get_domain_stats(id)` | 6 个计数+最近更新 | DomainNotFoundError |
| D9 | `update_domain_term_count(id)` | 刷新 term_count 冗余列 | DomainNotFoundError |
| D10| `assign_owner_role(id, owner_role, updated_by)` | 改 owner_role | RoleAssignmentError |

### Term 12 法

| # | 方法签名 | 核心 | 主异常 |
|---|---------|------|--------|
| T1 | `create_term(domain_id, canonical_name, term_type, created_by, ...)` | 新建 term（UUID 生成 id） | DomainNotFoundError / TermDuplicateError |
| T2 | `get_term(id)` | 单查 term | TermNotFoundError |
| T3 | `get_term_by_canonical(domain_id, canonical_name)` | domain+canonical 精确查询 | TermNotFoundError |
| T4 | `update_term(id, updated_by, ...)` | 改 term | TermNotFoundError / TermDuplicateError |
| T5 | `list_terms(domain_id?, q?, term_type?, ...)` | 分页+多维度筛选 | - |
| T6 | `deprecate_term(id, deprecated_by, preferred_id?)` | 软弃用（is_deprecated=1） | TermNotFoundError |
| T7 | `undeprecate_term(id, restored_by)` | 恢复弃用 | TermNotFoundError |
| T8 | `delete_term(id, deleted_by, force?)` | 彻底删除（有 hierarchy/property → TermInUseError 除非 force） | TermInUseError |
| T9 | `search_terms_by_synonym(domain_id, text, fuzz, top_k)` | QueryEngine 同义词回查 → [{term, matched, score}] | - |
| T10| `merge_terms(target_id, source_ids[], merged_by, ...)` | 合并 source→target，source 置 deprecated | TermNotFoundError |
| T11| `clone_term(src_id, new_domain_id?, new_canonical?, cloned_by)` | 浅拷贝 term 基本信息 + property_specs | TermNotFoundError |
| T12| `get_term_full_graph(id, depth=2)` | 6 维单术语详情（前端详情页） | TermNotFoundError |

### Hierarchy 8 法

| # | 方法签名 | 核心 | 主异常 |
|---|---------|------|--------|
| H1 | `add_hierarchy_edge(domain_id, parent, child, type, created_by, ...)` | 加边（**写前环检测** detect_hierarchy_cycle） | CycleError / SelfRefError |
| H2 | `get_hierarchy_edge(id)` | 单查边 | - |
| H3 | `list_hierarchy_tree(domain_id, root_id?, depth=5, type?)` | 生成 nested tree + edges + levels | - |
| H4 | `list_parent_edges(child_id, type?)` | child → parents 直接边列表 | - |
| H5 | `list_child_edges(parent_id, type?)` | parent → children 直接边列表 | - |
| H6 | `delete_hierarchy_edge(edge_id, deleted_by)` | 删边 | - |
| H7 | `update_hierarchy_edge(id, updated_by, sort_order?, confidence?)` | 改边排序/置信度 | - |
| H8 | `detect_hierarchy_cycle(domain_id, parent, child, type?)` | 环检测（返回环路径列表或 None） | - |

### Property 8 法（含按域批量）

| # | 方法签名 | 核心 | 主异常 |
|---|---------|------|--------|
| P1 | `add_property_spec(term_id, code, name, datatype, created_by, ...)` | 新增属性规范（datatype=ENUM 时 enum_values 必填） | InvalidPropSpecError |
| P2 | `get_property_spec(id)` | 单查 | - |
| P3 | `list_property_specs(term_id?, code?, datatype?, ref_domain_id?)` | 4 维过滤 | - |
| P4 | `batch_add_property_specs(term_ids[], base_spec, created_by)` | **按域批量应用同一套 spec 模板** | DatatypeMismatchError |
| P5 | `update_property_spec(id, updated_by, name?, datatype?, required?, ...)` | 改 spec | InvalidPropSpecError |
| P6 | `delete_property_spec(id, deleted_by)` | 删除 spec | - |
| P7 | `validate_term_value(spec, raw_value)` | 值 vs datatype/enum/rules 校验 | - |
| P8 | `list_domain_global_specs(domain_id)` | 列出域级模板 spec（term_id 未绑的） | - |
