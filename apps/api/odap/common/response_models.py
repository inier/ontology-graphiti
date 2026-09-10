"""跨层共享的响应模型 (Shared response models).

Stage G · C2-2 下沉：此模块原位于 ``odap.web.api.response_models``，但 ``DictResponse``
是一个零内部依赖（仅 pydantic + typing）的纯共享 schema，却被 3 个 biz 路由模块反向
reach-up 引用，构成 C2（web 是顶层，biz/infra 不得依赖 web）违规。

按 C2 烧账方向「共享设施应下沉到 common 或 infra」，将其下沉到 common 叶子层：
    - common 是叶子（C1：不得依赖 biz/infra/web），DictResponse 只依赖 pydantic，
      放入 common 不破坏 C1；
    - biz / web 均可合法依赖 common，reach-up 变为 reach-down。

原路径 ``odap.web.api.response_models`` 保留为向后兼容再导出 shim（见该文件）。
新代码请直接从本模块导入：

    from odap.common.response_models import DictResponse
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional


class DictResponse(BaseModel):
    """Flexible response model that accepts arbitrary dict shapes from service layer.

    Uses ``extra="allow"`` to remain backward compatible with all existing
    service-layer dicts while still being a proper Pydantic model — so the
    generated OpenAPI schema is well-typed and ``response_model=dict`` is no
    longer required.
    """
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    message: Optional[str] = None


__all__ = ["DictResponse"]
