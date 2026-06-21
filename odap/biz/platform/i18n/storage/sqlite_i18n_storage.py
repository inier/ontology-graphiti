import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.translation import Translation, LocaleInfo


class SQLiteI18nStorage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "i18n.db",
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS translations (
                key TEXT NOT NULL,
                module TEXT NOT NULL,
                locale TEXT NOT NULL,
                value TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL DEFAULT 'system',
                PRIMARY KEY (key, module, locale)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS locales (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                native_name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        self._migrate_add_columns(conn)
        conn.commit()
        conn.close()

    def _migrate_add_columns(self, conn: sqlite3.Connection):
        """Add status and updated_by columns to existing translations table."""
        cursor = conn.execute("PRAGMA table_info(translations)")
        columns = {row[1] for row in cursor.fetchall()}
        if "status" not in columns:
            conn.execute(
                "ALTER TABLE translations ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'"
            )
        if "updated_by" not in columns:
            conn.execute(
                "ALTER TABLE translations ADD COLUMN updated_by TEXT NOT NULL DEFAULT 'system'"
            )

    # ── Translation CRUD ──

    def save_translation(
        self, translation: Translation, updated_by: str = "system"
    ) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO translations (key, module, locale, value, status, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    translation.key,
                    translation.module,
                    translation.locale,
                    translation.value,
                    translation.status,
                    translation.updated_at,
                    updated_by,
                ),
            )
            conn.commit()
            return {
                "key": translation.key,
                "module": translation.module,
                "locale": translation.locale,
                "value": translation.value,
                "status": translation.status,
                "updated_at": translation.updated_at,
                "updated_by": updated_by,
            }
        finally:
            conn.close()

    def save_translations_bulk(
        self, items: List[Dict[str, Any]], updated_by: str = "system"
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now().isoformat()
            rows = []
            for item in items:
                rows.append(
                    (
                        item["key"],
                        item["module"],
                        item["locale"],
                        item["value"],
                        item.get("status", "draft"),
                        now,
                        updated_by,
                    )
                )
            conn.executemany(
                """
                INSERT OR REPLACE INTO translations (key, module, locale, value, status, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    def get_translation(self, key: str, module: str, locale: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT key, module, locale, value, status, updated_at, updated_by FROM translations WHERE key=? AND module=? AND locale=?",
                (key, module, locale),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "key": row[0],
                    "module": row[1],
                    "locale": row[2],
                    "value": row[3],
                    "status": row[4],
                    "updated_at": row[5],
                    "updated_by": row[6],
                }
            return None
        finally:
            conn.close()

    def list_translations(
        self,
        module: Optional[str] = None,
        locale: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conditions = []
            params = []

            if module:
                conditions.append("module=?")
                params.append(module)
            if locale:
                conditions.append("locale=?")
                params.append(locale)

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

            count_cursor = conn.execute(f"SELECT COUNT(*) FROM translations{where_clause}", params)
            total = count_cursor.fetchone()[0]

            offset = (page - 1) * page_size
            cursor = conn.execute(
                f"SELECT key, module, locale, value, status, updated_at, updated_by FROM translations{where_clause} ORDER BY module, key LIMIT ? OFFSET ?",
                params + [page_size, offset],
            )

            items = []
            for row in cursor.fetchall():
                items.append(
                    {
                        "key": row[0],
                        "module": row[1],
                        "locale": row[2],
                        "value": row[3],
                        "status": row[4],
                        "updated_at": row[5],
                        "updated_by": row[6],
                    }
                )

            return {
                "translations": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        finally:
            conn.close()

    def delete_translation(self, key: str, module: str, locale: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM translations WHERE key=? AND module=? AND locale=?",
                (key, module, locale),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def review_translation(
        self, key: str, module: str, locale: str, approved: bool, updated_by: str = "system"
    ) -> bool:
        status = "approved" if approved else "draft"
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "UPDATE translations SET status=?, updated_at=?, updated_by=? WHERE key=? AND module=? AND locale=?",
                (status, datetime.now().isoformat(), updated_by, key, module, locale),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_bundle(self, module: str, locale: str) -> Dict[str, str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT key, value FROM translations WHERE module=? AND locale=?",
                (module, locale),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

    def scan_missing(self, module: str, locale: str) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            all_keys_cursor = conn.execute(
                "SELECT DISTINCT key FROM translations WHERE module=?",
                (module,),
            )
            all_keys = [row[0] for row in all_keys_cursor.fetchall()]

            existing_cursor = conn.execute(
                "SELECT DISTINCT key FROM translations WHERE module=? AND locale=?",
                (module, locale),
            )
            existing_keys = {row[0] for row in existing_cursor.fetchall()}

            missing_keys = [k for k in all_keys if k not in existing_keys]
            return {
                "total": len(all_keys),
                "missing": len(missing_keys),
                "missing_keys": missing_keys,
            }
        finally:
            conn.close()

    # ── Module ──

    def list_modules(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT module, COUNT(DISTINCT key) as key_count, COUNT(DISTINCT locale) as locale_count
                FROM translations GROUP BY module ORDER BY module
                """
            )
            return [
                {"name": row[0], "key_count": row[1], "locales": [], "locale_count": row[2]}
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    # ── Locale management ──

    def add_locale(self, code: str, name: str, native_name: str) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO locales (code, name, native_name, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                (code, name, native_name, now),
            )
            conn.commit()
            return {
                "code": code,
                "name": name,
                "native_name": native_name,
                "is_active": True,
                "created_at": now,
            }
        finally:
            conn.close()

    def remove_locale(self, code: str, delete_translations: bool = False) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            if delete_translations:
                conn.execute("DELETE FROM translations WHERE locale=?", (code,))
            conn.execute("UPDATE locales SET is_active=0 WHERE code=?", (code,))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def list_locales(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT code, name, native_name, is_active, created_at FROM locales WHERE is_active=1 ORDER BY code"
            )
            locales = [
                {
                    "code": row[0],
                    "name": row[1],
                    "native_name": row[2],
                    "is_active": bool(row[3]),
                    "created_at": row[4],
                }
                for row in cursor.fetchall()
            ]
            # Also include locales that exist in translations but not in locales table
            existing_codes = {loc["code"] for loc in locales}
            db_locale_cursor = conn.execute(
                "SELECT DISTINCT locale FROM translations ORDER BY locale"
            )
            for row in db_locale_cursor.fetchall():
                if row[0] not in existing_codes:
                    locales.append(
                        {
                            "code": row[0],
                            "name": row[0],
                            "native_name": row[0],
                            "is_active": True,
                            "created_at": "",
                        }
                    )
            return locales
        finally:
            conn.close()
