"""区块链管理接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.chain import Block, BlockChain, BlockStatus, ChainStatus


class IBlockChainManager(ABC):
    """区块链管理接口"""
    
    @abstractmethod
    def create_chain(self, name: str, validation_enabled: bool = True) -> BlockChain:
        """创建链
        
        Args:
            name: 链名称
            validation_enabled: 是否启用验证
            
        Returns:
            创建的链
        """
        pass
    
    @abstractmethod
    def get_chain(self, chain_id: str) -> Optional[BlockChain]:
        """获取链
        
        Args:
            chain_id: 链ID
            
        Returns:
            链对象
        """
        pass
    
    @abstractmethod
    def create_block(self, chain_id: str, logs: List[str]) -> Block:
        """创建区块
        
        Args:
            chain_id: 链ID
            logs: 日志ID列表
            
        Returns:
            创建的区块
        """
        pass
    
    @abstractmethod
    def get_block(self, block_id: str) -> Optional[Block]:
        """获取区块
        
        Args:
            block_id: 区块ID
            
        Returns:
            区块对象
        """
        pass
    
    @abstractmethod
    def add_logs_to_block(self, block_id: str, log_ids: List[str]) -> bool:
        """添加日志到区块
        
        Args:
            block_id: 区块ID
            log_ids: 日志ID列表
            
        Returns:
            是否添加成功
        """
        pass
    
    @abstractmethod
    def commit_block(self, block_id: str) -> bool:
        """提交区块
        
        Args:
            block_id: 区块ID
            
        Returns:
            是否提交成功
        """
        pass
    
    @abstractmethod
    def get_chain_blocks(self, chain_id: str) -> List[Block]:
        """获取链的区块
        
        Args:
            chain_id: 链ID
            
        Returns:
            区块列表
        """
        pass
    
    @abstractmethod
    def verify_chain(self, chain_id: str) -> Dict[str, Any]:
        """验证链
        
        Args:
            chain_id: 链ID
            
        Returns:
            验证结果
        """
        pass
    
    @abstractmethod
    def get_block_stats(self, chain_id: str) -> Dict[str, Any]:
        """获取区块统计
        
        Args:
            chain_id: 链ID
            
        Returns:
            区块统计信息
        """
        pass
