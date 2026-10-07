"""四步法菜单种子数据 — 建/见/演/用 + 系统管理 + 帮助。

依据: docs/02-architecture/ARCHITECTURE_FOUR_STEPS.md
设计: docs/08-tasks/MENU_REFACTOR_PLAN.md Iter 1 · docs/08-tasks/MENU_DEDUP_PLAN.md（去重/消歧）

菜单树结构（6 个顶级目录）:
  建本体 → 本体类型设计/蓝图编排/目标看板/版本管理/数据接入(子目录)/知识库·管理/语义管理(子目录)
  见本体 → 图谱与映射(子目录)/知识库·浏览
  演本体 → 决策智能/仿真沙盘/业务建模(子目录)/本体记忆/感知数据
  用本体 → 问答检索(子目录)/MCP工具集/服务化目录/智能体(子目录)
  系统管理 → 工作空间/角色权限/用户管理/策略编辑器/审计日志/菜单配置/设置/渠道管理/国际化
  帮助 → 使用指南

Iter 2 变更（D4 仿真入口合并）:
  - 移除"策略推演"和"模拟器"独立菜单项，合并到"仿真沙盘"/simulation 统一入口
  - 旧路由 /simulator + /simulation/deduction 通过 redirect 兼容

Iter 3 变更（D5/D6/D7 命名消歧 + HE 关联 + MCP 入口）:
  - D5: 见本体"本体图谱"路径 /ontology/graph → /ontology/explorer
  - D6: 建本体新增"HE 抽取链"菜单（/he/extraction）
  - D7: 用本体新增"MCP 工具集"菜单（/mcp/tools，7 个语义检索工具）

Iter 4 变更（P3 缺失前端页面补齐）:
  - 见本体新增"语义地图"/"消歧图"；演本体新增"本体记忆"/"感知数据"；用本体新增"服务化目录"

Iter 7 变更（MENU_DEDUP_PLAN 去重/消歧 + 决策主线显性化）:
  - 消歧改名：本体设计器→本体类型设计、蓝图设计器→蓝图编排、数据摄入→数据摄入管道、
    HE 抽取链→HE 文本抽取、知识库→知识库·管理、知识导航→知识库·浏览、
    本体图谱→本体图谱浏览、语义地图→语义映射管理、消歧图→消歧快照管理、
    QA 管理→智能问答、QA 查询→检索查询台、QA 评估→检索评估、
    智能体对话→智能体调度、管理后台→智能体管理
  - 分组子目录：建本体「数据接入」、见本体「图谱与映射」、演本体「业务建模」、用本体「问答检索」
  - 移位：QA 三项 见本体→用本体（问答检索子目录）；策略编辑器 演本体→系统管理（OPA 权限域）
  - 合并/移除：总览仪表盘 /semantic-admin/dashboard 与质量仪表盘同后端 API → 从种子移除，
    路由 redirect 到 /semantic-admin/quality；图谱查看器 /iframe-viewer 为通用 iframe 容器
    （固定菜单点进去必空）→ 从种子移除，路由保留供内嵌调用
  - 决策主线显性化：演本体「决策智能」/decisions 从末位(sort 10)提升到首位(sort 1)，
    使"基于本体的辅助决策"在信息架构中一眼可见（ADR-073/ADR-076）

约束:
  - 所有函数体 ≤ 40 行 (Constitution I)
  - 中文 as i18n key (project_memory)
  - code 唯一 (SQLite UNIQUE 约束)；移位/改名保持 code 稳定以不破坏 role_menus 授权
  - 幂等: 通过 code 判断是否已存在；对已有 DB 的结构变更需配套 migrations/ 脚本
"""

from __future__ import annotations

from typing import Any, Dict, List

# ── 顶级目录 ─────────────────────────────────────────────────────


def _directory(code: str, name: str, icon: str, sort_order: int) -> Dict[str, Any]:
    """构建顶级目录菜单项。

    path/url 使用空字符串而非 None — 兼容旧版 DB schema（path NOT NULL 约束）。
    """
    return {
        "id": code,
        "parent_id": None,
        "name": name,
        "code": code,
        "menu_type": "directory",
        "link_type": "internal",
        "path": "",
        "url": "",
        "icon": icon,
        "sort_order": sort_order,
        "is_active": True,
        "is_visible": True,
        "description": "",
    }


def _top_directories() -> List[Dict[str, Any]]:
    """6 个顶级目录：建/见/演/用/系统管理/帮助。"""
    return [
        _directory("dir:build", "建本体", "BuildOutlined", 1),
        _directory("dir:see", "见本体", "EyeOutlined", 2),
        _directory("dir:simulate", "演本体", "ExperimentOutlined", 3),
        _directory("dir:use", "用本体", "ApiOutlined", 4),
        _directory("dir:system", "系统管理", "SettingOutlined", 5),
        _directory("dir:help", "帮助", "QuestionCircleOutlined", 6),
    ]


# ── 菜单项构建辅助 ───────────────────────────────────────────────


def _menu(
    code: str, name: str, path: str, icon: str, sort_order: int,
    parent_code: str, description: str = "",
) -> Dict[str, Any]:
    """构建菜单项（可点击导航）。"""
    return {
        "id": code,
        "parent_id": parent_code,
        "name": name,
        "code": code,
        "menu_type": "menu",
        "link_type": "internal",
        "path": path,
        "url": None,
        "icon": icon,
        "sort_order": sort_order,
        "is_active": True,
        "is_visible": True,
        "description": description,
    }


def _subdir(
    code: str, name: str, icon: str, sort_order: int, parent_code: str,
) -> Dict[str, Any]:
    """构建二级目录（可折叠分组）。

    path/url 使用空字符串而非 None — 兼容旧版 DB schema（path NOT NULL 约束）。
    """
    return {
        "id": code,
        "parent_id": parent_code,
        "name": name,
        "code": code,
        "menu_type": "directory",
        "link_type": "internal",
        "path": "",
        "url": "",
        "icon": icon,
        "sort_order": sort_order,
        "is_active": True,
        "is_visible": True,
        "description": "",
    }


# ── 建本体菜单 ───────────────────────────────────────────────────


def _build_menus() -> List[Dict[str, Any]]:
    """建本体：本体类型设计/蓝图编排/目标/版本 + 数据接入(子目录) + 知识库·管理 + 语义管理(子目录)。

    Iter 7: designer/blueprint 消歧改名；新增「数据接入」子目录收拢 ingest + HE；
    知识库→知识库·管理（与见本体"知识库·浏览"区分管理/浏览职责）。
    """
    parent = "dir:build"
    items = [
        _menu("menu:build:designer", "本体类型设计", "/ontology/designer",
              "CodeSandboxOutlined", 1, parent),
        _menu("menu:build:blueprint", "蓝图编排", "/blueprint",
              "BlockOutlined", 2, parent),
        _menu("menu:build:goals", "目标看板", "/ontology/goals",
              "AimOutlined", 3, parent),
        _menu("menu:build:versions", "版本管理", "/versions",
              "HistoryOutlined", 4, parent),
        _subdir("dir:build:ingest", "数据接入", "CloudUploadOutlined", 5, parent),
        _menu("menu:build:knowledge", "知识库·管理", "/knowledge",
              "BookOutlined", 6, parent),
        _subdir("dir:build:semantic", "语义管理", "BulbOutlined", 7, parent),
    ]
    items.extend(_build_ingest_submenus())
    items.extend(_build_semantic_submenus())
    return items


def _build_ingest_submenus() -> List[Dict[str, Any]]:
    """数据接入子目录：数据摄入管道 + HE 文本抽取（Iter 7 消歧改名）。"""
    parent = "dir:build:ingest"
    return [
        _menu("menu:build:ingest", "数据摄入管道", "/ingest",
              "CloudUploadOutlined", 1, parent),
        _menu("menu:build:he_extraction", "HE 文本抽取", "/he/extraction",
              "ExperimentOutlined", 2, parent),
    ]


def _build_semantic_submenus() -> List[Dict[str, Any]]:
    """语义管理子目录：USL配置/USL本体管理/流水线/候选/审批/质量仪表盘/概念缺口/缺口统计。

    Iter 7: 见本体"总览仪表盘"(dashboard) 与本目录"质量仪表盘"调用同一组后端 API，
    已从种子移除，dashboard 路由 redirect 到 quality，语义管理页面全部聚合在建本体。
    """
    parent = "dir:build:semantic"
    return [
        _menu("menu:build:semantic:usl", "USL 配置", "/semantic-admin/usl",
              "SettingOutlined", 1, parent),
        _menu("menu:build:semantic:usl_ontologies", "USL 本体管理",
              "/semantic-admin/usl-ontologies", "ApartmentOutlined", 2, parent),
        _menu("menu:build:semantic:pipeline", "OL 流水线",
              "/semantic-admin/pipeline", "DeploymentUnitOutlined", 3, parent),
        _menu("menu:build:semantic:candidates", "候选管理",
              "/semantic-admin/candidates", "UnorderedListOutlined", 4, parent),
        _menu("menu:build:semantic:approvals", "审批工作流",
              "/semantic-admin/approvals", "CheckCircleOutlined", 5, parent),
        _menu("menu:build:semantic:quality", "质量仪表盘",
              "/semantic-admin/quality", "DashboardOutlined", 6, parent),
        _menu("menu:build:semantic:gaps", "概念缺口", "/semantic-admin/gaps",
              "WarningOutlined", 7, parent),
        _menu("menu:build:semantic:gap-stats", "缺口统计", "/semantic-admin/gaps/stats",
              "BarChartOutlined", 8, parent),
    ]


# ── 见本体菜单 ───────────────────────────────────────────────────


def _see_menus() -> List[Dict[str, Any]]:
    """见本体：图谱与映射(子目录) + 知识库·浏览。

    Iter 7: 本体图谱/语义地图/消歧图收进「图谱与映射」子目录并消歧改名；
    "图谱查看器"(/iframe-viewer 通用 iframe 容器)与"总览仪表盘"(dashboard 与 quality
    重复)已从种子移除；QA 管理移至用本体「问答检索」；知识导航→知识库·浏览。
    """
    parent = "dir:see"
    items = [
        _subdir("dir:see:graph", "图谱与映射", "ShareAltOutlined", 1, parent),
        _menu("menu:see:navigation", "知识库·浏览", "/knowledge/navigation",
              "CompassOutlined", 2, parent),
    ]
    items.extend(_see_graph_submenus())
    return items


def _see_graph_submenus() -> List[Dict[str, Any]]:
    """图谱与映射子目录：本体图谱浏览/语义映射管理/消歧快照管理（Iter 7 消歧改名）。"""
    parent = "dir:see:graph"
    return [
        _menu("menu:see:graph", "本体图谱浏览", "/ontology/explorer",
              "ShareAltOutlined", 1, parent),
        _menu("menu:see:semantic_map", "语义映射管理", "/ontology/semantic-map",
              "GlobalOutlined", 2, parent),
        _menu("menu:see:abution_graph", "消歧快照管理", "/ontology/abution-graph",
              "PartitionOutlined", 3, parent),
    ]


# ── 演本体菜单 ───────────────────────────────────────────────────


def _simulate_menus() -> List[Dict[str, Any]]:
    """演本体：决策智能/仿真沙盘/业务建模(子目录)/本体记忆/感知数据。

    Iter 7: 「决策智能」/decisions 从末位提升到首位——演本体是"基于本体的辅助决策"
    的价值兑现层，决策主线应在 IA 中一眼可见（ADR-073/ADR-076）。
    5 个"业务*"收进「业务建模」子目录；「策略编辑器」(OPA 权限策略)移至系统管理。
    Iter 2 (D4): "策略推演"/"模拟器"合并到"仿真沙盘"/simulation 统一入口。
    """
    parent = "dir:simulate"
    items = [
        _menu("menu:simulate:decision", "决策智能", "/decisions",
              "FundOutlined", 1, parent),
        _menu("menu:simulate:sandbox", "仿真沙盘", "/simulation",
              "ExperimentOutlined", 2, parent),
        _subdir("dir:simulate:business", "业务建模", "NodeIndexOutlined", 3, parent),
        _menu("menu:simulate:memory", "本体记忆", "/simulation/memory",
              "BrainOutlined", 4, parent),
        _menu("menu:simulate:perception", "感知数据", "/simulation/perception",
              "EyeOutlined", 5, parent),
    ]
    items.extend(_simulate_business_submenus())
    return items


def _simulate_business_submenus() -> List[Dict[str, Any]]:
    """业务建模子目录：流程/规则/指标/逻辑/对象管理（沿用 Iter1 D1 归演本体决策）。"""
    parent = "dir:simulate:business"
    return [
        _menu("menu:simulate:process", "业务流程", "/business/process",
              "NodeIndexOutlined", 1, parent),
        _menu("menu:simulate:rules", "业务规则", "/business/rules",
              "RuleOutlined", 2, parent),
        _menu("menu:simulate:indicators", "业务指标", "/business/indicators",
              "BarChartOutlined", 3, parent),
        _menu("menu:simulate:logic", "业务逻辑", "/business/logic",
              "BranchesOutlined", 4, parent),
        _menu("menu:simulate:entities", "对象管理", "/business/entities",
              "DatabaseOutlined", 5, parent),
    ]


# ── 用本体菜单 ───────────────────────────────────────────────────


def _use_menus() -> List[Dict[str, Any]]:
    """用本体：问答检索(子目录)/MCP工具集/服务化目录 + 智能体(子目录)。

    Iter 7: QA 三项(智能问答/检索查询台/检索评估)从见本体聚合到「问答检索」子目录，
    使"用本体"完整承载对外消费能力（问答 + 语义检索 + MCP + 服务化 + 智能体）。
    """
    parent = "dir:use"
    items = [
        _subdir("dir:use:qa", "问答检索", "SearchOutlined", 1, parent),
        _menu("menu:use:mcp_tools", "MCP 工具集", "/mcp/tools",
              "ThunderboltOutlined", 2, parent),
        _menu("menu:use:service_catalog", "服务化目录", "/ontology/service-catalog",
              "AppstoreOutlined", 3, parent),
        _subdir("dir:use:agent", "智能体", "RobotOutlined", 4, parent),
    ]
    items.extend(_use_qa_submenus())
    items.extend(_use_agent_submenus())
    return items


def _use_qa_submenus() -> List[Dict[str, Any]]:
    """问答检索子目录：智能问答/检索查询台/检索评估（Iter 7 移位 + 消歧改名）。

    注：menu:see:qa 的 code 保持不变（原属见本体），移位到用本体后仍复用旧 code，
    以不破坏 role_menus 已有授权。
    """
    parent = "dir:use:qa"
    return [
        _menu("menu:see:qa", "智能问答", "/qa",
              "QuestionCircleOutlined", 1, parent),
        _menu("menu:use:qa_query", "检索查询台", "/qa/query",
              "SearchOutlined", 2, parent),
        _menu("menu:use:qa_eval", "检索评估", "/qa/evaluation",
              "LikeOutlined", 3, parent),
    ]


def _use_agent_submenus() -> List[Dict[str, Any]]:
    """智能体子目录：我的智能体/智能体调度/智能体管理/技能管理（Iter 7 消歧改名）。

    /agent 实为 OODA 决策链调度台（intent→dispatch→observe/orient/decide/act），
    原"智能体对话"是错名（真对话在 /agent-chat/:id）→ 改「智能体调度」；
    "管理后台"名过泛 → 改「智能体管理」。
    """
    parent = "dir:use:agent"
    return [
        _menu("menu:use:agent:my", "我的智能体", "/my-agents",
              "UserOutlined", 1, parent),
        _menu("menu:use:agent:chat", "智能体调度", "/agent",
              "MessageOutlined", 2, parent),
        _menu("menu:use:agent:admin", "智能体管理", "/admin/agents",
              "TeamOutlined", 3, parent),
        _menu("menu:use:agent:skills", "技能管理", "/skills",
              "ToolOutlined", 4, parent),
    ]


# ── 系统管理菜单 ─────────────────────────────────────────────────


def _system_menus() -> List[Dict[str, Any]]:
    """系统管理：工作空间/角色权限/用户管理/策略编辑器/审计/菜单配置/设置/渠道/国际化。

    Iter 7: 「策略编辑器」(/policy-editor，OPA 权限策略)从演本体移入系统管理，
    与「角色权限」相邻——它属于权限治理域，不是本体推演能力。
    注：menu:simulate:policy 的 code 保持不变以不破坏 role_menus 授权。
    """
    parent = "dir:system"
    return [
        _menu("menu:system:workspace", "工作空间", "/workspace/manage",
              "AppstoreOutlined", 1, parent),
        _menu("menu:system:roles", "角色权限", "/roles",
              "SafetyOutlined", 2, parent),
        _menu("menu:system:users", "用户管理", "/users",
              "TeamOutlined", 3, parent),
        _menu("menu:simulate:policy", "策略编辑器", "/policy-editor",
              "SafetyCertificateOutlined", 4, parent),
        _menu("menu:system:audit", "审计日志", "/audit",
              "AuditOutlined", 5, parent),
        _menu("menu:system:menu", "菜单配置", "/menu-config",
              "MenuOutlined", 6, parent),
        _menu("menu:system:settings", "设置", "/settings",
              "SettingOutlined", 7, parent),
        _menu("menu:system:channels", "渠道管理", "/settings/channels/default",
              "ApiOutlined", 8, parent),
        _menu("menu:system:i18n", "国际化", "/i18n-admin",
              "GlobalOutlined", 9, parent),
    ]


# ── 帮助菜单 ─────────────────────────────────────────────────────


def _help_menus() -> List[Dict[str, Any]]:
    """帮助：使用指南。"""
    return [
        _menu("menu:help:guide", "使用指南", "/guide",
              "QuestionCircleOutlined", 1, "dir:help"),
    ]


# ── 汇总入口 ─────────────────────────────────────────────────────


def get_four_steps_seed_data() -> List[Dict[str, Any]]:
    """返回完整的四步法菜单种子数据（扁平列表，含 parent_id 关联）。

    顺序：顶级目录 → 建本体 → 见本体 → 演本体 → 用本体 → 系统管理 → 帮助

    Iter 7 后共 59 项：
      6 顶级目录
      + 17 建本体（7 直属含2子目录 + 2 数据接入 + 8 语义管理）
      +  5 见本体（2 直属含1子目录 + 3 图谱与映射）
      + 10 演本体（5 直属含1子目录 + 5 业务建模）
      + 11 用本体（4 直属含2子目录 + 3 问答检索 + 4 智能体）
      +  9 系统管理
      +  1 帮助
    （Iter 7 移除 iframe-viewer + dashboard 两项，新增 4 个分组子目录；
     概念缺口回路新增 2 项：概念缺口/缺口统计，挂在语义管理子目录下）
    """
    items: List[Dict[str, Any]] = []
    items.extend(_top_directories())
    items.extend(_build_menus())
    items.extend(_see_menus())
    items.extend(_simulate_menus())
    items.extend(_use_menus())
    items.extend(_system_menus())
    items.extend(_help_menus())
    return items
