"""MongoDB存储实现"""

from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.collection import Collection


class MongoDBStorage:
    """MongoDB存储实现"""

    def __init__(self, connection_string: str = "mongodb://localhost:27017"):
        self.client = MongoClient(connection_string)
        self.db = self.client["ontology"]

        # 集合
        self.ingest_records: Collection = self.db["ingest_records"]
        self.audit_logs: Collection = self.db["audit_logs"]
        self.build_results: Collection = self.db["build_results"]
        self.ontology_documents: Collection = self.db["ontology_documents"]
        self.ontology_versions: Collection = self.db["ontology_versions"]
        self.validation_rules: Collection = self.db["validation_rules"]
        self.validation_results: Collection = self.db["validation_results"]

        self._init_db()

    def _init_db(self):
        """初始化数据库和索引"""
        self.ingest_records.create_index("id", unique=True)
        self.ingest_records.create_index("workspace_id")
        self.ingest_records.create_index("created_at")

        self.audit_logs.create_index("id", unique=True)
        self.audit_logs.create_index("timestamp")

        self.build_results.create_index("id", unique=True)
        self.build_results.create_index("workspace_id")

        self.ontology_documents.create_index("id", unique=True)
        self.ontology_documents.create_index("workspace_id")

        self.ontology_versions.create_index("id", unique=True)
        self.ontology_versions.create_index("document_id")

        self.validation_rules.create_index("id", unique=True)

        self.validation_results.create_index("id", unique=True)
        self.validation_results.create_index("build_id")

    def get_ingest_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """获取摄入记录"""
        data = self.ingest_records.find_one({"id": record_id})
        return data

    def save_ingest_record(self, record: Dict[str, Any]) -> None:
        """保存摄入记录"""
        self.ingest_records.update_one({"id": record["id"]}, {"$set": record}, upsert=True)

    def list_ingest_records(self, workspace_id: str, page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """列出摄入记录"""
        records = self.ingest_records.find({"workspace_id": workspace_id}).skip((page - 1) * page_size).limit(page_size)
        return list(records)

    def save_audit_log(self, log: Dict[str, Any]) -> None:
        """保存审计日志"""
        self.audit_logs.update_one({"id": log["id"]}, {"$set": log}, upsert=True)

    def query_audit_logs(self, filters: Dict[str, Any], page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
        """查询审计日志"""
        query = filters or {}
        logs = self.audit_logs.find(query).skip((page - 1) * page_size).limit(page_size)
        return list(logs)

    def save_build_result(self, result: Dict[str, Any]) -> None:
        """保存构建结果"""
        self.build_results.update_one({"id": result["id"]}, {"$set": result}, upsert=True)

    def get_build_result(self, build_id: str) -> Optional[Dict[str, Any]]:
        """获取构建结果"""
        return self.build_results.find_one({"id": build_id})

    def save_ontology_document(self, document: Dict[str, Any]) -> None:
        """保存本体文档"""
        self.ontology_documents.update_one({"id": document["id"]}, {"$set": document}, upsert=True)

    def get_ontology_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取本体文档"""
        return self.ontology_documents.find_one({"id": doc_id})

    def list_ontology_documents(self, workspace_id: str, page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """列出本体文档"""
        docs = self.ontology_documents.find({"workspace_id": workspace_id}).skip((page - 1) * page_size).limit(page_size)
        return list(docs)

    def save_ontology_version(self, version: Dict[str, Any]) -> None:
        """保存本体版本"""
        self.ontology_versions.update_one({"id": version["id"]}, {"$set": version}, upsert=True)

    def get_ontology_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取本体版本"""
        return self.ontology_versions.find_one({"id": version_id})

    def list_ontology_versions(self, document_id: str) -> List[Dict[str, Any]]:
        """列出本体版本"""
        return list(self.ontology_versions.find({"document_id": document_id}).sort("created_at", -1))

    def save_validation_rule(self, rule: Dict[str, Any]) -> None:
        """保存验证规则"""
        self.validation_rules.update_one({"id": rule["id"]}, {"$set": rule}, upsert=True)

    def get_validation_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """获取验证规则"""
        return self.validation_rules.find_one({"id": rule_id})

    def list_validation_rules(self, document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出验证规则"""
        query = {"document_id": document_id} if document_id else {}
        return list(self.validation_rules.find(query))

    def save_validation_result(self, result: Dict[str, Any]) -> None:
        """保存验证结果"""
        self.validation_results.update_one({"id": result["id"]}, {"$set": result}, upsert=True)

    def get_validation_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """获取验证结果"""
        return self.validation_results.find_one({"id": result_id})

    def list_validation_results(self, build_id: str) -> List[Dict[str, Any]]:
        """列出验证结果"""
        return list(self.validation_results.find({"build_id": build_id}))

    def close(self):
        """关闭连接"""
        self.client.close()