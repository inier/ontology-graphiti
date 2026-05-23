"""SQLite存储实现 - 替代 MongoDB"""

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
        
        self._migrate_scenarios(conn)
        self._migrate_workspaces(conn)
        conn.commit()
        conn.close()
    
    def _migrate_scenarios(self, conn):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(scenarios)").fetchall()]
        if 'current_ontology_version' not in cols:
            conn.execute("ALTER TABLE scenarios ADD COLUMN current_ontology_version TEXT DEFAULT ''")

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
        conn.close()
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作空间"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM workspaces WHERE id = ?', (workspace_id,))
        row = cursor.fetchone()
        
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
        """删除工作空间（含关联数据级联删除）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM workspaces WHERE id = ?', (workspace_id,))
        cursor.execute('DELETE FROM isolation_policies WHERE workspace_id = ?', (workspace_id,))
        cursor.execute('DELETE FROM import_export_records WHERE workspace_id = ?', (workspace_id,))

        try:
            cursor.execute('DELETE FROM scenarios WHERE workspace_id = ?', (workspace_id,))
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()
    
    def list_workspaces(self, filters: Dict[str, Any] = None, 
                      page: int = 1, page_size: int = 10) -> List[Workspace]:
        """列出工作空间"""
        conn = sqlite3.connect(self.db_path)
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
        cursor = conn.cursor()
        
        workspace_id = policy.get('workspace_id')
        if not workspace_id:
            conn.close()
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
        conn.close()
    
    def get_isolation_policy(self, workspace_id: str) -> Dict[str, Any]:
        """获取隔离策略"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM isolation_policies WHERE workspace_id = ?', (workspace_id,))
        row = cursor.fetchone()
        
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
        conn.close()
    
    def get_import_export_record(self, record_id: str) -> Optional[ImportExportRecord]:
        """获取导入导出记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM import_export_records WHERE id = ?', (record_id,))
        row = cursor.fetchone()
        
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
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO scenarios 
            (scenario_id, name, description, workspace_id, ontology_id, current_ontology_version,
             doc_count, event_count, entity_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scenario['scenario_id'],
            scenario['name'],
            scenario.get('description', ''),
            scenario['workspace_id'],
            scenario.get('ontology_id'),
            scenario.get('current_ontology_version', ''),
            scenario.get('doc_count', 0),
            scenario.get('event_count', 0),
            scenario.get('entity_count', 0),
            scenario['created_at'],
            scenario['updated_at']
        ))
        
        conn.commit()
        conn.close()
    
    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取场景"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM scenarios WHERE scenario_id = ?', (scenario_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        d = dict(row)
        return d
    
    def get_scenarios_by_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        """获取工作空间下的所有场景"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM scenarios WHERE workspace_id = ? ORDER BY created_at DESC', (workspace_id,))
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_scenario(self, scenario_id: str, updates: Dict[str, Any]) -> None:
        """更新场景"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        set_clause = []
        params = []
        
        for key, value in updates.items():
            if key != 'scenario_id' and key != 'workspace_id' and key != 'created_at':
                set_clause.append(f"{key} = ?")
                params.append(value)
        
        if set_clause:
            set_clause.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(scenario_id)
            
            query = f"UPDATE scenarios SET {', '.join(set_clause)} WHERE scenario_id = ?"
            cursor.execute(query, params)
        
        conn.commit()
        conn.close()
    
    def delete_scenario(self, scenario_id: str) -> None:
        """删除场景"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM scenarios WHERE scenario_id = ?', (scenario_id,))
        
        conn.commit()
        conn.close()