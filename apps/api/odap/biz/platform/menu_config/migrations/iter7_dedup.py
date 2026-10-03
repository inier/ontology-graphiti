"""Iter 7 菜单去重/消歧迁移脚本（一次性，幂等）。

对应设计：docs/08-tasks/MENU_DEDUP_PLAN.md（v0.2）+ seed_four_steps.py Iter 7。

作用：把**已有数据库**的菜单结构对齐到新种子状态。因 init_default_menu() 对已存在
code 直接 skip，改名/移位/排序/路径变更对既有 DB 无效，必须用本脚本按 code 就地覆盖。

行为：
  1. 逐条应用新种子（save_menu_item = INSERT OR REPLACE，按 id/code 命中）：
     - 已存在的 code → 就地更新 name/parent_id/sort_order/path/icon（保留 created_at）
     - 新增的 code（4 个分组子目录）→ 插入
  2. 软删已移除项（is_active=False, is_visible=False）：
     - menu:see:viewer（/iframe-viewer 通用 iframe 容器，固定菜单点进去必空；路由保留）
     - menu:see:dashboard（/semantic-admin/dashboard 与质量仪表盘同后端 API；路由 redirect）
  3. code/id 全程稳定 → role_menus 授权不失效；新分组子目录由服务层
     _ensure_parent_directories 在建树时自动补全，无需迁移 role_menus。

用法：
    python -m odap.biz.platform.menu_config.migrations.iter7_dedup
或在部署初始化流程中调用 migrate_iter7_dedup(storage)。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..seeds.seed_four_steps import get_four_steps_seed_data

logger = logging.getLogger(__name__)

# Iter 7 从种子移除、需在既有 DB 软删的菜单 code（路由本身保留）
REMOVED_CODES: List[str] = [
    "menu:see:viewer",      # /iframe-viewer 通用 iframe 容器
    "menu:see:dashboard",   # /semantic-admin/dashboard 与 quality 重复
]


def migrate_iter7_dedup(storage: Any) -> Dict[str, Any]:
    """将既有数据库菜单结构对齐到 Iter 7 新种子（幂等）。

    Args:
        storage: SQLiteMenuConfigStorage 实例（需暴露 get_menu_item_by_code /
                 save_menu_item）。

    Returns:
        {"status": "success", "updated": N, "inserted": M, "soft_deleted": K,
         "total_seed": T}
    """
    seed_items = get_four_steps_seed_data()
    now = datetime.now().isoformat()
    updated = 0
    inserted = 0

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

    soft_deleted = _soft_delete_removed(storage, now)

    logger.info(
        "Iter7 菜单迁移完成: updated=%d inserted=%d soft_deleted=%d total_seed=%d",
        updated, inserted, soft_deleted, len(seed_items),
    )
    return {
        "status": "success",
        "updated": updated,
        "inserted": inserted,
        "soft_deleted": soft_deleted,
        "total_seed": len(seed_items),
    }


def _soft_delete_removed(storage: Any, now: str) -> int:
    """软删已移除的菜单项（保留行以维持历史 role_menus 一致性，仅置不可见/不可用）。"""
    count = 0
    for code in REMOVED_CODES:
        existing = storage.get_menu_item_by_code(code)
        if not existing:
            continue  # 全新 DB 从未有过该行 → 无需处理（幂等）
        existing["is_active"] = False
        existing["is_visible"] = False
        existing["updated_at"] = now
        storage.save_menu_item(existing)
        count += 1
    return count


def _run() -> None:  # pragma: no cover - CLI 入口
    logging.basicConfig(level=logging.INFO)
    from ..storage import Storage

    storage = Storage()
    result = migrate_iter7_dedup(storage)
    print(f"Iter7 菜单迁移结果: {result}")


if __name__ == "__main__":  # pragma: no cover
    _run()
