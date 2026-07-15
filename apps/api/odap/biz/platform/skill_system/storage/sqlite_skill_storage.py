import os
import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime


class SQLiteSkillStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "skills.db",
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                skill_type TEXT NOT NULL DEFAULT 'action',
                status TEXT NOT NULL DEFAULT 'draft',
                description TEXT DEFAULT '',
                path TEXT DEFAULT '',
                files TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1,
                version INTEGER DEFAULT 1,
                input_schema TEXT DEFAULT '{}',
                output_schema TEXT DEFAULT '{}',
                triggers TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
            )
            conn.commit()
        finally:
            conn.close()

    def save_skill(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now().isoformat()
            existing = self.get_skill_by_name(skill.get("name", ""))
            if existing:
                conn.execute(
                    """UPDATE skills SET category=?, skill_type=?, status=?, description=?,
                    path=?, files=?, enabled=?, input_schema=?, output_schema=?,
                    triggers=?, updated_at=? WHERE name=?""",
                    (
                        skill.get("category", ""),
                        skill.get("skill_type", "action"),
                        skill.get("status", "active"),
                        skill.get("description", ""),
                        skill.get("path", ""),
                        json.dumps(skill.get("files", []), ensure_ascii=False),
                        1 if skill.get("enabled", True) else 0,
                        json.dumps(skill.get("input_schema", {}), ensure_ascii=False),
                        json.dumps(skill.get("output_schema", {}), ensure_ascii=False),
                        json.dumps(skill.get("triggers", []), ensure_ascii=False),
                        now,
                        skill["name"],
                    ),
                )
            else:
                skill_id = skill.get("skill_id", f"skill-{os.urandom(4).hex()}")
                conn.execute(
                    """INSERT OR REPLACE INTO skills
                    (skill_id, name, category, skill_type, status, description, path,
                    files, enabled, version, input_schema, output_schema, triggers,
                    created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        skill_id,
                        skill["name"],
                        skill.get("category", ""),
                        skill.get("skill_type", "action"),
                        skill.get("status", "active"),
                        skill.get("description", ""),
                        skill.get("path", ""),
                        json.dumps(skill.get("files", []), ensure_ascii=False),
                        1 if skill.get("enabled", True) else 0,
                        skill.get("version", 1),
                        json.dumps(skill.get("input_schema", {}), ensure_ascii=False),
                        json.dumps(skill.get("output_schema", {}), ensure_ascii=False),
                        json.dumps(skill.get("triggers", []), ensure_ascii=False),
                        skill.get("created_at", now),
                        now,
                    ),
                )
            conn.commit()
            return skill
        finally:
            conn.close()

    def get_skill_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM skills WHERE name = ?", (name,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))
            result["files"] = json.loads(result.get("files", "[]"))
            result["input_schema"] = json.loads(result.get("input_schema", "{}"))
            result["output_schema"] = json.loads(result.get("output_schema", "{}"))
            result["triggers"] = json.loads(result.get("triggers", "[]"))
            result["enabled"] = bool(result.get("enabled", 1))
            return result
        finally:
            conn.close()

    def list_skills(self, category: str = None, status: str = None) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            query = "SELECT * FROM skills WHERE 1=1"
            params = []
            if category:
                query += " AND category = ?"
                params.append(category)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY updated_at DESC"
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                r = dict(zip(columns, row))
                r["files"] = json.loads(r.get("files", "[]"))
                r["input_schema"] = json.loads(r.get("input_schema", "{}"))
                r["output_schema"] = json.loads(r.get("output_schema", "{}"))
                r["triggers"] = json.loads(r.get("triggers", "[]"))
                r["enabled"] = bool(r.get("enabled", 1))
                results.append(r)
            return results
        finally:
            conn.close()

    def delete_skill(self, name: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM skills WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def toggle_skill(self, name: str, enabled: bool) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "UPDATE skills SET enabled = ?, updated_at = ? WHERE name = ?",
                (1 if enabled else 0, now, name),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
