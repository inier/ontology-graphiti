from odap.infra.storage.sqlite_base import SqliteBaseStorage
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from odap.infra.security.audit_helper import storage_audit

def _migrate_add_column(cursor, table: str, column: str, column_type: str):
    """安全添加列（兼容 SQLite 不支持 IF NOT EXISTS for ALTER TABLE）"""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
    except sqlite3.OperationalError:
        pass  # 列已存在

class SQLiteKnowledgeBaseStorage(SqliteBaseStorage):
    def __init__(self, db_path: str = None):
        super().__init__(db_path, db_name="knowledge_bases.db")

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_bases (
            kb_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            knowledge_count INTEGER DEFAULT 0,
            category_count INTEGER DEFAULT 0,
            created_by TEXT DEFAULT 'system',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS kb_categories (
            category_id TEXT PRIMARY KEY,
            kb_id TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id TEXT,
            document_count INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(kb_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS kb_documents (
            doc_id TEXT PRIMARY KEY,
            kb_id TEXT NOT NULL,
            category_id TEXT,
            title TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            file_type TEXT,
            file_size INTEGER,
            file_url TEXT,
            content TEXT,
            raw_content TEXT,
            cleaned_content TEXT,
            cleaning_status TEXT DEFAULT 'pending',
            cleaning_level TEXT DEFAULT 'basic',
            keywords TEXT DEFAULT '[]',
            summary TEXT,
            segments_json TEXT,
            entities_json TEXT,
            status TEXT DEFAULT 'pending',
            graph_built INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(kb_id)
        )''')
        # 增量迁移：为已有表添加清洗相关字段（如果不存在）
        _migrate_add_column(c, "kb_documents", "raw_content", "TEXT")
        _migrate_add_column(c, "kb_documents", "cleaned_content", "TEXT")
        _migrate_add_column(c, "kb_documents", "cleaning_status", "TEXT DEFAULT 'pending'")
        _migrate_add_column(c, "kb_documents", "cleaning_level", "TEXT DEFAULT 'basic'")
        _migrate_add_column(c, "kb_documents", "segments_json", "TEXT")
        _migrate_add_column(c, "kb_documents", "entities_json", "TEXT")
        _migrate_add_column(c, "kb_documents", "relations_json", "TEXT")
        _migrate_add_column(c, "kb_documents", "extraction_quality_json", "TEXT")
        _migrate_add_column(c, "kb_documents", "extraction_method", "TEXT")
        conn.commit()
        conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if 'keywords' in d and isinstance(d['keywords'], str):
            try:
                d['keywords'] = json.loads(d['keywords'])
            except (json.JSONDecodeError, TypeError):
                d['keywords'] = []
        # Sanitize keywords → always List[str] (matches Pydantic schema KnowledgeDocument.keywords)
        if isinstance(d.get('keywords'), list):
            sanitized: List[str] = []
            for kw in d['keywords']:
                if isinstance(kw, str):
                    if kw:
                        sanitized.append(kw)
                elif isinstance(kw, dict):
                    val = (
                        kw.get('keyword')
                        or kw.get('content')
                        or kw.get('name')
                        or kw.get('value')
                        or kw.get('label')
                    )
                    if isinstance(val, str) and val:
                        sanitized.append(val)
                elif kw is None:
                    continue
                else:
                    s = str(kw)
                    if s:
                        sanitized.append(s)
            d['keywords'] = sanitized
        elif d.get('keywords') is not None:
            d['keywords'] = []
        if 'graph_built' in d:
            d['graph_built'] = bool(d['graph_built'])
        # 反序列化 JSON 字段
        for json_field in ('segments_json', 'entities_json'):
            if json_field in d and isinstance(d[json_field], str) and d[json_field]:
                try:
                    d[json_field] = json.loads(d[json_field])
                except (json.JSONDecodeError, TypeError):
                    d[json_field] = None
        return d

    # Knowledge Base CRUD
    def list_knowledge_bases(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM knowledge_bases ORDER BY created_at DESC").fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def get_knowledge_base(self, kb_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM knowledge_bases WHERE kb_id = ?", (kb_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def create_knowledge_base(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        kb_id = f"kb_{uuid.uuid4().hex[:12]}"
        record = {
            'kb_id': kb_id,
            'name': data.get('name', ''),
            'description': data.get('description', ''),
            'knowledge_count': 0,
            'category_count': 0,
            'created_by': data.get('created_by', 'system'),
            'status': 'active',
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO knowledge_bases ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.commit()
            result = self.get_knowledge_base(kb_id)
            storage_audit(
                "storage_create_kb_success",
                resource=kb_id,
                details={
                    "kb_id": kb_id,
                    "name": record['name'],
                    "description_length": len(record['description']),
                },
            )
            return result
        except Exception as e:
            storage_audit(
                "storage_create_kb_failed",
                result_status="failure",
                result_message=str(e),
                resource=kb_id,
                details={
                    "kb_id": kb_id,
                    "name": record.get('name', ''),
                },
            )
            raise
        finally:
            conn.close()

    def update_knowledge_base(self, kb_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_knowledge_base(kb_id)
        if not existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        sets = []
        values = []
        changed_keys = []
        for key, val in data.items():
            if key in ('kb_id', 'created_at', 'created_by'):
                continue
            if val is not None:
                sets.append(f"{key} = ?")
                values.append(val)
                changed_keys.append(key)
        sets.append("updated_at = ?")
        values.append(now)
        values.append(kb_id)
        conn = self._get_conn()
        try:
            conn.execute(f"UPDATE knowledge_bases SET {', '.join(sets)} WHERE kb_id = ?", values)
            conn.commit()
            result = self.get_knowledge_base(kb_id)
            storage_audit(
                "storage_update_kb_success",
                resource=kb_id,
                details={"kb_id": kb_id, "changed_keys": changed_keys},
            )
            return result
        except Exception as e:
            storage_audit(
                "storage_update_kb_failed",
                result_status="failure",
                result_message=str(e),
                resource=kb_id,
                details={"kb_id": kb_id, "changed_keys": changed_keys},
            )
            raise
        finally:
            conn.close()

    def delete_knowledge_base(self, kb_id: str) -> bool:
        existing = self.get_knowledge_base(kb_id)
        if not existing:
            return False
        doc_count = existing.get('knowledge_count', 0)
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM kb_documents WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM kb_categories WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM knowledge_bases WHERE kb_id = ?", (kb_id,))
            conn.commit()
            storage_audit(
                "storage_delete_kb_success",
                resource=kb_id,
                details={"kb_id": kb_id, "doc_count": doc_count},
            )
            return True
        except Exception as e:
            storage_audit(
                "storage_delete_kb_failed",
                result_status="failure",
                result_message=str(e),
                resource=kb_id,
                details={"kb_id": kb_id},
            )
            raise
        finally:
            conn.close()

    # Category CRUD
    def list_categories(self, kb_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM kb_categories WHERE kb_id = ? ORDER BY name", (kb_id,)).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def create_category(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        category_id = f"cat_{uuid.uuid4().hex[:12]}"
        record = {
            'category_id': category_id,
            'kb_id': kb_id,
            'name': data.get('name', ''),
            'parent_id': data.get('parent_id'),
            'document_count': 0,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO kb_categories ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.execute("UPDATE knowledge_bases SET category_count = category_count + 1, updated_at = ? WHERE kb_id = ?", (now, kb_id))
            conn.commit()
            storage_audit(
                "storage_create_category_success",
                resource=category_id,
                details={
                    "kb_id": kb_id,
                    "category_id": category_id,
                    "name": record['name'],
                },
            )
            return dict(record)
        except Exception as e:
            storage_audit(
                "storage_create_category_failed",
                result_status="failure",
                result_message=str(e),
                resource=category_id,
                details={
                    "kb_id": kb_id,
                    "category_id": category_id,
                    "name": record.get('name', ''),
                },
            )
            raise
        finally:
            conn.close()

    def delete_category(self, kb_id: str, category_id: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM kb_categories WHERE category_id = ? AND kb_id = ?", (category_id, kb_id)).fetchone()
            if not row:
                return False
            cat_name = dict(row).get('name', '')
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("DELETE FROM kb_categories WHERE category_id = ? AND kb_id = ?", (category_id, kb_id))
            conn.execute("UPDATE knowledge_bases SET category_count = category_count - 1, updated_at = ? WHERE kb_id = ?", (now, kb_id))
            conn.commit()
            storage_audit(
                "storage_delete_category_success",
                resource=category_id,
                details={
                    "kb_id": kb_id,
                    "category_id": category_id,
                    "name": cat_name,
                },
            )
            return True
        except Exception as e:
            storage_audit(
                "storage_delete_category_failed",
                result_status="failure",
                result_message=str(e),
                resource=category_id,
                details={
                    "kb_id": kb_id,
                    "category_id": category_id,
                },
            )
            raise
        finally:
            conn.close()

    # Document CRUD
    def list_documents(self, kb_id: str, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            if category_id:
                rows = conn.execute("SELECT * FROM kb_documents WHERE kb_id = ? AND category_id = ? ORDER BY created_at DESC", (kb_id, category_id)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM kb_documents WHERE kb_id = ? ORDER BY created_at DESC", (kb_id,)).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def create_document(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        content = data.get('content') or ''
        record = {
            'doc_id': doc_id,
            'kb_id': kb_id,
            'category_id': data.get('category_id'),
            'title': data.get('title', ''),
            'content_type': data.get('content_type', 'text'),
            'file_type': data.get('file_type'),
            'file_size': data.get('file_size'),
            'file_url': data.get('file_url'),
            'content': content,
            'raw_content': data.get('raw_content') or content,
            'cleaned_content': data.get('cleaned_content'),
            'cleaning_status': data.get('cleaning_status', 'pending'),
            'cleaning_level': data.get('cleaning_level', 'basic'),
            'keywords': json.dumps(data.get('keywords', []), ensure_ascii=False),
            'summary': data.get('summary'),
            'segments_json': json.dumps(data.get('segments'), ensure_ascii=False) if data.get('segments') else None,
            'entities_json': json.dumps(data.get('entities'), ensure_ascii=False) if data.get('entities') else None,
            'status': 'pending',
            'graph_built': 0,
            'created_at': now,
            'updated_at': now,
        }
        conn = self._get_conn()
        try:
            cols = ', '.join(record.keys())
            placeholders = ', '.join(['?'] * len(record))
            conn.execute(f"INSERT INTO kb_documents ({cols}) VALUES ({placeholders})", list(record.values()))
            conn.execute("UPDATE knowledge_bases SET knowledge_count = knowledge_count + 1, updated_at = ? WHERE kb_id = ?", (now, kb_id))
            conn.commit()
            result = self._row_to_dict(conn.execute("SELECT * FROM kb_documents WHERE doc_id = ?", (doc_id,)).fetchone())
            storage_audit(
                "storage_create_document_success",
                resource=doc_id,
                details={
                    "kb_id": kb_id,
                    "doc_id": doc_id,
                    "title": record['title'],
                    "file_size": record.get('file_size'),
                    "content_length": len(content) if isinstance(content, str) else 0,
                },
            )
            return result
        except Exception as e:
            storage_audit(
                "storage_create_document_failed",
                result_status="failure",
                result_message=str(e),
                resource=doc_id,
                details={
                    "kb_id": kb_id,
                    "doc_id": doc_id,
                    "title": record.get('title', ''),
                },
            )
            raise
        finally:
            conn.close()

    def get_document(self, kb_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM kb_documents WHERE doc_id = ? AND kb_id = ?", (doc_id, kb_id)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        except Exception as e:
            storage_audit(
                "storage_get_document_failed",
                result_status="failure",
                result_message=str(e),
                resource=doc_id,
                details={"kb_id": kb_id, "doc_id": doc_id},
            )
            raise
        finally:
            conn.close()

    def delete_document(self, kb_id: str, doc_id: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM kb_documents WHERE doc_id = ? AND kb_id = ?", (doc_id, kb_id)).fetchone()
            if not row:
                return False
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("DELETE FROM kb_documents WHERE doc_id = ? AND kb_id = ?", (doc_id, kb_id))
            conn.execute("UPDATE knowledge_bases SET knowledge_count = knowledge_count - 1, updated_at = ? WHERE kb_id = ?", (now, kb_id))
            conn.commit()
            storage_audit(
                "storage_delete_document_success",
                resource=doc_id,
                details={"kb_id": kb_id, "doc_id": doc_id},
            )
            return True
        except Exception as e:
            storage_audit(
                "storage_delete_document_failed",
                result_status="failure",
                result_message=str(e),
                resource=doc_id,
                details={"kb_id": kb_id, "doc_id": doc_id},
            )
            raise
        finally:
            conn.close()

    def update_document_graph_status(self, doc_id: str, graph_built: bool, entities_extracted: int = 0) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM kb_documents WHERE doc_id = ?", (doc_id,)).fetchone()
            if not row:
                return False
            now = datetime.now(timezone.utc).isoformat()
            # 同步更新 status 字段：图谱已构建 → indexed，否则回退 pending
            new_status = "indexed" if graph_built else "pending"
            conn.execute(
                "UPDATE kb_documents SET graph_built = ?, status = ?, updated_at = ? WHERE doc_id = ?",
                (1 if graph_built else 0, new_status, now, doc_id)
            )
            conn.commit()
            storage_audit(
                "storage_update_document_graph_status_success",
                resource=doc_id,
                details={
                    "doc_id": doc_id,
                    "graph_built": graph_built,
                    "entities_count": entities_extracted,
                },
            )
            return True
        except Exception as e:
            storage_audit(
                "storage_update_document_graph_status_failed",
                result_status="failure",
                result_message=str(e),
                resource=doc_id,
                details={"doc_id": doc_id},
            )
            raise
        finally:
            conn.close()

    def find_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM kb_documents WHERE doc_id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        except Exception as e:
            storage_audit(
                "storage_find_document_by_id_failed",
                result_status="failure",
                result_message=str(e),
                resource=doc_id,
                details={"doc_id": doc_id},
            )
            raise
        finally:
            conn.close()

    def update_document_cleaning_status(self, doc_id: str, status: str, level: str = "basic") -> bool:
        """更新文档清洗状态"""
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE kb_documents SET cleaning_status = ?, cleaning_level = ?, updated_at = ? WHERE doc_id = ?",
                (status, level, now, doc_id)
            )
            conn.commit()
            result = conn.total_changes > 0
            storage_audit(
                "storage_update_document_cleaning_status_success",
                resource=doc_id,
                details={
                    "doc_id": doc_id,
                    "status": status,
                    "level": level,
                },
            )
            return result
        except Exception as e:
            storage_audit(
                "storage_update_document_cleaning_status_failed",
                result_status="failure",
                result_message=str(e),
                resource=doc_id,
                details={"doc_id": doc_id},
            )
            raise
        finally:
            conn.close()

    def update_document_cleaned_content(
        self,
        doc_id: str,
        raw_content: str,
        cleaned_content: str,
        cleaning_status: str,
        cleaning_level: str,
        keywords: List[str] = None,
        summary: str = None,
        segments: List[Dict[str, Any]] = None,
        entities: List[Dict[str, Any]] = None,
    ) -> bool:
        """更新文档清洗后的全部内容"""
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """UPDATE kb_documents SET
                    raw_content = ?, cleaned_content = ?,
                    cleaning_status = ?, cleaning_level = ?,
                    keywords = ?, summary = ?,
                    segments_json = ?, entities_json = ?,
                    updated_at = ?
                WHERE doc_id = ?""",
                (
                    raw_content,
                    cleaned_content,
                    cleaning_status,
                    cleaning_level,
                    json.dumps(keywords or [], ensure_ascii=False),
                    summary or "",
                    json.dumps(segments or [], ensure_ascii=False),
                    json.dumps(entities or [], ensure_ascii=False),
                    now,
                    doc_id,
                ),
            )
            conn.commit()
            result = conn.total_changes > 0
            storage_audit(
                "storage_update_document_keywords_success",
                resource=doc_id,
                details={
                    "doc_id": doc_id,
                    "keywords_count": len(keywords) if keywords else 0,
                    "entities_count": len(entities) if entities else 0,
                },
            )
            return result
        except Exception as e:
            storage_audit(
                "storage_update_document_keywords_failed",
                result_status="failure",
                result_message=str(e),
                resource=doc_id,
                details={"doc_id": doc_id},
            )
            raise
        finally:
            conn.close()

    def save_extraction_result(
        self,
        doc_id: str,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        quality: Dict[str, Any] = None,
        method: str = "",
    ) -> bool:
        """保存提取中间结果（entities + relations + quality），供业务审查编辑。"""
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """UPDATE kb_documents SET
                    entities_json = ?, relations_json = ?,
                    extraction_quality_json = ?, extraction_method = ?,
                    updated_at = ?
                WHERE doc_id = ?""",
                (
                    json.dumps(entities, ensure_ascii=False),
                    json.dumps(relations, ensure_ascii=False),
                    json.dumps(quality, ensure_ascii=False) if quality else None,
                    method,
                    now,
                    doc_id,
                ),
            )
            conn.commit()
            return conn.total_changes > 0
        except Exception as e:
            logger.warning(f"保存提取结果失败: {e}")
            return False
        finally:
            conn.close()

    def get_extraction_result(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """读取文档的提取中间结果"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT entities_json, relations_json, extraction_quality_json, "
                "extraction_method FROM kb_documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "entities": json.loads(row[0]) if row[0] else [],
                "relations": json.loads(row[1]) if row[1] else [],
                "quality": json.loads(row[2]) if row[2] else {},
                "method": row[3] or "",
            }
        except Exception as e:
            logger.warning(f"读取提取结果失败: {e}")
            return None
        finally:
            conn.close()
