"""SQLite存储实现"""

import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.workspace import Workspace
from ..models.import_export import ImportExportRecord

# 优先使用 DATA_DIR 环境变量，如果没有则使用当前目录下的 data 文件夹
DEFAULT_WORKSPACE_DB_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_WORKSPACE_DB_PATH = os.path.join(DEFAULT_WORKSPACE_DB_DIR, "workspace.db")


class SQLiteStorage:
    """SQLite存储实现"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_WORKSPACE_DB_DIR, exist_ok=True)
            db_path = DEFAULT_WORKSPACE_DB_PATH
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # 创建工作空间表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    members TEXT,
                    config TEXT,
                    tags TEXT,
                    resources TEXT,
                    bound_ontology_ids TEXT,
                    last_accessed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # 创建隔离策略表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS isolation_policies (
                    workspace_id TEXT PRIMARY KEY,
                    isolation_level TEXT,
                    resource_quota TEXT,
                    network_policy TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # 创建导入导出记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS import_export_records (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT,
                    destination TEXT,
                    progress REAL DEFAULT 0,
                    file_size INTEGER,
                    errors TEXT,
                    created_by TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL
                )
            ''')
            
            # 创建场景表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    workspace_id TEXT NOT NULL,
                    ontology_id TEXT,
                    current_ontology_version TEXT,
                    doc_count INTEGER DEFAULT 0,
                    event_count INTEGER DEFAULT 0,
                    entity_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scenario_ontology_bindings (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    ontology_id TEXT NOT NULL,
                    binding_status TEXT NOT NULL DEFAULT 'active',
                    bound_by TEXT NOT NULL DEFAULT 'system',
                    bound_at TEXT NOT NULL,
                    unbound_at TEXT,
                    UNIQUE(scenario_id, ontology_id),
                    FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
                )
            ''')
            
            self._migrate_scenarios(conn)
            self._migrate_workspaces(conn)
            self._migrate_scenario_ontology_bindings(conn)
            conn.commit()
        finally:
            conn.close()
    
    def _migrate_scenarios(self, conn):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(scenarios)").fetchall()]
        if 'current_ontology_version' not in cols:
            conn.execute("ALTER TABLE scenarios ADD COLUMN current_ontology_version TEXT DEFAULT ''")
        if 'status' not in cols:
            conn.execute("ALTER TABLE scenarios ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
        if 'tags' not in cols:
            conn.execute("ALTER TABLE scenarios ADD COLUMN tags TEXT")
        if 'ontology_ids' not in cols:
            conn.execute("ALTER TABLE scenarios ADD COLUMN ontology_ids TEXT")

    def _migrate_scenario_ontology_bindings(self, conn):
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(scenario_ontology_bindings)").fetchall()]
        except sqlite3.OperationalError:
            return

    def _migrate_workspaces(self, conn):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(workspaces)").fetchall()]
        if 'resources' not in cols:
            conn.execute("ALTER TABLE workspaces ADD COLUMN resources TEXT")
        if 'bound_ontology_ids' not in cols:
            conn.execute("ALTER TABLE workspaces ADD COLUMN bound_ontology_ids TEXT")
        if 'last_accessed_at' not in cols:
            conn.execute("ALTER TABLE workspaces ADD COLUMN last_accessed_at TEXT")

    def _serialize_json(self, data: Any) -> str:
        """序列化JSON数据"""
        return json.dumps(data, ensure_ascii=False)
    
    def _deserialize_json(self, data: str) -> Any:
        """反序列化JSON数据"""
        if not data:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    
    # 工作空间相关
    def save_workspace(self, workspace: Workspace) -> None:
        """保存工作空间"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            data = workspace.model_dump()
            cursor.execute('''
                INSERT OR REPLACE INTO workspaces 
                (id, name, description, type, status, owner, members, config, tags,
                 resources, bound_ontology_ids, last_accessed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['id'],
                data['name'],
                data.get('description', ''),
                data['type'].value,
                data['status'].value,
                data['owner'],
                self._serialize_json(data.get('members', [])),
                self._serialize_json(data.get('config', {})),
                self._serialize_json(data.get('tags', [])),
                self._serialize_json(data.get('resources', {})),
                self._serialize_json(data.get('bound_ontology_ids', [])),
                data['last_accessed_at'].isoformat() if data.get('last_accessed_at') else None,
                data['created_at'].isoformat(),
                data['updated_at'].isoformat()
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作空间"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM workspaces WHERE id = ?', (workspace_id,))
            row = cursor.fetchone()
        finally:
            conn.close()
        
        if not row:
            return None
        
        from ..models.workspace import WorkspaceStatus, WorkspaceType, WorkspaceConfig
        
        workspace_data = {
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'type': WorkspaceType(row['type']),
            'status': WorkspaceStatus(row['status']),
            'owner': row['owner'],
            'members': self._deserialize_json(row['members']) or [],
            'config': WorkspaceConfig(**(self._deserialize_json(row['config']) or {})),
            'tags': self._deserialize_json(row['tags']) or [],
            'resources': self._deserialize_json(row['resources']) if row['resources'] else {},
            'bound_ontology_ids': self._deserialize_json(row['bound_ontology_ids']) if row['bound_ontology_ids'] else [],
            'last_accessed_at': datetime.fromisoformat(row['last_accessed_at']) if row['last_accessed_at'] else None,
            'created_at': datetime.fromisoformat(row['created_at']),
            'updated_at': datetime.fromisoformat(row['updated_at'])
        }
        
        return Workspace(**workspace_data)
    
    def update_workspace(self, workspace: Workspace) -> None:
        """更新工作空间"""
        self.save_workspace(workspace)
    
    def delete_workspace(self, workspace_id: str) -> None:
        """删除工作空间（含关联数据完整级联删除）"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # 1. 获取场景ID列表，用于删除场景关联数据
            scenario_ids = []
            try:
                cursor.execute('SELECT scenario_id FROM scenarios WHERE workspace_id = ?', (workspace_id,))
                scenario_ids = [row[0] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                pass

            # 2. 删除场景-本体绑定
            try:
                for sid in scenario_ids:
                    cursor.execute('DELETE FROM scenario_ontology_bindings WHERE scenario_id = ?', (sid,))
            except sqlite3.OperationalError:
                pass

            # 3. 删除场景
            try:
                cursor.execute('DELETE FROM scenarios WHERE workspace_id = ?', (workspace_id,))
            except sqlite3.OperationalError:
                pass

            # 4. 删除隔离策略
            cursor.execute('DELETE FROM isolation_policies WHERE workspace_id = ?', (workspace_id,))

            # 5. 删除导入导出记录
            cursor.execute('DELETE FROM import_export_records WHERE workspace_id = ?', (workspace_id,))

            # 6. 删除工作空间本体绑定关系（bound_ontology_ids 在 workspaces 表中）
            # 7. 删除工作空间本身
            cursor.execute('DELETE FROM workspaces WHERE id = ?', (workspace_id,))

            # 8. 级联删除其他数据库中的 workspace_id 关联数据
            self._cascade_delete_external_tables(cursor, workspace_id, scenario_ids)

            conn.commit()
        finally:
            conn.close()

    def _cascade_delete_external_tables(self, cursor, workspace_id: str, scenario_ids: list) -> None:
        """级联删除其他数据库中与工作空间关联的数据"""
        data_dir = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))

        # 删除 sessions.db 中的会话数据
        sessions_db = os.path.join(data_dir, "sessions.db")
        if os.path.exists(sessions_db):
            try:
                sconn = sqlite3.connect(sessions_db)
                try:
                    scursor = sconn.cursor()
                    scursor.execute('DELETE FROM sessions WHERE workspace_id = ?', (workspace_id,))
                    sconn.commit()
                finally:
                    sconn.close()
            except Exception:
                pass

        # 删除 agents.db 中的智能体配置
        agents_db = os.path.join(data_dir, "agents.db")
        if os.path.exists(agents_db):
            try:
                aconn = sqlite3.connect(agents_db)
                try:
                    acursor = aconn.cursor()
                    acursor.execute('DELETE FROM agents WHERE workspace_id = ?', (workspace_id,))
                    aconn.commit()
                finally:
                    aconn.close()
            except Exception:
                pass

        # 删除 ingest_tasks 中的摄入任务
        ingest_db = os.path.join(data_dir, "ingest.db")
        if os.path.exists(ingest_db):
            try:
                iconn = sqlite3.connect(ingest_db)
                try:
                    icursor = iconn.cursor()
                    icursor.execute('DELETE FROM ingest_tasks WHERE workspace_id = ?', (workspace_id,))
                    iconn.commit()
                finally:
                    iconn.close()
            except Exception:
                pass

        # 删除 simulation 相关数据
        for db_name in ["simulation.db", "sandbox.db", "event_simulator.db"]:
            sim_db = os.path.join(data_dir, db_name)
            if os.path.exists(sim_db):
                try:
                    simconn = sqlite3.connect(sim_db)
                    try:
                        simcursor = simconn.cursor()
                        # 尝试按 workspace_id 删除
                        for table_name in ["sandboxes", "simulations", "event_sequences", "timelines"]:
                            try:
                                simcursor.execute(f'DELETE FROM {table_name} WHERE workspace_id = ?', (workspace_id,))
                            except Exception:
                                pass
                        # 尝试按 scenario_id 删除
                        for sid in scenario_ids:
                            for table_name in ["sandboxes", "simulations", "event_sequences", "timelines"]:
                                try:
                                    simcursor.execute(f'DELETE FROM {table_name} WHERE scenario_id = ?', (sid,))
                                except Exception:
                                    pass
                        simconn.commit()
                    finally:
                        simconn.close()
                except Exception:
                    pass

    def get_workspace_deletion_preview(self, workspace_id: str) -> Dict[str, Any]:
        """获取工作空间删除预览（将级联删除的资源类型及数量）"""
        preview = {
            "workspace_id": workspace_id,
            "resources": [],
            "total_count": 0,
        }

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # 工作空间本身
            cursor.execute('SELECT COUNT(*) FROM workspaces WHERE id = ?', (workspace_id,))
            ws_count = cursor.fetchone()[0]
            if ws_count > 0:
                preview["resources"].append({"type": "workspace", "label": "工作空间", "count": ws_count})
                preview["total_count"] += ws_count

            # 隔离策略
            cursor.execute('SELECT COUNT(*) FROM isolation_policies WHERE workspace_id = ?', (workspace_id,))
            count = cursor.fetchone()[0]
            if count > 0:
                preview["resources"].append({"type": "isolation_policy", "label": "隔离策略", "count": count})
                preview["total_count"] += count

            # 导入导出记录
            cursor.execute('SELECT COUNT(*) FROM import_export_records WHERE workspace_id = ?', (workspace_id,))
            count = cursor.fetchone()[0]
            if count > 0:
                preview["resources"].append({"type": "import_export_record", "label": "导入导出记录", "count": count})
                preview["total_count"] += count

            # 场景
            try:
                cursor.execute('SELECT COUNT(*) FROM scenarios WHERE workspace_id = ?', (workspace_id,))
                count = cursor.fetchone()[0]
                if count > 0:
                    preview["resources"].append({"type": "scenario", "label": "场景", "count": count})
                    preview["total_count"] += count
            except sqlite3.OperationalError:
                pass

            # 场景-本体绑定
            try:
                scenario_ids = [row[0] for row in cursor.execute('SELECT scenario_id FROM scenarios WHERE workspace_id = ?', (workspace_id,)).fetchall()]
                if scenario_ids:
                    placeholders = ','.join(['?'] * len(scenario_ids))
                    cursor.execute(f'SELECT COUNT(*) FROM scenario_ontology_bindings WHERE scenario_id IN ({placeholders})', scenario_ids)
                    count = cursor.fetchone()[0]
                    if count > 0:
                        preview["resources"].append({"type": "scenario_ontology_binding", "label": "场景-本体绑定", "count": count})
                        preview["total_count"] += count
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()

        # 外部数据库统计
        data_dir = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))

        # 会话
        sessions_db = os.path.join(data_dir, "sessions.db")
        if os.path.exists(sessions_db):
            try:
                sconn = sqlite3.connect(sessions_db)
                try:
                    scursor = sconn.cursor()
                    scursor.execute('SELECT COUNT(*) FROM sessions WHERE workspace_id = ?', (workspace_id,))
                    count = scursor.fetchone()[0]
                finally:
                    sconn.close()
                if count > 0:
                    preview["resources"].append({"type": "session", "label": "会话", "count": count})
                    preview["total_count"] += count
            except Exception:
                pass

        # 智能体
        agents_db = os.path.join(data_dir, "agents.db")
        if os.path.exists(agents_db):
            try:
                aconn = sqlite3.connect(agents_db)
                try:
                    acursor = aconn.cursor()
                    acursor.execute('SELECT COUNT(*) FROM agents WHERE workspace_id = ?', (workspace_id,))
                    count = acursor.fetchone()[0]
                finally:
                    aconn.close()
                if count > 0:
                    preview["resources"].append({"type": "agent", "label": "智能体", "count": count})
                    preview["total_count"] += count
            except Exception:
                pass

        # 摄入任务
        ingest_db = os.path.join(data_dir, "ingest.db")
        if os.path.exists(ingest_db):
            try:
                iconn = sqlite3.connect(ingest_db)
                try:
                    icursor = iconn.cursor()
                    icursor.execute('SELECT COUNT(*) FROM ingest_tasks WHERE workspace_id = ?', (workspace_id,))
                    count = icursor.fetchone()[0]
                finally:
                    iconn.close()
                if count > 0:
                    preview["resources"].append({"type": "ingest_task", "label": "摄入任务", "count": count})
                    preview["total_count"] += count
            except Exception:
                pass

        return preview
    
    def list_workspaces(self, filters: Dict[str, Any] = None, 
                      page: int = 1, page_size: int = 10) -> List[Workspace]:
        """列出工作空间"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM workspaces'
            params = []
            
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if key == 'type' or key == 'status':
                        where_clauses.append(f"{key} = ?")
                        params.append(value)
                    elif key == 'owner':
                        where_clauses.append(f"owner = ?")
                        params.append(value)
                
                if where_clauses:
                    query += ' WHERE ' + ' AND '.join(where_clauses)
            
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([page_size, (page - 1) * page_size])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
        finally:
            conn.close()
        
        workspaces = []
        from ..models.workspace import WorkspaceStatus, WorkspaceType, WorkspaceConfig
        
        for row in rows:
            workspace_data = {
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'type': WorkspaceType(row['type']),
                'status': WorkspaceStatus(row['status']),
                'owner': row['owner'],
                'members': self._deserialize_json(row['members']) or [],
                'config': WorkspaceConfig(**(self._deserialize_json(row['config']) or {})),
                'tags': self._deserialize_json(row['tags']) or [],
                'resources': self._deserialize_json(row['resources']) if row['resources'] else {},
                'bound_ontology_ids': self._deserialize_json(row['bound_ontology_ids']) if row['bound_ontology_ids'] else [],
                'last_accessed_at': datetime.fromisoformat(row['last_accessed_at']) if row['last_accessed_at'] else None,
                'created_at': datetime.fromisoformat(row['created_at']),
                'updated_at': datetime.fromisoformat(row['updated_at'])
            }
            workspaces.append(Workspace(**workspace_data))
        
        return workspaces
    
    # 隔离策略相关
    def save_isolation_policy(self, policy: Dict[str, Any]) -> None:
        """保存隔离策略"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            workspace_id = policy.get('workspace_id')
            if not workspace_id:
                return
            
            cursor.execute('''
                INSERT OR REPLACE INTO isolation_policies 
                (workspace_id, isolation_level, resource_quota, network_policy, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                workspace_id,
                policy.get('isolation_level'),
                self._serialize_json(policy.get('resource_quota', {})),
                self._serialize_json(policy.get('network_policy', {})),
                datetime.now().isoformat()
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_isolation_policy(self, workspace_id: str) -> Dict[str, Any]:
        """获取隔离策略"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM isolation_policies WHERE workspace_id = ?', (workspace_id,))
            row = cursor.fetchone()
        finally:
            conn.close()
        
        if not row:
            return {}
        
        return {
            'workspace_id': row[0],
            'isolation_level': row[1],
            'resource_quota': self._deserialize_json(row[2]) or {},
            'network_policy': self._deserialize_json(row[3]) or {},
            'created_at': row[4]
        }
    
    def update_isolation_policy(self, workspace_id: str, policy: Dict[str, Any]) -> None:
        """更新隔离策略"""
        policy['workspace_id'] = workspace_id
        self.save_isolation_policy(policy)
    
    # 导入导出记录相关
    def save_import_export_record(self, record: ImportExportRecord) -> None:
        """保存导入导出记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            data = record.model_dump()
            cursor.execute('''
                INSERT OR REPLACE INTO import_export_records 
                (id, workspace_id, operation, status, source, destination, progress, 
                 file_size, errors, created_by, start_time, end_time, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['id'],
                data.get('workspace_id'),
                data['operation'],
                data['status'].value,
                data.get('source'),
                data.get('destination'),
                data.get('progress', 0),
                data.get('file_size'),
                self._serialize_json(data.get('errors', [])),
                data['created_by'],
                data['start_time'].isoformat(),
                data['end_time'].isoformat() if data.get('end_time') else None,
                data.get('duration_seconds')
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_import_export_record(self, record_id: str) -> Optional[ImportExportRecord]:
        """获取导入导出记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM import_export_records WHERE id = ?', (record_id,))
            row = cursor.fetchone()
        finally:
            conn.close()
        
        if not row:
            return None
        
        # 构建导入导出记录对象
        from ..models.import_export import ImportExportStatus
        
        record_data = {
            'id': row[0],
            'workspace_id': row[1],
            'operation': row[2],
            'status': ImportExportStatus(row[3]),
            'source': row[4],
            'destination': row[5],
            'progress': row[6],
            'file_size': row[7],
            'errors': self._deserialize_json(row[8]) or [],
            'created_by': row[9],
            'start_time': datetime.fromisoformat(row[10]),
            'end_time': datetime.fromisoformat(row[11]) if row[11] else None,
            'duration_seconds': row[12]
        }
        
        return ImportExportRecord(**record_data)
    
    def update_import_export_record(self, record: ImportExportRecord) -> None:
        """更新导入导出记录"""
        self.save_import_export_record(record)
    
    def list_import_export_records(self, filters: Dict[str, Any] = None, 
                                 page: int = 1, page_size: int = 10) -> List[ImportExportRecord]:
        """列出导入导出记录"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # 构建查询
            query = 'SELECT * FROM import_export_records'
            params = []
            
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if key == 'workspace_id':
                        where_clauses.append(f"workspace_id = ?")
                        params.append(value)
                    elif key == 'operation':
                        where_clauses.append(f"operation = ?")
                        params.append(value)
                    elif key == 'status':
                        where_clauses.append(f"status = ?")
                        params.append(value)
                
                if where_clauses:
                    query += ' WHERE ' + ' AND '.join(where_clauses)
            
            # 添加排序和分页
            query += ' ORDER BY start_time DESC LIMIT ? OFFSET ?'
            params.extend([page_size, (page - 1) * page_size])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
        finally:
            conn.close()
        
        # 构建导入导出记录列表
        records = []
        from ..models.import_export import ImportExportStatus
        
        for row in rows:
            record_data = {
                'id': row[0],
                'workspace_id': row[1],
                'operation': row[2],
                'status': ImportExportStatus(row[3]),
                'source': row[4],
                'destination': row[5],
                'progress': row[6],
                'file_size': row[7],
                'errors': self._deserialize_json(row[8]) or [],
                'created_by': row[9],
                'start_time': datetime.fromisoformat(row[10]),
                'end_time': datetime.fromisoformat(row[11]) if row[11] else None,
                'duration_seconds': row[12]
            }
            records.append(ImportExportRecord(**record_data))
        
        return records
    
    # 场景相关
    def save_scenario(self, scenario: Dict[str, Any]) -> None:
        """保存场景"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO scenarios 
                (scenario_id, name, description, workspace_id, status, tags, ontology_id, ontology_ids,
                 current_ontology_version, doc_count, event_count, entity_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                scenario['scenario_id'],
                scenario['name'],
                scenario.get('description', ''),
                scenario['workspace_id'],
                scenario.get('status', 'draft'),
                self._serialize_json(scenario.get('tags', [])),
                scenario.get('ontology_id'),
                self._serialize_json(scenario.get('ontology_ids', [])),
                scenario.get('current_ontology_version', ''),
                scenario.get('doc_count', 0),
                scenario.get('event_count', 0),
                scenario.get('entity_count', 0),
                scenario['created_at'],
                scenario['updated_at']
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取场景"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM scenarios WHERE scenario_id = ?', (scenario_id,))
            row = cursor.fetchone()
        finally:
            conn.close()
        
        if not row:
            return None
        
        d = dict(row)
        d['tags'] = self._deserialize_json(d.get('tags')) or []
        d['ontology_ids'] = self._deserialize_json(d.get('ontology_ids')) or []
        return d
    
    def get_scenarios_by_workspace(self, workspace_id: str, page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """获取工作空间下的所有场景"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM scenarios WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?',
                (workspace_id, page_size, (page - 1) * page_size)
            )
            rows = cursor.fetchall()
        finally:
            conn.close()
        
        results = []
        for row in rows:
            d = dict(row)
            d['tags'] = self._deserialize_json(d.get('tags')) or []
            d['ontology_ids'] = self._deserialize_json(d.get('ontology_ids')) or []
            results.append(d)
        return results
    
    def update_scenario(self, scenario_id: str, updates: Dict[str, Any]) -> None:
        """更新场景"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            set_clause = []
            params = []
            
            json_keys = {'tags', 'ontology_ids'}
            
            for key, value in updates.items():
                if key != 'scenario_id' and key != 'workspace_id' and key != 'created_at':
                    if key in json_keys:
                        value = self._serialize_json(value)
                    set_clause.append(f"{key} = ?")
                    params.append(value)
            
            if set_clause:
                set_clause.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append(scenario_id)
                
                query = f"UPDATE scenarios SET {', '.join(set_clause)} WHERE scenario_id = ?"
                cursor.execute(query, params)
            
            conn.commit()
        finally:
            conn.close()
    
    def delete_scenario(self, scenario_id: str) -> None:
        """删除场景"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM scenario_ontology_bindings WHERE scenario_id = ?', (scenario_id,))
            cursor.execute('DELETE FROM scenarios WHERE scenario_id = ?', (scenario_id,))
            
            conn.commit()
        finally:
            conn.close()
    
    def bind_ontology_to_scenario(self, scenario_id: str, ontology_id: str, bound_by: str = 'system') -> Dict[str, Any]:
        """绑定本体到场景"""
        import uuid as _uuid
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            binding_id = str(_uuid.uuid4())
            now = datetime.now().isoformat()
            
            try:
                cursor.execute('''
                    INSERT INTO scenario_ontology_bindings (id, scenario_id, ontology_id, binding_status, bound_by, bound_at)
                    VALUES (?, ?, ?, 'active', ?, ?)
                ''', (binding_id, scenario_id, ontology_id, bound_by, now))
                
                cursor.execute('''
                    UPDATE scenarios SET ontology_ids = ? WHERE scenario_id = ?
                ''', (self._serialize_json(self._get_ontology_ids_for_scenario(conn, scenario_id)), scenario_id))
                
                conn.commit()
                return {"binding_id": binding_id, "scenario_id": scenario_id, "ontology_id": ontology_id, "binding_status": "active", "bound_by": bound_by, "bound_at": now}
            except sqlite3.IntegrityError:
                cursor.execute('''
                    UPDATE scenario_ontology_bindings SET binding_status = 'active', bound_by = ?, bound_at = ?, unbound_at = NULL
                    WHERE scenario_id = ? AND ontology_id = ?
                ''', (bound_by, now, scenario_id, ontology_id))
                cursor.execute('''
                    UPDATE scenarios SET ontology_ids = ? WHERE scenario_id = ?
                ''', (self._serialize_json(self._get_ontology_ids_for_scenario(conn, scenario_id)), scenario_id))
                cursor2_conn = conn
                conn.commit()
                return {"scenario_id": scenario_id, "ontology_id": ontology_id, "binding_status": "active", "bound_by": bound_by, "bound_at": now}
        finally:
            conn.close()
    
    def unbind_ontology_from_scenario(self, scenario_id: str, ontology_id: str) -> bool:
        """解绑本体"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            cursor.execute('''
                UPDATE scenario_ontology_bindings SET binding_status = 'inactive', unbound_at = ?
                WHERE scenario_id = ? AND ontology_id = ? AND binding_status = 'active'
            ''', (now, scenario_id, ontology_id))
            
            if cursor.rowcount > 0:
                cursor.execute('''
                    UPDATE scenarios SET ontology_ids = ? WHERE scenario_id = ?
                ''', (self._serialize_json(self._get_ontology_ids_for_scenario(conn, scenario_id)), scenario_id))
                conn.commit()
                return True
            
            return False
        finally:
            conn.close()
    
    def _get_ontology_ids_for_scenario(self, conn_or_cursor, scenario_id: str) -> List[str]:
        """获取场景所有活跃绑定的本体ID列表"""
        if hasattr(conn_or_cursor, 'cursor'):
            cursor = conn_or_cursor.cursor()
        else:
            cursor = conn_or_cursor
        cursor.execute('''
            SELECT ontology_id FROM scenario_ontology_bindings
            WHERE scenario_id = ? AND binding_status = 'active'
        ''', (scenario_id,))
        return [row[0] for row in cursor.fetchall()]
    
    def get_scenario_ontology_bindings(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取场景的所有绑定"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM scenario_ontology_bindings WHERE scenario_id = ? ORDER BY bound_at DESC
            ''', (scenario_id,))
            rows = cursor.fetchall()
        finally:
            conn.close()
        return [dict(row) for row in rows]

    def get_scenario_documents(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取场景关联的摄入文档"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # 从 ingest_records 表查询该场景的文档
            cursor.execute('''
                SELECT * FROM ingest_records WHERE scenario_id = ? ORDER BY created_at DESC
            ''', (scenario_id,))
            rows = cursor.fetchall()
        except Exception:
            # 表可能不存在
            return []
        finally:
            conn.close()
        return [dict(row) for row in rows]

    def get_ontology_scenarios(self, ontology_id: str) -> List[Dict[str, Any]]:
        """获取使用该本体的所有场景绑定"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM scenario_ontology_bindings WHERE ontology_id = ? AND binding_status = 'active' ORDER BY bound_at DESC
            ''', (ontology_id,))
            rows = cursor.fetchall()
        finally:
            conn.close()
        return [dict(row) for row in rows]
