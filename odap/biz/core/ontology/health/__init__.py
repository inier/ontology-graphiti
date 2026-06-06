"""Data Health 模块 - 数据健康监控与质量保证

提供：
- HealthRule: 健康检查规则定义
- HealthReport: 扫描结果报告
- HealthScanner: 5 种规则（not_null/unique/regex/range/referential_integrity）
- NotificationDispatcher: 通知派发（email/webhook/im）
- REST API: /api/ontology/health/*
"""
