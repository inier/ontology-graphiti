from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Translation(BaseModel):
    key: str
    module: str
    locale: str
    value: str
    status: str = "draft"
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_by: str = "system"


class LocaleInfo(BaseModel):
    code: str
    name: str
    native_name: str
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
