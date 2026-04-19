"""验证服务"""

from typing import Dict, Any, List, Optional
from ..impl.validation import LogValidator
from ..impl.chain import BlockChainManager
from ..impl.storage import LogStorage


class ValidationService:
    """验证服务"""
    
    def __init__(self):
        self.storage = LogStorage()
        self.validator = LogValidator(storage=self.storage)
        self.chain_manager = BlockChainManager()
    
    def validate_log(self, log_id: str) -> Dict[str, Any]:
        """验证日志完整性
        
        Args:
            log_id: 日志ID
            
        Returns:
            验证结果
        """
        result = self.validator.validate_log_integrity(log_id)
        
        return {
            "validation_id": result.id,
            "block_id": result.block_id,
            "chain_id": result.chain_id,
            "status": result.status.value,
            "is_valid": result.is_valid,
            "issue_count": result.issue_count,
            "issues": result.issues
        }
    
    def validate_block(self, block_id: str) -> Dict[str, Any]:
        """验证区块
        
        Args:
            block_id: 区块ID
            
        Returns:
            验证结果
        """
        result = self.validator.validate_block(block_id)
        
        return {
            "validation_id": result.id,
            "block_id": result.block_id,
            "chain_id": result.chain_id,
            "status": result.status.value,
            "is_valid": result.is_valid,
            "issue_count": result.issue_count
        }
    
    def validate_chain(self, chain_id: str) -> Dict[str, Any]:
        """验证链
        
        Args:
            chain_id: 链ID
            
        Returns:
            验证结果
        """
        result = self.validator.validate_chain(chain_id)
        
        return {
            "validation_id": result.id,
            "chain_id": result.chain_id,
            "status": result.status.value,
            "is_valid": result.is_valid,
            "issue_count": result.issue_count
        }
    
    def detect_tampering(self, log_id: str) -> Dict[str, Any]:
        """检测篡改
        
        Args:
            log_id: 日志ID
            
        Returns:
            篡改检测结果
        """
        issues = self.validator.detect_tampering(log_id)
        
        issue_list = []
        for issue in issues:
            issue_list.append({
                "issue_id": issue.id,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "message": issue.message,
                "details": issue.details
            })
        
        return {
            "log_id": log_id,
            "issue_count": len(issue_list),
            "issues": issue_list
        }
    
    def verify_hash_chain(self, chain_id: str) -> Dict[str, Any]:
        """验证哈希链
        
        Args:
            chain_id: 链ID
            
        Returns:
            验证结果
        """
        return self.validator.verify_hash_chain(chain_id)
    
    def create_chain(self, name: str, validation_enabled: bool = True) -> Dict[str, Any]:
        """创建链
        
        Args:
            name: 链名称
            validation_enabled: 是否启用验证
            
        Returns:
            创建的链信息
        """
        chain = self.chain_manager.create_chain(name, validation_enabled)
        
        return {
            "chain_id": chain.id,
            "name": chain.name,
            "status": chain.status.value,
            "validation_enabled": chain.validation_enabled,
            "created_at": chain.created_at.isoformat()
        }
    
    def create_block(self, chain_id: str, log_ids: List[str]) -> Dict[str, Any]:
        """创建区块
        
        Args:
            chain_id: 链ID
            log_ids: 日志ID列表
            
        Returns:
            创建的区块信息
        """
        try:
            block = self.chain_manager.create_block(chain_id, log_ids)
            
            return {
                "block_id": block.id,
                "chain_id": block.chain_id,
                "log_count": block.log_count,
                "status": block.status.value,
                "previous_hash": block.previous_hash,
                "current_hash": block.current_hash,
                "created_at": block.created_at.isoformat()
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def commit_block(self, block_id: str) -> Dict[str, Any]:
        """提交区块
        
        Args:
            block_id: 区块ID
            
        Returns:
            提交结果
        """
        success = self.chain_manager.commit_block(block_id)
        
        return {
            "status": "success" if success else "error",
            "block_id": block_id
        }
    
    def verify_chain(self, chain_id: str) -> Dict[str, Any]:
        """验证链
        
        Args:
            chain_id: 链ID
            
        Returns:
            验证结果
        """
        return self.chain_manager.verify_chain(chain_id)
    
    def get_chain_stats(self, chain_id: str) -> Dict[str, Any]:
        """获取链统计
        
        Args:
            chain_id: 链ID
            
        Returns:
            链统计信息
        """
        return self.chain_manager.get_block_stats(chain_id)
