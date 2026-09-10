"""core.ontology 路由聚合门面 (Router Facade) —— public.py 的姊妹模块。

背景（Stage F，见 core-ontology 拆分迁移方案 附录四）：
    public.py 把 ontology 的**类型/服务符号**收敛为唯一对外 API 面后，全仓对
    ontology 内部子包的深层 reach-in 只剩一类无法符号化的边——**路由注册**。
    web/router_registry.py（生产入口 web/app.py 消费它）与 web/api/app.py（本地
    8765 开发入口）为注册路由，各自 `from odap.biz.core.ontology.<深层子包>.api.routes
    import router`，共 38 条直接深插边（C3 契约的最后一批 ignore 债账）。

    `router` 这个名字在 31 个模块里全都叫 `router`，跨模块冲突，无法像类型符号那样
    直接塞进 public.py 的 _PUBLIC_MAP（会互相覆盖）。故单设本模块，为每个 ontology
    路由分配**唯一的公共别名**（如 `oms_router` / `action_type_router`），把「31 个同名
    router」拍平成「31 个异名公共符号」。

本模块的职责：
    作为 core.ontology **路由面的唯一稳定入口**。外部（web 层）只应从本模块导入
    ontology 路由：

        from odap.biz.core.ontology.public_routers import oms_router, action_type_router

    禁止再 `from odap.biz.core.ontology.<深层子包>.api.routes import router`。内部路由
    重构（拆分/合并/改名 routes 模块）时只需维护本文件的 _ROUTER_MAP，web 层无感。

设计要点（与 public.py 完全一致）：
    1. PEP 562 惰性 __getattr__：导入本模块本身零级联开销，只有真正取用某个
       `xxx_router` 时才 import 对应 routes 模块并 getattr 其 `router`。这保持了
       router_registry.create_router_registry() 原有的「按需、函数内」导入语义，
       且注册顺序完全由消费者的列表顺序决定（本模块不改变任何顺序）。
    2. _ROUTER_MAP 是「公共别名 → (真实 routes 模块路径, 模块内 router 属性名)」的
       唯一映射表。所有真实路径以生产入口已验证可注册（755 paths / 957 operations）
       的为准。
    3. grimp 静态视角：web 层 → `ontology.public_routers`（1 条边，非 forbidden，
       C3 放行）；本模块 → 各深层 routes 的边是 **importlib 动态调用**，grimp 不可见，
       且即便可见也属 ontology 包内部边（C3 的 source_modules 刻意排除 ontology 自身），
       不构成违规。这正是 public.py 已验证可行的同一机制。

约定：
    - 新增对外 ontology 路由 → 加到 _ROUTER_MAP + __all__ + TYPE_CHECKING 块，
      并给一个不与现有别名冲突的公共名（建议 `<域>_router` 或 `ontology_<域>_router`）。
    - 别名一旦发布即为对外契约，改名等同破坏 web 层导入，需同步改消费者。
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

# ─────────────────────────────────────────────────────────────────────────
# 公共别名 → (真实 routes 模块路径, 模块内 router 属性名)
# 全部 31 个 ontology 路由，属性名统一为 "router"。路径与生产入口
# web/router_registry.py 原先直接导入的深层路径逐条对应，运行期已验证可注册。
# ─────────────────────────────────────────────────────────────────────────
_ROUTER_MAP: dict[str, tuple[str, str]] = {
    # ── 本体 - 动作 / 消歧图 ──
    "action_type_router": ("odap.biz.core.ontology.action.api.routes", "router"),
    "abution_graph_router": ("odap.biz.core.ontology.application.abution_graph.api.routes", "router"),

    # ── 本体 - Harness / 蓝图设计器 ──
    "harness_router": ("odap.biz.core.ontology.application.harness.api.routes", "router"),
    "blueprint_designer_router": ("odap.biz.core.ontology.application.harness.blueprint.routes", "router"),
    "blueprint_runtime_router": ("odap.biz.core.ontology.application.harness.blueprint.api.runtime_routes", "router"),

    # ── 本体 - OMS 与统一查询 ──
    "oms_router": ("odap.biz.core.ontology.application.oms.routes", "router"),
    "ontology_nl_router": ("odap.biz.core.ontology.application.query_api.nl_routes", "router"),
    "ontology_ingest_router": ("odap.biz.core.ontology.application.query_api.routes", "router"),

    # ── 本体 - 运行时 / 状态机 ──
    "runtime_router": ("odap.biz.core.ontology.application.runtime.api.routes", "router"),
    "state_machine_router": ("odap.biz.core.ontology.application.runtime.state_machine.api.routes", "router"),

    # ── 本体 - 服务化 ──
    "servitization_router": ("odap.biz.core.ontology.application.servitization.api.routes", "router"),
    "deployment_router": ("odap.biz.core.ontology.application.servitization.api.deployment_routes", "router"),
    "catalog_router": ("odap.biz.core.ontology.application.servitization.catalog.routes", "router"),

    # ── 本体 - AI 辅助设计 ──
    "ontology_assistant_router": ("odap.biz.core.ontology.assistant.api.routes", "router"),

    # ── 本体 - 分支 / 冷启动 / 计算 / 冲突 / 继承 ──
    "branch_router": ("odap.biz.core.ontology.branch.api.routes", "router"),
    "cold_start_router": ("odap.biz.core.ontology.cold_start.api.routes", "router"),
    "computed_router": ("odap.biz.core.ontology.computed.api.routes", "router"),
    "conflict_router": ("odap.biz.core.ontology.conflict.api.routes", "router"),
    "inheritance_router": ("odap.biz.core.ontology.inheritance.api.routes", "router"),

    # ── 本体 - L1 设计层（引擎 / SHACL-OWL / 摄入 / 模型 / 版本）──
    "ontology_engine_router": ("odap.biz.core.ontology.design.engine.api.routes", "router"),
    "shacl_owl_router": ("odap.biz.core.ontology.design.engine.api.shacl_owl_routes", "router"),
    "ingestion_router": ("odap.biz.core.ontology.design.ingestion.api.routes", "router"),
    "ontology_model_router": ("odap.biz.core.ontology.design.model.api.routes", "router"),
    "ontology_version_router": ("odap.biz.core.ontology.design.version.api.routes", "router"),

    # ── 本体 - 抽取 / 目标 / 核心 API ──
    "extraction_router": ("odap.biz.core.ontology.extraction.api", "router"),
    "goal_router": ("odap.biz.core.ontology.goal.api.routes", "router"),
    "ontology_api_router": ("odap.biz.core.ontology.ontology_api.api", "router"),

    # ── 本体 - 推理 / TypeRegistry / 语义检索 / 视图 ──
    "reasoning_router": ("odap.biz.core.ontology.reasoning.api.routes", "router"),
    "registry_router": ("odap.biz.core.ontology.registry.api.routes", "router"),
    "semantic_retrieval_router": ("odap.biz.core.ontology.semantic_retrieval.api.routes", "router"),
    "object_view_router": ("odap.biz.core.ontology.view.api.routes", "router"),
}


__all__ = list(_ROUTER_MAP.keys())


def __getattr__(name: str) -> Any:
    """PEP 562 惰性解析：按需从真实 routes 模块加载 `router` 对象。

    `import odap.biz.core.ontology.public_routers` 本身不触发任何 routes 加载，
    只有真正取用某个 `xxx_router` 时才 import 对应模块。这样消费者能保持
    「函数内、按需」的原有导入语义与注册顺序。
    """
    target = _ROUTER_MAP.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr = target
    module = importlib.import_module(module_path)
    try:
        return getattr(module, attr)
    except AttributeError:
        raise AttributeError(
            f"router facade: {module_path!r} 不再导出 {attr!r}；"
            f"内部路由重构后请同步更新 core/ontology/public_routers.py 的 _ROUTER_MAP"
        ) from None


def __dir__() -> list[str]:
    return sorted(__all__)


# ─────────────────────────────────────────────────────────────────────────
# 静态可见性（仅供 IDE / 类型检查器；运行期不执行导入）
# 各 routes 模块的对象都叫 `router`，此处用别名导入以匹配 _ROUTER_MAP 的公共名。
# ─────────────────────────────────────────────────────────────────────────
if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter

    from odap.biz.core.ontology.action.api.routes import router as action_type_router
    from odap.biz.core.ontology.application.abution_graph.api.routes import router as abution_graph_router
    from odap.biz.core.ontology.application.harness.api.routes import router as harness_router
    from odap.biz.core.ontology.application.harness.blueprint.routes import router as blueprint_designer_router
    from odap.biz.core.ontology.application.harness.blueprint.api.runtime_routes import router as blueprint_runtime_router
    from odap.biz.core.ontology.application.oms.routes import router as oms_router
    from odap.biz.core.ontology.application.query_api.nl_routes import router as ontology_nl_router
    from odap.biz.core.ontology.application.query_api.routes import router as ontology_ingest_router
    from odap.biz.core.ontology.application.runtime.api.routes import router as runtime_router
    from odap.biz.core.ontology.application.runtime.state_machine.api.routes import router as state_machine_router
    from odap.biz.core.ontology.application.servitization.api.routes import router as servitization_router
    from odap.biz.core.ontology.application.servitization.api.deployment_routes import router as deployment_router
    from odap.biz.core.ontology.application.servitization.catalog.routes import router as catalog_router
    from odap.biz.core.ontology.assistant.api.routes import router as ontology_assistant_router
    from odap.biz.core.ontology.branch.api.routes import router as branch_router
    from odap.biz.core.ontology.cold_start.api.routes import router as cold_start_router
    from odap.biz.core.ontology.computed.api.routes import router as computed_router
    from odap.biz.core.ontology.conflict.api.routes import router as conflict_router
    from odap.biz.core.ontology.inheritance.api.routes import router as inheritance_router
    from odap.biz.core.ontology.design.engine.api.routes import router as ontology_engine_router
    from odap.biz.core.ontology.design.engine.api.shacl_owl_routes import router as shacl_owl_router
    from odap.biz.core.ontology.design.ingestion.api.routes import router as ingestion_router
    from odap.biz.core.ontology.design.model.api.routes import router as ontology_model_router
    from odap.biz.core.ontology.design.version.api.routes import router as ontology_version_router
    from odap.biz.core.ontology.extraction.api import router as extraction_router
    from odap.biz.core.ontology.goal.api.routes import router as goal_router
    from odap.biz.core.ontology.ontology_api.api import router as ontology_api_router
    from odap.biz.core.ontology.reasoning.api.routes import router as reasoning_router
    from odap.biz.core.ontology.registry.api.routes import router as registry_router
    from odap.biz.core.ontology.semantic_retrieval.api.routes import router as semantic_retrieval_router
    from odap.biz.core.ontology.view.api.routes import router as object_view_router
