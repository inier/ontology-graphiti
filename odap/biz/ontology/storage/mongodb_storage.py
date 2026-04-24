"""本体模块 MongoDB 存储实现"""

from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.collection import Collection
import os


class MongoDBStorage:
    """本体模块 MongoDB 存储实现
    
    存储内容：
    - 摄入记录
    - 审计日志
    - 构建结果
    - 本体文档
    - 版本信息
    - 验证规则
    - 验证结果
    """
    
    def __init__(self, connection_string: str = None):
        """初始化 MongoDB 存储
        
        Args:
            connection_string: MongoDB 连接字符串
        """
        self.connection_string = connection_string or os.getenv("MONGODB_URI", "mongodb://graphiti-mongodb:27017")
        self.client = MongoClient(self.connection_string)
        self.db = self.client["ontology"]
        
        # 初始化集合
        self.ingest_records = self.db["ingest_records"]
        self.audit_logs = self.db["audit_logs"]
        self.build_results = self.db["build_results"]
        self.ontology_documents = self.db["ontology_documents"]
        self.versions = self.db["versions"]
        self.validation_rules = self.db["validation_rules"]
        self.validation_results = self.db["validation_results"]
        
        # 创建索引
        self._create_indexes()
    
    def _create_indexes(self):
        """创建必要的索引"""
        # 摄入记录索引
        self.ingest_records.create_index("ingest_id")
        self.ingest_records.create_index("status")
        self.ingest_records.create_index("created_at")
        
        # 审计日志索引
        self.audit_logs.create_index("event_id")
        self.audit_logs.create_index("timestamp")
        
        # 构建结果索引
        self.build_results.create_index("build_id")
        self.build_results.create_index("status")
        
        # 本体文档索引
        self.ontology_documents.create_index("document_id")
        self.ontology_documents.create_index("type")
        
        # 版本索引
        self.versions.create_index("version_id")
        self.versions.create_index("ontology_id")
        
        # 验证规则索引
        self.validation_rules.create_index("rule_id")
        self.validation_rules.create_index("rule_type")
        
        # 验证结果索引
        self.validation_results.create_index("result_id")
        self.validation_results.create_index("rule_id")
    
    # ==================== 摄入记录 ====================
    
    def save_ingest_record(self, record: Dict[str, Any]) -> str:
        """保存摄入记录
        
        Args:
            record: 摄入记录
        
        Returns:
            str: 记录 ID
        """
        result = self.ingest_records.insert_one(record)
        return str(result.inserted_id)
    
    def get_ingest_record(self, ingest_id: str) -> Optional[Dict[str, Any]]:
        """获取摄入记录
        
        Args:
            ingest_id: 摄入记录 ID
        
        Returns:
            Optional[Dict]: 摄入记录
        """
        return self.ingest_records.find_one({"ingest_id": ingest_id})
    
    def update_ingest_record(self, ingest_id: str, updates: Dict[str, Any]) -> bool:
        """更新摄入记录
        
        Args:
            ingest_id: 摄入记录 ID
            updates: 更新内容
        
        Returns:
            bool: 是否更新成功
        """
        result = self.ingest_records.update_one(
            {"ingest_id": ingest_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    def list_ingest_records(self, filters: Dict[str, Any] = None, 
                          page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """列出摄入记录
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页大小
        
        Returns:
            List[Dict]: 摄入记录列表
        """
        query = filters or {}
        records = self.ingest_records.find(query).skip((page - 1) * page_size).limit(page_size)
        return list(records)
    
    # ==================== 审计日志 ====================
    
    def save_audit_log(self, log: Dict[str, Any]) -> str:
        """保存审计日志
        
        Args:
            log: 审计日志
        
        Returns:
            str: 日志 ID
        """
        result = self.audit_logs.insert_one(log)
        return str(result.inserted_id)
    
    def get_audit_log(self, event_id: str) -> Optional[Dict[str, Any]]:
        """获取审计日志
        
        Args:
            event_id: 事件 ID
        
        Returns:
            Optional[Dict]: 审计日志
        """
        return self.audit_logs.find_one({"event_id": event_id})
    
    def list_audit_logs(self, filters: Dict[str, Any] = None, 
                      page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """列出审计日志
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页大小
        
        Returns:
            List[Dict]: 审计日志列表
        """
        query = filters or {}
        logs = self.audit_logs.find(query).skip((page - 1) * page_size).limit(page_size)
        return list(logs)
    
    # ==================== 构建结果 ====================
    
    def save_build_result(self, result: Dict[str, Any]) -> str:
        """保存构建结果
        
        Args:
            result: 构建结果
        
        Returns:
            str: 结果 ID
        """
        result_doc = self.build_results.insert_one(result)
        return str(result_doc.inserted_id)
    
    def get_build_result(self, build_id: str) -> Optional[Dict[str, Any]]:
        """获取构建结果
        
        Args:
            build_id: 构建 ID
        
        Returns:
            Optional[Dict]: 构建结果
        """
        return self.build_results.find_one({"build_id": build_id})
    
    def update_build_result(self, build_id: str, updates: Dict[str, Any]) -> bool:
        """更新构建结果
        
        Args:
            build_id: 构建 ID
            updates: 更新内容
        
        Returns:
            bool: 是否更新成功
        """
        result = self.build_results.update_one(
            {"build_id": build_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    # ==================== 本体文档 ====================
    
    def save_ontology_document(self, document: Dict[str, Any]) -> str:
        """保存本体文档
        
        Args:
            document: 本体文档
        
        Returns:
            str: 文档 ID
        """
        result = self.ontology_documents.insert_one(document)
        return str(result.inserted_id)
    
    def get_ontology_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取本体文档
        
        Args:
            document_id: 文档 ID
        
        Returns:
            Optional[Dict]: 本体文档
        """
        return self.ontology_documents.find_one({"document_id": document_id})
    
    def update_ontology_document(self, document_id: str, updates: Dict[str, Any]) -> bool:
        """更新本体文档
        
        Args:
            document_id: 文档 ID
            updates: 更新内容
        
        Returns:
            bool: 是否更新成功
        """
        result = self.ontology_documents.update_one(
            {"document_id": document_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    def list_ontology_documents(self, filters: Dict[str, Any] = None, 
                              page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """列出本体文档
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页大小
        
        Returns:
            List[Dict]: 本体文档列表
        """
        query = filters or {}
        documents = self.ontology_documents.find(query).skip((page - 1) * page_size).limit(page_size)
        return list(documents)
    
    # ==================== 版本 ====================
    
    def save_version(self, version: Dict[str, Any]) -> str:
        """保存版本信息
        
        Args:
            version: 版本信息
        
        Returns:
            str: 版本 ID
        """
        result = self.versions.insert_one(version)
        return str(result.inserted_id)
    
    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取版本信息
        
        Args:
            version_id: 版本 ID
        
        Returns:
            Optional[Dict]: 版本信息
        """
        return self.versions.find_one({"version_id": version_id})
    
    def list_versions(self, ontology_id: str, 
                     page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """列出版本信息
        
        Args:
            ontology_id: 本体 ID
            page: 页码
            page_size: 每页大小
        
        Returns:
            List[Dict]: 版本信息列表
        """
        query = {"ontology_id": ontology_id}
        versions = self.versions.find(query).skip((page - 1) * page_size).limit(page_size)
        return list(versions)
    
    # ==================== 验证规则 ====================
    
    def save_validation_rule(self, rule: Dict[str, Any]) -> str:
        """保存验证规则
        
        Args:
            rule: 验证规则
        
        Returns:
            str: 规则 ID
        """
        result = self.validation_rules.insert_one(rule)
        return str(result.inserted_id)
    
    def get_validation_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """获取验证规则
        
        Args:
            rule_id: 规则 ID
        
        Returns:
            Optional[Dict]: 验证规则
        """
        return self.validation_rules.find_one({"rule_id": rule_id})
    
    def list_validation_rules(self, rule_type: str = None, 
                            page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """列出验证规则
        
        Args:
            rule_type: 规则类型
            page: 页码
            page_size: 每页大小
        
        Returns:
            List[Dict]: 验证规则列表
        """
        query = {}
        if rule_type:
            query["rule_type"] = rule_type
        rules = self.validation_rules.find(query).skip((page - 1) * page_size).limit(page_size)
        return list(rules)
    
    # ==================== 验证结果 ====================
    
    def save_validation_result(self, result: Dict[str, Any]) -> str:
        """保存验证结果
        
        Args:
            result: 验证结果
        
        Returns:
            str: 结果 ID
        """
        result_doc = self.validation_results.insert_one(result)
        return str(result_doc.inserted_id)
    
    def get_validation_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """获取验证结果
        
        Args:
            result_id: 结果 ID
        
        Returns:
            Optional[Dict]: 验证结果
        """
        return self.validation_results.find_one({"result_id": result_id})
    
    def list_validation_results(self, rule_id: str = None, 
                              page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """列出验证结果
        
        Args:
            rule_id: 规则 ID
            page: 页码
            page_size: 每页大小
        
        Returns:
            List[Dict]: 验证结果列表
        """
        query = {}
        if rule_id:
            query["rule_id"] = rule_id
        results = self.validation_results.find(query).skip((page - 1) * page_size).limit(page_size)
        return list(results)
    
    # ==================== 统计 ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            Dict: 统计信息
        """
        return {
            "ingest_records_count": self.ingest_records.count_documents({}),
            "audit_logs_count": self.audit_logs.count_documents({}),
            "build_results_count": self.build_results.count_documents({}),
            "ontology_documents_count": self.ontology_documents.count_documents({}),
            "versions_count": self.versions.count_documents({}),
            "validation_rules_count": self.validation_rules.count_documents({}),
            "validation_results_count": self.validation_results.count_documents({})
        }
    
    def close(self):
        """关闭连接"""
        self.client.close()