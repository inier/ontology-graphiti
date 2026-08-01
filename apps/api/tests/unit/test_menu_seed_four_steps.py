"""TDD 单元测试：四步法菜单种子数据初始化（Iter 1 + Iter 2）。

设计文档：docs/08-tasks/MENU_REFACTOR_PLAN.md Iter 1 & Iter 2

Sandbox 策略：
  - tmp_path 真实 SQLite DB，不污染生产数据
  - 测试 init_default_menu() 幂等性 + 菜单树结构正确性

测试用例：
  T-SEED-1: 首次调用 init_default_menu() → created=46, skipped=0
  T-SEED-2: 二次调用 init_default_menu() → created=0, skipped=46（幂等）
  T-SEED-3: 菜单树含 6 个顶级目录（建/见/演/用/系统管理/帮助）
  T-SEED-4: 建本体目录含语义管理子目录 + 5 个子菜单
  T-SEED-5: 演本体目录含 business/* 5 个菜单项（D1 偏差修复）
  T-SEED-6: 种子数据 code 唯一（无重复）
  T-SEED-7: get_tree() 返回可嵌套树形结构
  T-SEED-8: 用本体含智能体子目录 + 4 个子菜单
  T-SEED-9: 演本体不含"策略推演"和"模拟器"独立菜单（Iter 2 / D4 修复）
  T-SEED-10: 演本体含"仿真沙盘"统一入口（Iter 2 / D4 修复）
  T-SEED-11: QA 菜单已拆分（/qa→见本体，/qa/query+/qa/evaluation→用本体，Iter 2 / D3 修复）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

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


# =====================================================================
# T-SEED-1: 首次调用 → created=46, skipped=0
# =====================================================================


def test_seed_1_first_init_creates_all(menu_service: MenuConfigService):
    """T-SEED-1: 首次调用写入全部种子数据。"""
    result = menu_service.init_default_menu()
    assert result["status"] == "success"
    assert result["created"] == 46, f"应创建 46 项，实际 {result['created']}"
    assert result["skipped"] == 0
    assert result["total"] == 46


# =====================================================================
# T-SEED-2: 二次调用 → created=0, skipped=46（幂等）
# =====================================================================


def test_seed_2_second_init_is_idempotent(menu_service: MenuConfigService):
    """T-SEED-2: 二次调用跳过已存在项，不重复写入。"""
    menu_service.init_default_menu()  # 第一次
    result = menu_service.init_default_menu()  # 第二次
    assert result["created"] == 0, "二次调用不应创建新项"
    assert result["skipped"] == 46, f"应跳过 46 项，实际 {result['skipped']}"


# =====================================================================
# T-SEED-3: 菜单树含 6 个顶级目录
# =====================================================================


def test_seed_3_six_top_directories(menu_service: MenuConfigService):
    """T-SEED-3: 顶级目录 = 建/见/演/用/系统管理/帮助。"""
    menu_service.init_default_menu()
    tree = menu_service.get_tree(active_only=False)
    top_names = [node["name"] for node in tree]
    expected = ["建本体", "见本体", "演本体", "用本体", "系统管理", "帮助"]
    assert top_names == expected, f"顶级目录={top_names}，预期={expected}"


# =====================================================================
# T-SEED-4: 建本体含语义管理子目录 + 5 个子菜单
# =====================================================================


def test_seed_4_build_has_semantic_subdir(menu_service: MenuConfigService):
    """T-SEED-4: 建本体 → 语义管理子目录 → 5 个子菜单。"""
    menu_service.init_default_menu()
    tree = menu_service.get_tree(active_only=False)
    build_dir = next(n for n in tree if n["name"] == "建本体")
    semantic = next(
        c for c in build_dir["children"] if c["name"] == "语义管理"
    )
    semantic_children = [c["name"] for c in semantic["children"]]
    assert len(semantic_children) == 5, f"语义管理应有 5 子项，实际 {len(semantic_children)}"
    assert "USL 配置" in semantic_children
    assert "候选管理" in semantic_children
    assert "审批工作流" in semantic_children


# =====================================================================
# T-SEED-5: 演本体含 business/* 5 个菜单（D1 偏差修复）
# =====================================================================


def test_seed_5_simulate_has_business_menus(menu_service: MenuConfigService):
    """T-SEED-5: 演本体含业务流程/规则/指标/逻辑/对象管理（D1 修复）。"""
    menu_service.init_default_menu()
    tree = menu_service.get_tree(active_only=False)
    simulate_dir = next(n for n in tree if n["name"] == "演本体")
    child_names = [c["name"] for c in simulate_dir["children"]]
    assert "业务流程" in child_names, "演本体应含业务流程（D1 修复）"
    assert "业务规则" in child_names
    assert "业务指标" in child_names
    assert "业务逻辑" in child_names
    assert "对象管理" in child_names


# =====================================================================
# T-SEED-6: 种子数据 code 唯一
# =====================================================================


def test_seed_6_codes_unique():
    """T-SEED-6: 种子数据中 code 字段无重复。"""
    seed_items = get_four_steps_seed_data()
    codes = [item["code"] for item in seed_items]
    assert len(codes) == len(set(codes)), f"code 有重复: {set([c for c in codes if codes.count(c) > 1])}"


# =====================================================================
# T-SEED-7: get_tree() 返回嵌套树形结构
# =====================================================================


def test_seed_7_tree_is_nested(menu_service: MenuConfigService):
    """T-SEED-7: get_tree() 返回嵌套 children 结构。"""
    menu_service.init_default_menu()
    tree = menu_service.get_tree(active_only=False)
    assert len(tree) == 6, f"顶级应有 6 个目录，实际 {len(tree)}"
    for node in tree:
        assert "children" in node, f"{node['name']} 应有 children 字段"
        assert isinstance(node["children"], list)
    # 验证建本体有 children
    build = next(n for n in tree if n["name"] == "建本体")
    assert len(build["children"]) >= 7, f"建本体应有 ≥7 子项，实际 {len(build['children'])}"


# =====================================================================
# 附加：用本体含智能体子目录
# =====================================================================


def test_seed_8_use_has_agent_subdir(menu_service: MenuConfigService):
    """附加：用本体 → 智能体子目录 → 4 个子菜单。"""
    menu_service.init_default_menu()
    tree = menu_service.get_tree(active_only=False)
    use_dir = next(n for n in tree if n["name"] == "用本体")
    agent = next(c for c in use_dir["children"] if c["name"] == "智能体")
    agent_children = [c["name"] for c in agent["children"]]
    assert len(agent_children) == 4, f"智能体应有 4 子项，实际 {len(agent_children)}"
    assert "我的智能体" in agent_children
    assert "技能管理" in agent_children


# =====================================================================
# T-SEED-9: 演本体不含"策略推演"和"模拟器"独立菜单（Iter 2 / D4）
# =====================================================================


def test_seed_9_simulate_no_deduction_simulator(menu_service: MenuConfigService):
    """T-SEED-9: 演本体不含"策略推演"和"模拟器"独立菜单（D4 合并到仿真沙盘）。"""
    menu_service.init_default_menu()
    tree = menu_service.get_tree(active_only=False)
    simulate_dir = next(n for n in tree if n["name"] == "演本体")
    child_names = [c["name"] for c in simulate_dir["children"]]
    assert "策略推演" not in child_names, "Iter 2 应移除独立的'策略推演'菜单项"
    assert "模拟器" not in child_names, "Iter 2 应移除独立的'模拟器'菜单项"


# =====================================================================
# T-SEED-10: 演本体含"仿真沙盘"统一入口（Iter 2 / D4）
# =====================================================================


def test_seed_10_simulate_has_sandbox_entry(menu_service: MenuConfigService):
    """T-SEED-10: 演本体含"仿真沙盘"统一入口（/simulation）。"""
    menu_service.init_default_menu()
    tree = menu_service.get_tree(active_only=False)
    simulate_dir = next(n for n in tree if n["name"] == "演本体")
    sandbox = next(
        (c for c in simulate_dir["children"] if c["name"] == "仿真沙盘"), None
    )
    assert sandbox is not None, "演本体应含'仿真沙盘'菜单项"
    assert sandbox["path"] == "/simulation", f"仿真沙盘 path 应为 /simulation，实际 {sandbox['path']}"
    # 演本体应含 7 个子项（仿真沙盘 + 5 业务 + 策略编辑器）
    assert len(simulate_dir["children"]) == 7, (
        f"演本体应有 7 子项，实际 {len(simulate_dir['children'])}"
    )


# =====================================================================
# T-SEED-11: QA 菜单已拆分（Iter 2 / D3）
# =====================================================================


def test_seed_11_qa_menu_split(menu_service: MenuConfigService):
    """T-SEED-11: QA 管理→见本体；QA 查询/评估→用本体（D3 拆分）。"""
    menu_service.init_default_menu()
    tree = menu_service.get_tree(active_only=False)

    # 见本体含"QA 管理"(/qa)
    see_dir = next(n for n in tree if n["name"] == "见本体")
    see_names = [c["name"] for c in see_dir["children"]]
    assert "QA 管理" in see_names, "见本体应含'QA 管理'菜单项（D3 拆分）"

    # 用本体含"QA 查询"(/qa/query) 和"QA 评估"(/qa/evaluation)
    use_dir = next(n for n in tree if n["name"] == "用本体")
    use_names = [c["name"] for c in use_dir["children"]]
    assert "QA 查询" in use_names, "用本体应含'QA 查询'菜单项（D3 拆分）"
    assert "QA 评估" in use_names, "用本体应含'QA 评估'菜单项（D3 拆分）"

    # 验证路径
    qa_query = next(c for c in use_dir["children"] if c["name"] == "QA 查询")
    assert qa_query["path"] == "/qa/query"
    qa_eval = next(c for c in use_dir["children"] if c["name"] == "QA 评估")
    assert qa_eval["path"] == "/qa/evaluation"
