"""knowledge 域公共门面（域级入口）。

域内结构：
    knowledge/
      models/        共享模型（DocStatus / Citation）
      wiki/          F1 LLM Wiki（条目 / 版本 / 引用 / 去重 / 双向同步）
      governance/    F2 文档治理（纳管 / supersede / 机械校验）

跨域消费者（web 路由注册、scripts）从这里取；域内互相引用走各自 `public.py`。
"""

from __future__ import annotations

from odap.biz.knowledge.governance.public import (
    get_doc_service,
    get_supersede_service,
    get_sync_service,
    get_verify_service,
)
from odap.biz.knowledge.wiki.public import (
    get_citation_service,
    get_dedupe_service,
    get_entry_service,
    get_version_service,
)

__all__ = [
    "get_entry_service",
    "get_version_service",
    "get_citation_service",
    "get_dedupe_service",
    "get_doc_service",
    "get_supersede_service",
    "get_verify_service",
    "get_sync_service",
]
