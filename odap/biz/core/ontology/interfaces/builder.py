"""本体构建接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.ontology import EntityExtractionResult, OntologyBuildResult, OntologyDocument


class IOntologyBuilder(ABC):
    """本体构建接口"""
    
    @abstractmethod
    def extract_entities(self, data: Dict[str, Any]) -> EntityExtractionResult:
        """提取实体
        
        Args:
            data: 输入数据
            
        Returns:
            实体提取结果
        """
        pass
    
    @abstractmethod
    def build_ontology(self, ingest_id: str, extracted_data: EntityExtractionResult) -> OntologyBuildResult:
        """构建本体
        
        Args:
            ingest_id: 摄入任务ID
            extracted_data: 提取的实体数据
            
        Returns:
            本体构建结果
        """
        pass
    
    @abstractmethod
    def create_ontology_document(self, name: str, description: str = "") -> OntologyDocument:
        """创建本体文档
        
        Args:
            name: 本体名称
            description: 本体描述
            
        Returns:
            本体文档
        """
        pass
    
    @abstractmethod
    def update_ontology_document(self, ontology_id: str, updates: Dict[str, Any]) -> OntologyDocument:
        """更新本体文档
        
        Args:
            ontology_id: 本体ID
            updates: 更新内容
            
        Returns:
            更新后的本体文档
        """
        pass
    
    @abstractmethod
    def get_ontology_document(self, ontology_id: str) -> Optional[OntologyDocument]:
        """获取本体文档
        
        Args:
            ontology_id: 本体ID
            
        Returns:
            本体文档
        """
        pass
    
    @abstractmethod
    def list_ontology_documents(self, filters: Dict[str, Any] = None, 
                               page: int = 1, page_size: int = 10) -> List[OntologyDocument]:
        """列出本体文档
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            本体文档列表
        """
        pass
    
    @abstractmethod
    def validate_ontology(self, ontology_id: str) -> Dict[str, Any]:
        """验证本体
        
        Args:
            ontology_id: 本体ID
            
        Returns:
            验证结果
        """
        pass
