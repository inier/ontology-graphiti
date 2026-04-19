"""日志验证实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
from ..interfaces.validation import ILogValidator
from ..interfaces.storage import ILogStorage
from ..models.validation import ValidationResult, ValidationIssue, ValidationStatus


class LogValidator(ILogValidator):
    """日志验证实现"""
    
    def __init__(self, storage: ILogStorage):
        self.storage = storage
        self._validation_history: List[ValidationResult] = []
    
    def _compute_log_hash(self, log_data: Dict[str, Any]) -> str:
        """计算日志哈希"""
        content = f"{log_data.get('id')}{log_data.get('timestamp')}{log_data.get('level')}{log_data.get('type')}{log_data.get('service')}{log_data.get('action')}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def validate_log_integrity(self, log_id: str) -> ValidationResult:
        """验证日志完整性"""
        log = self.storage.get_log(log_id)
        if not log:
            return ValidationResult(
                block_id="",
                chain_id="",
                status=ValidationStatus.FAILED,
                is_valid=False
            )
        
        # 计算期望的哈希
        expected_hash = self._compute_log_hash(log.model_dump())
        stored_hash = log.details.get("hash", "")
        
        # 比较哈希
        is_valid = expected_hash == stored_hash
        
        result = ValidationResult(
            block_id=log.block_id or "",
            chain_id="",
            status=ValidationStatus.SUCCESS if is_valid else ValidationStatus.FAILED,
            is_valid=is_valid,
            end_time=datetime.now()
        )
        
        if not is_valid:
            result.issues.append({
                "type": "hash_mismatch",
                "severity": "critical",
                "message": "Log hash does not match",
                "details": {
                    "expected": expected_hash,
                    "stored": stored_hash
                }
            })
            result.issue_count = 1
        
        self._validation_history.append(result)
        return result
    
    def validate_block(self, block_id: str) -> ValidationResult:
        """验证区块"""
        # 实际项目中应该从存储中获取区块数据
        # 这里简化实现
        return ValidationResult(
            block_id=block_id,
            chain_id="",
            status=ValidationStatus.SUCCESS,
            is_valid=True
        )
    
    def validate_chain(self, chain_id: str) -> ValidationResult:
        """验证链"""
        # 实际项目中应该遍历链中的所有区块进行验证
        # 这里简化实现
        return ValidationResult(
            block_id="",
            chain_id=chain_id,
            status=ValidationStatus.SUCCESS,
            is_valid=True
        )
    
    def detect_tampering(self, log_id: str) -> List[ValidationIssue]:
        """检测篡改"""
        issues = []
        log = self.storage.get_log(log_id)
        
        if not log:
            return [ValidationIssue(
                validation_id="",
                block_id="",
                issue_type="log_not_found",
                severity="critical",
                message=f"Log {log_id} not found"
            )]
        
        # 检测哈希篡改
        expected_hash = self._compute_log_hash(log.model_dump())
        stored_hash = log.details.get("hash", "")
        
        if expected_hash != stored_hash:
            issues.append(ValidationIssue(
                validation_id="",
                block_id=log.block_id or "",
                issue_type="hash_tampering",
                severity="critical",
                message="Log hash has been tampered",
                details={"expected": expected_hash, "stored": stored_hash}
            ))
        
        return issues
    
    def verify_hash_chain(self, chain_id: str) -> Dict[str, Any]:
        """验证哈希链"""
        # 实际项目中应该验证区块之间的哈希链接
        return {
            "chain_id": chain_id,
            "is_valid": True,
            "verified_blocks": 0,
            "total_blocks": 0
        }
    
    def get_validation_history(self, chain_id: str, 
                                start_time: str = None, 
                                end_time: str = None) -> List[ValidationResult]:
        """获取验证历史"""
        history = [r for r in self._validation_history if r.chain_id == chain_id]
        
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            history = [r for r in history if r.start_time >= start_dt]
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            history = [r for r in history if r.start_time <= end_dt]
        
        return history
