"""sa_config 子模块：语义管理台的动态配置服务。

提供 sa_config 表的 6 层封装，用于替代 core/ontology/semantic_layer/semantic_config.py
中的硬编码常量（SANGUO_SEMANTIC / XIYOU_SEMANTIC / SHARED_SEMANTIC）。

结构：
    models    SaConfigEntry Pydantic
    storage   SQLite 持久化（DDL + CRUD）
    interfaces  ISaConfigStorage ABC
    impl      SaConfigManager（scope=domain 等业务语义封装）
    services  SaConfigService（Dict 返回 + 错误映射）
    api       HTTP FastAPI 路由（/api/semantic-admin/config）
"""
