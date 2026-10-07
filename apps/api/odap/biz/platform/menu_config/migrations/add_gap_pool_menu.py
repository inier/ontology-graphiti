"""概念缺口回路菜单迁移脚本（一次性，幂等）。

对应设计：.superpowers/sdd/2026-10-07-concept-gap-loop（Task 8）+ seed_four_steps.py。

作用：为**已有数据库**补上概念缺口回路的 2 个菜单项（概念缺口 / 缺口统计，
挂在「建本体 → 语义管理」子目录 dir:build:semantic 下）。因 init_default_menu()
对已存在的种子按 code 幂等 skip、且只对全新 DB 完整生效，改 seed 对既有 DB 无效，
必须用本脚本按 code 就地补插/更新。

行为：
  1. 从 get_four_steps_seed_data()（单一事实源）过滤出 2 个新 code 的记录，
     不重复硬编码列/字段。
  2. 已存在的 code → 就地更新（保留 created_at，仅刷新 updated_at）；
     不存在 → 插入。save_menu_item = INSERT OR REPLACE，按 id/code 命中。
  3. 仅插入 menu_items，**不**自动授予 role_menus（避免未经评审的 RBAC 策略变更，
     规则 14）。新菜单对既有非 admin 角色暂不可见，需在 /menu-config 重新分配；
     admin 走 is_admin 短路可见全部。

用法：
    python -m odap.biz.platform.menu_config.migrations.add_gap_pool_menu
或在部署初始化流程中调用 migrate_add_gap_pool_menu(storage)。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Set

from ..seeds.seed_four_steps import get_four_steps_seed_data

logger = logging.getLogger(__name__)

# 概念缺口回路新增的菜单 code（记录形状以 seed 为准，此处仅做过滤）
GAP_MENU_CODES: Set[str] = {
    "menu:build:semantic:gaps",        # 概念缺口 /semantic-admin/gaps
    "menu:build:semantic:gap-stats",   # 缺口统计 /semantic-admin/gaps/stats
}


def migrate_add_gap_pool_menu(storage: Any) -> Dict[str, Any]:
    """将概念缺口回路的 2 个菜单项补入既有数据库（幂等）。

    Args:
        storage: SQLiteMenuConfigStorage 实例（需暴露 get_menu_item_by_code /
                 save_menu_item）。

    Returns:
        {"status": "success", "inserted": N, "updated": M}
    """
    seed_items = [
        item for item in get_four_steps_seed_data()
        if item["code"] in GAP_MENU_CODES
    ]
    if len(seed_items) != len(GAP_MENU_CODES):
        # seed 与迁移脚本失配属于显式失败场景（规则 14：禁止静默降级）
        raise ValueError(
            f"seed 中缺口菜单项不完整: 期望 {sorted(GAP_MENU_CODES)}，"
            f"实际 {[i['code'] for i in seed_items]}"
        )

    now = datetime.now().isoformat()
    inserted = 0
    updated = 0

    for item in seed_items:
        existing = storage.get_menu_item_by_code(item["code"])
        record = dict(item)
        if existing:
            # 保留原始 created_at，仅刷新 updated_at
            record["created_at"] = existing.get("created_at") or now
            record["updated_at"] = now
            storage.save_menu_item(record)
            updated += 1
        else:
            record["created_at"] = now
            record["updated_at"] = now
            storage.save_menu_item(record)
            inserted += 1

    logger.info(
        "概念缺口菜单迁移完成: inserted=%d updated=%d", inserted, updated,
    )
    return {
        "status": "success",
        "inserted": inserted,
        "updated": updated,
    }


def _run() -> None:  # pragma: no cover - CLI 入口
    logging.basicConfig(level=logging.INFO)
    from ..storage import Storage

    storage = Storage()
    result = migrate_add_gap_pool_menu(storage)
    print(f"概念缺口菜单迁移结果: {result}")


if __name__ == "__main__":  # pragma: no cover
    _run()
