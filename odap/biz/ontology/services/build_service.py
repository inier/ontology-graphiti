"""本体构建服务"""

from typing import Dict, Any, List, Optional
from ..impl.builder import OntologyBuilder
from ..impl.audit import DataIngestAudit
from ..models.ontology import OntologyDocument, OntologyStatus


class OntologyBuildService:
    """本体构建服务"""
    
    def __init__(self):
        self.builder = OntologyBuilder()
        self.audit = DataIngestAudit()
    
    def build_from_ingest(self, ingest_id: str) -> Dict[str, Any]:
        """从数据摄入构建本体
        
        Args:
            ingest_id: 摄入任务ID
            
        Returns:
            构建结果
        """
        # 检查摄入任务状态
        ingest_record = self.audit.get_ingest_record(ingest_id)
        if not ingest_record:
            return {"status": "error", "message": "Ingest record not found"}
        
        if ingest_record.status.value != "completed":
            return {"status": "error", "message": "Ingest task not completed"}
        
        # 模拟从摄入数据中提取实体
        # 实际项目中应该从存储中获取摄入的数据
        sample_data = {
            "entities": [
                {"id": "1", "type": "Person", "name": "Alice"},
                {"id": "2", "type": "Person", "name": "Bob"},
                {"id": "3", "type": "Organization", "name": "Acme Corp"}
            ],
            "relations": [
                {"id": "1", "type": "WORKS_FOR", "source": "1", "target": "3"},
                {"id": "2", "type": "WORKS_FOR", "source": "2", "target": "3"}
            ]
        }
        
        # 提取实体
        extraction_result = self.builder.extract_entities(sample_data)
        
        # 构建本体
        build_result = self.builder.build_ontology(ingest_id, extraction_result)
        
        # 创建本体文档
        ontology_name = f"Ontology_{ingest_id[:8]}"
        ontology_doc = self.builder.create_ontology_document(
            name=ontology_name,
            description=f"Ontology built from ingest {ingest_id}"
        )
        
        # 更新本体文档内容
        updates = {
            "entities": extraction_result.entities,
            "relations": extraction_result.relations,
            "status": OntologyStatus.VALIDATED
        }
        updated_doc = self.builder.update_ontology_document(ontology_doc.id, updates)
        
        return {
            "status": "success",
            "build_id": build_result.build_id,
            "ontology_id": ontology_doc.id,
            "entity_count": build_result.entity_count,
            "relation_count": build_result.relation_count,
            "build_time": build_result.duration_seconds
        }
    
    def create_ontology(self, name: str, description: str = "") -> OntologyDocument:
        """创建本体
        
        Args:
            name: 本体名称
            description: 本体描述
            
        Returns:
            本体文档
        """
        return self.builder.create_ontology_document(name, description)
    
    def update_ontology(self, ontology_id: str, updates: Dict[str, Any]) -> OntologyDocument:
        """更新本体
        
        Args:
            ontology_id: 本体ID
            updates: 更新内容
            
        Returns:
            更新后的本体文档
        """
        return self.builder.update_ontology_document(ontology_id, updates)
    
    def get_ontology(self, ontology_id: str) -> Optional[OntologyDocument]:
        """获取本体
        
        Args:
            ontology_id: 本体ID
            
        Returns:
            本体文档
        """
        return self.builder.get_ontology_document(ontology_id)
    
    def list_ontologies(self, filters: Dict[str, Any] = None, 
                       page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """列出本体
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            本体列表和分页信息
        """
        docs = self.builder.list_ontology_documents(filters, page, page_size)
        
        ontologies = []
        for doc in docs:
            ontologies.append({
                "ontology_id": doc.id,
                "name": doc.name,
                "description": doc.description,
                "status": doc.status.value,
                "version": doc.version,
                "entity_count": len(doc.entities),
                "relation_count": len(doc.relations),
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat()
            })
        
        return {
            "ontologies": ontologies,
            "page": page,
            "page_size": page_size,
            "total": len(docs)  # 实际项目中应该返回总记录数
        }
    
    def validate_ontology(self, ontology_id: str) -> Dict[str, Any]:
        """验证本体
        
        Args:
            ontology_id: 本体ID
            
        Returns:
            验证结果
        """
        return self.builder.validate_ontology(ontology_id)
