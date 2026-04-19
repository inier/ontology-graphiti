"""异步通道实现"""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from collections import deque
import threading
from ..interfaces.channel import IChannelManager
from ..models.channel import Channel, ChannelStatus, ChannelType


class ChannelManager(IChannelManager):
    """异步通道管理实现"""
    
    def __init__(self):
        self._channels: Dict[str, Channel] = {}
        self._queues: Dict[str, deque] = {}
        self._processors: Dict[str, Callable] = {}
        self._lock = threading.Lock()
    
    def create_channel(self, name: str, channel_type: ChannelType = ChannelType.MEMORY, 
                      capacity: int = 10000, config: Dict[str, Any] = None) -> Channel:
        """创建通道"""
        channel = Channel(
            name=name,
            type=channel_type,
            capacity=capacity,
            config=config or {},
            status=ChannelStatus.ACTIVE
        )
        
        with self._lock:
            self._channels[channel.id] = channel
            self._queues[channel.id] = deque(maxlen=capacity)
        
        return channel
    
    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """获取通道"""
        return self._channels.get(channel_id)
    
    def enqueue(self, channel_id: str, item: Dict[str, Any]) -> bool:
        """入队"""
        channel = self._channels.get(channel_id)
        if not channel or channel.status != ChannelStatus.ACTIVE:
            return False
        
        queue = self._queues.get(channel_id)
        if not queue:
            return False
        
        with self._lock:
            if len(queue) < channel.capacity:
                queue.append(item)
                channel.current_size = len(queue)
                return True
        return False
    
    def dequeue(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """出队"""
        channel = self._channels.get(channel_id)
        if not channel or channel.status != ChannelStatus.ACTIVE:
            return None
        
        queue = self._queues.get(channel_id)
        if not queue:
            return None
        
        with self._lock:
            if queue:
                item = queue.popleft()
                channel.current_size = len(queue)
                channel.processed_count += 1
                channel.last_processed_at = datetime.now()
                return item
        return None
    
    def batch_dequeue(self, channel_id: str, batch_size: int = 100) -> List[Dict[str, Any]]:
        """批量出队"""
        items = []
        for _ in range(batch_size):
            item = self.dequeue(channel_id)
            if item is None:
                break
            items.append(item)
        return items
    
    def flush(self, channel_id: str) -> int:
        """刷新通道"""
        channel = self._channels.get(channel_id)
        if not channel:
            return 0
        
        queue = self._queues.get(channel_id)
        if not queue:
            return 0
        
        with self._lock:
            count = len(queue)
            queue.clear()
            channel.current_size = 0
            return count
    
    def pause_channel(self, channel_id: str) -> bool:
        """暂停通道"""
        channel = self._channels.get(channel_id)
        if not channel:
            return False
        channel.status = ChannelStatus.PAUSED
        channel.updated_at = datetime.now()
        return True
    
    def resume_channel(self, channel_id: str) -> bool:
        """恢复通道"""
        channel = self._channels.get(channel_id)
        if not channel:
            return False
        channel.status = ChannelStatus.ACTIVE
        channel.updated_at = datetime.now()
        return True
    
    def set_processor(self, channel_id: str, processor: Callable) -> bool:
        """设置处理器"""
        if channel_id not in self._channels:
            return False
        self._processors[channel_id] = processor
        return True
    
    def get_channel_stats(self, channel_id: str) -> Dict[str, Any]:
        """获取通道统计"""
        channel = self._channels.get(channel_id)
        if not channel:
            return {}
        
        return {
            "channel_id": channel.id,
            "name": channel.name,
            "type": channel.type.value,
            "status": channel.status.value,
            "capacity": channel.capacity,
            "current_size": channel.current_size,
            "processed_count": channel.processed_count,
            "failed_count": channel.failed_count,
            "last_processed_at": channel.last_processed_at.isoformat() if channel.last_processed_at else None
        }
