"""日志验证接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.validation import ValidationResult, ValidationIssue


class ILogValidator(ABC):
    """日志验证接口"""
    
    @abstractmethod
    def validate_log_integrity(self, log_id: str) -> ValidationResult:
        """验证日志完整性
        
        Args:
            log_id: 日志ID
            
        Returns:
            验证结果
        """
        pass
    
    @abstractmethod
    def validate_block(self, block_id: str) -> ValidationResult:
        """验证区块
        
        Args:
            block_id: 区块ID
            
        Returns:
            验证结果
        """
        pass
    
    @abstractmethod
    def validate_chain(self, chain_id: str) -> ValidationResult:
        """验证链
        
        Args:
            chain_id: 链ID
            
        Returns:
            验证结果
        """
        pass
    
    @abstractmethod
    def detect_tampering(self, log_id: str) -> List[ValidationIssue]:
        """检测篡改
        
        Args:
            log_id: 日志ID
            
        Returns:
            篡改检测问题列表
        """
        pass
    
    @abstractmethod
    def verify_hash_chain(self, chain_id: str) -> Dict[str, Any]:
        """验证哈希链
        
        Args:
            chain_id: 链ID
            
        Returns:
            验证结果
        """
        pass
    
    @abstractmethod
    def get_validation_history(self, chain_id: str, 
                                start_time: str = None, 
                                end_time: str = None) -> List[ValidationResult]:
        """获取验证历史
        
        Args:
            chain_id: 链ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            验证结果列表
        """
        pass
