from fastapi import APIRouter, HTTPException

from .schemas import (
    AutoTranslateRequest,
    AutoTranslateResponse,
    LocaleListResponse,
    LocaleResponse,
    ModuleListResponse,
    TranslationListResponse,
    TranslationRequest,
    TranslationResponse,
)
from ..services import I18nService

router = APIRouter(prefix="/api/i18n", tags=["i18n"])

i18n_service = I18nService()


@router.get("/translations", response_model=TranslationListResponse)
async def get_translations(
    module: str = None,
    locale: str = None,
    page: int = 1,
    page_size: int = 50,
):
    try:
        result = i18n_service.get_translations(module=module, locale=locale)
        return TranslationListResponse(
            translations=result.get("translations", []),
            total=result.get("total", 0),
            page=result.get("page", page),
            page_size=result.get("page_size", page_size),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translations", response_model=TranslationResponse)
async def save_translation(request: TranslationRequest):
    try:
        result = i18n_service.save_translation(
            key=request.key,
            module=request.module,
            locale=request.locale,
            value=request.value,
        )
        return TranslationResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translations/auto-translate", response_model=AutoTranslateResponse)
async def auto_translate(request: AutoTranslateRequest):
    try:
        result = i18n_service.auto_translate(
            module=request.module,
            source_locale=request.source_locale,
            target_locale=request.target_locale,
        )
        return AutoTranslateResponse(
            status=result.get("status", "error"),
            module=result.get("module", request.module),
            source_locale=result.get("source_locale", request.source_locale),
            target_locale=result.get("target_locale", request.target_locale),
            translated_count=result.get("translated_count", 0),
            total_count=result.get("total_count", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/modules", response_model=ModuleListResponse)
async def list_modules():
    try:
        result = i18n_service.list_modules()
        return ModuleListResponse(
            modules=result.get("modules", []),
            count=result.get("count", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locales", response_model=LocaleListResponse)
async def list_locales():
    try:
        result = i18n_service.list_locales()
        return LocaleListResponse(
            locales=result.get("locales", []),
            count=result.get("count", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
