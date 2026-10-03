"""TDD 单元测试：Iter 7 菜单去重迁移脚本（migrations/iter7_dedup.py）。

设计文档：docs/08-tasks/MENU_DEDUP_PLAN.md §4.1（幂等 skip → 需按 code 迁移）

验证要点：
  M-1: 迁移把既有 DB 的旧名/旧父级就地更新到新种子状态（改名 + 移位）
  M-2: 新增分组子目录（如图谱与映射）被插入，且旧子项 parent_id 重指向新子目录
  M-3: 已移除项（iframe-viewer / dashboard）被软删（is_active=False, is_visible=False）
  M-4: code/id 全程稳定 → role_menus 既有授权不丢失
  M-5: created_at 保留，不被迁移覆盖
  M-6: 幂等——重复执行结果一致，不报错
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from odap.biz.platform.menu_config.migrations.iter7_dedup import (
    REMOVED_CODES,
    migrate_iter7_dedup,
)
from odap.biz.platform.menu_config.storage.sqlite_menu_config_storage import (
    SQLiteMenuConfigStorage,
)


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteMenuConfigStorage:
    return SQLiteMenuConfigStorage(db_path=str(tmp_path / "menu_migrate_test.db"))


def _legacy(code: str, name: str, parent: str, path: str,
            menu_type: str = "menu", is_active: bool = True) -> Dict[str, Any]:
    """构造一条 Iter7 之前的旧菜单行（id=code，与生产一致）。"""
    return {
        "id": code,
        "parent_id": parent,
        "name": name,
        "code": code,
        "menu_type": menu_type,
        "link_type": "internal",
        "path": path,
        "url": "",
        "icon": "AppstoreOutlined",
        "sort_order": 0,
        "is_active": is_active,
        "is_visible": is_active,
        "description": "",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }


def _seed_legacy_db(storage: SQLiteMenuConfigStorage) -> None:
    """写入一批代表性的 Iter7 之前的旧行（含被移除项 + 待移位项）。"""
    legacy_rows = [
        # 顶级目录（旧行，迁移应保留）
        _legacy("dir:see", "见本体", None, "", menu_type="directory"),
        _legacy("dir:use", "用本体", None, "", menu_type="directory"),
        _legacy("dir:simulate", "演本体", None, "", menu_type="directory"),
        _legacy("dir:system", "系统管理", None, "", menu_type="directory"),
        # 待改名 + 待收进新子目录
        _legacy("menu:see:graph", "本体图谱", "dir:see", "/ontology/explorer"),
        # 待软删（伪菜单 + 重复仪表盘）
        _legacy("menu:see:viewer", "图谱查看器", "dir:see", "/iframe-viewer"),
        _legacy("menu:see:dashboard", "总览仪表盘", "dir:see", "/semantic-admin/dashboard"),
        # 待移位：策略编辑器 演本体→系统管理；QA管理 见本体→用本体问答检索
        _legacy("menu:simulate:policy", "策略编辑器", "dir:simulate", "/policy-editor"),
        _legacy("menu:see:qa", "QA 管理", "dir:see", "/qa"),
    ]
    for row in legacy_rows:
        storage.save_menu_item(row)
    # 既有 RBAC 授权：observer 拥有 menu:see:graph（迁移后应仍持有）
    storage.set_role_menus("observer", ["menu:see:graph"])


def test_m1_rename_and_reparent_in_place(storage: SQLiteMenuConfigStorage):
    """M-1/M-2: 改名就地生效，新子目录被插入且旧子项重指向它。"""
    _seed_legacy_db(storage)
    result = migrate_iter7_dedup(storage)
    assert result["status"] == "success"

    graph = storage.get_menu_item_by_code("menu:see:graph")
    assert graph["name"] == "本体图谱浏览", "应就地改名为'本体图谱浏览'"
    assert graph["parent_id"] == "dir:see:graph", "应重指向新子目录'图谱与映射'"

    group = storage.get_menu_item_by_code("dir:see:graph")
    assert group is not None, "新分组子目录'图谱与映射'应被插入"
    assert group["menu_type"] == "directory"
    assert group["name"] == "图谱与映射"


def test_m3_removed_items_soft_deleted(storage: SQLiteMenuConfigStorage):
    """M-3: iframe-viewer / dashboard 被软删（不物理删除，保留行）。"""
    _seed_legacy_db(storage)
    result = migrate_iter7_dedup(storage)
    assert result["soft_deleted"] == len(REMOVED_CODES)

    for code in REMOVED_CODES:
        row = storage.get_menu_item_by_code(code)
        assert row is not None, f"{code} 行应保留（软删而非物理删除）"
        assert row["is_active"] is False, f"{code} 应 is_active=False"
        assert row["is_visible"] is False, f"{code} 应 is_visible=False"

    # 软删项不出现在 active_only 列表中
    active_codes = {i["code"] for i in storage.list_menu_items(active_only=True)}
    for code in REMOVED_CODES:
        assert code not in active_codes


def test_m4_rbac_grants_preserved(storage: SQLiteMenuConfigStorage):
    """M-4: code 稳定 → observer 对 menu:see:graph 的既有授权迁移后不丢。"""
    _seed_legacy_db(storage)
    before = set(storage.get_role_menu_ids("observer"))
    assert "menu:see:graph" in before
    migrate_iter7_dedup(storage)
    after = set(storage.get_role_menu_ids("observer"))
    assert "menu:see:graph" in after, "迁移不得破坏既有 role_menus 授权"
    assert before == after, "迁移不应改动 role_menus"


def test_m5_created_at_preserved(storage: SQLiteMenuConfigStorage):
    """M-5: 既有行的 created_at 保留，不被迁移覆盖为当前时间。"""
    _seed_legacy_db(storage)
    migrate_iter7_dedup(storage)
    graph = storage.get_menu_item_by_code("menu:see:graph")
    assert graph["created_at"] == "2026-01-01T00:00:00", "created_at 应保留原值"


def test_m6_idempotent(storage: SQLiteMenuConfigStorage):
    """M-6: 重复执行结果一致，不报错、不产生重复行。"""
    _seed_legacy_db(storage)
    first = migrate_iter7_dedup(storage)
    second = migrate_iter7_dedup(storage)

    assert first["total_seed"] == second["total_seed"]
    # 第二次所有种子 code 均已存在 → updated 覆盖全部种子，inserted=0
    assert second["inserted"] == 0, "二次迁移不应再插入新行"
    assert second["updated"] == first["total_seed"]

    # 结构仍正确
    graph = storage.get_menu_item_by_code("menu:see:graph")
    assert graph["name"] == "本体图谱浏览"
    assert graph["parent_id"] == "dir:see:graph"
    # 无重复 code（UNIQUE 约束保证，但显式校验行数）
    all_items = storage.list_menu_items(active_only=False)
    codes = [i["code"] for i in all_items]
    assert len(codes) == len(set(codes)), "迁移后 code 不应重复"


def test_migrate_moves_policy_and_qa(storage: SQLiteMenuConfigStorage):
    """补充：策略编辑器→系统管理；QA管理→用本体问答检索（移位 + 改名）。"""
    _seed_legacy_db(storage)
    migrate_iter7_dedup(storage)

    policy = storage.get_menu_item_by_code("menu:simulate:policy")
    assert policy["parent_id"] == "dir:system", "策略编辑器应移到系统管理"
    assert policy["name"] == "策略编辑器"

    qa = storage.get_menu_item_by_code("menu:see:qa")
    assert qa["parent_id"] == "dir:use:qa", "QA管理应移到用本体问答检索子目录"
    assert qa["name"] == "智能问答", "QA管理应改名为智能问答"
