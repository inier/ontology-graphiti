"""区块链管理实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import uuid
from ..interfaces.chain import IBlockChainManager
from ..models.chain import Block, BlockChain, BlockStatus, ChainStatus


class BlockChainManager(IBlockChainManager):
    """区块链管理实现"""
    
    def __init__(self):
        self._chains: Dict[str, BlockChain] = {}
        self._blocks: Dict[str, Block] = {}
    
    def _compute_block_hash(self, block: Block) -> str:
        """计算区块哈希"""
        content = f"{block.id}{block.chain_id}{block.previous_hash}{block.timestamp.isoformat()}{len(block.logs)}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def create_chain(self, name: str, validation_enabled: bool = True) -> BlockChain:
        """创建链"""
        chain = BlockChain(
            name=name,
            validation_enabled=validation_enabled,
            status=ChainStatus.ACTIVE
        )
        self._chains[chain.id] = chain
        return chain
    
    def get_chain(self, chain_id: str) -> Optional[BlockChain]:
        """获取链"""
        return self._chains.get(chain_id)
    
    def create_block(self, chain_id: str, logs: List[str]) -> Block:
        """创建区块"""
        chain = self._chains.get(chain_id)
        if not chain:
            raise ValueError("Chain not found")
        
        # 获取上一个区块的哈希
        previous_hash = chain.last_block_hash or "0" * 64
        
        block = Block(
            chain_id=chain_id,
            previous_hash=previous_hash,
            current_hash="",  # 稍后计算
            logs=logs,
            log_count=len(logs),
            status=BlockStatus.PENDING
        )
        
        # 计算当前区块的哈希
        block.current_hash = self._compute_block_hash(block)
        
        # 保存区块
        self._blocks[block.id] = block
        
        # 更新链
        chain.block_count += 1
        chain.last_block_id = block.id
        chain.last_block_hash = block.current_hash
        chain.updated_at = datetime.now()
        
        return block
    
    def get_block(self, block_id: str) -> Optional[Block]:
        """获取区块"""
        return self._blocks.get(block_id)
    
    def add_logs_to_block(self, block_id: str, log_ids: List[str]) -> bool:
        """添加日志到区块"""
        block = self._blocks.get(block_id)
        if not block or block.status != BlockStatus.PENDING:
            return False
        
        block.logs.extend(log_ids)
        block.log_count = len(block.logs)
        block.current_hash = self._compute_block_hash(block)
        block.updated_at = datetime.now()
        return True
    
    def commit_block(self, block_id: str) -> bool:
        """提交区块"""
        block = self._blocks.get(block_id)
        if not block:
            return False
        
        block.status = BlockStatus.COMMITTED
        block.updated_at = datetime.now()
        return True
    
    def get_chain_blocks(self, chain_id: str) -> List[Block]:
        """获取链的区块"""
        return [b for b in self._blocks.values() if b.chain_id == chain_id]
    
    def verify_chain(self, chain_id: str) -> Dict[str, Any]:
        """验证链"""
        chain = self._chains.get(chain_id)
        if not chain:
            return {"status": "error", "message": "Chain not found"}
        
        blocks = self.get_chain_blocks(chain_id)
        
        # 验证每个区块的哈希
        for block in blocks:
            expected_hash = self._compute_block_hash(block)
            if block.current_hash != expected_hash:
                return {
                    "status": "error",
                    "message": f"Block {block.id} hash mismatch",
                    "is_valid": False
                }
        
        # 验证区块之间的链接
        for i in range(len(blocks) - 1):
            current_block = blocks[i]
            next_block = blocks[i + 1]
            
            if current_block.current_hash != next_block.previous_hash:
                return {
                    "status": "error",
                    "message": f"Chain broken between block {current_block.id} and {next_block.id}",
                    "is_valid": False
                }
        
        return {
            "status": "success",
            "chain_id": chain_id,
            "is_valid": True,
            "verified_blocks": len(blocks)
        }
    
    def get_block_stats(self, chain_id: str) -> Dict[str, Any]:
        """获取区块统计"""
        chain = self._chains.get(chain_id)
        if not chain:
            return {}
        
        blocks = self.get_chain_blocks(chain_id)
        
        return {
            "chain_id": chain_id,
            "chain_name": chain.name,
            "total_blocks": len(blocks),
            "total_logs": sum(b.log_count for b in blocks),
            "pending_blocks": len([b for b in blocks if b.status == BlockStatus.PENDING]),
            "committed_blocks": len([b for b in blocks if b.status == BlockStatus.COMMITTED]),
            "invalid_blocks": len([b for b in blocks if b.status == BlockStatus.INVALID])
        }
