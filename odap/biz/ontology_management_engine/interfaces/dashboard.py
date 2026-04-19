"""审计仪表盘接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime


class IAuditDashboard(ABC):
    """审计仪表盘接口"""
    
    @abstractmethod
    def get_ingest_summary(self, start_time: Optional[datetime] = None, 
                          end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """获取摄入摘要
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            摄入摘要统计
        """
        pass
    
    @abstractmethod
    def get_ontology_summary(self, status: Optional[str] = None) -> Dict[str, Any]:
        """获取本体摘要
        
        Args:
            status: 状态过滤
            
        Returns:
            本体摘要统计
        """
        pass
    
    @abstractmethod
    def get_validation_summary(self, start_time: Optional[datetime] = None, 
                              end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """获取验证摘要
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            验证摘要统计
        """
        pass
    
    @abstractmethod
    def get_version_summary(self, ontology_id: Optional[str] = None) -> Dict[str, Any]:
        """获取版本摘要
        
        Args:
            ontology_id: 本体ID
            
        Returns:
            版本摘要统计
        """
        pass
    
    @abstractmethod
    def get_performance_metrics(self, start_time: Optional[datetime] = None, 
                               end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """获取性能指标
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            性能指标
        """
        pass
    
    @abstractmethod
    def get_error_trends(self, start_time: Optional[datetime] = None, 
                        end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """获取错误趋势
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            错误趋势数据
        """
        pass
    
    @abstractmethod
    def get_top_issues(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取top问题
        
        Args:
            limit: 限制数量
            
        Returns:
            top问题列表
        """
        pass
