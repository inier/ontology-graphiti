"""Shared response models used across multiple route modules.

Centralizing these here avoids duplicating the same ``DictResponse`` definition
in every feature ``schemas.py`` while still giving routes a proper Pydantic
``response_model`` (eliminating raw ``response_model=dict`` usage).
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
