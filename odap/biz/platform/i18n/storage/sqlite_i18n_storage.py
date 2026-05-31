import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

from ..models.translation import Translation


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
                updated_at TEXT NOT NULL,
                PRIMARY KEY (key, module, locale)
            )
            """
        )
        conn.commit()
        conn.close()

    def save_translation(self, translation: Translation) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO translations (key, module, locale, value, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    translation.key,
                    translation.module,
                    translation.locale,
                    translation.value,
                    translation.updated_at,
                ),
            )
            conn.commit()
            return {
                "key": translation.key,
                "module": translation.module,
                "locale": translation.locale,
                "value": translation.value,
                "updated_at": translation.updated_at,
            }
        finally:
            conn.close()

    def get_translation(self, key: str, module: str, locale: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT key, module, locale, value, updated_at FROM translations WHERE key=? AND module=? AND locale=?",
                (key, module, locale),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "key": row[0],
                    "module": row[1],
                    "locale": row[2],
                    "value": row[3],
                    "updated_at": row[4],
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
                f"SELECT key, module, locale, value, updated_at FROM translations{where_clause} ORDER BY module, key LIMIT ? OFFSET ?",
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
                        "updated_at": row[4],
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

    def list_modules(self) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT DISTINCT module FROM translations ORDER BY module")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def list_locales(self) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT DISTINCT locale FROM translations ORDER BY locale")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
