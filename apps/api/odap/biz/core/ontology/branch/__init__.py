"""本体 Branch & Merge 模块 - 6 层结构 (T347)

实现 ADR-XXX (Phase 11 M1 FR-032) 本体分支与合并：
- api/         FastAPI 路由
- models/      领域 Pydantic 模型
- interfaces/  抽象基类 (ABC)
- impl/        接口实现
- services/    编排层
- storage/     SQLite 持久化
"""
