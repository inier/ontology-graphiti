import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("runtime_storage")


class SQLiteRuntimeStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")), "ontology_core.db")
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS ontology_functions (
                    function_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    display_name TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    function_type TEXT DEFAULT 'transform',
                    status TEXT DEFAULT 'draft',
                    target_object_type TEXT DEFAULT '',
                    input_schema TEXT DEFAULT '{}',
                    output_schema TEXT DEFAULT '{}',
                    implementation TEXT DEFAULT '',
                    implementation_type TEXT DEFAULT 'python',
                    dependencies TEXT DEFAULT '[]',
                    bound_action_contract TEXT,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS action_contracts (
                    contract_id TEXT PRIMARY KEY,
                    action_type_id TEXT NOT NULL,
                    action_name TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    read_set TEXT DEFAULT '[]',
                    write_set TEXT DEFAULT '[]',
                    side_effect_set TEXT DEFAULT '[]',
                    preconditions TEXT DEFAULT '[]',
                    postconditions TEXT DEFAULT '[]',
                    is_verified INTEGER DEFAULT 0,
                    verified_at TEXT,
                    created_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS state_propagation_graphs (
                    graph_id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    edges TEXT DEFAULT '[]',
                    object_types TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS mutation_records (
                    mutation_id TEXT PRIMARY KEY,
                    action_type_id TEXT DEFAULT '',
                    action_name TEXT DEFAULT '',
                    target_object_id TEXT DEFAULT '',
                    target_object_type TEXT DEFAULT '',
                    property_name TEXT DEFAULT '',
                    old_value TEXT,
                    new_value TEXT,
                    mutation_type TEXT DEFAULT 'update',
                    timestamp TEXT DEFAULT '',
                    actor TEXT DEFAULT '',
                    scenario_id TEXT
                );

                CREATE TABLE IF NOT EXISTS world_state_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    object_states TEXT DEFAULT '{}',
                    scenario_id TEXT,
                    is_baseline INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS aggregate_definitions (
                    agg_id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    target_object_type TEXT DEFAULT '',
                    target_property TEXT DEFAULT '',
                    method TEXT DEFAULT 'sum',
                    window TEXT DEFAULT 'raw',
                    group_by TEXT DEFAULT '[]',
                    output_property TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_functions_type ON ontology_functions(function_type);
                CREATE INDEX IF NOT EXISTS idx_functions_target ON ontology_functions(target_object_type);
                CREATE INDEX IF NOT EXISTS idx_contracts_action ON action_contracts(action_type_id);
                CREATE INDEX IF NOT EXISTS idx_mutations_object ON mutation_records(target_object_id);
                CREATE INDEX IF NOT EXISTS idx_mutations_action ON mutation_records(action_type_id);
                CREATE INDEX IF NOT EXISTS idx_mutations_time ON mutation_records(timestamp);
                CREATE INDEX IF NOT EXISTS idx_snapshots_scenario ON world_state_snapshots(scenario_id);
                CREATE INDEX IF NOT EXISTS idx_aggregates_target ON aggregate_definitions(target_object_type);

                CREATE TABLE IF NOT EXISTS action_triggers (
                    trigger_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    conditions TEXT DEFAULT '[]',
                    action_type_id TEXT DEFAULT '',
                    action_name TEXT DEFAULT '',
                    target_object_type TEXT DEFAULT '',
                    target_object_id TEXT,
                    parameters TEXT DEFAULT '{}',
                    is_active INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0,
                    cooldown_seconds INTEGER DEFAULT 0,
                    last_fired_at TEXT,
                    fire_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS trigger_executions (
                    execution_id TEXT PRIMARY KEY,
                    trigger_id TEXT NOT NULL,
                    action_type_id TEXT DEFAULT '',
                    action_name TEXT DEFAULT '',
                    triggered_by TEXT DEFAULT '{}',
                    target_object_id TEXT DEFAULT '',
                    target_object_type TEXT DEFAULT '',
                    parameters TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    error TEXT,
                    started_at TEXT DEFAULT '',
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_triggers_type ON action_triggers(target_object_type);
                CREATE INDEX IF NOT EXISTS idx_triggers_active ON action_triggers(is_active);
                CREATE INDEX IF NOT EXISTS idx_executions_trigger ON trigger_executions(trigger_id);
                CREATE INDEX IF NOT EXISTS idx_executions_status ON trigger_executions(status);
            """)
            conn.commit()
        finally:
            conn.close()

    # ── Function CRUD ──

    def save_function(self, func: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO ontology_functions
                (function_id, name, display_name, description, function_type, status,
                 target_object_type, input_schema, output_schema, implementation,
                 implementation_type, dependencies, bound_action_contract, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                func["function_id"], func.get("name", ""), func.get("display_name", ""),
                func.get("description", ""), func.get("function_type", "transform"),
                func.get("status", "draft"), func.get("target_object_type", ""),
                json.dumps(func.get("input_schema", {}), ensure_ascii=False),
                json.dumps(func.get("output_schema", {}), ensure_ascii=False),
                func.get("implementation", ""), func.get("implementation_type", "python"),
                json.dumps(func.get("dependencies", []), ensure_ascii=False),
                func.get("bound_action_contract"), func.get("created_at", ""),
                func.get("updated_at", ""),
            ))
            conn.commit()
            return func
        finally:
            conn.close()

    def get_function(self, function_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM ontology_functions WHERE function_id = ?", (function_id,)).fetchone()
            if not row:
                return None
            return self._row_to_function(row)
        finally:
            conn.close()

    def list_functions(self, function_type: Optional[str] = None, target_object_type: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM ontology_functions WHERE 1=1"
            params = []
            if function_type:
                sql += " AND function_type = ?"
                params.append(function_type)
            if target_object_type:
                sql += " AND target_object_type = ?"
                params.append(target_object_type)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_function(r) for r in rows]
        finally:
            conn.close()

    def delete_function(self, function_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM ontology_functions WHERE function_id = ?", (function_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_function(self, row) -> Dict[str, Any]:
        return {
            "function_id": row[0], "name": row[1], "display_name": row[2],
            "description": row[3], "function_type": row[4], "status": row[5],
            "target_object_type": row[6],
            "input_schema": json.loads(row[7]) if row[7] else {},
            "output_schema": json.loads(row[8]) if row[8] else {},
            "implementation": row[9], "implementation_type": row[10],
            "dependencies": json.loads(row[11]) if row[11] else [],
            "bound_action_contract": row[12],
            "created_at": row[13], "updated_at": row[14],
        }

    # ── ActionContract CRUD ──

    def save_contract(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO action_contracts
                (contract_id, action_type_id, action_name, description,
                 read_set, write_set, side_effect_set, preconditions, postconditions,
                 is_verified, verified_at, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                contract["contract_id"], contract.get("action_type_id", ""),
                contract.get("action_name", ""), contract.get("description", ""),
                json.dumps(contract.get("read_set", []), ensure_ascii=False),
                json.dumps(contract.get("write_set", []), ensure_ascii=False),
                json.dumps(contract.get("side_effect_set", []), ensure_ascii=False),
                json.dumps(contract.get("preconditions", []), ensure_ascii=False),
                json.dumps(contract.get("postconditions", []), ensure_ascii=False),
                1 if contract.get("is_verified") else 0,
                contract.get("verified_at"), contract.get("created_at", ""),
            ))
            conn.commit()
            return contract
        finally:
            conn.close()

    def get_contract(self, contract_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM action_contracts WHERE contract_id = ?", (contract_id,)).fetchone()
            if not row:
                return None
            return self._row_to_contract(row)
        finally:
            conn.close()

    def get_contract_by_action(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM action_contracts WHERE action_type_id = ?", (action_type_id,)).fetchone()
            if not row:
                return None
            return self._row_to_contract(row)
        finally:
            conn.close()

    def list_contracts(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM action_contracts ORDER BY created_at DESC").fetchall()
            return [self._row_to_contract(r) for r in rows]
        finally:
            conn.close()

    def delete_contract(self, contract_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM action_contracts WHERE contract_id = ?", (contract_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_contract(self, row) -> Dict[str, Any]:
        return {
            "contract_id": row[0], "action_type_id": row[1], "action_name": row[2],
            "description": row[3],
            "read_set": json.loads(row[4]) if row[4] else [],
            "write_set": json.loads(row[5]) if row[5] else [],
            "side_effect_set": json.loads(row[6]) if row[6] else [],
            "preconditions": json.loads(row[7]) if row[7] else [],
            "postconditions": json.loads(row[8]) if row[8] else [],
            "is_verified": bool(row[9]), "verified_at": row[10], "created_at": row[11],
        }

    # ── StatePropagationGraph CRUD ──

    def save_propagation_graph(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO state_propagation_graphs
                (graph_id, name, description, edges, object_types, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?)
            """, (
                graph["graph_id"], graph.get("name", ""), graph.get("description", ""),
                json.dumps(graph.get("edges", []), ensure_ascii=False),
                json.dumps(graph.get("object_types", []), ensure_ascii=False),
                graph.get("created_at", ""), graph.get("updated_at", ""),
            ))
            conn.commit()
            return graph
        finally:
            conn.close()

    def get_propagation_graph(self, graph_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM state_propagation_graphs WHERE graph_id = ?", (graph_id,)).fetchone()
            if not row:
                return None
            return {
                "graph_id": row[0], "name": row[1], "description": row[2],
                "edges": json.loads(row[3]) if row[3] else [],
                "object_types": json.loads(row[4]) if row[4] else [],
                "created_at": row[5], "updated_at": row[6],
            }
        finally:
            conn.close()

    def list_propagation_graphs(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM state_propagation_graphs ORDER BY created_at DESC").fetchall()
            return [{
                "graph_id": r[0], "name": r[1], "description": r[2],
                "edges": json.loads(r[3]) if r[3] else [],
                "object_types": json.loads(r[4]) if r[4] else [],
                "created_at": r[5], "updated_at": r[6],
            } for r in rows]
        finally:
            conn.close()

    def delete_propagation_graph(self, graph_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM state_propagation_graphs WHERE graph_id = ?", (graph_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ── MutationRecord CRUD ──

    def save_mutation(self, mutation: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO mutation_records
                (mutation_id, action_type_id, action_name, target_object_id, target_object_type,
                 property_name, old_value, new_value, mutation_type, timestamp, actor, scenario_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                mutation["mutation_id"], mutation.get("action_type_id", ""),
                mutation.get("action_name", ""), mutation.get("target_object_id", ""),
                mutation.get("target_object_type", ""), mutation.get("property_name", ""),
                json.dumps(mutation.get("old_value"), ensure_ascii=False) if mutation.get("old_value") is not None else None,
                json.dumps(mutation.get("new_value"), ensure_ascii=False) if mutation.get("new_value") is not None else None,
                mutation.get("mutation_type", "update"), mutation.get("timestamp", ""),
                mutation.get("actor", ""), mutation.get("scenario_id"),
            ))
            conn.commit()
            return mutation
        finally:
            conn.close()

    def query_mutations(self, target_object_id: Optional[str] = None, action_type_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM mutation_records WHERE 1=1"
            params = []
            if target_object_id:
                sql += " AND target_object_id = ?"
                params.append(target_object_id)
            if action_type_id:
                sql += " AND action_type_id = ?"
                params.append(action_type_id)
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_mutation(r) for r in rows]
        finally:
            conn.close()

    def _row_to_mutation(self, row) -> Dict[str, Any]:
        return {
            "mutation_id": row[0], "action_type_id": row[1], "action_name": row[2],
            "target_object_id": row[3], "target_object_type": row[4],
            "property_name": row[5],
            "old_value": json.loads(row[6]) if row[6] is not None else None,
            "new_value": json.loads(row[7]) if row[7] is not None else None,
            "mutation_type": row[8], "timestamp": row[9],
            "actor": row[10], "scenario_id": row[11],
        }

    # ── WorldStateSnapshot CRUD ──

    def save_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO world_state_snapshots
                (snapshot_id, name, description, object_states, scenario_id, is_baseline, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (
                snapshot["snapshot_id"], snapshot.get("name", ""), snapshot.get("description", ""),
                json.dumps(snapshot.get("object_states", {}), ensure_ascii=False),
                snapshot.get("scenario_id"), 1 if snapshot.get("is_baseline") else 0,
                snapshot.get("created_at", ""),
            ))
            conn.commit()
            return snapshot
        finally:
            conn.close()

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM world_state_snapshots WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
            if not row:
                return None
            return {
                "snapshot_id": row[0], "name": row[1], "description": row[2],
                "object_states": json.loads(row[3]) if row[3] else {},
                "scenario_id": row[4], "is_baseline": bool(row[5]), "created_at": row[6],
            }
        finally:
            conn.close()

    def list_snapshots(self, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if scenario_id:
                rows = conn.execute("SELECT * FROM world_state_snapshots WHERE scenario_id = ? ORDER BY created_at DESC", (scenario_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM world_state_snapshots ORDER BY created_at DESC").fetchall()
            return [{
                "snapshot_id": r[0], "name": r[1], "description": r[2],
                "object_states": json.loads(r[3]) if r[3] else {},
                "scenario_id": r[4], "is_baseline": bool(r[5]), "created_at": r[6],
            } for r in rows]
        finally:
            conn.close()

    def delete_snapshot(self, snapshot_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM world_state_snapshots WHERE snapshot_id = ?", (snapshot_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ── AggregateDefinition CRUD ──

    def save_aggregate(self, agg: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO aggregate_definitions
                (agg_id, name, target_object_type, target_property, method, window, group_by, output_property, is_active)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                agg["agg_id"], agg.get("name", ""), agg.get("target_object_type", ""),
                agg.get("target_property", ""), agg.get("method", "sum"),
                agg.get("window", "raw"), json.dumps(agg.get("group_by", []), ensure_ascii=False),
                agg.get("output_property", ""), 1 if agg.get("is_active", True) else 0,
            ))
            conn.commit()
            return agg
        finally:
            conn.close()

    def get_aggregate(self, agg_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM aggregate_definitions WHERE agg_id = ?", (agg_id,)).fetchone()
            if not row:
                return None
            return self._row_to_aggregate(row)
        finally:
            conn.close()

    def list_aggregates(self, target_object_type: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if target_object_type:
                rows = conn.execute("SELECT * FROM aggregate_definitions WHERE target_object_type = ?", (target_object_type,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM aggregate_definitions").fetchall()
            return [self._row_to_aggregate(r) for r in rows]
        finally:
            conn.close()

    def delete_aggregate(self, agg_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM aggregate_definitions WHERE agg_id = ?", (agg_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_aggregate(self, row) -> Dict[str, Any]:
        return {
            "agg_id": row[0], "name": row[1], "target_object_type": row[2],
            "target_property": row[3], "method": row[4], "window": row[5],
            "group_by": json.loads(row[6]) if row[6] else [],
            "output_property": row[7], "is_active": bool(row[8]),
        }

    # ── ActionTrigger CRUD ──

    def save_trigger(self, trigger: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO action_triggers
                (trigger_id, name, description, conditions, action_type_id, action_name,
                 target_object_type, target_object_id, parameters, is_active, priority,
                 cooldown_seconds, last_fired_at, fire_count, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                trigger["trigger_id"], trigger.get("name", ""),
                trigger.get("description", ""),
                json.dumps(trigger.get("conditions", []), ensure_ascii=False),
                trigger.get("action_type_id", ""), trigger.get("action_name", ""),
                trigger.get("target_object_type", ""), trigger.get("target_object_id"),
                json.dumps(trigger.get("parameters", {}), ensure_ascii=False),
                1 if trigger.get("is_active", True) else 0,
                trigger.get("priority", 0), trigger.get("cooldown_seconds", 0),
                trigger.get("last_fired_at"), trigger.get("fire_count", 0),
                trigger.get("created_at", ""),
            ))
            conn.commit()
            return trigger
        finally:
            conn.close()

    def get_trigger(self, trigger_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM action_triggers WHERE trigger_id = ?", (trigger_id,)).fetchone()
            if not row:
                return None
            return self._row_to_trigger(row)
        finally:
            conn.close()

    def list_triggers(self, target_object_type: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            sql = "SELECT * FROM action_triggers WHERE 1=1"
            params = []
            if target_object_type:
                sql += " AND target_object_type = ?"
                params.append(target_object_type)
            if is_active is not None:
                sql += " AND is_active = ?"
                params.append(1 if is_active else 0)
            sql += " ORDER BY priority DESC, created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_trigger(r) for r in rows]
        finally:
            conn.close()

    def delete_trigger(self, trigger_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM action_triggers WHERE trigger_id = ?", (trigger_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def _row_to_trigger(self, row) -> Dict[str, Any]:
        return {
            "trigger_id": row[0], "name": row[1], "description": row[2],
            "conditions": json.loads(row[3]) if row[3] else [],
            "action_type_id": row[4], "action_name": row[5],
            "target_object_type": row[6], "target_object_id": row[7],
            "parameters": json.loads(row[8]) if row[8] else {},
            "is_active": bool(row[9]), "priority": row[10],
            "cooldown_seconds": row[11], "last_fired_at": row[12],
            "fire_count": row[13], "created_at": row[14],
        }

    # ── TriggerExecution CRUD ──

    def save_execution(self, execution: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO trigger_executions
                (execution_id, trigger_id, action_type_id, action_name, triggered_by,
                 target_object_id, target_object_type, parameters, status, result,
                 error, started_at, completed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                execution["execution_id"], execution.get("trigger_id", ""),
                execution.get("action_type_id", ""), execution.get("action_name", ""),
                json.dumps(execution.get("triggered_by", {}), ensure_ascii=False),
                execution.get("target_object_id", ""), execution.get("target_object_type", ""),
                json.dumps(execution.get("parameters", {}), ensure_ascii=False),
                execution.get("status", "pending"),
                json.dumps(execution.get("result"), ensure_ascii=False) if execution.get("result") is not None else None,
                execution.get("error"), execution.get("started_at", ""),
                execution.get("completed_at"),
            ))
            conn.commit()
            return execution
        finally:
            conn.close()

    def query_executions(self, trigger_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if trigger_id:
                rows = conn.execute(
                    "SELECT * FROM trigger_executions WHERE trigger_id = ? ORDER BY started_at DESC LIMIT ?",
                    (trigger_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trigger_executions ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_execution(r) for r in rows]
        finally:
            conn.close()

    def _row_to_execution(self, row) -> Dict[str, Any]:
        return {
            "execution_id": row[0], "trigger_id": row[1],
            "action_type_id": row[2], "action_name": row[3],
            "triggered_by": json.loads(row[4]) if row[4] else {},
            "target_object_id": row[5], "target_object_type": row[6],
            "parameters": json.loads(row[7]) if row[7] else {},
            "status": row[8],
            "result": json.loads(row[9]) if row[9] is not None else None,
            "error": row[10], "started_at": row[11], "completed_at": row[12],
        }
