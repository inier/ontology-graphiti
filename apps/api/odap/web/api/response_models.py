"""共享响应模型 —— 从 common 层重新导出（向后兼容 shim）。

Stage G · C2-2 下沉：``DictResponse`` 的真实定义已下沉到 ``odap.common.response_models``
（叶子层，biz/web 均可合法依赖）。本文件保留为向后兼容再导出，使旧路径
``odap.web.api.response_models`` 仍可导入，但**新代码请直接从 common 导入**：

    from odap.common.response_models import DictResponse
"""
from odap.common.response_models import DictResponse  # noqa: F401

__all__ = ["DictResponse"]
