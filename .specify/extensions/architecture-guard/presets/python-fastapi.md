---
description: Apply FastAPI/Python-specific architecture conventions during architecture review. Custom preset for ODAP platform.
---

# Architecture Guard — FastAPI/Python Architecture Adapter

Use the core architecture review rules first. This adapter refines generic architecture concepts with **FastAPI** and **Pydantic v2** conventions, as used by the ODAP platform.

---

## Boundary Mapping

When reviewing a FastAPI project, map generic architecture boundaries to FastAPI primitives:

### Entry Boundary

| Generic Concept | FastAPI Equivalent |
| --- | --- |
| HTTP entry point | `APIRouter` in `*/api/routes.py` |
| Application bootstrap | `odap/web/app.py` (wires routers only) |
| Global request/response hooks | `odap/infra/security/middleware.py` |
| WebSocket entry | `WebSocket` route in `*/api/routes.py` |
| Background tasks | `BackgroundTasks` in FastAPI or external task queue |

### Validation Boundary

| Generic Concept | FastAPI Equivalent |
| --- | --- |
| API input validation | **Pydantic v2 models** in `*/api/schemas.py` |
| Query/Path parameter validation | FastAPI `Query` / `Path` with types |
| Request body validation | Pydantic request models with `Field()` constraints |
| Response validation | Pydantic response models with `response_model=` |
| Error response shape | FastAPI `HTTPException` with structured detail |

### Contract Boundary

| Generic Concept | FastAPI Equivalent |
| --- | --- |
| Stable request shapes | **Pydantic BaseModel** in `*/api/schemas.py` |
| Stable response shapes | Pydantic response models |
| Shared interfaces | **Abstract Base Classes (ABC)** in `*/interfaces/` |
| View objects (read-only) | **`@dataclass(frozen=True)`** for read-only views |
| Event contracts | Pydantic models in `*/events.py` |

### Application Boundary

| Generic Concept | FastAPI Equivalent |
| --- | --- |
| Use case coordination | `Service` classes in `*/services/` |
| Domain logic | `*Manager` or `*Engine` classes |
| External integration | `*Client` classes in `infra/*` |
| Background workers | Workers in `infra/messaging/` or task queue |

### Domain Boundary

| Generic Concept | FastAPI Equivalent |
| --- | --- |
| Business rules | `*/domain/` or `*/models/` |
| Domain types | **Pydantic v2** with `model_config = ConfigDict(...)` |
| Domain errors | Custom exceptions in `*/errors.py` |
| Domain events | Pydantic event models in `*/events.py` |
| Invariants | `validate_*` methods on domain models |

### Infrastructure Boundary

| Generic Concept | FastAPI Equivalent |
| --- | --- |
| Data access | **SQLAlchemy 2.0** repositories in `*/storage/` |
| External services | `infra/*/client.py` (LLM, OPA, Neo4j, MinIO) |
| Configuration | Pydantic Settings in `infra/config.py` |
| Logging | `logging` module with structured JSON |

---

## Pydantic v2 Enforcement Rules

- **Field definitions**: MUST use `Field(default_factory=...)` for containers (`list`, `dict`, `set`)
- **Mutable defaults**: `field: List[str] = []` is **FORBIDDEN** — use `Field(default_factory=list)`
- **Validation**: MUST use field validators with `@field_validator` (not `validator` from v1)
- **Config**: MUST use `ConfigDict()` (v2) not `class Config` (v1)
- **Discriminated unions**: MUST use `Field(discriminator=...)` for tagged unions
- **Immutability**: For view objects, Pydantic models SHOULD use `model_config = ConfigDict(frozen=True)`

## FastAPI Route Rules

- **Routes**: MUST live in domain modules (`odap/biz/*/api/routes.py`)
- **`odap/web/app.py`**: MUST only wire routers; no business logic
- **Auth**: Routes MUST use `Depends(get_current_user)` unless explicitly public
- **Error handling**: All routes MUST have try/except with `except HTTPException: raise`
- **Response models**: Routes SHOULD declare `response_model=...` for OpenAPI
- **Status codes**: MUST return correct status codes (200/201/204/400/401/403/404/409/500)

## Pydantic Field Rules

```python
# ✅ CORRECT
class MyRequest(BaseModel):
    items: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)

# ❌ FORBIDDEN
class MyRequest(BaseModel):
    items: List[str] = []  # Mutable default — shared state risk
    config: Dict[str, Any] = {}  # Mutable default — shared state risk
```

## Cross-Module Communication Rules

- **Read queries** MUST go through `odap.infra.query.QueryService` or domain contracts
- **Direct SQL JOINs across modules** are FORBIDDEN
- **Cross-module mutations** MUST go through service-layer calls, not direct storage access
- **Event-driven communication** MUST use Pydantic event contracts

---

## Ontology Subsystem Specific Rules (ODAP Custom)

| Subsystem | Path | Contract |
| --- | --- | --- |
| **Design** | `odap/biz/core/ontology/design/` | `design/contract/` |
| **Application** | `odap/biz/core/ontology/application/` | Per-module APIs |
| **Unified Query** | `odap/infra/query/` | `infra/query/__init__.py` |

**Strict Rules**:
1. Application code MUST import from design ONLY via `design.contract`
2. Design code MUST NOT import from application (no reverse dependencies)
3. The only allowed bridge is `odap.infra.query.ontology_source.OntologyDesignSource`
4. View objects are `@dataclass(frozen=True)` — immutable

---

## Severity Levels

| Level | Examples |
| --- | --- |
| **P0** | Mutable defaults, missing auth, hardcoded secrets, boundary violations |
| **P1** | Missing tests, no error handling, Pydantic v1 patterns |
| **P2** | Long functions, magic numbers, naming |
| **P3** | Style, comments |
