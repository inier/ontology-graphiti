"""SQLite存储实现 - 数据摄入审计"""

import sqlite3
import json
import os
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..ingestion import OntologyDocument


DEFAULT_INGEST_DB_DIR = os.path.join(tempfile.gettempdir(), "odap")
DEFAULT_INGEST_DB_PATH = os.path.join(DEFAULT_INGEST_DB_DIR, "ingest.db")


class SQLiteIngestStorage:
    """数据摄入的SQLite存储实现 - 用于轻量级结构化数据
    
    存储内容:
    - ingest_records: 数据摄入记录
    - process_logs: 处理阶段日志
    - build_history: 构建历史记录
    - audit_logs: 审计日志
    """
    
    SQLITE_TIMEOUT = 30

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_INGEST_DB_DIR, exist_ok=True)
            db_path = DEFAULT_INGEST_DB_PATH
        self.db_path = db_path
        self._init_db()
        self._enable_wal()
    
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=self.SQLITE_TIMEOUT)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _enable_wal(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.close()
        except Exception:
            pass
    
    def _init_db(self):
        """初始化数据库"""
        import os
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 创建数据摄入记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingest_records (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_details TEXT,
                data_schema TEXT,
                record_count INTEGER DEFAULT 0,
                processed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                errors TEXT,
                quality_metrics TEXT,
                extracted_data TEXT,
                original_content TEXT,
                created_by TEXT DEFAULT 'system'
            )
        ''')
        
        # 创建审计日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                ingest_id TEXT,
                timestamp TEXT NOT NULL,
                level TEXT DEFAULT 'info',
                message TEXT NOT NULL,
                details TEXT,
                actor TEXT DEFAULT 'system'
            )
        ''')
        
        # 创建本体文档表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ontology_documents (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                source TEXT,
                meta TEXT,
                entities TEXT,
                relations TEXT,
                events TEXT,
                actions TEXT,
                rules TEXT,
                constraints TEXT,
                ontology_version TEXT,
                scenario_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 创建构建结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS build_results (
                id TEXT PRIMARY KEY,
                source_ingest_id TEXT,
                entity_count INTEGER DEFAULT 0,
                relation_count INTEGER DEFAULT 0,
                property_count INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                errors TEXT,
                warnings TEXT,
                ontology_version TEXT DEFAULT '1.0.0'
            )
        ''')
        
        # 创建版本表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ontology_versions (
                id TEXT PRIMARY KEY,
                ontology_id TEXT,
                version_number TEXT NOT NULL,
                parent_version_id TEXT,
                status TEXT DEFAULT 'draft',
                changes TEXT,
                change_summary TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT DEFAULT 'system',
                is_current INTEGER DEFAULT 0,
                is_stable INTEGER DEFAULT 0
            )
        ''')
        
        # 创建验证结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS validation_results (
                id TEXT PRIMARY KEY,
                ontology_id TEXT,
                ontology_version TEXT,
                validation_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                errors TEXT,
                warnings TEXT,
                info TEXT,
                error_count INTEGER DEFAULT 0,
                warning_count INTEGER DEFAULT 0,
                info_count INTEGER DEFAULT 0,
                overall_score REAL DEFAULT 1.0,
                duration_seconds REAL DEFAULT 0.0
            )
        ''')
        
        # 创建处理日志表（用于保存管道每阶段的处理记录）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS process_logs (
                id TEXT PRIMARY KEY,
                ingest_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                operation TEXT NOT NULL,
                details TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                duration_ms REAL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (ingest_id) REFERENCES ingest_records(id)
            )
        ''')
        
        # 创建构建历史表（关联摄入记录和构建结果）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS build_history (
                id TEXT PRIMARY KEY,
                ingest_id TEXT NOT NULL,
                build_id TEXT NOT NULL,
                version_id TEXT,
                document_id TEXT,
                entity_count INTEGER DEFAULT 0,
                relation_count INTEGER DEFAULT 0,
                event_count INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                FOREIGN KEY (ingest_id) REFERENCES ingest_records(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _serialize_json(self, data: Any) -> str:
        """序列化JSON数据"""
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def _deserialize_json(self, data: str) -> Any:
        """反序列化JSON数据"""
        if not data:
            return None
        try:
            return json.loads(data)
        except:
            return None
    
    # 数据摄入记录相关
    def save_ingest_record(self, record: Dict[str, Any]) -> str:
        """保存摄入记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO ingest_records 
            (id, source, source_details, data_schema, record_count, processed_count, 
             failed_count, status, start_time, end_time, duration_seconds, 
             errors, quality_metrics, extracted_data, original_content, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.get('id'),
            record.get('source'),
            self._serialize_json(record.get('source_details')),
            self._serialize_json(record.get('data_schema')),
            record.get('record_count', 0),
            record.get('processed_count', 0),
            record.get('failed_count', 0),
            record.get('status'),
            record.get('start_time'),
            record.get('end_time'),
            record.get('duration_seconds'),
            self._serialize_json(record.get('errors')),
            self._serialize_json(record.get('quality_metrics')),
            self._serialize_json(record.get('extracted_data')),
            record.get('original_content'),
            record.get('created_by', 'system')
        ))
        
        conn.commit()
        conn.close()
        return record.get('id')
    
    def get_ingest_record(self, ingest_id: str) -> Optional[Dict[str, Any]]:
        """获取摄入记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM ingest_records WHERE id = ?', (ingest_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        record = {
            'id': row[0],
            'source': row[1],
            'source_details': self._deserialize_json(row[2]),
            'data_schema': self._deserialize_json(row[3]),
            'record_count': row[4],
            'processed_count': row[5],
            'failed_count': row[6],
            'status': row[7],
            'start_time': row[8],
            'end_time': row[9],
            'duration_seconds': row[10],
            'errors': self._deserialize_json(row[11]),
            'quality_metrics': self._deserialize_json(row[12]),
            'extracted_data': self._deserialize_json(row[13]),
            'original_content': row[14],
            'created_by': row[15]
        }
        
        # 获取关联的构建历史
        builds = self._get_builds_for_ingest(cursor, ingest_id)
        record['builds'] = builds
        
        # 计算构建状态
        record['build_status'] = self._calculate_build_status(builds)
        
        conn.close()
        return record
    
    def _get_builds_for_ingest(self, cursor, ingest_id: str) -> List[Dict[str, Any]]:
        """获取某摄入记录的所有构建历史"""
        cursor.execute('SELECT * FROM build_history WHERE ingest_id = ? ORDER BY start_time DESC', (ingest_id,))
        rows = cursor.fetchall()
        
        builds = []
        for row in rows:
            builds.append({
                'id': row[0],
                'build_id': row[2],
                'version_id': row[3],
                'document_id': row[4],
                'entity_count': row[5],
                'relation_count': row[6],
                'event_count': row[7],
                'status': row[8],
                'start_time': row[9],
                'end_time': row[10],
                'duration_seconds': row[11],
                # 同时添加 version_info 供前端使用
                'version_info': {'version_id': row[3]} if row[3] else None
            })
        return builds
    
    def _calculate_build_status(self, builds: List[Dict[str, Any]]) -> str:
        """
        计算构建状态
        
        Returns:
            str: 'none' | 'pending' | 'completed' | 'failed' | 'partial'
        """
        if not builds:
            return 'none'
        
        # 获取所有构建的状态
        statuses = [b.get('status') for b in builds]
        
        # 如果所有构建都完成
        if all(s == 'completed' for s in statuses):
            return 'completed'
        
        # 如果有任何一个失败
        if any(s == 'failed' for s in statuses):
            # 如果部分成功部分失败
            if any(s == 'completed' for s in statuses):
                return 'partial'
            return 'failed'
        
        # 如果有正在进行的
        if any(s == 'pending' for s in statuses):
            return 'pending'
        
        return 'none'
    
    def update_ingest_record(self, ingest_id: str, record: Dict[str, Any]) -> bool:
        """更新摄入记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE ingest_records SET 
            source = ?, source_details = ?, data_schema = ?, record_count = ?, 
            processed_count = ?, failed_count = ?, status = ?, start_time = ?, 
            end_time = ?, duration_seconds = ?, errors = ?, quality_metrics = ?, 
            extracted_data = ?, original_content = ?, created_by = ?
            WHERE id = ?
        ''', (
            record.get('source'),
            self._serialize_json(record.get('source_details')),
            self._serialize_json(record.get('data_schema')),
            record.get('record_count', 0),
            record.get('processed_count', 0),
            record.get('failed_count', 0),
            record.get('status'),
            record.get('start_time'),
            record.get('end_time'),
            record.get('duration_seconds'),
            self._serialize_json(record.get('errors')),
            self._serialize_json(record.get('quality_metrics')),
            self._serialize_json(record.get('extracted_data')),
            record.get('original_content'),
            record.get('created_by', 'system'),
            ingest_id
        ))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    def get_ingest_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取摄入记录列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM ingest_records ORDER BY start_time DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        
        records = []
        for row in rows:
            record = {
                'id': row[0],
                'source': row[1],
                'source_details': self._deserialize_json(row[2]),
                'record_count': row[4],
                'processed_count': row[5],
                'failed_count': row[6],
                'status': row[7],
                'start_time': row[8],
                'end_time': row[9],
                'duration_seconds': row[10],
                'errors': self._deserialize_json(row[11]),
                'quality_metrics': self._deserialize_json(row[12]),
                'extracted_data': self._deserialize_json(row[13]),
                'original_content': row[14],
                'created_by': row[15]
            }
            # 获取关联的构建历史
            builds = self._get_builds_for_ingest(cursor, row[0])
            record['builds'] = builds
            # 计算构建状态
            record['build_status'] = self._calculate_build_status(builds)
            records.append(record)
        
        conn.close()
        return records
    
    # 审计日志相关
    def save_audit_log(self, log: Dict[str, Any]) -> str:
        """保存审计日志"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO audit_logs (id, ingest_id, timestamp, level, message, details, actor)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            log.get('id'),
            log.get('ingest_id'),
            log.get('timestamp'),
            log.get('level', 'info'),
            log.get('message'),
            self._serialize_json(log.get('details')),
            log.get('actor', 'system')
        ))
        
        conn.commit()
        conn.close()
        return log.get('id')
    
    # 本体文档相关
    def save_ontology_document(self, doc: OntologyDocument) -> str:
        """保存本体文档"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        doc_data = doc.to_dict()
        now = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO ontology_documents 
            (id, doc_id, doc_type, source, meta, entities, relations, events, 
             actions, rules, constraints, ontology_version, scenario_id, 
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_data.get('doc_id'),
            doc_data.get('doc_id'),
            doc_data.get('doc_type'),
            self._serialize_json(doc_data.get('source')),
            self._serialize_json(doc_data.get('meta')),
            self._serialize_json(doc_data.get('entities')),
            self._serialize_json(doc_data.get('relations')),
            self._serialize_json(doc_data.get('events')),
            self._serialize_json(doc_data.get('actions')),
            self._serialize_json(doc_data.get('rules')),
            self._serialize_json(doc_data.get('constraints')),
            self._serialize_json(doc_data.get('ontology_version')),
            doc_data.get('scenario_id'),
            now,
            now
        ))
        
        conn.commit()
        conn.close()
        return doc.doc_id
    
    def get_ontology_document(self, doc_id: str) -> Optional[OntologyDocument]:
        """获取本体文档"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM ontology_documents WHERE doc_id = ?', (doc_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        doc_data = {
            'doc_id': row[1],
            'doc_type': row[2],
            'source': self._deserialize_json(row[3]),
            'meta': self._deserialize_json(row[4]),
            'entities': self._deserialize_json(row[5]),
            'relations': self._deserialize_json(row[6]),
            'events': self._deserialize_json(row[7]),
            'actions': self._deserialize_json(row[8]),
            'rules': self._deserialize_json(row[9]),
            'constraints': self._deserialize_json(row[10]),
            'ontology_version': self._deserialize_json(row[11]),
            'scenario_id': row[12]
        }
        
        from ..ingestion import OntologyDocument
        return OntologyDocument.from_dict(doc_data)
    
    def list_ontology_documents(self, scenario_id: Optional[str] = None, limit: int = 100) -> List[OntologyDocument]:
        """列出本体文档"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if scenario_id:
            cursor.execute('''
                SELECT * FROM ontology_documents 
                WHERE scenario_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (scenario_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM ontology_documents 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        documents = []
        from ..ingestion import OntologyDocument
        
        for row in rows:
            doc_data = {
                'doc_id': row[1],
                'doc_type': row[2],
                'source': self._deserialize_json(row[3]),
                'meta': self._deserialize_json(row[4]),
                'entities': self._deserialize_json(row[5]),
                'relations': self._deserialize_json(row[6]),
                'events': self._deserialize_json(row[7]),
                'actions': self._deserialize_json(row[8]),
                'rules': self._deserialize_json(row[9]),
                'constraints': self._deserialize_json(row[10]),
                'ontology_version': self._deserialize_json(row[11]),
                'scenario_id': row[12]
            }
            documents.append(OntologyDocument.from_dict(doc_data))
        
        return documents
    
    # 构建结果相关
    def save_build_result(self, build_result: Dict[str, Any]) -> str:
        """保存构建结果"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO build_results 
            (id, source_ingest_id, entity_count, relation_count, property_count, 
             status, start_time, end_time, duration_seconds, errors, warnings, 
             ontology_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            build_result.get('build_id'),
            build_result.get('source_ingest_id'),
            build_result.get('entity_count', 0),
            build_result.get('relation_count', 0),
            build_result.get('property_count', 0),
            build_result.get('status'),
            build_result.get('start_time'),
            build_result.get('end_time'),
            build_result.get('duration_seconds'),
            self._serialize_json(build_result.get('errors')),
            self._serialize_json(build_result.get('warnings')),
            build_result.get('ontology_version', '1.0.0')
        ))
        
        conn.commit()
        conn.close()
        return build_result.get('build_id')
    
    def get_build_result(self, build_id: str) -> Optional[Dict[str, Any]]:
        """获取构建结果"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM build_results WHERE id = ?', (build_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        return {
            'build_id': row[0],
            'source_ingest_id': row[1],
            'entity_count': row[2],
            'relation_count': row[3],
            'property_count': row[4],
            'status': row[5],
            'start_time': row[6],
            'end_time': row[7],
            'duration_seconds': row[8],
            'errors': self._deserialize_json(row[9]),
            'warnings': self._deserialize_json(row[10]),
            'ontology_version': row[11]
        }
    
    def update_build_result(self, build_id: str, build_result: Dict[str, Any]) -> bool:
        """更新构建结果"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE build_results SET 
            source_ingest_id = ?, entity_count = ?, relation_count = ?, 
            property_count = ?, status = ?, start_time = ?, end_time = ?, 
            duration_seconds = ?, errors = ?, warnings = ?, ontology_version = ?
            WHERE id = ?
        ''', (
            build_result.get('source_ingest_id'),
            build_result.get('entity_count', 0),
            build_result.get('relation_count', 0),
            build_result.get('property_count', 0),
            build_result.get('status'),
            build_result.get('start_time'),
            build_result.get('end_time'),
            build_result.get('duration_seconds'),
            self._serialize_json(build_result.get('errors')),
            self._serialize_json(build_result.get('warnings')),
            build_result.get('ontology_version', '1.0.0'),
            build_id
        ))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    # 版本管理相关
    def save_version(self, version: Dict[str, Any]) -> str:
        """保存版本"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO ontology_versions 
            (id, ontology_id, version_number, parent_version_id, status, changes, 
             change_summary, created_at, created_by, is_current, is_stable)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            version.get('id'),
            version.get('ontology_id'),
            version.get('version_number'),
            version.get('parent_version_id'),
            version.get('status', 'draft'),
            self._serialize_json(version.get('changes')),
            version.get('change_summary', ''),
            version.get('created_at'),
            version.get('created_by', 'system'),
            1 if version.get('is_current', False) else 0,
            1 if version.get('is_stable', False) else 0
        ))
        
        conn.commit()
        conn.close()
        return version.get('id')
    
    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取版本"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM ontology_versions WHERE id = ?', (version_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'ontology_id': row[1],
            'version_number': row[2],
            'parent_version_id': row[3],
            'status': row[4],
            'changes': self._deserialize_json(row[5]),
            'change_summary': row[6],
            'created_at': row[7],
            'created_by': row[8],
            'is_current': bool(row[9]),
            'is_stable': bool(row[10])
        }
    
    def get_current_version(self, ontology_id: str) -> Optional[Dict[str, Any]]:
        """获取当前版本"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM ontology_versions 
            WHERE ontology_id = ? AND is_current = 1 
            LIMIT 1
        ''', (ontology_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'ontology_id': row[1],
            'version_number': row[2],
            'parent_version_id': row[3],
            'status': row[4],
            'changes': self._deserialize_json(row[5]),
            'change_summary': row[6],
            'created_at': row[7],
            'created_by': row[8],
            'is_current': bool(row[9]),
            'is_stable': bool(row[10])
        }
    
    def get_versions(self, ontology_id: str) -> List[Dict[str, Any]]:
        """获取版本列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM ontology_versions 
            WHERE ontology_id = ? 
            ORDER BY created_at DESC
        ''', (ontology_id,))
        rows = cursor.fetchall()
        
        conn.close()
        
        versions = []
        for row in rows:
            versions.append({
                'id': row[0],
                'ontology_id': row[1],
                'version_number': row[2],
                'parent_version_id': row[3],
                'status': row[4],
                'change_summary': row[6],
                'created_at': row[7],
                'is_current': bool(row[9]),
                'is_stable': bool(row[10])
            })
        return versions
    
    def update_version(self, version_id: str, version_data: Dict[str, Any]) -> bool:
        """更新版本"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE ontology_versions SET 
            status = ?, changes = ?, change_summary = ?, 
            is_current = ?, is_stable = ?
            WHERE id = ?
        ''', (
            version_data.get('status'),
            self._serialize_json(version_data.get('changes')),
            version_data.get('change_summary'),
            1 if version_data.get('is_current', False) else 0,
            1 if version_data.get('is_stable', False) else 0,
            version_id
        ))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    # 验证结果相关
    def save_validation_result(self, validation_result: Dict[str, Any]) -> str:
        """保存验证结果"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO validation_results 
            (id, ontology_id, ontology_version, validation_time, status, errors, 
             warnings, info, error_count, warning_count, info_count, 
             overall_score, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            validation_result.get('id'),
            validation_result.get('ontology_id'),
            validation_result.get('ontology_version'),
            validation_result.get('validation_time'),
            validation_result.get('status', 'pending'),
            self._serialize_json(validation_result.get('errors')),
            self._serialize_json(validation_result.get('warnings')),
            self._serialize_json(validation_result.get('info')),
            validation_result.get('error_count', 0),
            validation_result.get('warning_count', 0),
            validation_result.get('info_count', 0),
            validation_result.get('overall_score', 1.0),
            validation_result.get('duration_seconds', 0.0)
        ))
        
        conn.commit()
        conn.close()
        return validation_result.get('id')
    
    def get_validation_result(self, validation_id: str) -> Optional[Dict[str, Any]]:
        """获取验证结果"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM validation_results WHERE id = ?', (validation_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'ontology_id': row[1],
            'ontology_version': row[2],
            'validation_time': row[3],
            'status': row[4],
            'errors': self._deserialize_json(row[5]),
            'warnings': self._deserialize_json(row[6]),
            'info': self._deserialize_json(row[7]),
            'error_count': row[8],
            'warning_count': row[9],
            'info_count': row[10],
            'overall_score': row[11],
            'duration_seconds': row[12]
        }
    
    def get_validation_results(self) -> List[Dict[str, Any]]:
        """获取验证结果列表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM validation_results ORDER BY validation_time DESC LIMIT 100')
        rows = cursor.fetchall()
        
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'ontology_id': row[1],
                'ontology_version': row[2],
                'validation_time': row[3],
                'status': row[4],
                'error_count': row[8],
                'warning_count': row[9],
                'overall_score': row[11]
            })
        return results
    
    # 验证规则相关
    def save_validation_rule(self, rule: Dict[str, Any]) -> str:
        """保存验证规则"""
        # 这里可以添加验证规则表的实现
        pass
    
    def get_validation_rules(self, rule_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取验证规则"""
        # 这里可以添加验证规则表的实现
        return []
    
    # 处理日志相关（管道每阶段的处理记录）
    def save_process_log(self, log: Dict[str, Any]) -> str:
        """保存处理日志（管道每阶段的处理记录）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO process_logs 
            (id, ingest_id, stage, operation, details, status, error_message, duration_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            log.get('id'),
            log.get('ingest_id'),
            log.get('stage'),
            log.get('operation'),
            self._serialize_json(log.get('details')),
            log.get('status', 'pending'),
            log.get('error_message'),
            log.get('duration_ms'),
            log.get('timestamp')
        ))
        
        conn.commit()
        conn.close()
        return log.get('id')
    
    def get_process_logs(self, ingest_id: str) -> List[Dict[str, Any]]:
        """获取某摄入记录的所有处理日志"""
        conn = self._get_conn()
        cursor.execute('SELECT * FROM process_logs WHERE ingest_id = ? ORDER BY timestamp', (ingest_id,))
        rows = cursor.fetchall()
        
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                'id': row[0],
                'ingest_id': row[1],
                'stage': row[2],
                'operation': row[3],
                'details': self._deserialize_json(row[4]),
                'status': row[5],
                'error_message': row[6],
                'duration_ms': row[7],
                'timestamp': row[8]
            })
        return logs
    
    # 构建历史相关（关联摄入记录和构建结果）
    def save_build_history(self, build_history: Dict[str, Any]) -> str:
        """保存构建历史记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO build_history 
            (id, ingest_id, build_id, version_id, document_id, entity_count, 
             relation_count, event_count, status, start_time, end_time, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            build_history.get('id'),
            build_history.get('ingest_id'),
            build_history.get('build_id'),
            build_history.get('version_id'),
            build_history.get('document_id'),
            build_history.get('entity_count', 0),
            build_history.get('relation_count', 0),
            build_history.get('event_count', 0),
            build_history.get('status'),
            build_history.get('start_time'),
            build_history.get('end_time'),
            build_history.get('duration_seconds')
        ))
        
        conn.commit()
        conn.close()
        return build_history.get('id')
    
    def get_build_history(self, ingest_id: str) -> Optional[Dict[str, Any]]:
        """获取某摄入记录的构建历史"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM build_history WHERE ingest_id = ? ORDER BY start_time DESC LIMIT 1', (ingest_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'ingest_id': row[1],
            'build_id': row[2],
            'version_id': row[3],
            'document_id': row[4],
            'entity_count': row[5],
            'relation_count': row[6],
            'event_count': row[7],
            'status': row[8],
            'start_time': row[9],
            'end_time': row[10],
            'duration_seconds': row[11]
        }
    
    def get_all_build_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取所有构建历史记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM build_history ORDER BY start_time DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                'id': row[0],
                'ingest_id': row[1],
                'build_id': row[2],
                'version_id': row[3],
                'document_id': row[4],
                'entity_count': row[5],
                'relation_count': row[6],
                'event_count': row[7],
                'status': row[8],
                'start_time': row[9],
                'end_time': row[10],
                'duration_seconds': row[11]
            })
        return history