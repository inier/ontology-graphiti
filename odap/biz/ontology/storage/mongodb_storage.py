"""本体模块 MongoDB 存储实现"""

from typing import Dict, Any, List, Optional, Union
from pymongo import MongoClient
from pymongo.collection import Collection
import os
import uuid
from datetime import datetime
from ..models.version import OntologyVersion, VersionStatus, VersionChange


class MongoDBStorage:
    """本体模块 MongoDB 存储实现 - 用于大型非结构化数据
    
    存储内容：
    - ontology_documents: 完整本体文档（包含实体、关系、事件等）
    - versions: 版本管理（完整版本历史数据）
    - process_logs: 详细处理日志（可选备份）
    
    当 MongoDB 不可用时，自动使用内存存储（仅用于测试）。
    """
    
    def __init__(self, connection_string: str = None):
        """初始化 MongoDB 存储
        
        Args:
            connection_string: MongoDB 连接字符串
        """
        self.connection_string = connection_string or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.use_memory = False
        self._memory_store: Dict[str, List] = {
            "ingest_records": [],
            "audit_logs": [],
            "build_results": [],
            "ontology_documents": [],
            "versions": [],
            "validation_rules": [],
            "validation_results": []
        }
        
        try:
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=2000)
            self.client.admin.command('ping')
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
        except Exception as e:
            print(f"MongoDB 存储初始化失败，使用内存存储: {e}")
            self.use_memory = True
    
    def _create_indexes(self):
        """创建必要的索引"""
        if self.use_memory:
            return
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
    
    def _version_to_dict(self, version: OntologyVersion) -> Dict[str, Any]:
        """将 OntologyVersion 对象转换为字典"""
        # 手动转换，确保所有值都是简单类型
        data = {
            "version_id": version.id,
            "ontology_id": version.ontology_id,
            "version_number": version.version_number,
            "parent_version_id": version.parent_version_id,
            "status": version.status.value if hasattr(version.status, "value") else str(version.status),
            "change_summary": version.change_summary,
            "created_at": version.created_at.isoformat() if hasattr(version.created_at, "isoformat") else str(version.created_at),
            "created_by": version.created_by,
            "is_current": version.is_current,
            "is_stable": version.is_stable,
            "ingest_id": version.ingest_id,
            "entity_count": version.entity_count,
            "relation_count": version.relation_count,
            "changes": [],
            "logs": []
        }
        return data
    
    def _dict_to_version(self, data: Dict[str, Any]) -> OntologyVersion:
        """将字典转换为 OntologyVersion 对象"""
        # 从 MongoDB 的 _id 字段提取 version_id（如果没有的话）
        if not data.get("version_id"):
            if data.get("_id"):
                data["id"] = str(data["_id"])
            elif not data.get("id"):
                data["id"] = str(uuid.uuid4())
        else:
            data["id"] = data["version_id"]
        
        # 转换 status
        if "status" in data and isinstance(data["status"], str):
            try:
                data["status"] = VersionStatus(data["status"])
            except ValueError:
                data["status"] = VersionStatus.DRAFT
        
        # 转换 created_at
        if "created_at" in data and isinstance(data["created_at"], str):
            try:
                data["created_at"] = datetime.fromisoformat(data["created_at"])
            except ValueError:
                data["created_at"] = datetime.now()
        
        # 转换 changes
        if "changes" in data and isinstance(data["changes"], list):
            changes = []
            for c in data["changes"]:
                if isinstance(c, dict):
                    if "timestamp" in c and isinstance(c["timestamp"], str):
                        try:
                            c["timestamp"] = datetime.fromisoformat(c["timestamp"])
                        except ValueError:
                            c["timestamp"] = datetime.now()
                    changes.append(VersionChange(**c))
            data["changes"] = changes
        
        return OntologyVersion(**data)
    
    # ==================== 摄入记录 ====================
    
    def save_ingest_record(self, record: Dict[str, Any]) -> str:
        """保存摄入记录
        
        Args:
            record: 摄入记录
        
        Returns:
            str: 记录 ID
        """
        if self.use_memory:
            record_id = f"mem_{len(self._memory_store['ingest_records'])}"
            record["_id"] = record_id
            self._memory_store["ingest_records"].append(record)
            return record_id
        result = self.ingest_records.insert_one(record)
        return str(result.inserted_id)
    
    def get_ingest_record(self, ingest_id: str) -> Optional[Dict[str, Any]]:
        """获取摄入记录
        
        Args:
            ingest_id: 摄入记录 ID
        
        Returns:
            Optional[Dict]: 摄入记录
        """
        if self.use_memory:
            for record in self._memory_store["ingest_records"]:
                if record.get("ingest_id") == ingest_id:
                    return record
            return None
        return self.ingest_records.find_one({"ingest_id": ingest_id})
    
    def update_ingest_record(self, ingest_id: str, updates: Dict[str, Any]) -> bool:
        """更新摄入记录
        
        Args:
            ingest_id: 摄入记录 ID
            updates: 更新内容
        
        Returns:
            bool: 是否更新成功
        """
        if self.use_memory:
            for i, record in enumerate(self._memory_store["ingest_records"]):
                if record.get("ingest_id") == ingest_id:
                    self._memory_store["ingest_records"][i].update(updates)
                    return True
            return False
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
        if self.use_memory:
            records = self._memory_store["ingest_records"]
            if filters:
                records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
            start = (page - 1) * page_size
            end = start + page_size
            return records[start:end]
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
        if self.use_memory:
            log_id = f"mem_{len(self._memory_store['audit_logs'])}"
            log["_id"] = log_id
            self._memory_store["audit_logs"].append(log)
            return log_id
        result = self.audit_logs.insert_one(log)
        return str(result.inserted_id)
    
    def get_audit_log(self, event_id: str) -> Optional[Dict[str, Any]]:
        """获取审计日志
        
        Args:
            event_id: 事件 ID
        
        Returns:
            Optional[Dict]: 审计日志
        """
        if self.use_memory:
            for log in self._memory_store["audit_logs"]:
                if log.get("event_id") == event_id:
                    return log
            return None
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
        if self.use_memory:
            logs = self._memory_store["audit_logs"]
            if filters:
                logs = [l for l in logs if all(l.get(k) == v for k, v in filters.items())]
            start = (page - 1) * page_size
            end = start + page_size
            return logs[start:end]
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
        if self.use_memory:
            result_id = f"mem_{len(self._memory_store['build_results'])}"
            result["_id"] = result_id
            self._memory_store["build_results"].append(result)
            return result_id
        result_doc = self.build_results.insert_one(result)
        return str(result_doc.inserted_id)
    
    def get_build_result(self, build_id: str) -> Optional[Dict[str, Any]]:
        """获取构建结果
        
        Args:
            build_id: 构建 ID
        
        Returns:
            Optional[Dict]: 构建结果
        """
        if self.use_memory:
            for r in self._memory_store["build_results"]:
                if r.get("build_id") == build_id:
                    return r
            return None
        return self.build_results.find_one({"build_id": build_id})
    
    def update_build_result(self, build_id: str, updates: Dict[str, Any]) -> bool:
        """更新构建结果
        
        Args:
            build_id: 构建 ID
            updates: 更新内容
        
        Returns:
            bool: 是否更新成功
        """
        if self.use_memory:
            for i, r in enumerate(self._memory_store["build_results"]):
                if r.get("build_id") == build_id:
                    self._memory_store["build_results"][i].update(updates)
                    return True
            return False
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
        if self.use_memory:
            doc_id = f"mem_{len(self._memory_store['ontology_documents'])}"
            document["_id"] = doc_id
            self._memory_store["ontology_documents"].append(document)
            return doc_id
        result = self.ontology_documents.insert_one(document)
        return str(result.inserted_id)
    
    def get_ontology_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取本体文档
        
        Args:
            document_id: 文档 ID
        
        Returns:
            Optional[Dict]: 本体文档
        """
        if self.use_memory:
            for doc in self._memory_store["ontology_documents"]:
                if doc.get("document_id") == document_id:
                    return doc
            return None
        return self.ontology_documents.find_one({"document_id": document_id})
    
    def update_ontology_document(self, document_id: str, updates: Dict[str, Any]) -> bool:
        """更新本体文档
        
        Args:
            document_id: 文档 ID
            updates: 更新内容
        
        Returns:
            bool: 是否更新成功
        """
        if self.use_memory:
            for i, doc in enumerate(self._memory_store["ontology_documents"]):
                if doc.get("document_id") == document_id:
                    self._memory_store["ontology_documents"][i].update(updates)
                    return True
            return False
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
        if self.use_memory:
            docs = self._memory_store["ontology_documents"]
            if filters:
                docs = [d for d in docs if all(d.get(k) == v for k, v in filters.items())]
            start = (page - 1) * page_size
            end = start + page_size
            return docs[start:end]
        query = filters or {}
        documents = self.ontology_documents.find(query).skip((page - 1) * page_size).limit(page_size)
        return list(documents)
    
    # ==================== 版本 ====================
    
    def save_version(self, version: Union[Dict[str, Any], OntologyVersion]) -> str:
        """保存版本信息
        
        Args:
            version: 版本信息（Dict 或 OntologyVersion 对象）
        
        Returns:
            str: 版本 ID
        """
        # 转换对象为字典
        if isinstance(version, OntologyVersion):
            version_dict = self._version_to_dict(version)
            # 确保有 version_id 字段
            version_dict["version_id"] = version_dict.get("id") or str(uuid.uuid4())
        else:
            version_dict = version
            if not version_dict.get("version_id"):
                version_dict["version_id"] = str(uuid.uuid4())
        
        if self.use_memory:
            version_dict["_id"] = version_dict["version_id"]
            self._memory_store["versions"].append(version_dict)
            return version_dict["version_id"]
        
        # MongoDB 存储
        result = self.versions.insert_one(version_dict)
        return version_dict["version_id"]
    
    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        """获取版本信息
        
        Args:
            version_id: 版本 ID
        
        Returns:
            Optional[OntologyVersion]: 版本信息
        """
        if self.use_memory:
            for v in self._memory_store["versions"]:
                if v.get("version_id") == version_id:
                    return self._dict_to_version(v)
            return None
        
        data = self.versions.find_one({"version_id": version_id})
        if data:
            return self._dict_to_version(data)
        return None
    
    def update_version(self, version: Union[Dict[str, Any], OntologyVersion]) -> bool:
        """更新版本信息
        
        Args:
            version: 版本信息（Dict 或 OntologyVersion 对象）
        
        Returns:
            bool: 是否成功
        """
        if isinstance(version, OntologyVersion):
            version_dict = self._version_to_dict(version)
            version_id = version.id
        else:
            version_dict = version
            version_id = version.get("version_id") or version.get("id")
        
        if not version_id:
            return False
        
        if self.use_memory:
            for i, v in enumerate(self._memory_store["versions"]):
                if v.get("version_id") == version_id:
                    self._memory_store["versions"][i] = version_dict
                    return True
            return False
        
        result = self.versions.update_one(
            {"version_id": version_id},
            {"$set": version_dict}
        )
        return result.modified_count > 0
    
    def list_versions(self, ontology_id: str, 
                     page: int = 1, page_size: int = 10) -> List[OntologyVersion]:
        """列出版本信息

        Args:
            ontology_id: 本体 ID
            page: 页码
            page_size: 每页大小

        Returns:
            List[OntologyVersion]: 版本信息列表
        """
        if self.use_memory:
            versions = [v for v in self._memory_store["versions"] if v.get("ontology_id") == ontology_id]
            start = (page - 1) * page_size
            end = start + page_size
            return [self._dict_to_version(v) for v in versions[start:end]]
        
        query = {"ontology_id": ontology_id}
        cursor = self.versions.find(query).skip((page - 1) * page_size).limit(page_size)
        return [self._dict_to_version(data) for data in cursor]
    
    def get_versions(self, scenario_id: Optional[str] = None, 
                     limit: int = 50) -> List[OntologyVersion]:
        """获取版本列表（支持按场景过滤）

        Args:
            scenario_id: 场景 ID
            limit: 限制数量

        Returns:
            List[OntologyVersion]: 版本信息列表
        """
        if self.use_memory:
            versions = self._memory_store["versions"]
            if scenario_id:
                versions = [v for v in versions if v.get("scenario_id") == scenario_id]
            return [self._dict_to_version(v) for v in versions[:limit]]
        
        query = {} if not scenario_id else {"scenario_id": scenario_id}
        cursor = self.versions.find(query).limit(limit)
        return [self._dict_to_version(data) for data in cursor]
    
    def unset_current_version(self, scenario_id: str) -> bool:
        """取消场景当前版本的标记
        
        Args:
            scenario_id: 场景 ID
        
        Returns:
            bool: 是否成功
        """
        if self.use_memory:
            for v in self._memory_store["versions"]:
                if v.get("scenario_id") == scenario_id and v.get("is_current"):
                    v["is_current"] = False
            return True
        
        self.versions.update_many(
            {"scenario_id": scenario_id},
            {"$set": {"is_current": False}}
        )
        return True
    
    def bind_version(self, version_id: str, scenario_id: str, is_current: bool = True) -> bool:
        """绑定版本到场景
        
        Args:
            version_id: 版本 ID
            scenario_id: 场景 ID
            is_current: 是否设为当前版本
        
        Returns:
            bool: 是否成功
        """
        if self.use_memory:
            for v in self._memory_store["versions"]:
                if v.get("version_id") == version_id:
                    v["scenario_id"] = scenario_id
                    v["is_current"] = is_current
                    return True
            return False
        
        result = self.versions.update_one(
            {"version_id": version_id},
            {"$set": {"scenario_id": scenario_id, "is_current": is_current}}
        )
        return result.modified_count > 0
    
    def get_scenarios_by_version(self, version_id: str) -> List[Dict[str, Any]]:
        """获取版本绑定的场景
        
        Args:
            version_id: 版本 ID
        
        Returns:
            List[Dict]: 场景列表
        """
        if self.use_memory:
            for v in self._memory_store["versions"]:
                if v.get("version_id") == version_id and v.get("scenario_id"):
                    return [{"scenario_id": v["scenario_id"], "is_current": v.get("is_current", False)}]
            return []
        
        data = self.versions.find_one({"version_id": version_id})
        if data and data.get("scenario_id"):
            return [{"scenario_id": data["scenario_id"], "is_current": data.get("is_current", False)}]
        return []
    
    def get_versions_by_scenario(self, scenario_id: str) -> List[OntologyVersion]:
        """获取场景绑定的所有版本
        
        Args:
            scenario_id: 场景 ID
        
        Returns:
            List[OntologyVersion]: 版本列表
        """
        return self.get_versions(scenario_id=scenario_id)
    
    def unbind_version(self, version_id: str, scenario_id: str) -> bool:
        """解绑版本和场景
        
        Args:
            version_id: 版本 ID
            scenario_id: 场景 ID
        
        Returns:
            bool: 是否成功
        """
        if self.use_memory:
            for v in self._memory_store["versions"]:
                if v.get("version_id") == version_id and v.get("scenario_id") == scenario_id:
                    v.pop("scenario_id", None)
                    v["is_current"] = False
                    return True
            return False
        
        result = self.versions.update_one(
            {"version_id": version_id, "scenario_id": scenario_id},
            {"$unset": {"scenario_id": ""}, "$set": {"is_current": False}}
        )
        return result.modified_count > 0
    
    # ==================== 验证规则 ====================
    
    def save_validation_rule(self, rule: Dict[str, Any]) -> str:
        """保存验证规则
        
        Args:
            rule: 验证规则
        
        Returns:
            str: 规则 ID
        """
        if self.use_memory:
            rule_id = f"mem_{len(self._memory_store['validation_rules'])}"
            rule["_id"] = rule_id
            self._memory_store["validation_rules"].append(rule)
            return rule_id
        result = self.validation_rules.insert_one(rule)
        return str(result.inserted_id)
    
    def get_validation_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """获取验证规则
        
        Args:
            rule_id: 规则 ID
        
        Returns:
            Optional[Dict]: 验证规则
        """
        if self.use_memory:
            for r in self._memory_store["validation_rules"]:
                if r.get("rule_id") == rule_id:
                    return r
            return None
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
        if self.use_memory:
            rules = self._memory_store["validation_rules"]
            if rule_type:
                rules = [r for r in rules if r.get("rule_type") == rule_type]
            start = (page - 1) * page_size
            end = start + page_size
            return rules[start:end]
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
        if self.use_memory:
            result_id = f"mem_{len(self._memory_store['validation_results'])}"
            result["_id"] = result_id
            self._memory_store["validation_results"].append(result)
            return result_id
        result_doc = self.validation_results.insert_one(result)
        return str(result_doc.inserted_id)
    
    def get_validation_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """获取验证结果
        
        Args:
            result_id: 结果 ID
        
        Returns:
            Optional[Dict]: 验证结果
        """
        if self.use_memory:
            for r in self._memory_store["validation_results"]:
                if r.get("result_id") == result_id:
                    return r
            return None
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
        if self.use_memory:
            results = self._memory_store["validation_results"]
            if rule_id:
                results = [r for r in results if r.get("rule_id") == rule_id]
            start = (page - 1) * page_size
            end = start + page_size
            return results[start:end]
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
        if self.use_memory:
            return {
                "ingest_records_count": len(self._memory_store["ingest_records"]),
                "audit_logs_count": len(self._memory_store["audit_logs"]),
                "build_results_count": len(self._memory_store["build_results"]),
                "ontology_documents_count": len(self._memory_store["ontology_documents"]),
                "versions_count": len(self._memory_store["versions"]),
                "validation_rules_count": len(self._memory_store["validation_rules"]),
                "validation_results_count": len(self._memory_store["validation_results"])
            }
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
        if not self.use_memory and hasattr(self, 'client'):
            self.client.close()