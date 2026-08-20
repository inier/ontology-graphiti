"""四步法菜单种子数据 — 建/见/演/用 + 系统管理 + 帮助。

依据: docs/02-architecture/ARCHITECTURE_FOUR_STEPS.md
设计: docs/08-tasks/MENU_REFACTOR_PLAN.md Iter 1

菜单树结构（6 个顶级目录）:
  建本体 → 本体设计器/蓝图/目标/版本/数据摄入/HE抽取链/知识库/语义管理(子目录)
  见本体 → 本体图谱/图谱查看器/知识导航/仪表盘/QA管理
  演本体 → 仿真沙盘/业务流程/规则/指标/逻辑/对象管理/策略编辑器
  用本体 → QA查询/QA评估/MCP工具集/智能体(子目录)
  系统管理 → 工作空间/角色/用户/审计/菜单配置/设置/渠道/国际化
  帮助 → 使用指南

Iter 2 变更（D4 仿真入口合并）:
  - 移除"策略推演"和"模拟器"独立菜单项
  - "/simulation"作为统一入口，内部 Tab 切换沙盘/推演/事件
  - 旧路由 /simulator + /simulation/deduction 通过 redirect 兼容

Iter 3 变更（D5/D6/D7 命名消歧 + HE 关联 + MCP 入口）:
  - D5: 见本体"本体图谱"路径 /ontology/graph → /ontology/explorer（命名消歧）
  - D6: 建本体新增"HE 抽取链"菜单（/he/extraction）
  - D7: 用本体新增"MCP 工具集"菜单（/mcp/tools，7 个语义检索工具）

Iter 4 变更（P3 缺失前端页面补齐）:
  - 见本体新增"语义地图"菜单（/ontology/semantic-map）
  - 见本体新增"消歧图"菜单（/ontology/abution-graph）
  - 演本体新增"本体记忆"菜单（/simulation/memory）
  - 演本体新增"感知数据"菜单（/simulation/perception）
  - 用本体新增"服务化目录"菜单（/ontology/service-catalog）

约束:
  - 所有函数体 ≤ 40 行 (Constitution I)
  - 中文 as i18n key (project_memory)
  - code 唯一 (SQLite UNIQUE 约束)
  - 幂等: 通过 code 判断是否已存在
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
    """建本体：本体设计器/蓝图/目标/版本/数据摄入/HE抽取链/知识库 + 语义管理子目录。

    Iter 3 (D6): 新增"HE 抽取链"菜单项（/he/extraction），置于数据摄入与知识库之间。
    """
    parent = "dir:build"
    items = [
        _menu("menu:build:designer", "本体设计器", "/ontology/designer",
              "CodeSandboxOutlined", 1, parent),
        _menu("menu:build:blueprint", "蓝图设计器", "/blueprint",
              "BlockOutlined", 2, parent),
        _menu("menu:build:goals", "目标看板", "/ontology/goals",
              "AimOutlined", 3, parent),
        _menu("menu:build:versions", "版本管理", "/versions",
              "HistoryOutlined", 4, parent),
        _menu("menu:build:ingest", "数据摄入", "/ingest",
              "CloudUploadOutlined", 5, parent),
        _menu("menu:build:he_extraction", "HE 抽取链", "/he/extraction",
              "ExperimentOutlined", 6, parent),
        _menu("menu:build:knowledge", "知识库", "/knowledge",
              "BookOutlined", 7, parent),
        _subdir("dir:build:semantic", "语义管理", "BulbOutlined", 8, parent),
    ]
    items.extend(_build_semantic_submenus())
    return items


def _build_semantic_submenus() -> List[Dict[str, Any]]:
    """语义管理子目录：USL配置/流水线/候选/审批/质量。"""
    parent = "dir:build:semantic"
    return [
        _menu("menu:build:semantic:usl", "USL 配置", "/semantic-admin/usl",
              "SettingOutlined", 1, parent),
        _menu("menu:build:semantic:pipeline", "OL 流水线",
              "/semantic-admin/pipeline", "DeploymentUnitOutlined", 2, parent),
        _menu("menu:build:semantic:candidates", "候选管理",
              "/semantic-admin/candidates", "UnorderedListOutlined", 3, parent),
        _menu("menu:build:semantic:approvals", "审批工作流",
              "/semantic-admin/approvals", "CheckCircleOutlined", 4, parent),
        _menu("menu:build:semantic:quality", "质量仪表盘",
              "/semantic-admin/quality", "DashboardOutlined", 5, parent),
    ]


# ── 见本体菜单 ───────────────────────────────────────────────────


def _see_menus() -> List[Dict[str, Any]]:
    """见本体：本体图谱/图谱查看器/知识导航/仪表盘/QA管理/语义地图/消歧图。

    Iter 3 (D5): 本体图谱路径 /ontology/graph → /ontology/explorer（命名消歧），
    旧路由通过 AppRoutes redirect 兼容。
    Iter 4: 新增"语义地图"和"消歧图"菜单项（P3 缺失页面补齐）。
    """
    parent = "dir:see"
    return [
        _menu("menu:see:graph", "本体图谱", "/ontology/explorer",
              "ShareAltOutlined", 1, parent),
        _menu("menu:see:viewer", "图谱查看器", "/iframe-viewer",
              "FundProjectionScreenOutlined", 2, parent),
        _menu("menu:see:navigation", "知识导航", "/knowledge/navigation",
              "CompassOutlined", 3, parent),
        _menu("menu:see:dashboard", "总览仪表盘", "/semantic-admin/dashboard",
              "DashboardOutlined", 4, parent),
        _menu("menu:see:qa", "QA 管理", "/qa",
              "QuestionCircleOutlined", 5, parent),
        _menu("menu:see:semantic_map", "语义地图", "/ontology/semantic-map",
              "GlobalOutlined", 6, parent),
        _menu("menu:see:abution_graph", "消歧图", "/ontology/abution-graph",
              "PartitionOutlined", 7, parent),
    ]


# ── 演本体菜单 ───────────────────────────────────────────────────


def _simulate_menus() -> List[Dict[str, Any]]:
    """演本体：仿真沙盘（统一入口）/业务*/策略编辑器/本体记忆/感知数据/决策智能。

    Iter 2 (D4): 移除独立的"策略推演"和"模拟器"菜单项，
    合并到"仿真沙盘"/simulation 统一入口（内部 Tab 切换）。
    旧路由 /simulator + /simulation/deduction 通过 redirect 兼容。
    Iter 4: 新增"本体记忆"和"感知数据"菜单项（P3 缺失页面补齐）。
    Iter 5: 新增"决策智能"菜单项（ADR-076 决策记录/先例/影响分析，/decisions）。
    """
    parent = "dir:simulate"
    items = [
        _menu("menu:simulate:sandbox", "仿真沙盘", "/simulation",
              "ExperimentOutlined", 1, parent),
        _menu("menu:simulate:process", "业务流程", "/business/process",
              "NodeIndexOutlined", 2, parent),
        _menu("menu:simulate:rules", "业务规则", "/business/rules",
              "RuleOutlined", 3, parent),
        _menu("menu:simulate:indicators", "业务指标", "/business/indicators",
              "BarChartOutlined", 4, parent),
        _menu("menu:simulate:logic", "业务逻辑", "/business/logic",
              "BranchesOutlined", 5, parent),
        _menu("menu:simulate:entities", "对象管理", "/business/entities",
              "DatabaseOutlined", 6, parent),
        _menu("menu:simulate:policy", "策略编辑器", "/policy-editor",
              "SafetyCertificateOutlined", 7, parent),
        _menu("menu:simulate:memory", "本体记忆", "/simulation/memory",
              "BrainOutlined", 8, parent),
        _menu("menu:simulate:perception", "感知数据", "/simulation/perception",
              "EyeOutlined", 9, parent),
        _menu("menu:simulate:decision", "决策智能", "/decisions",
              "FundOutlined", 10, parent),
    ]
    return items


# ── 用本体菜单 ───────────────────────────────────────────────────


def _use_menus() -> List[Dict[str, Any]]:
    """用本体：QA查询/QA评估/MCP工具集/服务化目录 + 智能体子目录。

    Iter 3 (D7): 新增"MCP 工具集"菜单项（/mcp/tools），暴露 7 个语义检索 MCP 工具。
    Iter 4: 新增"服务化目录"菜单项（/ontology/service-catalog，P3 缺失页面补齐）。
    """
    parent = "dir:use"
    items = [
        _menu("menu:use:qa_query", "QA 查询", "/qa/query",
              "SearchOutlined", 1, parent),
        _menu("menu:use:qa_eval", "QA 评估", "/qa/evaluation",
              "LikeOutlined", 2, parent),
        _menu("menu:use:mcp_tools", "MCP 工具集", "/mcp/tools",
              "ThunderboltOutlined", 3, parent),
        _menu("menu:use:service_catalog", "服务化目录", "/ontology/service-catalog",
              "AppstoreOutlined", 4, parent),
        _subdir("dir:use:agent", "智能体", "RobotOutlined", 5, parent),
    ]
    items.extend(_use_agent_submenus())
    return items


def _use_agent_submenus() -> List[Dict[str, Any]]:
    """智能体子目录：我的智能体/对话/管理后台/技能管理。"""
    parent = "dir:use:agent"
    return [
        _menu("menu:use:agent:my", "我的智能体", "/my-agents",
              "UserOutlined", 1, parent),
        _menu("menu:use:agent:chat", "智能体对话", "/agent",
              "MessageOutlined", 2, parent),
        _menu("menu:use:agent:admin", "管理后台", "/admin/agents",
              "TeamOutlined", 3, parent),
        _menu("menu:use:agent:skills", "技能管理", "/skills",
              "ToolOutlined", 4, parent),
    ]


# ── 系统管理菜单 ─────────────────────────────────────────────────


def _system_menus() -> List[Dict[str, Any]]:
    """系统管理：工作空间/角色/用户/审计/菜单配置/设置/渠道/国际化。"""
    parent = "dir:system"
    return [
        _menu("menu:system:workspace", "工作空间", "/workspace/manage",
              "AppstoreOutlined", 1, parent),
        _menu("menu:system:roles", "角色权限", "/roles",
              "SafetyOutlined", 2, parent),
        _menu("menu:system:users", "用户管理", "/users",
              "TeamOutlined", 3, parent),
        _menu("menu:system:audit", "审计日志", "/audit",
              "AuditOutlined", 4, parent),
        _menu("menu:system:menu", "菜单配置", "/menu-config",
              "MenuOutlined", 5, parent),
        _menu("menu:system:settings", "设置", "/settings",
              "SettingOutlined", 6, parent),
        _menu("menu:system:channels", "渠道管理", "/settings/channels/default",
              "ApiOutlined", 7, parent),
        _menu("menu:system:i18n", "国际化", "/i18n-admin",
              "GlobalOutlined", 8, parent),
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
    共 6 目录 + 8 子目录/菜单(建) + 5(见) + 7(演) + 4+4(用) + 8(系统) + 1(帮助) = 48 项

    Iter 2 变更：演本体从 9 项减为 7 项（移除策略推演/模拟器，合并到仿真沙盘）
    Iter 3 变更：建本体新增 HE 抽取链(+1)，用本体新增 MCP 工具集(+1)，共 48 项
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
