"""sa_config 服务层包。"""
from odap.biz.semantic_admin.sa_config.services.sa_config_service import (
    SaConfigService,
    get_sa_config_service,
)

__all__ = ["SaConfigService", "get_sa_config_service"]
