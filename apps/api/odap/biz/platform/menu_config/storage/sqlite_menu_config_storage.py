"""菜单配置 SQLite 存储 — 支持三级树 + 角色权限关联"""

import os
import sqlite3
from typing import Any, Dict, List, Optional


class SQLiteMenuConfigStorage:
    """菜单配置持久化（SQLite）"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "menu_config.db",
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._connect()
        try:
            # Step 1: Create tables (no-op if already exists)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS menu_items (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL UNIQUE,
                    menu_type TEXT DEFAULT 'menu',
                    link_type TEXT DEFAULT 'internal',
                    path TEXT,
                    url TEXT,
                    icon TEXT DEFAULT 'AppstoreOutlined',
                    sort_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    is_visible INTEGER DEFAULT 1,
                    description TEXT DEFAULT '',
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS role_menus (
                    role_id TEXT NOT NULL,
                    menu_item_id TEXT NOT NULL,
                    PRIMARY KEY (role_id, menu_item_id)
                );
            """)
            conn.commit()

            # Step 2: Migrate old schema if needed (add missing columns)
            self._migrate_if_needed(conn)

            # Step 3: Create indexes (after migration ensures columns exist)
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_menu_parent ON menu_items(parent_id);
                CREATE INDEX IF NOT EXISTS idx_menu_code ON menu_items(code);
                CREATE INDEX IF NOT EXISTS idx_role_menus_role ON role_menus(role_id);
                CREATE INDEX IF NOT EXISTS idx_role_menus_menu ON role_menus(menu_item_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _migrate_if_needed(self, conn: sqlite3.Connection):
        """检测旧表并迁移（兼容 v1 group 模式 → v2 RBAC 三级树）"""
        cur = conn.execute("PRAGMA table_info(menu_items)")
        cols = {row[1] for row in cur.fetchall()}

        if "code" in cols and "link_type" in cols:
            return  # 已是新 schema

        # 添加缺失列（逐个 try/except 保证幂等）
        for col_sql in [
            "ALTER TABLE menu_items ADD COLUMN parent_id TEXT",
            "ALTER TABLE menu_items ADD COLUMN code TEXT DEFAULT ''",
            "ALTER TABLE menu_items ADD COLUMN link_type TEXT DEFAULT 'internal'",
            "ALTER TABLE menu_items ADD COLUMN is_visible INTEGER DEFAULT 1",
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass  # 列已存在

        # 迁移旧 menu_type（internal/iframe）→ link_type
        if "menu_type" in cols:
            conn.execute(
                "UPDATE menu_items SET link_type = menu_type "
                "WHERE menu_type IN ('internal', 'iframe')"
            )
            # 旧数据全部设为 menu 类型
            conn.execute("UPDATE menu_items SET menu_type = 'menu'")

        # 用 id 填充空 code
        conn.execute("UPDATE menu_items SET code = id WHERE code = '' OR code IS NULL")
        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_dict(self, row) -> Dict[str, Any]:
        if row is None:
            return {}
        return {k: bool(v) if k in ('is_active', 'is_visible') else v
                for k, v in dict(row).items()}

    # ── 菜单项 CRUD ──

    def save_menu_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO menu_items
                   (id, parent_id, name, code, menu_type, link_type, path, url,
                    icon, sort_order, is_active, is_visible, description,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["id"], item.get("parent_id"),
                    item["name"], item["code"],
                    item.get("menu_type", "menu"),
                    item.get("link_type", "internal"),
                    item.get("path"), item.get("url"),
                    item.get("icon", "AppstoreOutlined"),
                    item.get("sort_order", 0),
                    1 if item.get("is_active", True) else 0,
                    1 if item.get("is_visible", True) else 0,
                    item.get("description", ""),
                    item.get("created_at"), item.get("updated_at"),
                ),
            )
            conn.commit()
            return item
        finally:
            conn.close()

    def get_menu_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_menu_item_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM menu_items WHERE code = ?", (code,))
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_menu_items(
        self, active_only: bool = True, menu_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            query = "SELECT * FROM menu_items WHERE 1=1"
            params: list = []
            if active_only:
                query += " AND is_active = 1"
            if menu_type:
                query += " AND menu_type = ?"
                params.append(menu_type)
            query += " ORDER BY sort_order ASC, name ASC"
            return [self._row_to_dict(r) for r in conn.execute(query, params).fetchall()]
        finally:
            conn.close()

    def list_menu_items_by_ids(
        self, item_ids: List[str], active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        if not item_ids:
            return []
        conn = self._connect()
        try:
            ph = ",".join("?" for _ in item_ids)
            query = f"SELECT * FROM menu_items WHERE id IN ({ph})"
            params: list = list(item_ids)
            if active_only:
                query += " AND is_active = 1"
            query += " ORDER BY sort_order ASC, name ASC"
            return [self._row_to_dict(r) for r in conn.execute(query, params).fetchall()]
        finally:
            conn.close()

    def delete_menu_item(self, item_id: str) -> bool:
        conn = self._connect()
        try:
            descendants = self._get_descendant_ids(conn, item_id)
            all_ids = [item_id] + descendants
            for cid in all_ids:
                conn.execute("DELETE FROM role_menus WHERE menu_item_id = ?", (cid,))
            ph = ",".join("?" for _ in all_ids)
            conn.execute(f"DELETE FROM menu_items WHERE id IN ({ph})", all_ids)
            conn.commit()
            return True
        finally:
            conn.close()

    def _get_descendant_ids(self, conn: sqlite3.Connection, parent_id: str) -> List[str]:
        cur = conn.execute("SELECT id FROM menu_items WHERE parent_id = ?", (parent_id,))
        ids = [row[0] for row in cur.fetchall()]
        result = list(ids)
        for cid in ids:
            result.extend(self._get_descendant_ids(conn, cid))
        return result

    # ── 角色-菜单关联 ──

    def set_role_menus(self, role_id: str, menu_item_ids: List[str]) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM role_menus WHERE role_id = ?", (role_id,))
            for mid in menu_item_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO role_menus (role_id, menu_item_id) VALUES (?, ?)",
                    (role_id, mid),
                )
            conn.commit()
        finally:
            conn.close()

    def get_role_menu_ids(self, role_id: str) -> List[str]:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT menu_item_id FROM role_menus WHERE role_id = ?", (role_id,)
            )
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def get_menu_role_ids(self, menu_item_id: str) -> List[str]:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT role_id FROM role_menus WHERE menu_item_id = ?", (menu_item_id,)
            )
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def get_menus_for_roles(
        self, role_ids: List[str], active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        if not role_ids:
            return []
        conn = self._connect()
        try:
            ph = ",".join("?" for _ in role_ids)
            query = f"""
                SELECT DISTINCT m.* FROM menu_items m
                INNER JOIN role_menus rm ON m.id = rm.menu_item_id
                WHERE rm.role_id IN ({ph})
            """
            params: list = list(role_ids)
            if active_only:
                query += " AND m.is_active = 1"
            query += " ORDER BY m.sort_order ASC, m.name ASC"
            return [self._row_to_dict(r) for r in conn.execute(query, params).fetchall()]
        finally:
            conn.close()
