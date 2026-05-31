import logging
from typing import Any, Dict, List, Optional

from ..models.translation import Translation, LocaleInfo
from ..storage import Storage

logger = logging.getLogger("i18n_service")

SUPPORTED_LOCALES = [
    LocaleInfo(code="zh-CN", name="Chinese (Simplified)", native_name="简体中文"),
    LocaleInfo(code="en-US", name="English (US)", native_name="English"),
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
        self._initialized = True

    def get_translations(
        self, module: Optional[str] = None, locale: Optional[str] = None
    ) -> Dict[str, Any]:
        return self._storage.list_translations(module=module, locale=locale)

    def save_translation(
        self, key: str, module: str, locale: str, value: str
    ) -> Dict[str, Any]:
        translation = Translation(key=key, module=module, locale=locale, value=value)
        return self._storage.save_translation(translation)

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
            except Exception as e:
                logger.warning("Auto-translate failed for key %s: %s", item["key"], e)

        return {
            "status": "success",
            "module": module,
            "source_locale": source_locale,
            "target_locale": target_locale,
            "translated_count": len(translated),
            "total_count": len(items),
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

    def list_modules(self) -> Dict[str, Any]:
        modules = self._storage.list_modules()
        return {"status": "success", "modules": modules, "count": len(modules)}

    def list_locales(self) -> Dict[str, Any]:
        db_locales = self._storage.list_locales()
        all_locales = list(set(db_locales + [loc.code for loc in SUPPORTED_LOCALES]))
        locale_infos = []
        for loc in SUPPORTED_LOCALES:
            if loc.code in all_locales:
                locale_infos.append(loc.model_dump())
        for code in db_locales:
            if code not in [loc.code for loc in SUPPORTED_LOCALES]:
                locale_infos.append(
                    {"code": code, "name": code, "native_name": code}
                )
        return {"status": "success", "locales": locale_infos, "count": len(locale_infos)}
