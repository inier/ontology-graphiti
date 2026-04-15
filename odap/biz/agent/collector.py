"""
战场情报自动收集与更新模块
"""

import sys
import os
import time
import threading
import random
from datetime import datetime

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.infra.graph import GraphManager
from odap.biz.simulator.data_generator import generate_random_event

class IntelligenceCollector:
    """
    战场情报收集器
    """
    
    def __init__(self, update_interval=30):
        """
        初始化情报收集器
        
        Args:
            update_interval: 更新间隔（秒）
        """
        self.graph_manager = GraphManager()
        self.update_interval = update_interval
        self.running = False
        self.thread = None
        print(f"情报收集器初始化成功，更新间隔: {update_interval}秒")
    
    def start_collection(self):
        """
        开始情报收集
        """
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._collect_intelligence)
            self.thread.daemon = True
            self.thread.start()
            print("情报收集已开始")
    
    def stop_collection(self):
        """
        停止情报收集
        """
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join()
            print("情报收集已停止")
    
    def _collect_intelligence(self):
        """
        收集情报的主要逻辑
        """
        while self.running:
            try:
                # 收集情报
                intelligence = self._collect_current_intelligence()
                
                # 更新图谱
                self._update_graph(intelligence)
                
                # 等待下一次收集
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"情报收集出错: {e}")
                time.sleep(self.update_interval)
    
    def _collect_current_intelligence(self):
        """
        收集当前情报
        
        Returns:
            情报数据
        """
        # 生成随机事件
        random_event = generate_random_event()
        
        # 收集实体状态
        entities = self.graph_manager.query_entities()
        
        # 构建情报数据
        intelligence = {
            "timestamp": datetime.now().isoformat(),
            "random_event": random_event,
            "entity_count": len(entities),
            "entities": entities[:5]  # 只返回前5个实体作为示例
        }
        
        print(f"收集到情报: {random_event['description']}")
        return intelligence
    
    def _update_graph(self, intelligence):
        """
        更新图谱
        
        Args:
            intelligence: 情报数据
        """
        # 更新实体状态
        for entity in intelligence.get("entities", []):
            # 随机更新实体状态
            if entity["type"] == "MilitaryUnit":
                new_status = random.choice(["待命", "行动中", "受损"])
                self.graph_manager.update_entity(entity["id"], {"status": new_status})
            elif entity["type"] == "WeaponSystem":
                new_status = random.choice(["正常", "受损", "维修中"])
                self.graph_manager.update_entity(entity["id"], {"status": new_status})
        
        # 添加随机事件到图谱
        event_id = intelligence["random_event"]["id"]
        event_type = intelligence["random_event"]["type"]
        event_description = intelligence["random_event"]["description"]
        event_timestamp = intelligence["random_event"]["timestamp"]
        
        # 检查事件是否已存在
        event_exists = False
        for node_id in self.graph_manager.graph.nodes:
            if node_id == event_id:
                event_exists = True
                break
        
        if not event_exists:
            # 添加事件节点
            self.graph_manager.add_entity(
                event_id,
                "BattleEvent",
                {
                    "type": event_type,
                    "description": event_description,
                    "timestamp": event_timestamp,
                    "outcome": "未知"
                }
            )
            print(f"已添加事件到图谱: {event_description}")
    
    def get_latest_intelligence(self):
        """
        获取最新情报
        
        Returns:
            最新情报
        """
        return self._collect_current_intelligence()

if __name__ == "__main__":
    # 测试情报收集器
    collector = IntelligenceCollector(update_interval=10)
    
    try:
        collector.start_collection()
        print("情报收集器已启动，按Ctrl+C停止")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        collector.stop_collection()
        print("情报收集器已停止")