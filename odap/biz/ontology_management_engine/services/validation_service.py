"""验证服务"""

from typing import Dict, Any, List, Optional
from ..impl.validation import ValidationEngine
from ..models.validation import ValidationRule, ValidationSeverity


class ValidationService:
    """验证服务"""
    
    def __init__(self):
        self.engine = ValidationEngine()
    
    def add_validation_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """添加验证规则
        
        Args:
            rule_data: 规则数据
            
        Returns:
            添加的规则信息
        """
        rule = ValidationRule(**rule_data)
        saved_rule = self.engine.add_validation_rule(rule)
        
        return {
            "rule_id": saved_rule.id,
            "name": saved_rule.name,
            "description": saved_rule.description,
            "rule_type": saved_rule.rule_type,
            "severity": saved_rule.severity.value,
            "expression": saved_rule.expression,
            "enabled": saved_rule.enabled
        }
    
    def get_validation_rule(self, rule_id: str) -> Dict[str, Any]:
        """获取验证规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            规则信息
        """
        rule = self.engine.get_validation_rule(rule_id)
        if not rule:
            return {"status": "error", "message": "Rule not found"}
        
        return {
            "rule_id": rule.id,
            "name": rule.name,
            "description": rule.description,
            "rule_type": rule.rule_type,
            "severity": rule.severity.value,
            "expression": rule.expression,
            "params": rule.params,
            "enabled": rule.enabled
        }
    
    def list_validation_rules(self, filters: Dict[str, Any] = None, 
                             page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """列出验证规则
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            规则列表和分页信息
        """
        rules = self.engine.list_validation_rules(filters, page, page_size)
        
        rule_list = []
        for rule in rules:
            rule_list.append({
                "rule_id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "rule_type": rule.rule_type,
                "severity": rule.severity.value,
                "enabled": rule.enabled
            })
        
        return {
            "rules": rule_list,
            "page": page,
            "page_size": page_size,
            "total": len(rules)  # 实际项目中应该返回总记录数
        }
    
    def validate_ontology(self, ontology_id: str, 
                         rules: List[str] = None) -> Dict[str, Any]:
        """验证本体
        
        Args:
            ontology_id: 本体ID
            rules: 规则ID列表
            
        Returns:
            验证结果
        """
        result = self.engine.validate_ontology(ontology_id, rules)
        
        return {
            "result_id": result.id,
            "ontology_id": result.ontology_id,
            "ontology_version": result.ontology_version,
            "status": result.status,
            "error_count": result.error_count,
            "warning_count": result.warning_count,
            "info_count": result.info_count,
            "overall_score": result.overall_score,
            "duration_seconds": result.duration_seconds,
            "validation_time": result.validation_time.isoformat(),
            "errors": result.errors,
            "warnings": result.warnings,
            "info": result.info
        }
    
    def get_validation_result(self, result_id: str) -> Dict[str, Any]:
        """获取验证结果
        
        Args:
            result_id: 结果ID
            
        Returns:
            验证结果信息
        """
        result = self.engine.get_validation_result(result_id)
        if not result:
            return {"status": "error", "message": "Result not found"}
        
        return {
            "result_id": result.id,
            "ontology_id": result.ontology_id,
            "ontology_version": result.ontology_version,
            "status": result.status,
            "error_count": result.error_count,
            "warning_count": result.warning_count,
            "info_count": result.info_count,
            "overall_score": result.overall_score,
            "duration_seconds": result.duration_seconds,
            "validation_time": result.validation_time.isoformat()
        }
    
    def list_validation_issues(self, ontology_id: str, 
                              severity: Optional[str] = None, 
                              start_time: Optional[str] = None, 
                              end_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出验证问题
        
        Args:
            ontology_id: 本体ID
            severity: 严重程度
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            验证问题列表
        """
        severity_enum = ValidationSeverity(severity) if severity else None
        issues = self.engine.list_validation_issues(
            ontology_id=ontology_id,
            severity=severity_enum,
            start_time=start_time,
            end_time=end_time
        )
        
        issue_list = []
        for issue in issues:
            issue_list.append({
                "issue_id": issue.id,
                "rule_id": issue.rule_id,
                "rule_name": issue.rule_name,
                "severity": issue.severity.value,
                "entity_id": issue.entity_id,
                "relation_id": issue.relation_id,
                "property_name": issue.property_name,
                "message": issue.message,
                "details": issue.details,
                "timestamp": issue.timestamp.isoformat()
            })
        
        return issue_list
    
    def fix_validation_issue(self, issue_id: str, fix_action: Dict[str, Any]) -> Dict[str, Any]:
        """修复验证问题
        
        Args:
            issue_id: 问题ID
            fix_action: 修复动作
            
        Returns:
            修复结果
        """
        success = self.engine.fix_validation_issue(issue_id, fix_action)
        
        return {
            "status": "success" if success else "error",
            "issue_id": issue_id
        }
