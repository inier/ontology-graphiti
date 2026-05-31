from typing import List, Optional

from pydantic import BaseModel, Field


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
    updated_at: str


class TranslationListResponse(BaseModel):
    translations: List[TranslationResponse]
    total: int
    page: int
    page_size: int


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


class ModuleListResponse(BaseModel):
    modules: List[str]
    count: int


class LocaleResponse(BaseModel):
    code: str
    name: str
    native_name: str


class LocaleListResponse(BaseModel):
    locales: List[LocaleResponse]
    count: int
