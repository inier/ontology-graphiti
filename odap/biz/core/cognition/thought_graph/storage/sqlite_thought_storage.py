import os
import json
import sqlite3
import uuid
from typing import Dict, Any, List, Optional

from ..models.types import ThoughtType, ReasoningMethod, ThoughtNode, ReasoningChain


class ThoughtGraphStorage:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "ontology_core.db"
        )
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS thought_nodes (
            thought_id TEXT PRIMARY KEY,
            thought_type TEXT NOT NULL,
            content TEXT NOT NULL,
            premises TEXT DEFAULT '[]',
            conclusion TEXT DEFAULT '',
            confidence REAL DEFAULT 0.5,
            reasoning_method TEXT DEFAULT 'heuristic',
            source_entity_ids TEXT DEFAULT '[]',
            source_scenario_id TEXT,
            agent_id TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS reasoning_chains (
            chain_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            thought_ids TEXT DEFAULT '[]',
            chain_type TEXT DEFAULT 'sequential',
            scenario_id TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS thought_edges (
            edge_id TEXT PRIMARY KEY,
            source_thought_id TEXT NOT NULL,
            target_thought_id TEXT NOT NULL,
            edge_type TEXT DEFAULT 'leads_to',
            weight REAL DEFAULT 1.0,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (source_thought_id) REFERENCES thought_nodes(thought_id),
            FOREIGN KEY (target_thought_id) REFERENCES thought_nodes(thought_id)
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_thoughts_type ON thought_nodes(thought_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_thoughts_scenario ON thought_nodes(source_scenario_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_thoughts_agent ON thought_nodes(agent_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chains_scenario ON reasoning_chains(scenario_id)")
        conn.commit()
        conn.close()

    def save_thought(self, thought):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO thought_nodes
            (thought_id, thought_type, content, premises, conclusion, confidence,
             reasoning_method, source_entity_ids, source_scenario_id, agent_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (thought.thought_id, thought.thought_type.value, thought.content,
             json.dumps(thought.premises), thought.conclusion, thought.confidence,
             thought.reasoning_method.value, json.dumps(thought.source_entity_ids),
             thought.source_scenario_id, thought.agent_id,
             json.dumps(thought.metadata), thought.created_at))
        conn.commit()
        conn.close()
        return thought

    def get_thought(self, thought_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM thought_nodes WHERE thought_id = ?", (thought_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return ThoughtNode(
            thought_id=row["thought_id"], thought_type=ThoughtType(row["thought_type"]),
            content=row["content"], premises=json.loads(row["premises"]),
            conclusion=row["conclusion"], confidence=row["confidence"],
            reasoning_method=ReasoningMethod(row["reasoning_method"]),
            source_entity_ids=json.loads(row["source_entity_ids"]),
            source_scenario_id=row["source_scenario_id"], agent_id=row["agent_id"],
            metadata=json.loads(row["metadata"]), created_at=row["created_at"])

    def list_thoughts(self, thought_type=None, scenario_id=None, agent_id=None, limit=100):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        query = "SELECT * FROM thought_nodes WHERE 1=1"
        params = []
        if thought_type:
            query += " AND thought_type = ?"
            params.append(thought_type.value if isinstance(thought_type, ThoughtType) else thought_type)
        if scenario_id:
            query += " AND source_scenario_id = ?"
            params.append(scenario_id)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        results = []
        for row in rows:
            results.append(ThoughtNode(
                thought_id=row["thought_id"], thought_type=ThoughtType(row["thought_type"]),
                content=row["content"], premises=json.loads(row["premises"]),
                conclusion=row["conclusion"], confidence=row["confidence"],
                reasoning_method=ReasoningMethod(row["reasoning_method"]),
                source_entity_ids=json.loads(row["source_entity_ids"]),
                source_scenario_id=row["source_scenario_id"], agent_id=row["agent_id"],
                metadata=json.loads(row["metadata"]), created_at=row["created_at"]))
        return results

    def delete_thought(self, thought_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM thought_edges WHERE source_thought_id = ? OR target_thought_id = ?", (thought_id, thought_id))
        c.execute("DELETE FROM thought_nodes WHERE thought_id = ?", (thought_id,))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def save_chain(self, chain):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO reasoning_chains
            (chain_id, name, description, thought_ids, chain_type, scenario_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (chain.chain_id, chain.name, chain.description,
             json.dumps(chain.thought_ids), chain.chain_type,
             chain.scenario_id, json.dumps(chain.metadata), chain.created_at))
        conn.commit()
        conn.close()
        return chain

    def get_chain(self, chain_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM reasoning_chains WHERE chain_id = ?", (chain_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return ReasoningChain(
            chain_id=row["chain_id"], name=row["name"], description=row["description"],
            thought_ids=json.loads(row["thought_ids"]), chain_type=row["chain_type"],
            scenario_id=row["scenario_id"], metadata=json.loads(row["metadata"]),
            created_at=row["created_at"])

    def list_chains(self, scenario_id=None, limit=100):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        query = "SELECT * FROM reasoning_chains WHERE 1=1"
        params = []
        if scenario_id:
            query += " AND scenario_id = ?"
            params.append(scenario_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        return [ReasoningChain(
            chain_id=r["chain_id"], name=r["name"], description=r["description"],
            thought_ids=json.loads(r["thought_ids"]), chain_type=r["chain_type"],
            scenario_id=r["scenario_id"], metadata=json.loads(r["metadata"]),
            created_at=r["created_at"]) for r in rows]

    def delete_chain(self, chain_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM reasoning_chains WHERE chain_id = ?", (chain_id,))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def add_thought_edge(self, source_id, target_id, edge_type="leads_to", weight=1.0, metadata=None):
        edge_id = f"tedge-{uuid.uuid4().hex[:8]}"
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO thought_edges
            (edge_id, source_thought_id, target_thought_id, edge_type, weight, metadata)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (edge_id, source_id, target_id, edge_type, weight, json.dumps(metadata or {})))
        conn.commit()
        conn.close()
        return {"edge_id": edge_id, "source": source_id, "target": target_id, "edge_type": edge_type, "weight": weight}

    def get_thought_edges(self, thought_id, direction="both"):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        rows = []
        if direction in ("outgoing", "both"):
            c.execute("SELECT * FROM thought_edges WHERE source_thought_id = ?", (thought_id,))
            rows = list(c.fetchall())
        if direction in ("incoming", "both"):
            c.execute("SELECT * FROM thought_edges WHERE target_thought_id = ?", (thought_id,))
            rows = rows + list(c.fetchall())
        conn.close()
        return [dict(r) for r in rows]
