"""SQLite存储实现 - 替代 MongoDB"""

import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.workspace import Workspace
from ..models.import_export import ImportExportRecord


class SQLiteStorage:
    """SQLite存储实现"""
    
    def __init__(self, db_path: str = "/tmp/workspace.db"):
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
        
        conn.commit()
        conn.close()
    
    def _serialize_json(self, data: Any) -> str:
        """序列化JSON数据"""
        return json.dumps(data, ensure_ascii=False)
    
    def _deserialize_json(self, data: str) -> Any:
        """反序列化JSON数据"""
        if not data:
            return None
        try:
            return json.loads(data)
        except:
            return None
    
    # 工作空间相关
    def save_workspace(self, workspace: Workspace) -> None:
        """保存工作空间"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        data = workspace.model_dump()
        cursor.execute('''
            INSERT OR REPLACE INTO workspaces 
            (id, name, description, type, status, owner, members, config, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data['created_at'].isoformat(),
            data['updated_at'].isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作空间"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM workspaces WHERE id = ?', (workspace_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        # 构建工作空间对象
        from ..models.workspace import WorkspaceStatus, WorkspaceType, WorkspaceConfig
        
        workspace_data = {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'type': WorkspaceType(row[3]),
            'status': WorkspaceStatus(row[4]),
            'owner': row[5],
            'members': self._deserialize_json(row[6]) or [],
            'config': WorkspaceConfig(**(self._deserialize_json(row[7]) or {})),
            'tags': self._deserialize_json(row[8]) or [],
            'created_at': datetime.fromisoformat(row[9]),
            'updated_at': datetime.fromisoformat(row[10])
        }
        
        return Workspace(**workspace_data)
    
    def update_workspace(self, workspace: Workspace) -> None:
        """更新工作空间"""
        self.save_workspace(workspace)
    
    def delete_workspace(self, workspace_id: str) -> None:
        """删除工作空间"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM workspaces WHERE id = ?', (workspace_id,))
        cursor.execute('DELETE FROM isolation_policies WHERE workspace_id = ?', (workspace_id,))
        
        conn.commit()
        conn.close()
    
    def list_workspaces(self, filters: Dict[str, Any] = None, 
                      page: int = 1, page_size: int = 10) -> List[Workspace]:
        """列出工作空间"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 构建查询
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
        
        # 添加排序和分页
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([page_size, (page - 1) * page_size])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        # 构建工作空间列表
        workspaces = []
        from ..models.workspace import WorkspaceStatus, WorkspaceType, WorkspaceConfig
        
        for row in rows:
            workspace_data = {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'type': WorkspaceType(row[3]),
                'status': WorkspaceStatus(row[4]),
                'owner': row[5],
                'members': self._deserialize_json(row[6]) or [],
                'config': WorkspaceConfig(**(self._deserialize_json(row[7]) or {})),
                'tags': self._deserialize_json(row[8]) or [],
                'created_at': datetime.fromisoformat(row[9]),
                'updated_at': datetime.fromisoformat(row[10])
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