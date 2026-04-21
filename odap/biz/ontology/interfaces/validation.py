"""验证引擎接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.validation import ValidationRule, ValidationResult, ValidationIssue, ValidationSeverity


class IValidationEngine(ABC):
    """验证引擎接口"""
    
    @abstractmethod
    def add_validation_rule(self, rule: ValidationRule) -> ValidationRule:
        """添加验证规则
        
        Args:
            rule: 验证规则
            
        Returns:
            添加的验证规则
        """
        pass
    
    @abstractmethod
    def get_validation_rule(self, rule_id: str) -> Optional[ValidationRule]:
        """获取验证规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            验证规则
        """
        pass
    
    @abstractmethod
    def list_validation_rules(self, filters: Dict[str, Any] = None, 
                             page: int = 1, page_size: int = 10) -> List[ValidationRule]:
        """列出验证规则
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            验证规则列表
        """
        pass
    
    @abstractmethod
    def validate_ontology(self, ontology_id: str, 
                         rules: List[str] = None) -> ValidationResult:
        """验证本体
        
        Args:
            ontology_id: 本体ID
            rules: 规则ID列表
            
        Returns:
            验证结果
        """
        pass
    
    @abstractmethod
    def get_validation_result(self, result_id: str) -> Optional[ValidationResult]:
        """获取验证结果
        
        Args:
            result_id: 结果ID
            
        Returns:
            验证结果
        """
        pass
    
    @abstractmethod
    def list_validation_issues(self, ontology_id: str, 
                              severity: ValidationSeverity = None, 
                              start_time: Optional[str] = None, 
                              end_time: Optional[str] = None) -> List[ValidationIssue]:
        """列出验证问题
        
        Args:
            ontology_id: 本体ID
            severity: 严重程度
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            验证问题列表
        """
        pass
    
    @abstractmethod
    def fix_validation_issue(self, issue_id: str, fix_action: Dict[str, Any]) -> bool:
        """修复验证问题
        
        Args:
            issue_id: 问题ID
            fix_action: 修复动作
            
        Returns:
            是否修复成功
        """
        pass
