#!/usr/bin/env python3
"""
Graphiti 审计通道实现

将审计日志存储到 Graphiti 知识图谱中，
支持图遍历查询和时态分析。
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from .audit_models import AuditEvent, AuditFilter, AuditEventType, AuditSeverity


class GraphitiAuditChannel:
    """
    Graphiti 审计通道实现
    
    将审计日志存储到 Graphiti 知识图谱中：
    - 创建 AuditLog 实体
    - 创建 AuditUser、AuditResource、AuditService 实体
    - 创建实体间的关系（EXECUTED、AFFECTED、GENERATED）
    """
    
    def __init__(self, graph_manager=None):
        """
        初始化 Graphiti 审计通道
        
        Args:
            graph_manager: GraphManager 实例
        """
        self._graph_manager = graph_manager
        self._init_graph_manager()
    
    def _init_graph_manager(self):
        """初始化 GraphManager"""
        if self._graph_manager is None:
            try:
                from odap.infra.graph.graph_service import GraphManager
                self._graph_manager = GraphManager()
            except Exception as e:
                print(f"GraphManager初始化失败: {e}")
                self._graph_manager = None
    
    async def write(self, event: AuditEvent) -> None:
        """写入单个事件
        
        Args:
            event: 审计事件对象
        """
        if self._graph_manager is None:
            print("GraphManager 未初始化，跳过写入")
            return
        
        # 转换为字典格式
        event_dict = event.model_dump()
        
        # 创建审计日志实体
        audit_id = f"audit_{uuid.uuid4().hex[:12]}"
        
        # 构建实体属性
        action = event_dict.get("action", "unknown")
        timestamp = event_dict.get("timestamp", datetime.now().isoformat())
        properties = {
            "name": f"审计日志_{action}",
            "timestamp": timestamp,
            "level": event_dict.get("severity", "INFO"),
            "type": event_dict.get("event_type", "AUDIT"),
            "service": event_dict.get("source", "system"),
            "action": action,
            "details": str(event_dict.get("context", {})),
            "user": event_dict.get("actor", {}).get("actor_id", "system"),
            "resource": event_dict.get("resource", {}).get("resource_id", "unknown"),
            "status": event_dict.get("result", {}).get("status", "SUCCESS"),
            "execution_time": event_dict.get("duration_ms", 0),
            "trace_id": event_dict.get("trace_id", ""),
            "workspace_id": event_dict.get("workspace_id", "default")
        }
        
        # 添加到 Graphiti
        success = self._graph_manager.add_entity(
            entity_id=audit_id,
            entity_type="AuditLog",
            properties=properties
        )
        
        # 创建相关实体和关系
        if success:
            user_id = event_dict.get("actor", {}).get("actor_id", "system")
            resource_id = event_dict.get("resource", {}).get("resource_id", "unknown")
            service_id = event_dict.get("source", "system")
            
            self._ensure_user_entity(user_id, properties)
            self._ensure_resource_entity(resource_id, properties)
            self._ensure_service_entity(service_id, properties)
            self._create_relationships(audit_id, user_id, resource_id, service_id)
    
    def _ensure_user_entity(self, user_id: str, log_data: Dict[str, Any]):
        """确保用户实体存在"""
        properties = {
            "name": user_id,
            "role": "user"
        }
        
        self._graph_manager.add_entity(
            entity_id=f"user_{user_id}",
            entity_type="AuditUser",
            properties=properties
        )
    
    def _ensure_resource_entity(self, resource_id: str, log_data: Dict[str, Any]):
        """确保资源实体存在"""
        properties = {
            "name": resource_id,
            "type": "resource"
        }
        
        self._graph_manager.add_entity(
            entity_id=f"resource_{resource_id}",
            entity_type="AuditResource",
            properties=properties
        )
    
    def _ensure_service_entity(self, service_id: str, log_data: Dict[str, Any]):
        """确保服务实体存在"""
        properties = {
            "name": service_id,
            "version": "1.0"
        }
        
        self._graph_manager.add_entity(
            entity_id=f"service_{service_id}",
            entity_type="AuditService",
            properties=properties
        )
    
    def _create_relationships(self, audit_id: str, user_id: str, resource_id: str, service_id: str):
        """创建实体间的关系"""
        # 审计日志由用户执行
        self._graph_manager.add_relationship(
            source_id=f"user_{user_id}",
            target_id=audit_id,
            relationship="EXECUTED",
            properties={"type": "audit"}
        )
        
        # 审计日志操作资源
        self._graph_manager.add_relationship(
            source_id=audit_id,
            target_id=f"resource_{resource_id}",
            relationship="AFFECTED",
            properties={"type": "audit"}
        )
        
        # 审计日志来自服务
        self._graph_manager.add_relationship(
            source_id=f"service_{service_id}",
            target_id=audit_id,
            relationship="GENERATED",
            properties={"type": "audit"}
        )
    
    async def write_batch(self, events: List[AuditEvent]) -> None:
        """批量写入事件
        
        Args:
            events: 审计事件列表
        """
        for event in events:
            await self.write(event)
    
    async def query(self, filter: AuditFilter) -> List[AuditEvent]:
        """查询审计事件
        
        Args:
            filter: 审计事件查询过滤器
            
        Returns:
            List[AuditEvent]: 查询结果
        """
        if self._graph_manager is None:
            return []
        
        # 使用 Neo4j 查询
        if hasattr(self._graph_manager, 'neo4j_driver') and self._graph_manager.neo4j_driver:
            try:
                return await self._query_with_neo4j(filter)
            except Exception as e:
                print(f"Neo4j查询失败: {e}")
        
        # 回退到 GraphManager 搜索
        return self._query_with_search(filter)
    
    async def _query_with_neo4j(self, filter: AuditFilter) -> List[AuditEvent]:
        """使用 Neo4j 查询"""
        from neo4j import AsyncSession
        
        with self._graph_manager.neo4j_driver.session() as session:
            where_clauses = []
            params = {}
            
            if filter.actor_ids:
                placeholders = ','.join([f'"{uid}"' for uid in filter.actor_ids])
                where_clauses.append(f"n.user IN [{placeholders}]")
            if filter.workspace_id:
                where_clauses.append(f'n.workspace_id = "{filter.workspace_id}"')
            if filter.trace_id:
                where_clauses.append(f'n.trace_id = "{filter.trace_id}"')
            
            where_part = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            cypher = f"""MATCH (n:AuditLog) {where_part} 
                         RETURN n ORDER BY n.timestamp DESC LIMIT {filter.limit}"""
            
            result = session.run(cypher, **params)
            
            events = []
            for record in result:
                node = record["n"]
                properties = dict(node)
                events.append(self._convert_to_audit_event(properties))
            
            return events
    
    def _query_with_search(self, filter: AuditFilter) -> List[AuditEvent]:
        """使用搜索功能查询"""
        query_parts = []
        
        if filter.actor_ids:
            for uid in filter.actor_ids:
                query_parts.append(f"user:{uid}")
        if filter.workspace_id:
            query_parts.append(f"workspace:{filter.workspace_id}")
        
        search_query = " ".join(query_parts) if query_parts else "AuditLog"
        results = self._graph_manager.search(search_query, limit=filter.limit)
        
        events = []
        for result in results:
            if isinstance(result, dict) and result.get("type") == "AuditLog":
                events.append(self._convert_to_audit_event(result.get("properties", {})))
        
        return events
    
    def _convert_to_audit_event(self, properties: Dict[str, Any]) -> AuditEvent:
        """将属性字典转换为 AuditEvent"""
        from .audit_models import ActorInfo, ResourceInfo, ActionResult
        
        return AuditEvent(
            id=properties.get("id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(properties.get("timestamp", datetime.now().isoformat())),
            event_type=AuditEventType(properties.get("type", "system.health")),
            severity=AuditSeverity(properties.get("level", "info")),
            source=properties.get("service", "system"),
            actor=ActorInfo(
                actor_type="user",
                actor_id=properties.get("user", "system"),
                actor_name=properties.get("user", "System"),
                roles=[]
            ),
            action=properties.get("action", "unknown"),
            resource=ResourceInfo(
                resource_type="resource",
                resource_id=properties.get("resource", "unknown"),
                resource_name=properties.get("resource", "Unknown"),
                attributes={}
            ),
            result=ActionResult(
                status=properties.get("status", "success"),
                message=""
            ),
            context={},
            workspace_id=properties.get("workspace_id", "default"),
            trace_id=properties.get("trace_id", ""),
            parent_event_id=None,
            duration_ms=properties.get("execution_time")
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            Dict: 统计信息
        """
        # Graphiti 通道的统计信息需要通过图查询获取
        # 这里返回基本信息
        return {
            "total": 0,
            "by_severity": {},
            "by_type": {},
            "channel": "graphiti"
        }


# 全局 Graphiti 审计通道实例
_graphiti_channel_instance = None


def get_graphiti_audit_channel() -> GraphitiAuditChannel:
    """获取 Graphiti 审计通道实例
    
    Returns:
        GraphitiAuditChannel: 审计通道实例
    """
    global _graphiti_channel_instance
    if _graphiti_channel_instance is None:
        _graphiti_channel_instance = GraphitiAuditChannel()
    return _graphiti_channel_instance


__all__ = [
    'GraphitiAuditChannel',
    'get_graphiti_audit_channel'
]
