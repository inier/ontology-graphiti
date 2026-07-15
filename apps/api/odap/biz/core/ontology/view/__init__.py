"""Object View - 角色视图模块

提供：
- ObjectView: 角色视图定义（基于 ObjectType 投影 + 过滤 + 排序 + 行限制）
- ViewPermission: 视图权限（角色级脱敏规则）
- ViewRepository: 仓储抽象
- ViewQueryEngine: 查询引擎抽象（OPA 校验 + 投影 + 过滤 + 排序 + 脱敏）
- REST API: /api/ontology/views/*
"""
