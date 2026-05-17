import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "business.db")


class BusinessStorage:
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
        c.execute('''CREATE TABLE IF NOT EXISTS business_processes (
            process_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT,
            description TEXT,
            related_objects TEXT,
            related_processes TEXT,
            related_rules TEXT,
            related_logics TEXT,
            related_indicators TEXT,
            llm_description TEXT,
            flow_nodes TEXT,
            status TEXT DEFAULT 'draft',
            created_by TEXT DEFAULT 'system',
            created_at TEXT,
            updated_at TEXT,
            yaml_definition TEXT,
            ontology_id TEXT,
            version_id TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS business_rules (
            rule_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT,
            description TEXT,
            related_objects TEXT,
            related_processes TEXT,
            related_rules TEXT,
            related_logics TEXT,
            related_indicators TEXT,
            llm_description TEXT,
            rule_conditions TEXT,
            status TEXT DEFAULT 'draft',
            created_by TEXT DEFAULT 'system',
            created_at TEXT,
            updated_at TEXT,
            yaml_definition TEXT,
            ontology_id TEXT,
            version_id TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS business_logics (
            logic_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT,
            description TEXT,
            related_objects TEXT,
            related_processes TEXT,
            related_rules TEXT,
            related_logics TEXT,
            related_indicators TEXT,
            llm_description TEXT,
            logic_type TEXT DEFAULT 'filter',
            logic_expression TEXT,
            status TEXT DEFAULT 'draft',
            created_by TEXT DEFAULT 'system',
            created_at TEXT,
            updated_at TEXT,
            yaml_definition TEXT,
            ontology_id TEXT,
            version_id TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS business_indicators (
            indicator_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT,
            description TEXT,
            related_objects TEXT,
            related_processes TEXT,
            related_rules TEXT,
            related_logics TEXT,
            related_indicators TEXT,
            llm_description TEXT,
            indicator_type TEXT DEFAULT 'metric',
            calculation_formula TEXT,
            unit TEXT,
            status TEXT DEFAULT 'draft',
            created_by TEXT DEFAULT 'system',
            created_at TEXT,
            updated_at TEXT,
            yaml_definition TEXT,
            ontology_id TEXT,
            version_id TEXT
        )''')
        self._migrate_add_columns(conn)
        conn.commit()
        conn.close()

    def _migrate_add_columns(self, conn):
        existing_tables = {
            'business_processes': [r[1] for r in conn.execute("PRAGMA table_info(business_processes)").fetchall()],
            'business_rules': [r[1] for r in conn.execute("PRAGMA table_info(business_rules)").fetchall()],
            'business_logics': [r[1] for r in conn.execute("PRAGMA table_info(business_logics)").fetchall()],
            'business_indicators': [r[1] for r in conn.execute("PRAGMA table_info(business_indicators)").fetchall()],
        }
        new_cols = ['related_processes', 'related_rules', 'related_logics', 'related_indicators', 'ontology_id', 'version_id']
        for table, cols in existing_tables.items():
            for col in new_cols:
                if col not in cols:
                    default = "'[]'" if col.startswith('related_') else "''"
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT {default}")

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _parse_row(self, row, id_field: str) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        for key in ('related_objects', 'related_processes', 'related_rules', 'related_logics', 'related_indicators', 'flow_nodes', 'rule_conditions'):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key] = []
        return d

    def _version_filter(self, ontology_id: str = None, version_id: str = None) -> str:
        conditions = []
        if ontology_id:
            conditions.append("ontology_id = ?")
        if version_id:
            conditions.append("version_id = ?")
        return " WHERE " + " AND ".join(conditions) if conditions else ""

    def _version_params(self, ontology_id: str = None, version_id: str = None) -> list:
        params = []
        if ontology_id:
            params.append(ontology_id)
        if version_id:
            params.append(version_id)
        return params

    # ===== Business Processes =====
    def list_processes(self, ontology_id: str = None, version_id: str = None) -> List[Dict]:
        conn = self._get_conn()
        where = self._version_filter(ontology_id, version_id)
        params = self._version_params(ontology_id, version_id)
        rows = conn.execute(f"SELECT * FROM business_processes{where} ORDER BY created_at DESC", params).fetchall()
        conn.close()
        return [self._parse_row(r, 'process_id') for r in rows]

    def get_process(self, process_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM business_processes WHERE process_id=?", (process_id,)).fetchone()
        conn.close()
        return self._parse_row(row, 'process_id')

    def create_process(self, data: Dict) -> Dict:
        pid = data.get('process_id') or str(uuid.uuid4())
        now = self._now()
        conn = self._get_conn()
        conn.execute("""INSERT INTO business_processes
            (process_id, name, display_name, description, related_objects, related_processes, related_rules, related_logics, related_indicators, llm_description, flow_nodes, status, created_by, created_at, updated_at, yaml_definition, ontology_id, version_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, data['name'], data.get('display_name',''), data.get('description',''),
             json.dumps(data.get('related_objects',[])),
             json.dumps(data.get('related_processes',[])),
             json.dumps(data.get('related_rules',[])),
             json.dumps(data.get('related_logics',[])),
             json.dumps(data.get('related_indicators',[])),
             data.get('llm_description',''),
             json.dumps(data.get('flow_nodes',[])), data.get('status','draft'),
             data.get('created_by','system'), now, now, data.get('yaml_definition',''),
             data.get('ontology_id',''), data.get('version_id','')))
        conn.commit()
        conn.close()
        return self.get_process(pid)

    def update_process(self, process_id: str, data: Dict) -> Optional[Dict]:
        existing = self.get_process(process_id)
        if not existing:
            return None
        now = self._now()
        conn = self._get_conn()
        conn.execute("""UPDATE business_processes SET
            name=?, display_name=?, description=?, related_objects=?, related_processes=?, related_rules=?, related_logics=?, related_indicators=?, llm_description=?,
            flow_nodes=?, status=?, updated_at=?, yaml_definition=?, ontology_id=?, version_id=?
            WHERE process_id=?""",
            (data.get('name', existing['name']), data.get('display_name', existing.get('display_name','')),
             data.get('description', existing.get('description','')),
             json.dumps(data.get('related_objects', existing.get('related_objects',[]))),
             json.dumps(data.get('related_processes', existing.get('related_processes',[]))),
             json.dumps(data.get('related_rules', existing.get('related_rules',[]))),
             json.dumps(data.get('related_logics', existing.get('related_logics',[]))),
             json.dumps(data.get('related_indicators', existing.get('related_indicators',[]))),
             data.get('llm_description', existing.get('llm_description','')),
             json.dumps(data.get('flow_nodes', existing.get('flow_nodes',[]))),
             data.get('status', existing.get('status','draft')),
             now, data.get('yaml_definition', existing.get('yaml_definition','')),
             data.get('ontology_id', existing.get('ontology_id','')),
             data.get('version_id', existing.get('version_id','')),
             process_id))
        conn.commit()
        conn.close()
        return self.get_process(process_id)

    def delete_process(self, process_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM business_processes WHERE process_id=?", (process_id,))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return affected > 0

    # ===== Business Rules =====
    def list_rules(self, ontology_id: str = None, version_id: str = None) -> List[Dict]:
        conn = self._get_conn()
        where = self._version_filter(ontology_id, version_id)
        params = self._version_params(ontology_id, version_id)
        rows = conn.execute(f"SELECT * FROM business_rules{where} ORDER BY created_at DESC", params).fetchall()
        conn.close()
        return [self._parse_row(r, 'rule_id') for r in rows]

    def get_rule(self, rule_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM business_rules WHERE rule_id=?", (rule_id,)).fetchone()
        conn.close()
        return self._parse_row(row, 'rule_id')

    def create_rule(self, data: Dict) -> Dict:
        rid = data.get('rule_id') or str(uuid.uuid4())
        now = self._now()
        conn = self._get_conn()
        conn.execute("""INSERT INTO business_rules
            (rule_id, name, display_name, description, related_objects, related_processes, related_rules, related_logics, related_indicators, llm_description, rule_conditions, status, created_by, created_at, updated_at, yaml_definition, ontology_id, version_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, data['name'], data.get('display_name',''), data.get('description',''),
             json.dumps(data.get('related_objects',[])),
             json.dumps(data.get('related_processes',[])),
             json.dumps(data.get('related_rules',[])),
             json.dumps(data.get('related_logics',[])),
             json.dumps(data.get('related_indicators',[])),
             data.get('llm_description',''),
             json.dumps(data.get('rule_conditions',[])), data.get('status','draft'),
             data.get('created_by','system'), now, now, data.get('yaml_definition',''),
             data.get('ontology_id',''), data.get('version_id','')))
        conn.commit()
        conn.close()
        return self.get_rule(rid)

    def update_rule(self, rule_id: str, data: Dict) -> Optional[Dict]:
        existing = self.get_rule(rule_id)
        if not existing:
            return None
        now = self._now()
        conn = self._get_conn()
        conn.execute("""UPDATE business_rules SET
            name=?, display_name=?, description=?, related_objects=?, related_processes=?, related_rules=?, related_logics=?, related_indicators=?, llm_description=?,
            rule_conditions=?, status=?, updated_at=?, yaml_definition=?, ontology_id=?, version_id=?
            WHERE rule_id=?""",
            (data.get('name', existing['name']), data.get('display_name', existing.get('display_name','')),
             data.get('description', existing.get('description','')),
             json.dumps(data.get('related_objects', existing.get('related_objects',[]))),
             json.dumps(data.get('related_processes', existing.get('related_processes',[]))),
             json.dumps(data.get('related_rules', existing.get('related_rules',[]))),
             json.dumps(data.get('related_logics', existing.get('related_logics',[]))),
             json.dumps(data.get('related_indicators', existing.get('related_indicators',[]))),
             data.get('llm_description', existing.get('llm_description','')),
             json.dumps(data.get('rule_conditions', existing.get('rule_conditions',[]))),
             data.get('status', existing.get('status','draft')),
             now, data.get('yaml_definition', existing.get('yaml_definition','')),
             data.get('ontology_id', existing.get('ontology_id','')),
             data.get('version_id', existing.get('version_id','')),
             rule_id))
        conn.commit()
        conn.close()
        return self.get_rule(rule_id)

    def delete_rule(self, rule_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM business_rules WHERE rule_id=?", (rule_id,))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return affected > 0

    # ===== Business Logics =====
    def list_logics(self, ontology_id: str = None, version_id: str = None) -> List[Dict]:
        conn = self._get_conn()
        where = self._version_filter(ontology_id, version_id)
        params = self._version_params(ontology_id, version_id)
        rows = conn.execute(f"SELECT * FROM business_logics{where} ORDER BY created_at DESC", params).fetchall()
        conn.close()
        return [self._parse_row(r, 'logic_id') for r in rows]

    def get_logic(self, logic_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM business_logics WHERE logic_id=?", (logic_id,)).fetchone()
        conn.close()
        return self._parse_row(row, 'logic_id')

    def create_logic(self, data: Dict) -> Dict:
        lid = data.get('logic_id') or str(uuid.uuid4())
        now = self._now()
        conn = self._get_conn()
        conn.execute("""INSERT INTO business_logics
            (logic_id, name, display_name, description, related_objects, related_processes, related_rules, related_logics, related_indicators, llm_description, logic_type, logic_expression, status, created_by, created_at, updated_at, yaml_definition, ontology_id, version_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (lid, data['name'], data.get('display_name',''), data.get('description',''),
             json.dumps(data.get('related_objects',[])),
             json.dumps(data.get('related_processes',[])),
             json.dumps(data.get('related_rules',[])),
             json.dumps(data.get('related_logics',[])),
             json.dumps(data.get('related_indicators',[])),
             data.get('llm_description',''),
             data.get('logic_type','filter'), data.get('logic_expression',''),
             data.get('status','draft'), data.get('created_by','system'), now, now,
             data.get('yaml_definition',''),
             data.get('ontology_id',''), data.get('version_id','')))
        conn.commit()
        conn.close()
        return self.get_logic(lid)

    def update_logic(self, logic_id: str, data: Dict) -> Optional[Dict]:
        existing = self.get_logic(logic_id)
        if not existing:
            return None
        now = self._now()
        conn = self._get_conn()
        conn.execute("""UPDATE business_logics SET
            name=?, display_name=?, description=?, related_objects=?, related_processes=?, related_rules=?, related_logics=?, related_indicators=?, llm_description=?,
            logic_type=?, logic_expression=?, status=?, updated_at=?, yaml_definition=?, ontology_id=?, version_id=?
            WHERE logic_id=?""",
            (data.get('name', existing['name']), data.get('display_name', existing.get('display_name','')),
             data.get('description', existing.get('description','')),
             json.dumps(data.get('related_objects', existing.get('related_objects',[]))),
             json.dumps(data.get('related_processes', existing.get('related_processes',[]))),
             json.dumps(data.get('related_rules', existing.get('related_rules',[]))),
             json.dumps(data.get('related_logics', existing.get('related_logics',[]))),
             json.dumps(data.get('related_indicators', existing.get('related_indicators',[]))),
             data.get('llm_description', existing.get('llm_description','')),
             data.get('logic_type', existing.get('logic_type','filter')),
             data.get('logic_expression', existing.get('logic_expression','')),
             data.get('status', existing.get('status','draft')),
             now, data.get('yaml_definition', existing.get('yaml_definition','')),
             data.get('ontology_id', existing.get('ontology_id','')),
             data.get('version_id', existing.get('version_id','')),
             logic_id))
        conn.commit()
        conn.close()
        return self.get_logic(logic_id)

    def delete_logic(self, logic_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM business_logics WHERE logic_id=?", (logic_id,))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return affected > 0

    # ===== Business Indicators =====
    def list_indicators(self, ontology_id: str = None, version_id: str = None) -> List[Dict]:
        conn = self._get_conn()
        where = self._version_filter(ontology_id, version_id)
        params = self._version_params(ontology_id, version_id)
        rows = conn.execute(f"SELECT * FROM business_indicators{where} ORDER BY created_at DESC", params).fetchall()
        conn.close()
        return [self._parse_row(r, 'indicator_id') for r in rows]

    def get_indicator(self, indicator_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM business_indicators WHERE indicator_id=?", (indicator_id,)).fetchone()
        conn.close()
        return self._parse_row(row, 'indicator_id')

    def create_indicator(self, data: Dict) -> Dict:
        iid = data.get('indicator_id') or str(uuid.uuid4())
        now = self._now()
        conn = self._get_conn()
        conn.execute("""INSERT INTO business_indicators
            (indicator_id, name, display_name, description, related_objects, related_processes, related_rules, related_logics, related_indicators, llm_description, indicator_type, calculation_formula, unit, status, created_by, created_at, updated_at, yaml_definition, ontology_id, version_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (iid, data['name'], data.get('display_name',''), data.get('description',''),
             json.dumps(data.get('related_objects',[])),
             json.dumps(data.get('related_processes',[])),
             json.dumps(data.get('related_rules',[])),
             json.dumps(data.get('related_logics',[])),
             json.dumps(data.get('related_indicators',[])),
             data.get('llm_description',''),
             data.get('indicator_type','metric'), data.get('calculation_formula',''),
             data.get('unit',''), data.get('status','draft'),
             data.get('created_by','system'), now, now, data.get('yaml_definition',''),
             data.get('ontology_id',''), data.get('version_id','')))
        conn.commit()
        conn.close()
        return self.get_indicator(iid)

    def update_indicator(self, indicator_id: str, data: Dict) -> Optional[Dict]:
        existing = self.get_indicator(indicator_id)
        if not existing:
            return None
        now = self._now()
        conn = self._get_conn()
        conn.execute("""UPDATE business_indicators SET
            name=?, display_name=?, description=?, related_objects=?, related_processes=?, related_rules=?, related_logics=?, related_indicators=?, llm_description=?,
            indicator_type=?, calculation_formula=?, unit=?, status=?, updated_at=?, yaml_definition=?, ontology_id=?, version_id=?
            WHERE indicator_id=?""",
            (data.get('name', existing['name']), data.get('display_name', existing.get('display_name','')),
             data.get('description', existing.get('description','')),
             json.dumps(data.get('related_objects', existing.get('related_objects',[]))),
             json.dumps(data.get('related_processes', existing.get('related_processes',[]))),
             json.dumps(data.get('related_rules', existing.get('related_rules',[]))),
             json.dumps(data.get('related_logics', existing.get('related_logics',[]))),
             json.dumps(data.get('related_indicators', existing.get('related_indicators',[]))),
             data.get('llm_description', existing.get('llm_description','')),
             data.get('indicator_type', existing.get('indicator_type','metric')),
             data.get('calculation_formula', existing.get('calculation_formula','')),
             data.get('unit', existing.get('unit','')),
             data.get('status', existing.get('status','draft')),
             now, data.get('yaml_definition', existing.get('yaml_definition','')),
             data.get('ontology_id', existing.get('ontology_id','')),
             data.get('version_id', existing.get('version_id','')),
             indicator_id))
        conn.commit()
        conn.close()
        return self.get_indicator(indicator_id)

    def delete_indicator(self, indicator_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM business_indicators WHERE indicator_id=?", (indicator_id,))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return affected > 0
