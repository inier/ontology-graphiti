import os
import pytest
from datetime import datetime


class TestSQLiteI18nStorage:
    def setup_method(self):
        from odap.biz.platform.i18n.storage.sqlite_i18n_storage import SQLiteI18nStorage
        self.db_path = os.path.join(os.getcwd(), "test_i18n.db")
        self.storage = SQLiteI18nStorage(db_path=self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _make_translation(self, **overrides):
        defaults = {
            "key": "test.key",
            "module": "common",
            "locale": "zh-CN",
            "value": "测试值",
        }
        defaults.update(overrides)
        from odap.biz.platform.i18n.models.translation import Translation
        return Translation(**defaults)

    def test_save_and_get_translation(self):
        t = self._make_translation()
        result = self.storage.save_translation(t)
        assert result["key"] == "test.key"
        assert result["value"] == "测试值"

        fetched = self.storage.get_translation("test.key", "common", "zh-CN")
        assert fetched is not None
        assert fetched["value"] == "测试值"

    def test_get_translation_not_found(self):
        result = self.storage.get_translation("nonexistent", "common", "zh-CN")
        assert result is None

    def test_save_translation_upsert(self):
        t1 = self._make_translation(value="原始值")
        self.storage.save_translation(t1)
        t2 = self._make_translation(value="更新值")
        self.storage.save_translation(t2)

        fetched = self.storage.get_translation("test.key", "common", "zh-CN")
        assert fetched["value"] == "更新值"

    def test_list_translations(self):
        for i in range(5):
            t = self._make_translation(key=f"key{i}", value=f"值{i}")
            self.storage.save_translation(t)

        result = self.storage.list_translations(module="common", locale="zh-CN")
        assert result["total"] == 5
        assert len(result["translations"]) == 5

    def test_list_translations_pagination(self):
        for i in range(10):
            t = self._make_translation(key=f"key{i}", value=f"值{i}")
            self.storage.save_translation(t)

        page1 = self.storage.list_translations(module="common", locale="zh-CN", page=1, page_size=5)
        assert len(page1["translations"]) == 5
        assert page1["total"] == 10

        page2 = self.storage.list_translations(module="common", locale="zh-CN", page=2, page_size=5)
        assert len(page2["translations"]) == 5

    def test_list_translations_filter_by_module(self):
        t1 = self._make_translation(module="common", key="k1")
        t2 = self._make_translation(module="ontology", key="k2")
        self.storage.save_translation(t1)
        self.storage.save_translation(t2)

        result = self.storage.list_translations(module="common")
        assert result["total"] == 1
        assert result["translations"][0]["module"] == "common"

    def test_list_translations_filter_by_locale(self):
        t1 = self._make_translation(locale="zh-CN", key="k1")
        t2 = self._make_translation(locale="en-US", key="k1", value="test value")
        self.storage.save_translation(t1)
        self.storage.save_translation(t2)

        result = self.storage.list_translations(locale="en-US")
        assert result["total"] == 1
        assert result["translations"][0]["locale"] == "en-US"

    def test_delete_translation(self):
        t = self._make_translation()
        self.storage.save_translation(t)
        assert self.storage.delete_translation("test.key", "common", "zh-CN") is True
        assert self.storage.get_translation("test.key", "common", "zh-CN") is None

    def test_delete_translation_not_found(self):
        assert self.storage.delete_translation("nonexistent", "common", "zh-CN") is False

    def test_list_modules(self):
        self.storage.save_translation(self._make_translation(module="common"))
        self.storage.save_translation(self._make_translation(module="ontology", key="k2"))

        modules = self.storage.list_modules()
        assert "common" in modules
        assert "ontology" in modules

    def test_list_locales(self):
        self.storage.save_translation(self._make_translation(locale="zh-CN"))
        self.storage.save_translation(self._make_translation(locale="en-US", key="k2", value="test"))

        locales = self.storage.list_locales()
        assert "zh-CN" in locales
        assert "en-US" in locales


class TestTranslationModel:
    def test_translation_creation(self):
        from odap.biz.platform.i18n.models.translation import Translation
        t = Translation(key="test.key", module="common", locale="zh-CN", value="测试")
        assert t.key == "test.key"
        assert t.module == "common"
        assert t.locale == "zh-CN"
        assert t.value == "测试"
        assert t.updated_at is not None

    def test_translation_default_updated_at(self):
        from odap.biz.platform.i18n.models.translation import Translation
        t = Translation(key="k", module="m", locale="l", value="v")
        assert t.updated_at is not None
        assert len(t.updated_at) > 10

    def test_locale_info(self):
        from odap.biz.platform.i18n.models.translation import LocaleInfo
        info = LocaleInfo(code="zh-CN", name="Chinese", native_name="简体中文")
        assert info.code == "zh-CN"
        assert info.native_name == "简体中文"


class TestI18nService:
    def setup_method(self):
        from odap.biz.platform.i18n.storage.sqlite_i18n_storage import SQLiteI18nStorage
        from odap.biz.platform.i18n.services.i18n_service import I18nService
        self.db_path = os.path.join(os.getcwd(), "test_i18n_service.db")
        I18nService._instance = None
        self.service = I18nService()
        self.service._storage = SQLiteI18nStorage(db_path=self.db_path)
        self.service._initialized = True

    def teardown_method(self):
        from odap.biz.platform.i18n.services.i18n_service import I18nService
        I18nService._instance = None
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_save_translation(self):
        result = self.service.save_translation("greeting", "common", "zh-CN", "你好")
        assert result["key"] == "greeting"
        assert result["value"] == "你好"

    def test_get_translations(self):
        self.service.save_translation("greeting", "common", "zh-CN", "你好")
        self.service.save_translation("greeting", "common", "en-US", "Hello")

        result = self.service.get_translations(module="common")
        assert result["total"] == 2

    def test_get_translations_filtered(self):
        self.service.save_translation("greeting", "common", "zh-CN", "你好")
        self.service.save_translation("greeting", "common", "en-US", "Hello")

        result = self.service.get_translations(module="common", locale="zh-CN")
        assert result["total"] == 1
        assert result["translations"][0]["locale"] == "zh-CN"

    def test_list_modules(self):
        self.service.save_translation("k1", "common", "zh-CN", "v1")
        self.service.save_translation("k2", "ontology", "zh-CN", "v2")

        result = self.service.list_modules()
        assert result["status"] == "success"
        assert "common" in result["modules"]
        assert "ontology" in result["modules"]

    def test_list_locales(self):
        self.service.save_translation("k1", "common", "zh-CN", "v1")

        result = self.service.list_locales()
        assert result["status"] == "success"
        locale_codes = [loc["code"] for loc in result["locales"]]
        assert "zh-CN" in locale_codes

    def test_auto_translate_no_source(self):
        result = self.service.auto_translate("nonexistent", "zh-CN", "en-US")
        assert result["status"] == "error"
        assert "No source translations" in result["message"]

    def test_auto_translate_without_api_key(self):
        self.service.save_translation("hello", "common", "zh-CN", "你好")
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = self.service.auto_translate("common", "zh-CN", "en-US")
            assert result["status"] == "success"
            assert result["translated_count"] == 0
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
