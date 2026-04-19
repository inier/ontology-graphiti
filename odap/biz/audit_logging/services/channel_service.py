"""通道服务"""

from typing import Dict, Any, List, Optional, Callable
from ..impl.channel import ChannelManager
from ..models.channel import ChannelType, ChannelStatus


class ChannelService:
    """通道服务"""
    
    def __init__(self):
        self.manager = ChannelManager()
    
    def create_channel(self, name: str, channel_type: ChannelType = ChannelType.MEMORY, 
                     capacity: int = 10000, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建通道
        
        Args:
            name: 通道名称
            channel_type: 通道类型
            capacity: 容量
            config: 配置信息
            
        Returns:
            通道信息
        """
        channel = self.manager.create_channel(name, channel_type, capacity, config)
        
        return {
            "channel_id": channel.id,
            "name": channel.name,
            "type": channel.type.value,
            "status": channel.status.value,
            "capacity": channel.capacity,
            "created_at": channel.created_at.isoformat()
        }
    
    def get_channel(self, channel_id: str) -> Dict[str, Any]:
        """获取通道"""
        channel = self.manager.get_channel(channel_id)
        if not channel:
            return {"status": "error", "message": "Channel not found"}
        
        return {
            "channel_id": channel.id,
            "name": channel.name,
            "type": channel.type.value,
            "status": channel.status.value,
            "capacity": channel.capacity,
            "current_size": channel.current_size,
            "processed_count": channel.processed_count
        }
    
    def enqueue(self, channel_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """入队"""
        success = self.manager.enqueue(channel_id, item)
        
        return {
            "status": "success" if success else "error",
            "message": "Item enqueued" if success else "Failed to enqueue item"
        }
    
    def dequeue(self, channel_id: str) -> Dict[str, Any]:
        """出队"""
        item = self.manager.dequeue(channel_id)
        
        if item is None:
            return {"status": "error", "message": "No item to dequeue or channel not found"}
        
        return {
            "status": "success",
            "item": item
        }
    
    def batch_dequeue(self, channel_id: str, batch_size: int = 100) -> Dict[str, Any]:
        """批量出队"""
        items = self.manager.batch_dequeue(channel_id, batch_size)
        
        return {
            "status": "success",
            "count": len(items),
            "items": items
        }
    
    def flush(self, channel_id: str) -> Dict[str, Any]:
        """刷新通道"""
        count = self.manager.flush(channel_id)
        
        return {
            "status": "success",
            "flushed_count": count
        }
    
    def pause_channel(self, channel_id: str) -> Dict[str, Any]:
        """暂停通道"""
        success = self.manager.pause_channel(channel_id)
        
        return {
            "status": "success" if success else "error",
            "message": "Channel paused" if success else "Failed to pause channel"
        }
    
    def resume_channel(self, channel_id: str) -> Dict[str, Any]:
        """恢复通道"""
        success = self.manager.resume_channel(channel_id)
        
        return {
            "status": "success" if success else "error",
            "message": "Channel resumed" if success else "Failed to resume channel"
        }
    
    def set_processor(self, channel_id: str, processor: Callable) -> Dict[str, Any]:
        """设置处理器"""
        success = self.manager.set_processor(channel_id, processor)
        
        return {
            "status": "success" if success else "error",
            "message": "Processor set" if success else "Failed to set processor"
        }
    
    def get_stats(self, channel_id: str) -> Dict[str, Any]:
        """获取通道统计"""
        return self.manager.get_channel_stats(channel_id)
