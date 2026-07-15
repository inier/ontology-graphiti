"""统一语义层（USL）管理器子服务（Iter 1 生效）。

7 层完整架构：
- api/        FastAPI 路由 + Pydantic Schemas
- models/     6 个 Pydantic 领域模型
- interfaces/ UslRepository ABC（6 类 CRUD 抽象）
- impl/       UslManagerServiceImpl（实现 ABC，依赖 Storage）
- services/   UslManagerService（编排层，返回 Dict[str, Any]，不抛 HTTPException）
- storage/    SQLiteUslStorage（6 表 DDL + JSON/Enum/datetime 序列化）
- migrations/ seed_sanguo_xiyou.py（三国 + 西游语义层幂等迁移）
"""

from __future__ import annotations

__all__ = []
