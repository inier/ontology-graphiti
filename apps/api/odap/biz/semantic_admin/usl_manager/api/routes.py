"""USL Manager - FastAPI 路由。

9 类接口（6 资源 * 3 核心操作 GET/POST/PUT + DELETE 辅助）：
1. Domains        GET/POST/PUT/DELETE  /domains
2. Terms          GET/POST/PUT/DELETE  /terms
3. Hierarchy      GET/POST/PUT/DELETE  /hierarchy
4. Property Specs GET/POST/PUT/DELETE  /property-specs
5. Disjoint Pairs GET/POST/PUT/DELETE  /disjoint-pairs
6. Cardinalities  GET/POST/PUT/DELETE  /cardinalities

路由总前缀: /api/semantic-admin/usl

权限约定（Iter 1）：
  - 读操作（GET）：任何已登录用户可读
  - 写操作（POST/PUT/DELETE）：仅 admin 可写（通过 verify_admin Depends 控制）
  - Iter 3 将激活真实 OPA 策略校验 schema_auditor

严格遵守 AGENTS.md 路由规则：
  - except HTTPException: raise 透传，否则被 500 兜底吞掉
  - services 返回 {"status":"error"} 时，翻译为 HTTPException(4xx)
  - 不直接在路由层写业务逻辑
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from odap.infra.security.jwt_auth import get_current_user

from ..services import UslManagerService
from .schemas import (
    # Cardinality
    CardinalityListResponse,
    CardinalityResponse,
    CreateCardinalityRequest,
    UpdateCardinalityRequest,
    # DisjointPair
    CreateDisjointPairRequest,
    CreateDomainRequest,
    CreateHierarchyRequest,
    CreatePropertySpecRequest,
    CreateTermRequest,
    DeleteResponse,
    # Domain
    DisjointPairListResponse,
    DisjointPairResponse,
    DomainListResponse,
    DomainResponse,
    # Hierarchy
    HierarchyListResponse,
    HierarchyResponse,
    # PropertySpec
    PropertySpecListResponse,
    PropertySpecResponse,
    # Term
    TermListResponse,
    TermResponse,
    UpdateDisjointPairRequest,
    UpdateDomainRequest,
    UpdateHierarchyRequest,
    UpdatePropertySpecRequest,
    UpdateTermRequest,
    # Role
    AssignRoleRequest,
    RoleAssignmentListResponse,
    RoleAssignmentResponse,
)

# 全局写角色下界（Iter 1 粗粒度；Iter 3 激活 OPA 策略 + ws_role 细粒度后收敛）
_SEMANTIC_WRITER_GLOBAL_ROLES: set = {"admin", "schema_auditor", "editor"}
_SEMANTIC_WRITER_WS_ROLES: set = {"term_editor", "domain_editor", "reviewer", "super_admin", "owner", "schema_auditor"}


async def verify_semantic_writer(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """写权限 Depends：统一走 get_current_user（便于测试 fixture override），
    全局角色 ∈ {admin, schema_auditor, editor} 或 ws_role ∈ writer 集合 可写。
    与 approval_workflow/permissions.py 保持完全一致。Iter 3 激活 OPA。
    """
    role = (user.get("role") or "").lower()
    ws_role = (user.get("ws_role") or "").lower()
    if role in _SEMANTIC_WRITER_GLOBAL_ROLES or ws_role in _SEMANTIC_WRITER_WS_ROLES:
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"写操作需要全局角色 ∈ {sorted(_SEMANTIC_WRITER_GLOBAL_ROLES)} "
            f"或 ws_role ∈ {sorted(_SEMANTIC_WRITER_WS_ROLES)}，"
            f"当前 role={role!r}, ws_role={ws_role!r}"
        ),
    )


async def verify_semantic_admin_only(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """仅 admin 终审级可执行（如删除 domain 级联风险操作）。
    统一走 get_current_user 便于测试 fixture override。"""
    role = (user.get("role") or "").lower()
    if role == "admin":
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"终审操作仅允许全局 admin，当前 role={role!r}",
    )


async def _schema_auditor_placeholder(
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """最小占位钩：Iter 3 激活真实 OPA data.odap.semantic_admin.{action} 决策。"""
    return True  # pragma: no cover


# =====================================================================
# Router
# =====================================================================

router = APIRouter(prefix="/api/semantic-admin/usl", tags=["semantic-admin-usl"])

# 模块级单例
usl_service = UslManagerService()


# =====================================================================
# 1. Domains
# =====================================================================


@router.get("/domains", response_model=DomainListResponse)
async def list_domains(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页大小"),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """分页列出语义领域（GET 登录可读）。"""
    try:
        result = usl_service.list_domains(page=page, page_size=page_size)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/domains", response_model=DomainResponse)
async def create_domain(
    request: CreateDomainRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """创建语义领域（POST 仅 admin）。"""
    try:
        result = usl_service.create_domain(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/domains/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: str,
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """按 ID 获取单个领域。"""
    try:
        result = usl_service.get_domain(domain_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/domains/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: str,
    request: UpdateDomainRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """更新领域（PUT 仅 admin）。"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = usl_service.update_domain(domain_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "不存在" in str(result["message"]) else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/domains/{domain_id}", response_model=DeleteResponse)
async def delete_domain(
    domain_id: str,
    _auth: Dict[str, Any] = Depends(verify_semantic_admin_only),
):
    """删除领域（级联删除其子资源，仅 admin 终审级可删）。"""
    try:
        result = usl_service.delete_domain(domain_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# 2. Terms
# =====================================================================


@router.get("/terms", response_model=TermListResponse)
async def list_terms(
    domain_id: Optional[str] = Query(None, description="按领域 ID 过滤"),
    semantic_type: Optional[str] = Query(
        None, description="按语义类型过滤（OBJECT_TYPE/LINK_TYPE/...）"
    ),
    synonym_keyword: Optional[str] = Query(
        None, description="同义词/别名/规范术语模糊搜索关键字"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """分页列出术语，支持 semantic_type 过滤 + 同义词模糊搜索。"""
    try:
        result = usl_service.list_terms(
            domain_id=domain_id,
            semantic_type=semantic_type,
            synonym_keyword=synonym_keyword,
            page=page,
            page_size=page_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/terms", response_model=TermResponse)
async def create_term(
    request: CreateTermRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """创建规范术语（admin/schema_auditor/editor 可写）。"""
    try:
        result = usl_service.create_term(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/terms/{term_id}", response_model=TermResponse)
async def get_term(
    term_id: str,
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """按 ID 获取术语。"""
    try:
        result = usl_service.get_term(term_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/terms/{term_id}", response_model=TermResponse)
async def update_term(
    term_id: str,
    request: UpdateTermRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """更新术语（仅 admin）。"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = usl_service.update_term(term_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "不存在" in str(result["message"]) else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/terms/{term_id}", response_model=DeleteResponse)
async def delete_term(
    term_id: str,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """删除术语（仅 admin）。"""
    try:
        result = usl_service.delete_term(term_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# 3. Hierarchy
# =====================================================================


@router.get("/hierarchies", response_model=HierarchyListResponse)
async def list_hierarchies(
    domain_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """分页列出术语层级关系。"""
    try:
        result = usl_service.list_hierarchies(
            domain_id=domain_id,
            page=page,
            page_size=page_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hierarchies", response_model=HierarchyResponse)
async def create_hierarchy(
    request: CreateHierarchyRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """创建层级关系（仅 admin）。"""
    try:
        result = usl_service.create_hierarchy(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hierarchies/{hierarchy_id}", response_model=HierarchyResponse)
async def get_hierarchy(
    hierarchy_id: str,
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """按 ID 获取层级关系。"""
    try:
        result = usl_service.get_hierarchy(hierarchy_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/hierarchies/{hierarchy_id}", response_model=HierarchyResponse)
async def update_hierarchy(
    hierarchy_id: str,
    request: UpdateHierarchyRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """更新层级关系（仅 admin）。"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = usl_service.update_hierarchy(hierarchy_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "不存在" in str(result["message"]) else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/hierarchies/{hierarchy_id}", response_model=DeleteResponse)
async def delete_hierarchy(
    hierarchy_id: str,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """删除层级关系（仅 admin）。"""
    try:
        result = usl_service.delete_hierarchy(hierarchy_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# 4. Property Specs
# =====================================================================


@router.get("/property-specs", response_model=PropertySpecListResponse)
async def list_property_specs(
    domain_id: Optional[str] = Query(None),
    for_term: Optional[str] = Query(None, description="按所属术语名过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """分页列出属性规约。"""
    try:
        result = usl_service.list_property_specs(
            domain_id=domain_id,
            for_term=for_term,
            page=page,
            page_size=page_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/property-specs", response_model=PropertySpecResponse)
async def create_property_spec(
    request: CreatePropertySpecRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """创建属性规约（仅 admin）。"""
    try:
        result = usl_service.create_property_spec(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/property-specs/{spec_id}", response_model=PropertySpecResponse)
async def get_property_spec(
    spec_id: str,
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """按 ID 获取属性规约。"""
    try:
        result = usl_service.get_property_spec(spec_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/property-specs/{spec_id}", response_model=PropertySpecResponse)
async def update_property_spec(
    spec_id: str,
    request: UpdatePropertySpecRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """更新属性规约（仅 admin）。"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = usl_service.update_property_spec(spec_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "不存在" in str(result["message"]) else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/property-specs/{spec_id}", response_model=DeleteResponse)
async def delete_property_spec(
    spec_id: str,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """删除属性规约（仅 admin）。"""
    try:
        result = usl_service.delete_property_spec(spec_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# 5. Disjoint Pairs
# =====================================================================


@router.get("/disjoint-pairs", response_model=DisjointPairListResponse)
async def list_disjoint_pairs(
    domain_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """分页列出不相交术语对。"""
    try:
        result = usl_service.list_disjoint_pairs(
            domain_id=domain_id,
            page=page,
            page_size=page_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disjoint-pairs", response_model=DisjointPairResponse)
async def create_disjoint_pair(
    request: CreateDisjointPairRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """创建不相交对（仅 admin）。"""
    try:
        result = usl_service.create_disjoint_pair(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/disjoint-pairs/{pair_id}", response_model=DisjointPairResponse)
async def get_disjoint_pair(
    pair_id: str,
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """按 ID 获取不相交对。"""
    try:
        result = usl_service.get_disjoint_pair(pair_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/disjoint-pairs/{pair_id}", response_model=DisjointPairResponse)
async def update_disjoint_pair(
    pair_id: str,
    request: UpdateDisjointPairRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """更新不相交对（仅 admin）。"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = usl_service.update_disjoint_pair(pair_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "不存在" in str(result["message"]) else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/disjoint-pairs/{pair_id}", response_model=DeleteResponse)
async def delete_disjoint_pair(
    pair_id: str,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """删除不相交对（仅 admin）。"""
    try:
        result = usl_service.delete_disjoint_pair(pair_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# 6. Cardinalities
# =====================================================================


@router.get("/cardinalities", response_model=CardinalityListResponse)
async def list_cardinalities(
    domain_id: Optional[str] = Query(None),
    rel_name: Optional[str] = Query(None, description="按关系名过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """分页列出关系基数约束。"""
    try:
        result = usl_service.list_cardinalities(
            domain_id=domain_id,
            rel_name=rel_name,
            page=page,
            page_size=page_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cardinalities", response_model=CardinalityResponse)
async def create_cardinality(
    request: CreateCardinalityRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """创建基数约束（仅 admin）。"""
    try:
        result = usl_service.create_cardinality(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cardinalities/{card_id}", response_model=CardinalityResponse)
async def get_cardinality(
    card_id: str,
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """按 ID 获取基数约束。"""
    try:
        result = usl_service.get_cardinality(card_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/cardinalities/{card_id}", response_model=CardinalityResponse)
async def update_cardinality(
    card_id: str,
    request: UpdateCardinalityRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """更新基数约束（仅 admin）。"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = usl_service.update_cardinality(card_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "不存在" in str(result["message"]) else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cardinalities/{card_id}", response_model=DeleteResponse)
async def delete_cardinality(
    card_id: str,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """删除基数约束（仅 admin）。"""
    try:
        result = usl_service.delete_cardinality(card_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# 10. Role Assignments (POST/GET/DELETE /usl/roles)
# =====================================================================


@router.post("/roles", response_model=RoleAssignmentResponse)
async def assign_role(
    request: AssignRoleRequest,
    auth_user: Dict[str, Any] = Depends(verify_semantic_admin_only),
):
    """分配工作空间角色（仅全局 admin 可分配）。
    按 UNIQUE(workspace_id, user_id) 做 upsert，重复分配同用户同 ws 即更新。
    合法 ws_role：viewer / term_editor / domain_editor / reviewer / super_admin
    """
    try:
        payload = request.model_dump(mode="json")
        if not payload.get("assigned_by"):
            payload["assigned_by"] = str(
                auth_user.get("user_id") or auth_user.get("username") or "admin"
            )
        result = usl_service.assign_role(payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roles", response_model=RoleAssignmentListResponse)
async def list_role_assignments(
    workspace_id: Optional[str] = Query(None, description="按工作空间过滤"),
    ws_role: Optional[str] = Query(None, description="按 ws_role 过滤"),
    user_id: Optional[str] = Query(None, description="按 user_id 过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页大小"),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """分页列出角色分配（登录可读）。"""
    try:
        result = usl_service.list_role_assignments(
            workspace_id=workspace_id,
            ws_role=ws_role,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roles/by-user", response_model=RoleAssignmentResponse)
async def get_role_assignment_by_user(
    workspace_id: str = Query(..., description="工作空间 ID"),
    user_id: str = Query(..., description="用户 ID"),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    """按 (workspace_id, user_id) 查询单条角色分配（登录可读）。"""
    try:
        result = usl_service.get_role_assignment(workspace_id, user_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/roles/{assignment_id}", response_model=DeleteResponse)
async def remove_role_assignment(
    assignment_id: str,
    _auth: Dict[str, Any] = Depends(verify_semantic_admin_only),
):
    """删除角色分配（仅全局 admin）。"""
    try:
        result = usl_service.remove_role_assignment(assignment_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
