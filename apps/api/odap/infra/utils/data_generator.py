"""数据生成工具"""

from typing import Dict, Any, List
import random
from datetime import datetime


class DataGenerator:
    """数据生成器"""

    def __init__(self):
        self.names = ["张三", "李四", "王五", "赵六", "孙七", "Alice", "Bob", "Charlie"]
        self.organizations = ["百度", "腾讯", "阿里巴巴", "字节跳动", "华为"]
        self.locations = ["北京", "上海", "深圳", "广州", "杭州"]
        self.event_types = ["会议", "发布会", "战略合作", "收购"]

    def generate_sample_data(self, count: int = 10) -> Dict[str, Any]:
        """生成示例数据"""

        entities = []
        events = []
        relations = []

        # 生成实体
        for i in range(count):
            if i % 3 == 0:
                # 人物实体
                entity = {
                    "id": f"entity-{i}",
                    "type": "Person",
                    "name": random.choice(self.names) + str(i),
                    "properties": {}
                }
            elif i % 3 == 1:
                # 组织实体
                entity = {
                    "id": f"entity-{i}",
                    "type": "Organization",
                    "name": random.choice(self.organizations),
                    "properties": {}
                }
            else:
                # 地点实体
                entity = {
                    "id": f"entity-{i}",
                    "type": "Location",
                    "name": random.choice(self.locations),
                    "properties": {}
                }
            entities.append(entity)

        # 生成事件
        for i in range(count // 2):
            event = {
                "id": f"event-{i}",
                "type": random.choice(self.event_types),
                "title": f"事件 {i}",
                "description": f"这是事件 {i} 的描述",
                "timestamp": datetime.now().isoformat(),
                "participants": [random.choice(entities)["id"] for _ in range(2)]
            }
            events.append(event)

        # 生成关系
        for i in range(count // 3):
            source = random.choice(entities)
            target = random.choice([e for e in entities if e["id"] != source["id"]])

            relation = {
                "id": f"relation-{i}",
                "type": "ASSOCIATED_WITH",
                "source": source["id"],
                "target": target["id"],
                "properties": {}
            }
            relations.append(relation)

        return {
            "entities": entities,
            "events": events,
            "relations": relations
        }
