from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ScanRequest(BaseModel):
    ontology_id: Optional[str] = None
    domain_id: Optional[str] = None
