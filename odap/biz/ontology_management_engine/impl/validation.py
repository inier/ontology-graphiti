"""验证引擎实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.validation import IValidationEngine
from ..models.validation import ValidationRule, ValidationResult, ValidationIssue, ValidationSeverity
from ..storage.mongodb_storage import MongoDBStorage


class ValidationEngine(IValidationEngine):
    """验证引擎实现"""
    
    def __init__(self):
        self.storage = MongoDBStorage()
    
    def add_validation_rule(self, rule: ValidationRule) -> ValidationRule:
        """添加验证规则"""
        self.storage.save_validation_rule(rule)
        return rule
    
    def get_validation_rule(self, rule_id: str) -> Optional[ValidationRule]:
        """获取验证规则"""
        return self.storage.get_validation_rule(rule_id)
    
    def list_validation_rules(self, filters: Dict[str, Any] = None, 
                             page: int = 1, page_size: int = 10) -> List[ValidationRule]:
        """列出验证规则"""
        return self.storage.list_validation_rules(filters, page, page_size)
    
    def validate_ontology(self, ontology_id: str, 
                         rules: List[str] = None) -> ValidationResult:
        """验证本体"""
        start_time = datetime.now()
        result = ValidationResult(
            ontology_id=ontology_id,
            ontology_version="1.0.0",  # 需要从本体文档中获取
            status="running"
        )
        
        # 获取验证规则
        if rules:
            validation_rules = [self.get_validation_rule(rule_id) for rule_id in rules]
            validation_rules = [rule for rule in validation_rules if rule and rule.enabled]
        else:
            validation_rules = self.list_validation_rules({"enabled": True})
        
        # 执行验证
        errors = []
        warnings = []
        info = []
        
        # 这里实现验证逻辑
        # 实际项目中需要根据规则执行验证
        for rule in validation_rules:
            # 简单的示例验证
            issue = ValidationIssue(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"Validation issue for rule: {rule.name}"
            )
            
            if rule.severity == ValidationSeverity.ERROR:
                errors.append(issue.model_dump())
            elif rule.severity == ValidationSeverity.WARNING:
                warnings.append(issue.model_dump())
            else:
                info.append(issue.model_dump())
        
        # 完成验证
        result.status = "complete"
        result.errors = errors
        result.warnings = warnings
        result.info = info
        result.error_count = len(errors)
        result.warning_count = len(warnings)
        result.info_count = len(info)
        result.overall_score = max(0, 1 - (len(errors) * 0.5 + len(warnings) * 0.2) / len(validation_rules)) if validation_rules else 1.0
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        
        self.storage.save_validation_result(result)
        
        return result
    
    def get_validation_result(self, result_id: str) -> Optional[ValidationResult]:
        """获取验证结果"""
        return self.storage.get_validation_result(result_id)
    
    def list_validation_issues(self, ontology_id: str, 
                              severity: ValidationSeverity = None, 
                              start_time: Optional[str] = None, 
                              end_time: Optional[str] = None) -> List[ValidationIssue]:
        """列出验证问题"""
        # 这里实现获取验证问题的逻辑
        return []
    
    def fix_validation_issue(self, issue_id: str, fix_action: Dict[str, Any]) -> bool:
        """修复验证问题"""
        # 这里实现修复逻辑
        return True
