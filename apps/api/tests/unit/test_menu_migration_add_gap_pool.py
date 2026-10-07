"""TDD 单元测试：概念缺口菜单迁移脚本（migrations/add_gap_pool_menu.py）。

对应任务：.superpowers/sdd/2026-10-07-concept-gap-loop Task 8（R7/R8）。

验证要点：
  G-1: 既有 DB（无缺口菜单项、有父目录 dir:build:semantic）迁移后插入 2 项，
       parent_id/path/name/menu_type 与 seed 一致
  G-2: 幂等——二次执行 inserted=0，无重复 code，created_at 保留
  G-3: 迁移不触碰 role_menus（不自动授权，RBAC 变更需人工在 /menu-config 分配）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from odap.biz.platform.menu_config.migrations.add_gap_pool_menu import (
    GAP_MENU_CODES,
    migrate_add_gap_pool_menu,
)
from odap.biz.platform.menu_config.storage.sqlite_menu_config_storage import (
    SQLiteMenuConfigStorage,
)


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteMenuConfigStorage:
    return SQLiteMenuConfigStorage(db_path=str(tmp_path / "menu_gap_migrate_test.db"))


def _legacy(code: str, name: str, parent: str, path: str,
            menu_type: str = "menu", is_active: bool = True) -> Dict[str, Any]:
    """构造一条概念缺口回路之前的旧菜单行（id=code，与生产一致）。"""
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
    """写入缺口回路之前的代表性旧行：含父目录，但不含 2 个新缺口菜单 code。"""
    legacy_rows = [
        _legacy("dir:build", "建本体", None, "", menu_type="directory"),
        _legacy("dir:build:semantic", "语义管理", "dir:build", "",
                menu_type="directory"),
        _legacy("menu:build:semantic:quality", "质量仪表盘", "dir:build:semantic",
                "/semantic-admin/quality"),
    ]
    for row in legacy_rows:
        storage.save_menu_item(row)
    # 既有 RBAC 授权（迁移不得改动）
    storage.set_role_menus("observer", ["menu:build:semantic:quality"])


def test_g1_gap_menus_inserted(storage: SQLiteMenuConfigStorage):
    """G-1: 迁移插入 2 个缺口菜单项，字段与 seed 一致。"""
    _seed_legacy_db(storage)
    result = migrate_add_gap_pool_menu(storage)
    assert result["status"] == "success"
    assert result["inserted"] == 2
    assert result["updated"] == 0

    gaps = storage.get_menu_item_by_code("menu:build:semantic:gaps")
    assert gaps is not None, "概念缺口菜单应被插入"
    assert gaps["parent_id"] == "dir:build:semantic"
    assert gaps["path"] == "/semantic-admin/gaps"
    assert gaps["name"] == "概念缺口"
    assert gaps["menu_type"] == "menu"
    assert gaps["is_active"] is True and gaps["is_visible"] is True

    stats = storage.get_menu_item_by_code("menu:build:semantic:gap-stats")
    assert stats is not None, "缺口统计菜单应被插入"
    assert stats["parent_id"] == "dir:build:semantic"
    assert stats["path"] == "/semantic-admin/gaps/stats"
    assert stats["name"] == "缺口统计"
    assert stats["menu_type"] == "menu"


def test_g2_idempotent(storage: SQLiteMenuConfigStorage):
    """G-2: 二次执行 inserted=0、无重复 code、created_at 保留。"""
    _seed_legacy_db(storage)
    first = migrate_add_gap_pool_menu(storage)
    assert first["inserted"] == 2
    created_at_first = storage.get_menu_item_by_code(
        "menu:build:semantic:gaps")["created_at"]

    second = migrate_add_gap_pool_menu(storage)
    assert second["status"] == "success"
    assert second["inserted"] == 0, "二次迁移不应再插入新行"
    assert second["updated"] == len(GAP_MENU_CODES)

    # 无重复 code（UNIQUE 约束保证，但显式校验行数）
    all_items = storage.list_menu_items(active_only=False)
    codes = [i["code"] for i in all_items]
    assert len(codes) == len(set(codes)), "迁移后 code 不应重复"

    created_at_second = storage.get_menu_item_by_code(
        "menu:build:semantic:gaps")["created_at"]
    assert created_at_second == created_at_first, "created_at 应保留，不被二次迁移覆盖"


def test_g3_role_menus_untouched(storage: SQLiteMenuConfigStorage):
    """G-3: 迁移仅写 menu_items，不自动授予 role_menus。"""
    _seed_legacy_db(storage)
    before = set(storage.get_role_menu_ids("observer"))
    migrate_add_gap_pool_menu(storage)
    after = set(storage.get_role_menu_ids("observer"))
    assert before == after, "迁移不应改动 role_menus（RBAC 授权需人工分配）"
    for code in GAP_MENU_CODES:
        assert code not in after, "新菜单不应被自动授权给既有角色"
