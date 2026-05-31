import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Translation(BaseModel):
    key: str
    module: str
    locale: str
    value: str
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class LocaleInfo(BaseModel):
    code: str
    name: str
    native_name: str
