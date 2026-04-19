"""MongoDB存储实现"""

from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from ..models.audit import DataIngestRecord, AuditLog
from ..models.ontology import OntologyBuildResult, OntologyDocument
from ..models.version import OntologyVersion
from ..models.validation import ValidationRule, ValidationResult
import json


class MongoDBStorage:
    """MongoDB存储实现"""
    
    def __init__(self, connection_string: str = "mongodb://localhost:27017"):
        self.client = MongoClient(connection_string)
        self.db = self.client["ontology_management"]
        
        # 集合
        self.ingest_records: Collection = self.db["ingest_records"]
        self.audit_logs: Collection = self.db["audit_logs"]
        self.build_results: Collection = self.db["build_results"]
        self.ontology_documents: Collection = self.db["ontology_documents"]
        self.versions: Collection = self.db["versions"]
        self.validation_rules: Collection = self.db["validation_rules"]
        self.validation_results: Collection = self.db["validation_results"]
    
    # 数据摄入相关
    def save_ingest_record(self, record: DataIngestRecord) -> None:
        """保存摄入记录"""
        self.ingest_records.insert_one(record.model_dump())
    
    def get_ingest_record(self, ingest_id: str) -> Optional[DataIngestRecord]:
        """获取摄入记录"""
        data = self.ingest_records.find_one({"id": ingest_id})
        return DataIngestRecord(**data) if data else None
    
    def update_ingest_record(self, record: DataIngestRecord) -> None:
        """更新摄入记录"""
        self.ingest_records.update_one({"id": record.id}, {"$set": record.model_dump()})
    
    def list_ingest_records(self, filters: Dict[str, Any] = None, 
                          page: int = 1, page_size: int = 10) -> List[DataIngestRecord]:
        """列出摄入记录"""
        query = filters or {}
        records = self.ingest_records.find(query).skip((page - 1) * page_size).limit(page_size)
        return [DataIngestRecord(**record) for record in records]
    
    def save_audit_log(self, log: AuditLog) -> None:
        """保存审计日志"""
        self.audit_logs.insert_one(log.model_dump())
    
    def get_audit_logs(self, ingest_id: str, 
                     start_time: Optional[str] = None, 
                     end_time: Optional[str] = None) -> List[AuditLog]:
        """获取审计日志"""
        query = {"ingest_id": ingest_id}
        if start_time:
            query["timestamp"] = {"$gte": start_time}
        if end_time:
            query["timestamp"] = {**query.get("timestamp", {}), "$lte": end_time}
        logs = self.audit_logs.find(query)
        return [AuditLog(**log) for log in logs]
    
    # 本体构建相关
    def save_build_result(self, result: OntologyBuildResult) -> None:
        """保存构建结果"""
        self.build_results.insert_one(result.model_dump())
    
    def save_ontology_document(self, doc: OntologyDocument) -> None:
        """保存本体文档"""
        self.ontology_documents.insert_one(doc.model_dump())
    
    def get_ontology_document(self, ontology_id: str) -> Optional[OntologyDocument]:
        """获取本体文档"""
        data = self.ontology_documents.find_one({"id": ontology_id})
        return OntologyDocument(**data) if data else None
    
    def update_ontology_document(self, doc: OntologyDocument) -> None:
        """更新本体文档"""
        self.ontology_documents.update_one({"id": doc.id}, {"$set": doc.model_dump()})
    
    def list_ontology_documents(self, filters: Dict[str, Any] = None, 
                              page: int = 1, page_size: int = 10) -> List[OntologyDocument]:
        """列出本体文档"""
        query = filters or {}
        docs = self.ontology_documents.find(query).skip((page - 1) * page_size).limit(page_size)
        return [OntologyDocument(**doc) for doc in docs]
    
    # 版本管理相关
    def save_version(self, version: OntologyVersion) -> None:
        """保存版本"""
        self.versions.insert_one(version.model_dump())
    
    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        """获取版本"""
        data = self.versions.find_one({"id": version_id})
        return OntologyVersion(**data) if data else None
    
    def update_version(self, version: OntologyVersion) -> None:
        """更新版本"""
        self.versions.update_one({"id": version.id}, {"$set": version.model_dump()})
    
    def list_versions(self, ontology_id: str, 
                    filters: Dict[str, Any] = None, 
                    page: int = 1, page_size: int = 10) -> List[OntologyVersion]:
        """列出版本"""
        query = {"ontology_id": ontology_id, **(filters or {})}
        versions = self.versions.find(query).skip((page - 1) * page_size).limit(page_size)
        return [OntologyVersion(**version) for version in versions]
    
    # 验证相关
    def save_validation_rule(self, rule: ValidationRule) -> None:
        """保存验证规则"""
        self.validation_rules.insert_one(rule.model_dump())
    
    def get_validation_rule(self, rule_id: str) -> Optional[ValidationRule]:
        """获取验证规则"""
        data = self.validation_rules.find_one({"id": rule_id})
        return ValidationRule(**data) if data else None
    
    def list_validation_rules(self, filters: Dict[str, Any] = None, 
                           page: int = 1, page_size: int = 10) -> List[ValidationRule]:
        """列出验证规则"""
        query = filters or {}
        rules = self.validation_rules.find(query).skip((page - 1) * page_size).limit(page_size)
        return [ValidationRule(**rule) for rule in rules]
    
    def save_validation_result(self, result: ValidationResult) -> None:
        """保存验证结果"""
        self.validation_results.insert_one(result.model_dump())
    
    def get_validation_result(self, result_id: str) -> Optional[ValidationResult]:
        """获取验证结果"""
        data = self.validation_results.find_one({"id": result_id})
        return ValidationResult(**data) if data else None
