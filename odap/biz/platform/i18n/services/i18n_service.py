import logging
from typing import Any, Dict, List, Optional

from ..models.translation import Translation, LocaleInfo
from ..storage import Storage

logger = logging.getLogger("i18n_service")

# ── 审计工具（懒加载 + 容错） ──
def _i18n_audit(action: str, *, result_status: str = "success",
                result_message: str = "", resource: str = None,
                details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="platform_i18n",
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")

DEFAULT_LOCALES = [
    {"code": "zh-CN", "name": "Chinese (Simplified)", "native_name": "简体中文"},
    {"code": "en-US", "name": "English (US)", "native_name": "English"},
]


class I18nService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._storage = Storage()
        self._seed_default_locales()
        self._initialized = True

    def _seed_default_locales(self):
        """Seed default locales on first init."""
        existing = self._storage.list_locales()
        existing_codes = {loc["code"] for loc in existing}
        for loc in DEFAULT_LOCALES:
            if loc["code"] not in existing_codes:
                self._storage.add_locale(
                    code=loc["code"], name=loc["name"], native_name=loc["native_name"]
                )

    # ── Translation CRUD ──

    def get_translations(
        self, module: Optional[str] = None, locale: Optional[str] = None,
        page: int = 1, page_size: int = 20,
    ) -> Dict[str, Any]:
        return self._storage.list_translations(module=module, locale=locale, page=page, page_size=page_size)

    def save_translation(
        self, key: str, module: str, locale: str, value: str, updated_by: str = "system"
    ) -> Dict[str, Any]:
        translation = Translation(key=key, module=module, locale=locale, value=value)
        result = self._storage.save_translation(translation, updated_by=updated_by)
        _i18n_audit(
            action="i18n_translation_upsert",
            result_status="success",
            resource=key,
            details={
                "i18n_key_count": 1,
                "module": module,
                "locale": locale,
                "key_len": len(key),
            },
        )
        return result

    def save_translations_bulk(
        self, items: List[Dict[str, Any]], updated_by: str = "system"
    ) -> Dict[str, Any]:
        count = self._storage.save_translations_bulk(items, updated_by=updated_by)
        _i18n_audit(
            action="i18n_translation_bulk_save",
            result_status="success",
            resource="bulk",
            details={
                "i18n_key_count": count,
                "item_count": count,
            },
        )
        return {"status": "success", "count": count}

    def delete_translation(
        self, key: str, module: str, locale: str
    ) -> Dict[str, Any]:
        deleted = self._storage.delete_translation(key, module, locale)
        _i18n_audit(
            action="i18n_translation_delete",
            result_status="success" if deleted else "failure",
            result_message="" if deleted else "Translation not found",
            resource=key,
            details={
                "key": key,
                "module": module,
                "locale": locale,
                "i18n_key_count": 1 if deleted else 0,
            },
        )
        if not deleted:
            return {"status": "error", "message": "Translation not found"}
        return {"status": "success", "deleted": True}

    def review_translation(
        self, key: str, module: str, locale: str, approved: bool, updated_by: str = "system"
    ) -> Dict[str, Any]:
        updated = self._storage.review_translation(key, module, locale, approved, updated_by)
        _i18n_audit(
            action="i18n_translation_review",
            result_status="success" if updated else "failure",
            result_message="" if updated else "Translation not found",
            resource=key,
            details={
                "key": key,
                "module": module,
                "locale": locale,
                "approved": approved,
            },
        )
        if not updated:
            return {"status": "error", "message": "Translation not found"}
        return {"status": "success", "approved": approved}

    def get_bundle(self, namespace: str, locale: str) -> Dict[str, Any]:
        bundle = self._storage.get_bundle(namespace, locale)
        return {"status": "success", "namespace": namespace, "locale": locale, "bundle": bundle}

    def scan_missing(self, module: str, locale: str) -> Dict[str, Any]:
        result = self._storage.scan_missing(module, locale)
        return {"status": "success", "module": module, "locale": locale, **result}

    # ── Auto translate ──

    def auto_translate(
        self, module: str, source_locale: str, target_locale: str
    ) -> Dict[str, Any]:
        source_translations = self._storage.list_translations(
            module=module, locale=source_locale, page_size=1000
        )

        items = source_translations.get("translations", [])
        if not items:
            return {"status": "error", "message": "No source translations found"}

        translated = []
        skipped = 0
        for item in items:
            try:
                translated_value = self._call_llm_translate(
                    item["value"], source_locale, target_locale
                )
                if translated_value:
                    translation = Translation(
                        key=item["key"],
                        module=module,
                        locale=target_locale,
                        value=translated_value,
                    )
                    self._storage.save_translation(translation)
                    translated.append(
                        {
                            "key": item["key"],
                            "source_value": item["value"],
                            "translated_value": translated_value,
                        }
                    )
                else:
                    skipped += 1
            except Exception as e:
                logger.warning("Auto-translate failed for key %s: %s", item["key"], e)
                skipped += 1

        return {
            "status": "success",
            "module": module,
            "source_locale": source_locale,
            "target_locale": target_locale,
            "translated_count": len(translated),
            "total_count": len(items),
            "skipped": skipped,
            "translations": translated,
        }

    def _call_llm_translate(
        self, text: str, source_locale: str, target_locale: str
    ) -> Optional[str]:
        try:
            import openai

            api_key = __import__("os").environ.get("OPENAI_API_KEY", "")
            base_url = __import__("os").environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
            model = __import__("os").environ.get("OPENAI_MODEL", "gpt-4")

            if not api_key:
                return None

            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a professional translator. Translate the following text from {source_locale} to {target_locale}. Return only the translated text.",
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=1000,
                temperature=0.3,
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("LLM translate failed: %s", e)
            return None

    # ── Module ──

    def list_modules(self) -> Dict[str, Any]:
        modules = self._storage.list_modules()
        return {"status": "success", "modules": modules, "count": len(modules)}

    # ── Locale management ──

    def list_locales(self) -> Dict[str, Any]:
        locales = self._storage.list_locales()
        return {"status": "success", "locales": locales, "count": len(locales)}

    def add_locale(
        self, code: str, name: str, native_name: str, is_active: bool = True
    ) -> Dict[str, Any]:
        result = self._storage.add_locale(code, name, native_name)
        return {"status": "success", "locale": result}

    def remove_locale(self, code: str, delete_translations: bool = False) -> Dict[str, Any]:
        removed = self._storage.remove_locale(code, delete_translations)
        if not removed:
            return {"status": "error", "message": "Locale not found"}
        return {"status": "success", "code": code, "deactivated": True}
