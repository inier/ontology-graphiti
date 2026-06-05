import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DEFAULT_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "event_simulator.db")


class SQLiteEventStorage:
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
        c.execute('''CREATE TABLE IF NOT EXISTS event_templates (
            template_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            event_types TEXT DEFAULT '[]',
            entity_types TEXT DEFAULT '[]',
            config TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS event_sequences (
            sequence_id TEXT PRIMARY KEY,
            template_id TEXT NOT NULL,
            workspace_id TEXT DEFAULT 'default',
            events TEXT DEFAULT '[]',
            total_events INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS timelines (
            timeline_id TEXT PRIMARY KEY,
            clock_state TEXT DEFAULT 'stopped',
            start_time TEXT NOT NULL,
            current_time TEXT NOT NULL,
            speed REAL DEFAULT 1.0,
            events TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_sequences_template ON event_sequences(template_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_sequences_workspace ON event_sequences(workspace_id)''')
        conn.commit()
        conn.close()

    def _row_to_template(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for key in ('event_types', 'entity_types', 'config'):
            val = d.get(key)
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[key] = [] if key in ('event_types', 'entity_types') else {}
        return d

    def _row_to_sequence(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        val = d.get('events')
        if isinstance(val, str):
            try:
                d['events'] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d['events'] = []
        return d

    def _row_to_timeline(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        val = d.get('events')
        if isinstance(val, str):
            try:
                d['events'] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d['events'] = []
        return d

    def save_template(self, template: Dict) -> Dict:
        now = datetime.now(timezone.utc).isoformat()
        template_id = template.get('template_id') or f"tpl_{uuid.uuid4().hex[:12]}"
        record = {
            'template_id': template_id,
            'name': template.get('name', ''),
            'description': template.get('description', ''),
            'event_types': json.dumps(template.get('event_types', []), ensure_ascii=False),
            'entity_types': json.dumps(template.get('entity_types', []), ensure_ascii=False),
            'config': json.dumps(template.get('config', {}), ensure_ascii=False),
            'created_at': template.get('created_at') or now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(
                f"INSERT OR REPLACE INTO event_templates ({cols}) VALUES ({placeholders})",
                list(record.values()),
            )
            conn.commit()
            return self.get_template(template_id)
        finally:
            conn.close()

    def get_template(self, template_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM event_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_template(row)
        finally:
            conn.close()

    def list_templates(self) -> List[Dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM event_templates ORDER BY created_at DESC"
            ).fetchall()
            return [self._row_to_template(r) for r in rows]
        finally:
            conn.close()

    def delete_template(self, template_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM event_templates WHERE template_id = ?",
                (template_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def save_sequence(self, sequence: Dict) -> Dict:
        now = datetime.now(timezone.utc).isoformat()
        sequence_id = sequence.get('sequence_id') or f"seq_{uuid.uuid4().hex[:12]}"
        record = {
            'sequence_id': sequence_id,
            'template_id': sequence.get('template_id', ''),
            'workspace_id': sequence.get('workspace_id', 'default'),
            'events': json.dumps(sequence.get('events', []), ensure_ascii=False),
            'total_events': sequence.get('total_events', 0),
            'created_at': sequence.get('created_at') or now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(
                f"INSERT OR REPLACE INTO event_sequences ({cols}) VALUES ({placeholders})",
                list(record.values()),
            )
            conn.commit()
            return self.get_sequence(sequence_id)
        finally:
            conn.close()

    def get_sequence(self, sequence_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM event_sequences WHERE sequence_id = ?",
                (sequence_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_sequence(row)
        finally:
            conn.close()

    def save_timeline(self, timeline: Dict) -> Dict:
        now = datetime.now(timezone.utc).isoformat()
        timeline_id = timeline.get('timeline_id') or f"timeline_{uuid.uuid4().hex[:8]}"
        record = {
            'timeline_id': timeline_id,
            'clock_state': timeline.get('clock_state', 'stopped'),
            'start_time': timeline.get('start_time', now),
            'current_time': timeline.get('current_time', now),
            'speed': timeline.get('speed', 1.0),
            'events': json.dumps(timeline.get('events', []), ensure_ascii=False),
            'created_at': timeline.get('created_at') or now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(
                f"INSERT OR REPLACE INTO timelines ({cols}) VALUES ({placeholders})",
                list(record.values()),
            )
            conn.commit()
            return self.get_timeline(timeline_id)
        finally:
            conn.close()

    def get_timeline(self, timeline_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM timelines WHERE timeline_id = ?",
                (timeline_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_timeline(row)
        finally:
            conn.close()

    def list_timelines(self) -> List[Dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM timelines ORDER BY created_at DESC"
            ).fetchall()
            return [self._row_to_timeline(r) for r in rows]
        finally:
            conn.close()

    def delete_timeline(self, timeline_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM timelines WHERE timeline_id = ?",
                (timeline_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
