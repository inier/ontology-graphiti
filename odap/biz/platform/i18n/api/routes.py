from fastapi import APIRouter, HTTPException, Depends, Query
from odap.infra.security.jwt_auth import get_current_user

from .schemas import (
    AddLocaleRequest,
    AddLocaleResponse,
    AutoTranslateRequest,
    AutoTranslateResponse,
    BulkImportRequest,
    BulkImportResponse,
    BundleResponse,
    DeleteLocaleResponse,
    DeleteTranslationRequest,
    LocaleListResponse,
    LocaleResponse,
    ModuleInfo,
    ModuleListResponse,
    ReviewTranslationRequest,
    ScanMissingRequest,
    ScanMissingResponse,
    TranslationListResponse,
    TranslationRequest,
    TranslationResponse,
)
from ..services import I18nService

router = APIRouter(prefix="/api/i18n", tags=["i18n"])

i18n_service = I18nService()


def _get_username(user) -> str:
    """Extract username from user object."""
    if isinstance(user, dict):
        return user.get("username", "system")
    return getattr(user, "username", "system")


# ── Translations ──

@router.get("/translations", response_model=TranslationListResponse)
async def get_translations(
    module: str = None,
    locale: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user)):
    try:
        result = i18n_service.get_translations(module=module, locale=locale, page=page, page_size=page_size)
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
async def save_translation(request: TranslationRequest,
    user=Depends(get_current_user)):
    try:
        result = i18n_service.save_translation(
            key=request.key,
            module=request.module,
            locale=request.locale,
            value=request.value,
            updated_by=_get_username(user),
        )
        return TranslationResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/translations/bulk", response_model=BulkImportResponse)
async def save_translations_bulk(request: BulkImportRequest,
    user=Depends(get_current_user)):
    try:
        items = [item.model_dump() for item in request.items]
        result = i18n_service.save_translations_bulk(items, updated_by=_get_username(user))
        return BulkImportResponse(
            status=result.get("status", "success"),
            count=result.get("count", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/translations")
async def delete_translation(request: DeleteTranslationRequest,
    user=Depends(get_current_user)):
    try:
        result = i18n_service.delete_translation(
            key=request.key, module=request.module, locale=request.locale
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translations/review")
async def review_translation(request: ReviewTranslationRequest,
    user=Depends(get_current_user)):
    try:
        result = i18n_service.review_translation(
            key=request.key,
            module=request.module,
            locale=request.locale,
            approved=request.approved,
            updated_by=_get_username(user),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translations/auto-translate", response_model=AutoTranslateResponse)
async def auto_translate(request: AutoTranslateRequest,
    user=Depends(get_current_user)):
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
            skipped=result.get("skipped", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Bundles ──

@router.get("/bundles/{namespace}/{locale}", response_model=BundleResponse)
async def get_bundle(namespace: str, locale: str,
    user=Depends(get_current_user)):
    try:
        result = i18n_service.get_bundle(namespace=namespace, locale=locale)
        return BundleResponse(
            status=result.get("status", "success"),
            namespace=namespace,
            locale=locale,
            bundle=result.get("bundle", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Scan missing ──

@router.post("/scan-missing", response_model=ScanMissingResponse)
async def scan_missing(request: ScanMissingRequest,
    user=Depends(get_current_user)):
    try:
        result = i18n_service.scan_missing(module=request.module, locale=request.locale)
        return ScanMissingResponse(
            status=result.get("status", "success"),
            module=request.module,
            locale=request.locale,
            total=result.get("total", 0),
            missing=result.get("missing", 0),
            missing_keys=result.get("missing_keys", []),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Modules ──

@router.get("/modules", response_model=ModuleListResponse)
async def list_modules(user=Depends(get_current_user)):
    try:
        result = i18n_service.list_modules()
        modules = result.get("modules", [])
        return ModuleListResponse(
            modules=[ModuleInfo(**m) if isinstance(m, dict) else ModuleInfo(name=m) for m in modules],
            count=result.get("count", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Locales ──

@router.get("/locales", response_model=LocaleListResponse)
async def list_locales():
    """获取可用语言列表。
    
    公开接口，无需认证。
    """
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


@router.post("/locales", response_model=AddLocaleResponse)
async def add_locale(request: AddLocaleRequest,
    user=Depends(get_current_user)):
    try:
        result = i18n_service.add_locale(
            code=request.code,
            name=request.name,
            native_name=request.native_name,
            is_active=request.is_active,
        )
        return AddLocaleResponse(
            status=result.get("status", "success"),
            locale=LocaleResponse(**result.get("locale", {})),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/locales/{code}", response_model=DeleteLocaleResponse)
async def remove_locale(
    code: str,
    delete_translations: bool = Query(False),
    user=Depends(get_current_user)):
    try:
        result = i18n_service.remove_locale(code, delete_translations=delete_translations)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return DeleteLocaleResponse(
            status=result.get("status", "success"),
            code=code,
            deactivated=result.get("deactivated", True),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
