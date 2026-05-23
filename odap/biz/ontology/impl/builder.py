"""本体构建实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.builder import IOntologyBuilder
from ..models.ontology import EntityExtractionResult, OntologyBuildResult, OntologyDocument
from ..models.audit import ProcessingStatus
from ..storage.sqlite_ingest_storage import SQLiteIngestStorage


class OntologyBuilder(IOntologyBuilder):
    """本体构建实现"""
    
    def __init__(self):
        self.storage = SQLiteIngestStorage()
    
    def extract_entities(self, data: Dict[str, Any]) -> EntityExtractionResult:
        """提取实体"""
        # 这里实现实体提取逻辑
        # 实际项目中可能会使用NLP模型或规则引擎
        entities = []
        relations = []
        confidence_scores = {}
        
        # 简单的示例实现
        if 'entities' in data:
            entities = data['entities']
        if 'relations' in data:
            relations = data['relations']
        
        return EntityExtractionResult(
            entities=entities,
            relations=relations,
            confidence_scores=confidence_scores,
            processing_time=0.1
        )
    
    def build_ontology(self, ingest_id: str, extracted_data: EntityExtractionResult) -> OntologyBuildResult:
        """构建本体"""
        result = OntologyBuildResult(
            source_ingest_id=ingest_id,
            entity_count=len(extracted_data.entities),
            relation_count=len(extracted_data.relations),
            property_count=0,  # 需要根据实际情况计算
            status=ProcessingStatus.COMPLETED
        )
        result.end_time = datetime.now()
        result.duration_seconds = (result.end_time - result.start_time).total_seconds()
        
        # 转换为字典并保存构建结果
        result_dict = result.model_dump()
        self.storage.save_build_result(result_dict)
        
        return result
    
    def create_ontology_document(self, name: str, description: str = "") -> OntologyDocument:
        """创建本体文档"""
        doc = OntologyDocument(
            name=name,
            description=description
        )
        
        # 转换为字典并保存到 MongoDB
        doc_dict = doc.model_dump()
        # 确保有 document_id 字段
        doc_dict["document_id"] = doc_dict["id"]
        self.storage.save_ontology_document(doc_dict)
        
        return doc
    
    def update_ontology_document(self, ontology_id: str, updates: Dict[str, Any]) -> OntologyDocument:
        """更新本体文档"""
        doc = self.get_ontology_document(ontology_id)
        if doc:
            for key, value in updates.items():
                if hasattr(doc, key):
                    setattr(doc, key, value)
            doc.updated_at = datetime.now()
            
            # 转换为字典并更新
            doc_dict = doc.model_dump()
            doc_dict["document_id"] = doc_dict["id"]
            self.storage.update_ontology_document(ontology_id, doc_dict)
        
        return doc
    
    def get_ontology_document(self, ontology_id: str) -> Optional[OntologyDocument]:
        """获取本体文档"""
        doc_dict = self.storage.get_ontology_document(ontology_id)
        if doc_dict:
            # 将 MongoDB 的 document_id 映射回 id
            if 'document_id' in doc_dict and 'id' not in doc_dict:
                doc_dict['id'] = doc_dict['document_id']
            return OntologyDocument(**doc_dict)
        return None
    
    def list_ontology_documents(self, filters: Dict[str, Any] = None, 
                               page: int = 1, page_size: int = 10) -> List[OntologyDocument]:
        """列出本体文档"""
        doc_dicts = self.storage.list_ontology_documents(filters, page, page_size)
        docs = []
        for doc_dict in doc_dicts:
            # 将 MongoDB 的 document_id 映射回 id
            if 'document_id' in doc_dict and 'id' not in doc_dict:
                doc_dict['id'] = doc_dict['document_id']
            docs.append(OntologyDocument(**doc_dict))
        return docs
    
    def validate_ontology(self, ontology_id: str) -> Dict[str, Any]:
        """验证本体"""
        # 这里实现本体验证逻辑
        doc = self.get_ontology_document(ontology_id)
        if not doc:
            return {
                "status": "error",
                "message": "Ontology not found"
            }
        
        # 简单的验证逻辑
        issues = []
        if not doc.entities:
            issues.append("No entities defined")
        if not doc.relations:
            issues.append("No relations defined")
        
        return {
            "status": "success",
            "issues": issues,
            "entity_count": len(doc.entities),
            "relation_count": len(doc.relations)
        }
