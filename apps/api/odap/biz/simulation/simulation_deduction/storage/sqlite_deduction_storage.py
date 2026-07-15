import os
import json
import sqlite3
from typing import List, Dict, Any, Optional


class SQLiteDeductionStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "simulation_deduction.db"
        )
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deduction_scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    source_recommendation_id TEXT,
                    source_analysis_id TEXT,
                    target_object_id TEXT DEFAULT '',
                    target_object_type TEXT DEFAULT '',
                    baseline_metrics TEXT DEFAULT '{}',
                    available_conditions TEXT DEFAULT '[]',
                    chains TEXT DEFAULT '[]',
                    results TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'draft',
                    best_chain_id TEXT,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save_scenario(self, scenario: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO deduction_scenarios
                (scenario_id, name, description, source_recommendation_id,
                 source_analysis_id, target_object_id, target_object_type,
                 baseline_metrics, available_conditions, chains, results,
                 status, best_chain_id, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scenario.get("scenario_id", ""),
                scenario.get("name", ""),
                scenario.get("description", ""),
                scenario.get("source_recommendation_id"),
                scenario.get("source_analysis_id"),
                scenario.get("target_object_id", ""),
                scenario.get("target_object_type", ""),
                json.dumps(scenario.get("baseline_metrics", {}), ensure_ascii=False),
                json.dumps(scenario.get("available_conditions", []), ensure_ascii=False),
                json.dumps(scenario.get("chains", []), ensure_ascii=False),
                json.dumps(scenario.get("results", []), ensure_ascii=False),
                scenario.get("status", "draft"),
                scenario.get("best_chain_id"),
                json.dumps(scenario.get("tags", []), ensure_ascii=False),
                scenario.get("created_at", ""),
                scenario.get("updated_at", ""),
            ))
            conn.commit()
        finally:
            conn.close()

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM deduction_scenarios WHERE scenario_id = ?",
                (scenario_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def list_scenarios(self, filters: Dict[str, Any] = None,
                       page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            where_clauses = []
            params = []
            if filters:
                if filters.get("status"):
                    where_clauses.append("status = ?")
                    params.append(filters["status"])
                if filters.get("name"):
                    where_clauses.append("name LIKE ?")
                    params.append(f"%{filters['name']}%")
                if filters.get("target_object_type"):
                    where_clauses.append("target_object_type = ?")
                    params.append(filters["target_object_type"])

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            count_cursor = conn.execute(
                f"SELECT COUNT(*) FROM deduction_scenarios {where_sql}", params
            )
            total = count_cursor.fetchone()[0]

            offset = (page - 1) * page_size
            cursor = conn.execute(
                f"SELECT * FROM deduction_scenarios {where_sql} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()
            scenarios = [self._row_to_dict(row) for row in rows]

            return {
                "scenarios": scenarios,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        finally:
            conn.close()

    def delete_scenario(self, scenario_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM deduction_scenarios WHERE scenario_id = ?",
                (scenario_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_dict(self, row) -> Dict[str, Any]:
        d = dict(row)
        for key in ("baseline_metrics", "available_conditions", "chains",
                     "results", "tags"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key] = {} if key in ("baseline_metrics",) else []
        return d
