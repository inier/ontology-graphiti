"""异步通道接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from ..models.channel import Channel, ChannelStatus, ChannelType


class IChannelManager(ABC):
    """异步通道管理接口"""
    
    @abstractmethod
    def create_channel(self, name: str, channel_type: ChannelType = ChannelType.MEMORY, 
                      capacity: int = 10000, config: Dict[str, Any] = None) -> Channel:
        """创建通道
        
        Args:
            name: 通道名称
            channel_type: 通道类型
            capacity: 容量
            config: 配置信息
            
        Returns:
            创建的通道
        """
        pass
    
    @abstractmethod
    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """获取通道
        
        Args:
            channel_id: 通道ID
            
        Returns:
            通道对象
        """
        pass
    
    @abstractmethod
    def enqueue(self, channel_id: str, item: Dict[str, Any]) -> bool:
        """入队
        
        Args:
            channel_id: 通道ID
            item: 要入队的项
            
        Returns:
            是否入队成功
        """
        pass
    
    @abstractmethod
    def dequeue(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """出队
        
        Args:
            channel_id: 通道ID
            
        Returns:
            出队的项
        """
        pass
    
    @abstractmethod
    def batch_dequeue(self, channel_id: str, batch_size: int = 100) -> List[Dict[str, Any]]:
        """批量出队
        
        Args:
            channel_id: 通道ID
            batch_size: 批量大小
            
        Returns:
            出队的项列表
        """
        pass
    
    @abstractmethod
    def flush(self, channel_id: str) -> int:
        """刷新通道
        
        Args:
            channel_id: 通道ID
            
        Returns:
            刷新的项数量
        """
        pass
    
    @abstractmethod
    def pause_channel(self, channel_id: str) -> bool:
        """暂停通道
        
        Args:
            channel_id: 通道ID
            
        Returns:
            是否暂停成功
        """
        pass
    
    @abstractmethod
    def resume_channel(self, channel_id: str) -> bool:
        """恢复通道
        
        Args:
            channel_id: 通道ID
            
        Returns:
            是否恢复成功
        """
        pass
    
    @abstractmethod
    def set_processor(self, channel_id: str, processor: Callable) -> bool:
        """设置处理器
        
        Args:
            channel_id: 通道ID
            processor: 处理函数
            
        Returns:
            是否设置成功
        """
        pass
    
    @abstractmethod
    def get_channel_stats(self, channel_id: str) -> Dict[str, Any]:
        """获取通道统计
        
        Args:
            channel_id: 通道ID
            
        Returns:
            通道统计信息
        """
        pass
