"""sa_config storage 包别名：Storage = SQLiteSaConfigStorage。"""
from odap.biz.semantic_admin.sa_config.storage.sqlite_sa_config_storage import (
    SQLiteSaConfigStorage,
)

Storage = SQLiteSaConfigStorage

__all__ = ["SQLiteSaConfigStorage", "Storage"]
