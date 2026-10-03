"""TDD 单元测试：四步法菜单种子数据初始化（Iter 1–7）。

设计文档：
  docs/08-tasks/MENU_REFACTOR_PLAN.md（Iter 1–6）
  docs/08-tasks/MENU_DEDUP_PLAN.md（Iter 7 去重/消歧 + 决策主线显性化）

Sandbox 策略：
  - tmp_path 真实 SQLite DB，不污染生产数据
  - 测试 init_default_menu() 幂等性 + 菜单树结构正确性

Iter 7 结构要点（57 项）：
  - 新增 4 个分组子目录：数据接入 / 图谱与映射 / 业务建模 / 问答检索
  - QA 三项从见本体移到用本体「问答检索」；策略编辑器从演本体移到系统管理
  - iframe-viewer(图谱查看器) + semantic-admin/dashboard(总览仪表盘) 从种子移除
  - 决策智能 /decisions 提升到演本体首位（sort_order=1）
  - 大量消歧改名（本体类型设计/蓝图编排/智能体调度/智能体管理/…）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from odap.biz.platform.menu_config.seeds.seed_four_steps import (
    get_four_steps_seed_data,
)
from odap.biz.platform.menu_config.services.menu_config_service import (
    MenuConfigService,
)
from odap.biz.platform.menu_config.storage.sqlite_menu_config_storage import (
    SQLiteMenuConfigStorage,
)

# Iter 7 后的种子总数（6 目录 + 51 菜单/子目录）
TOTAL_SEED = 57


# =====================================================================
# Sandbox Fixtures
# =====================================================================


@pytest.fixture
def sandbox_storage(tmp_path: Path) -> SQLiteMenuConfigStorage:
    """Sandbox：独立临时 DB。"""
    return SQLiteMenuConfigStorage(db_path=str(tmp_path / "menu_seed_test.db"))


@pytest.fixture
def menu_service(sandbox_storage: SQLiteMenuConfigStorage) -> MenuConfigService:
    """注入 sandbox storage 的 MenuConfigService（绕过单例）。"""
    svc = MenuConfigService.__new__(MenuConfigService)
    svc._storage = sandbox_storage
    svc._initialized = True
    return svc


@pytest.fixture
def tree(menu_service: MenuConfigService) -> List[Dict[str, Any]]:
    """初始化种子后返回完整菜单树（active_only=False）。"""
    menu_service.init_default_menu()
    return menu_service.get_tree(active_only=False)


# =====================================================================
# 树遍历辅助
# =====================================================================


def _top(tree: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
    return next(n for n in tree if n["name"] == name)


def _child(node: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    return next((c for c in node["children"] if c["name"] == name), None)


def _names(node: Dict[str, Any]) -> List[str]:
    return [c["name"] for c in node["children"]]


def _require_child(node: Dict[str, Any], name: str) -> Dict[str, Any]:
    child = _child(node, name)
    assert child is not None, f"{node['name']} 下应有 '{name}'，实际 {_names(node)}"
    return child


def _flatten_names(node: Dict[str, Any]) -> List[str]:
    """递归收集节点及其所有后代的 name。"""
    result = [node["name"]]
    for c in node.get("children", []):
        result.extend(_flatten_names(c))
    return result


# =====================================================================
# T-SEED-1/2: 幂等初始化
# =====================================================================


def test_seed_1_first_init_creates_all(menu_service: MenuConfigService):
    """T-SEED-1: 首次调用写入全部种子数据（Iter 7 后 57 项）。"""
    result = menu_service.init_default_menu()
    assert result["status"] == "success"
    assert result["created"] == TOTAL_SEED, f"应创建 {TOTAL_SEED} 项，实际 {result['created']}"
    assert result["skipped"] == 0
    assert result["total"] == TOTAL_SEED
    assert result["role_grants"] >= 1, "首次初始化应同步授予默认角色菜单权限"


def test_seed_2_second_init_is_idempotent(menu_service: MenuConfigService):
    """T-SEED-2: 二次调用跳过已存在项，不重复写入。"""
    menu_service.init_default_menu()
    result = menu_service.init_default_menu()
    assert result["created"] == 0, "二次调用不应创建新项"
    assert result["skipped"] == TOTAL_SEED, f"应跳过 {TOTAL_SEED} 项，实际 {result['skipped']}"
    assert result["role_grants"] == 0, "幂等：二次调用不再重复授权"


# =====================================================================
# T-SEED-3: 6 个顶级目录
# =====================================================================


def test_seed_3_six_top_directories(tree: List[Dict[str, Any]]):
    """T-SEED-3: 顶级目录 = 建/见/演/用/系统管理/帮助。"""
    top_names = [node["name"] for node in tree]
    expected = ["建本体", "见本体", "演本体", "用本体", "系统管理", "帮助"]
    assert top_names == expected, f"顶级目录={top_names}，预期={expected}"


# =====================================================================
# T-SEED-4: 建本体 > 语义管理子目录（6 项，含 USL 本体管理）
# =====================================================================


def test_seed_4_build_has_semantic_subdir(tree: List[Dict[str, Any]]):
    """T-SEED-4: 建本体 → 语义管理子目录 → 6 个子菜单。"""
    build = _top(tree, "建本体")
    semantic = _require_child(build, "语义管理")
    children = _names(semantic)
    assert len(children) == 6, f"语义管理应有 6 子项，实际 {children}"
    for expected in ["USL 配置", "USL 本体管理", "OL 流水线", "候选管理", "审批工作流", "质量仪表盘"]:
        assert expected in children, f"语义管理应含 '{expected}'"


# =====================================================================
# T-SEED-5: 演本体 > 业务建模子目录（5 项，D1 + Iter7 收组）
# =====================================================================


def test_seed_5_simulate_has_business_subdir(tree: List[Dict[str, Any]]):
    """T-SEED-5: 演本体 → 业务建模子目录 → 流程/规则/指标/逻辑/对象管理。"""
    sim = _top(tree, "演本体")
    business = _require_child(sim, "业务建模")
    children = _names(business)
    for expected in ["业务流程", "业务规则", "业务指标", "业务逻辑", "对象管理"]:
        assert expected in children, f"业务建模应含 '{expected}'，实际 {children}"
    assert len(children) == 5, f"业务建模应有 5 子项，实际 {children}"


# =====================================================================
# T-SEED-6: 种子 code 唯一
# =====================================================================


def test_seed_6_codes_unique():
    """T-SEED-6: 种子数据中 code 字段无重复。"""
    seed_items = get_four_steps_seed_data()
    codes = [item["code"] for item in seed_items]
    assert len(codes) == len(set(codes)), (
        f"code 有重复: {set(c for c in codes if codes.count(c) > 1)}"
    )


# =====================================================================
# T-SEED-7: get_tree 返回嵌套结构 + 各顶级目录直属子项数
# =====================================================================


def test_seed_7_tree_is_nested(tree: List[Dict[str, Any]]):
    """T-SEED-7: get_tree() 返回嵌套 children，顶级目录直属子项数符合 Iter7 目标。"""
    assert len(tree) == 6, f"顶级应有 6 个目录，实际 {len(tree)}"
    for node in tree:
        assert "children" in node and isinstance(node["children"], list)
    expected_direct = {
        "建本体": 7,   # designer/blueprint/goals/versions/数据接入/知识库·管理/语义管理
        "见本体": 2,   # 图谱与映射/知识库·浏览
        "演本体": 5,   # 决策智能/仿真沙盘/业务建模/本体记忆/感知数据
        "用本体": 4,   # 问答检索/MCP工具集/服务化目录/智能体
        "系统管理": 9,
        "帮助": 1,
    }
    for name, count in expected_direct.items():
        node = _top(tree, name)
        assert len(node["children"]) == count, (
            f"{name} 直属子项应为 {count}，实际 {_names(node)}"
        )


# =====================================================================
# T-SEED-8: 用本体 > 智能体子目录（4 项 + Iter7 消歧改名）
# =====================================================================


def test_seed_8_use_has_agent_subdir(tree: List[Dict[str, Any]]):
    """T-SEED-8: 用本体 → 智能体子目录 → 我的智能体/智能体调度/智能体管理/技能管理。"""
    use = _top(tree, "用本体")
    agent = _require_child(use, "智能体")
    children = _names(agent)
    assert len(children) == 4, f"智能体应有 4 子项，实际 {children}"
    assert "我的智能体" in children
    assert "技能管理" in children
    # Iter 7 消歧改名
    assert "智能体调度" in children, "原'智能体对话'应改名为'智能体调度'（OODA 调度台）"
    assert "智能体管理" in children, "原'管理后台'应改名为'智能体管理'"
    dispatch = _require_child(agent, "智能体调度")
    assert dispatch["path"] == "/agent", f"智能体调度 path 应为 /agent，实际 {dispatch['path']}"


# =====================================================================
# T-SEED-9/10: 演本体仿真入口（D4）
# =====================================================================


def test_seed_9_simulate_no_deduction_simulator(tree: List[Dict[str, Any]]):
    """T-SEED-9: 演本体不含'策略推演'和'模拟器'独立菜单（D4 合并到仿真沙盘）。"""
    sim = _top(tree, "演本体")
    children = _names(sim)
    assert "策略推演" not in children
    assert "模拟器" not in children


def test_seed_10_simulate_has_sandbox_entry(tree: List[Dict[str, Any]]):
    """T-SEED-10: 演本体含'仿真沙盘'统一入口（/simulation）。"""
    sim = _top(tree, "演本体")
    sandbox = _require_child(sim, "仿真沙盘")
    assert sandbox["path"] == "/simulation", f"仿真沙盘 path 应为 /simulation，实际 {sandbox['path']}"


# =====================================================================
# T-SEED-11: QA 三项聚合到用本体「问答检索」（Iter7 C2）
# =====================================================================


def test_seed_11_qa_consolidated_under_use(tree: List[Dict[str, Any]]):
    """T-SEED-11: QA 三项全部聚合到用本体「问答检索」；见本体不再有 QA。"""
    see = _top(tree, "见本体")
    assert "QA 管理" not in _flatten_names(see), "见本体不应再有 QA 管理（已移至用本体）"

    use = _top(tree, "用本体")
    qa = _require_child(use, "问答检索")
    children = _names(qa)
    assert children == ["智能问答", "检索查询台", "检索评估"], f"问答检索子项={children}"
    assert _require_child(qa, "智能问答")["path"] == "/qa"
    assert _require_child(qa, "检索查询台")["path"] == "/qa/query"
    assert _require_child(qa, "检索评估")["path"] == "/qa/evaluation"


# =====================================================================
# T-SEED-12: 建本体 > 数据接入 > HE 文本抽取（Iter3 D6 + Iter7 收组改名）
# =====================================================================


def test_seed_12_build_has_he_extraction(tree: List[Dict[str, Any]]):
    """T-SEED-12: 建本体 → 数据接入子目录 → HE 文本抽取（/he/extraction）。"""
    build = _top(tree, "建本体")
    ingest = _require_child(build, "数据接入")
    children = _names(ingest)
    assert children == ["数据摄入管道", "HE 文本抽取"], f"数据接入子项={children}"
    he = _require_child(ingest, "HE 文本抽取")
    assert he["path"] == "/he/extraction", f"HE 文本抽取 path 应为 /he/extraction，实际 {he['path']}"
    assert _require_child(ingest, "数据摄入管道")["path"] == "/ingest"


# =====================================================================
# T-SEED-13: 用本体含 MCP 工具集（Iter3 D7）
# =====================================================================


def test_seed_13_use_has_mcp_tools(tree: List[Dict[str, Any]]):
    """T-SEED-13: 用本体含'MCP 工具集'菜单（/mcp/tools，D7）。"""
    use = _top(tree, "用本体")
    mcp = _require_child(use, "MCP 工具集")
    assert mcp["path"] == "/mcp/tools", f"MCP 工具集 path 应为 /mcp/tools，实际 {mcp['path']}"


# =====================================================================
# T-SEED-14/15/16: 见本体 > 图谱与映射子目录（Iter3 D5 + Iter4 + Iter7 消歧）
# =====================================================================


def test_seed_14_graph_subdir_explorer(tree: List[Dict[str, Any]]):
    """T-SEED-14: 见本体 → 图谱与映射 → 本体图谱浏览（/ontology/explorer，D5 改名）。"""
    see = _top(tree, "见本体")
    graph_group = _require_child(see, "图谱与映射")
    graph = _require_child(graph_group, "本体图谱浏览")
    assert graph["path"] == "/ontology/explorer", (
        f"本体图谱浏览 path 应为 /ontology/explorer，实际 {graph['path']}"
    )


def test_seed_15_semantic_map_renamed(tree: List[Dict[str, Any]]):
    """T-SEED-15: 图谱与映射含'语义映射管理'（/ontology/semantic-map，Iter7 消歧改名）。"""
    see = _top(tree, "见本体")
    graph_group = _require_child(see, "图谱与映射")
    sm = _require_child(graph_group, "语义映射管理")
    assert sm["path"] == "/ontology/semantic-map"


def test_seed_16_abution_graph_renamed(tree: List[Dict[str, Any]]):
    """T-SEED-16: 图谱与映射含'消歧快照管理'（/ontology/abution-graph，Iter7 消歧改名）。"""
    see = _top(tree, "见本体")
    graph_group = _require_child(see, "图谱与映射")
    ag = _require_child(graph_group, "消歧快照管理")
    assert ag["path"] == "/ontology/abution-graph"
    assert len(_names(graph_group)) == 3, "图谱与映射应有 3 子项"


# =====================================================================
# T-SEED-17/18: 演本体 本体记忆 / 感知数据（Iter4）
# =====================================================================


def test_seed_17_simulate_has_memory(tree: List[Dict[str, Any]]):
    """T-SEED-17: 演本体含'本体记忆'菜单（/simulation/memory）。"""
    sim = _top(tree, "演本体")
    mem = _require_child(sim, "本体记忆")
    assert mem["path"] == "/simulation/memory"


def test_seed_18_simulate_has_perception(tree: List[Dict[str, Any]]):
    """T-SEED-18: 演本体含'感知数据'菜单（/simulation/perception）。"""
    sim = _top(tree, "演本体")
    perc = _require_child(sim, "感知数据")
    assert perc["path"] == "/simulation/perception"


# =====================================================================
# T-SEED-19: 用本体 服务化目录（Iter4）
# =====================================================================


def test_seed_19_use_has_service_catalog(tree: List[Dict[str, Any]]):
    """T-SEED-19: 用本体含'服务化目录'菜单（/ontology/service-catalog）。"""
    use = _top(tree, "用本体")
    sc = _require_child(use, "服务化目录")
    assert sc["path"] == "/ontology/service-catalog"


# =====================================================================
# T-SEED-20: 决策智能提升到演本体首位（ADR-076 + Iter7 决策主线显性化）
# =====================================================================


def test_seed_20_decision_intelligence_first(tree: List[Dict[str, Any]]):
    """T-SEED-20: 演本体'决策智能'(/decisions) 提升到首位（sort_order=1）。"""
    sim = _top(tree, "演本体")
    dci = _require_child(sim, "决策智能")
    assert dci["path"] == "/decisions", f"决策智能 path 应为 /decisions，实际 {dci['path']}"
    assert dci["sort_order"] == 1, f"决策智能应置顶(sort_order=1)，实际 {dci['sort_order']}"
    # 建树按 sort_order 排序 → 决策智能应是演本体第一个直属子项
    assert _names(sim)[0] == "决策智能", f"演本体首项应为决策智能，实际 {_names(sim)}"


# =====================================================================
# T-SEED-21: 默认角色菜单权限（与 JWT role 对齐）
# =====================================================================


def test_seed_21_default_role_menus_granted(menu_service: MenuConfigService):
    """T-SEED-21: 非 admin 全局角色默认获得全部可见菜单，admin 不写 role_menus。"""
    menu_service.init_default_menu()
    observer_ids = menu_service._storage.get_role_menu_ids("observer")
    assert len(observer_ids) > 0, "observer 应被授予默认菜单权限"
    all_ids = [i["id"] for i in menu_service._storage.list_menu_items(active_only=True)]
    assert set(observer_ids) == set(all_ids), "observer 默认权限应覆盖全部可见菜单"
    admin_ids = menu_service._storage.get_role_menu_ids("admin")
    assert admin_ids == [], "admin 不写 role_menus（is_admin 短路）"


# =====================================================================
# T-SEED-22: 策略编辑器移至系统管理（Iter7 C7）
# =====================================================================


def test_seed_22_policy_editor_moved_to_system(tree: List[Dict[str, Any]]):
    """T-SEED-22: 策略编辑器(/policy-editor) 从演本体移到系统管理（OPA 权限域）。"""
    sim = _top(tree, "演本体")
    assert "策略编辑器" not in _flatten_names(sim), "演本体不应再有策略编辑器"
    system = _top(tree, "系统管理")
    policy = _require_child(system, "策略编辑器")
    assert policy["path"] == "/policy-editor"
    # code 保持稳定（RBAC 授权不失效）
    assert policy["code"] == "menu:simulate:policy", "移位应保持 code 稳定"


# =====================================================================
# T-SEED-23: iframe-viewer + dashboard 已从种子移除（Iter7 C1/C3）
# =====================================================================


def test_seed_23_removed_pseudo_and_duplicate():
    """T-SEED-23: 种子不含图谱查看器(iframe-viewer)与总览仪表盘(dashboard)。"""
    codes = {item["code"] for item in get_four_steps_seed_data()}
    paths = {item["path"] for item in get_four_steps_seed_data()}
    assert "menu:see:viewer" not in codes, "iframe-viewer 应从种子移除（通用容器伪菜单）"
    assert "menu:see:dashboard" not in codes, "dashboard 应从种子移除（与 quality 重复）"
    assert "/iframe-viewer" not in paths
    assert "/semantic-admin/dashboard" not in paths
    # 质量仪表盘保留为唯一仪表盘
    assert "/semantic-admin/quality" in paths


# =====================================================================
# T-SEED-24: 建本体消歧改名（本体类型设计/蓝图编排/知识库·管理）
# =====================================================================


def test_seed_24_build_renames(tree: List[Dict[str, Any]]):
    """T-SEED-24: 建本体直属项消歧改名到位。"""
    build = _top(tree, "建本体")
    children = _names(build)
    assert "本体类型设计" in children, "原'本体设计器'应改名'本体类型设计'"
    assert "蓝图编排" in children, "原'蓝图设计器'应改名'蓝图编排'"
    assert "知识库·管理" in children, "原'知识库'应改名'知识库·管理'"
    assert "本体设计器" not in children
    assert "蓝图设计器" not in children
    designer = _require_child(build, "本体类型设计")
    assert designer["path"] == "/ontology/designer"
    assert designer["code"] == "menu:build:designer", "改名应保持 code 稳定"


# =====================================================================
# T-SEED-25: 见本体知识库·浏览改名（Iter7 C4）
# =====================================================================


def test_seed_25_see_navigation_renamed(tree: List[Dict[str, Any]]):
    """T-SEED-25: 见本体'知识导航'改名为'知识库·浏览'。"""
    see = _top(tree, "见本体")
    nav = _require_child(see, "知识库·浏览")
    assert nav["path"] == "/knowledge/navigation"
    assert "知识导航" not in _names(see)
