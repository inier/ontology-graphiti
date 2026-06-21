from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Translation ──

class TranslationRequest(BaseModel):
    key: str
    module: str
    locale: str
    value: str


class TranslationResponse(BaseModel):
    key: str
    module: str
    locale: str
    value: str
    status: str = "draft"
    updated_at: str
    updated_by: str = "system"


class TranslationListResponse(BaseModel):
    translations: List[TranslationResponse]
    total: int
    page: int
    page_size: int


class BulkImportItem(BaseModel):
    key: str
    module: str
    locale: str
    value: str


class BulkImportRequest(BaseModel):
    items: List[BulkImportItem]


class BulkImportResponse(BaseModel):
    status: str
    count: int


class DeleteTranslationRequest(BaseModel):
    key: str
    module: str
    locale: str


class ReviewTranslationRequest(BaseModel):
    key: str
    module: str
    locale: str
    approved: bool


# ── Auto translate ──

class AutoTranslateRequest(BaseModel):
    module: str
    source_locale: str
    target_locale: str


class AutoTranslateResponse(BaseModel):
    status: str
    module: str
    source_locale: str
    target_locale: str
    translated_count: int
    total_count: int
    skipped: int = 0


# ── Module ──

class ModuleInfo(BaseModel):
    name: str
    key_count: int = 0
    locale_count: int = 0
    locales: List[str] = Field(default_factory=list)


class ModuleListResponse(BaseModel):
    modules: List[ModuleInfo]
    count: int


# ── Locale ──

class LocaleResponse(BaseModel):
    code: str
    name: str
    native_name: str
    is_active: bool = True
    created_at: str = ""


class LocaleListResponse(BaseModel):
    locales: List[LocaleResponse]
    count: int


class AddLocaleRequest(BaseModel):
    code: str
    name: str
    native_name: str
    is_active: bool = True


class AddLocaleResponse(BaseModel):
    status: str
    locale: LocaleResponse


class DeleteLocaleResponse(BaseModel):
    status: str
    code: str
    deactivated: bool


# ── Bundle ──

class BundleResponse(BaseModel):
    status: str
    namespace: str
    locale: str
    bundle: Dict[str, str] = Field(default_factory=dict)


# ── Scan missing ──

class ScanMissingRequest(BaseModel):
    module: str
    locale: str


class ScanMissingResponse(BaseModel):
    status: str
    module: str
    locale: str
    total: int
    missing: int
    missing_keys: List[str] = Field(default_factory=list)
