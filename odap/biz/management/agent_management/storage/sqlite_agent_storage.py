import sqlite3
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "agents.db")


def _resolve_names(data: Dict[str, Any]) -> Dict[str, Any]:
    """写入时同步解析所有 ID→名称映射，持久化到 resolved_names 字段"""
    resolved: Dict[str, Any] = {
        "workspace_name": "",
        "role_names": {},
        "object_names": {},
        "process_names": {},
        "rule_names": {},
        "logic_names": {},
        "indicator_names": {},
        "skill_names": {},
        "knowledge_base_names": {},
    }

    # workspace
    ws_id = data.get("workspace_id", "")
    if ws_id:
        try:
            from odap.biz.platform.workspace.services import get_workspace_service
            ws = get_workspace_service().get_workspace(ws_id)
            if ws and ws.get("name"):
                resolved["workspace_name"] = ws["name"]
        except Exception as e:
            logger.debug("resolve workspace_name failed for %s: %s", ws_id, e)

    # roles
    for role_id in data.get("allowed_roles", []):
        try:
            from odap.biz.platform.roles.services import get_role_service
            result = get_role_service().list_roles()
            for r in result.get("roles", []):
                if r.get("id") == role_id and r.get("name"):
                    resolved["role_names"][role_id] = r["name"]
                    break
        except Exception as e:
            logger.debug("resolve role_name failed for %s: %s", role_id, e)

    # objects
    for oid in data.get("related_objects", []):
        try:
            from odap.biz.core.ontology.application.oms.services import get_oms_service
            for obj in get_oms_service().list_object_types():
                if obj.get("type_id") == oid or obj.get("name") == oid:
                    resolved["object_names"][oid] = obj.get("display_name") or obj.get("name", "")
                    break
        except Exception as e:
            logger.debug("resolve object_name failed for %s: %s", oid, e)

    # processes
    for pid in data.get("related_processes", []):
        try:
            from odap.biz.management.business.services import get_business_service
            for item in get_business_service().list_processes():
                if item.get("process_id") == pid or item.get("name") == pid:
                    resolved["process_names"][pid] = item.get("display_name") or item.get("name", "")
                    break
        except Exception as e:
            logger.debug("resolve process_name failed for %s: %s", pid, e)

    # rules
    for rid in data.get("related_rules", []):
        try:
            from odap.biz.management.business.services import get_business_service
            for item in get_business_service().list_rules():
                if item.get("rule_id") == rid or item.get("name") == rid:
                    resolved["rule_names"][rid] = item.get("display_name") or item.get("name", "")
                    break
        except Exception as e:
            logger.debug("resolve rule_name failed for %s: %s", rid, e)

    # logic
    for lid in data.get("related_business_logic", []):
        try:
            from odap.biz.management.business.services import get_business_service
            for item in get_business_service().list_logics():
                if item.get("logic_id") == lid or item.get("name") == lid:
                    resolved["logic_names"][lid] = item.get("display_name") or item.get("name", "")
                    break
        except Exception as e:
            logger.debug("resolve logic_name failed for %s: %s", lid, e)

    # indicators
    for iid in data.get("related_indicators", []):
        try:
            from odap.biz.management.business.services import get_business_service
            for item in get_business_service().list_indicators():
                if item.get("indicator_id") == iid or item.get("name") == iid:
                    resolved["indicator_names"][iid] = item.get("display_name") or item.get("name", "")
                    break
        except Exception as e:
            logger.debug("resolve indicator_name failed for %s: %s", iid, e)

    # skills
    for sid in data.get("related_skills", []):
        try:
            from odap.biz.platform.skill_system.services.skill_service import SkillService
            for s in SkillService().list_skills().get("skills", []):
                if s.get("skill_id") == sid or s.get("name") == sid:
                    resolved["skill_names"][sid] = s.get("name", "")
                    break
        except Exception as e:
            logger.debug("resolve skill_name failed for %s: %s", sid, e)

    # knowledge bases
    for kid in data.get("related_knowledge_bases", []):
        try:
            from odap.biz.data.knowledge_base.services import get_kb_service
            for item in get_kb_service().list_knowledge_bases():
                if item.get("kb_id") == kid or item.get("name") == kid:
                    resolved["knowledge_base_names"][kid] = item.get("name", "")
                    break
        except Exception as e:
            logger.debug("resolve kb_name failed for %s: %s", kid, e)

    return resolved


class SQLiteAgentStorage:
    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            description TEXT DEFAULT '',
            main_object TEXT DEFAULT '',
            related_objects TEXT DEFAULT '[]',
            related_processes TEXT DEFAULT '[]',
            related_rules TEXT DEFAULT '[]',
            related_business_logic TEXT DEFAULT '[]',
            related_indicators TEXT DEFAULT '[]',
            related_skills TEXT DEFAULT '[]',
            related_knowledge_bases TEXT DEFAULT '[]',
            allowed_roles TEXT DEFAULT '[]',
            workspace_id TEXT DEFAULT '',
            resolved_names TEXT DEFAULT '{}',
            created_by TEXT DEFAULT 'system',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        conn.commit()
        self._migrate_workspace_id(conn)
        self._migrate_resolved_names(conn)
        conn.close()

    def _migrate_workspace_id(self, conn):
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(agents)").fetchall()]
            if 'workspace_id' not in cols:
                conn.execute("ALTER TABLE agents ADD COLUMN workspace_id TEXT DEFAULT ''")
                conn.commit()
        except Exception as e:
            logger.warning("Migration _migrate_workspace_id failed: %s", e)

    def _migrate_resolved_names(self, conn):
        """迁移：为已有数据补充 resolved_names 字段"""
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(agents)").fetchall()]
            if 'resolved_names' not in cols:
                conn.execute("ALTER TABLE agents ADD COLUMN resolved_names TEXT DEFAULT '{}'")
                conn.commit()
                # 为已有记录补充 resolved_names
                rows = conn.execute("SELECT * FROM agents").fetchall()
                for row in rows:
                    data = self._row_to_dict(row)
                    resolved = _resolve_names(data)
                    conn.execute(
                        "UPDATE agents SET resolved_names = ? WHERE agent_id = ?",
                        (json.dumps(resolved, ensure_ascii=False), data["agent_id"]),
                    )
                conn.commit()
        except Exception as e:
            logger.warning("Migration _migrate_resolved_names failed: %s", e)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for key in [
            'related_objects', 'related_processes', 'related_rules',
            'related_business_logic', 'related_indicators',
            'related_skills', 'related_knowledge_bases', 'allowed_roles',
        ]:
            val = d.get(key, '[]')
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[key] = []
            elif not isinstance(val, list):
                d[key] = []
        # resolved_names
        rn = d.get('resolved_names', '{}')
        if isinstance(rn, str):
            try:
                d['resolved_names'] = json.loads(rn)
            except (json.JSONDecodeError, TypeError):
                d['resolved_names'] = {}
        elif not isinstance(rn, dict):
            d['resolved_names'] = {}
        return d

    def list_agents(self, role_id: Optional[str] = None, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            conditions = []
            params = []
            if workspace_id:
                conditions.append("(workspace_id = ? OR workspace_id = '' OR workspace_id IS NULL)")
                params.append(workspace_id)
            if role_id:
                conditions.append(
                    "(allowed_roles = '[]' OR allowed_roles IS NULL OR allowed_roles = '') "
                    "OR agent_id IN (SELECT agent_id FROM agents, json_each(allowed_roles) WHERE json_each.value = ?)"
                )
                params.append(role_id)
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            rows = conn.execute(f"SELECT * FROM agents {where} ORDER BY created_at DESC", params).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def create_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        resolved = _resolve_names(data)
        record = {
            'agent_id': agent_id,
            'name': data.get('name', ''),
            'display_name': data.get('display_name', ''),
            'avatar': data.get('avatar', ''),
            'description': data.get('description', ''),
            'main_object': data.get('main_object', ''),
            'related_objects': json.dumps(data.get('related_objects', []), ensure_ascii=False),
            'related_processes': json.dumps(data.get('related_processes', []), ensure_ascii=False),
            'related_rules': json.dumps(data.get('related_rules', []), ensure_ascii=False),
            'related_business_logic': json.dumps(data.get('related_business_logic', []), ensure_ascii=False),
            'related_indicators': json.dumps(data.get('related_indicators', []), ensure_ascii=False),
            'related_skills': json.dumps(data.get('related_skills', []), ensure_ascii=False),
            'related_knowledge_bases': json.dumps(data.get('related_knowledge_bases', []), ensure_ascii=False),
            'allowed_roles': json.dumps(data.get('allowed_roles', []), ensure_ascii=False),
            'workspace_id': data.get('workspace_id', ''),
            'resolved_names': json.dumps(resolved, ensure_ascii=False),
            'created_by': data.get('created_by', 'system'),
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO agents ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.commit()
            return self.get_agent(agent_id)
        finally:
            conn.close()

    def update_agent(self, agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_agent(agent_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        json_fields = [
            'related_objects', 'related_processes', 'related_rules',
            'related_business_logic', 'related_indicators',
            'related_skills', 'related_knowledge_bases', 'allowed_roles',
        ]
        sets = []
        values = []
        for key, val in data.items():
            if key in ('agent_id', 'created_at', 'created_by'):
                continue
            if key in json_fields and isinstance(val, list):
                sets.append(f"{key} = ?")
                values.append(json.dumps(val, ensure_ascii=False))
            elif val is not None:
                sets.append(f"{key} = ?")
                values.append(val)
        # 合并已有数据后重新解析名称
        merged = {**existing, **data}
        resolved = _resolve_names(merged)
        sets.append("resolved_names = ?")
        values.append(json.dumps(resolved, ensure_ascii=False))
        sets.append("updated_at = ?")
        values.append(now)
        values.append(agent_id)
        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE agents SET {', '.join(sets)} WHERE agent_id = ?", values)
            conn.commit()
            return self.get_agent(agent_id)
        finally:
            conn.close()

    def save_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        agent_id = data.get('agent_id', f"agent_{uuid.uuid4().hex[:12]}")
        existing = self.get_agent(agent_id)

        json_fields = [
            'related_objects', 'related_processes', 'related_rules',
            'related_business_logic', 'related_indicators',
            'related_skills', 'related_knowledge_bases', 'allowed_roles',
        ]

        if existing:
            record = {}
            for key, val in data.items():
                if key in ('agent_id', 'created_at', 'created_by'):
                    continue
                if key in json_fields and isinstance(val, list):
                    record[key] = json.dumps(val, ensure_ascii=False)
                elif val is not None:
                    record[key] = val
            record['updated_at'] = now

            sets = ', '.join(f"{k} = ?" for k in record.keys())
            values = list(record.values()) + [agent_id]
            conn = self._get_conn()
            try:
                conn.execute(f"UPDATE agents SET {sets} WHERE agent_id = ?", values)
                conn.commit()
            finally:
                conn.close()
        else:
            record = {
                'agent_id': agent_id,
                'name': data.get('name', ''),
                'display_name': data.get('display_name', ''),
                'avatar': data.get('avatar', ''),
                'description': data.get('description', ''),
                'main_object': data.get('main_object', ''),
                'related_objects': json.dumps(data.get('related_objects', []), ensure_ascii=False),
                'related_processes': json.dumps(data.get('related_processes', []), ensure_ascii=False),
                'related_rules': json.dumps(data.get('related_rules', []), ensure_ascii=False),
                'related_business_logic': json.dumps(data.get('related_business_logic', []), ensure_ascii=False),
                'related_indicators': json.dumps(data.get('related_indicators', []), ensure_ascii=False),
                'related_skills': json.dumps(data.get('related_skills', []), ensure_ascii=False),
                'related_knowledge_bases': json.dumps(data.get('related_knowledge_bases', []), ensure_ascii=False),
                'allowed_roles': json.dumps(data.get('allowed_roles', []), ensure_ascii=False),
                'workspace_id': data.get('workspace_id', ''),
                'created_by': data.get('created_by', 'system'),
                'created_at': data.get('created_at', now),
                'updated_at': now,
            }
            conn = self._get_conn()
            try:
                cols = ', '.join(record.keys())
                placeholders = ', '.join(['?'] * len(record))
                conn.execute(f"INSERT OR REPLACE INTO agents ({cols}) VALUES ({placeholders})", list(record.values()))
                conn.commit()
            finally:
                conn.close()

        return self.get_agent(agent_id)

    def delete_agent(self, agent_id: str) -> bool:
        existing = self.get_agent(agent_id)
        if not existing:
            return False
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
            conn.commit()
            return True
        finally:
            conn.close()
