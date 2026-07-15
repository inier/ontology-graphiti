import pytest
from unittest.mock import patch, MagicMock


class TestSQLiteI18nStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.platform.i18n.storage.sqlite_i18n_storage import SQLiteI18nStorage
        return SQLiteI18nStorage(db_path=str(tmp_path / "i18n_test.db"))

    def test_save_translation(self, storage):
        from odap.biz.platform.i18n.models.translation import Translation
        t = Translation(key="greeting", module="common", locale="zh-CN", value="你好")
        result = storage.save_translation(t)
        assert result["key"] == "greeting"
        assert result["module"] == "common"
        assert result["locale"] == "zh-CN"
        assert result["value"] == "你好"

    def test_get_translation(self, storage):
        from odap.biz.platform.i18n.models.translation import Translation
        t = Translation(key="greeting", module="common", locale="zh-CN", value="你好")
        storage.save_translation(t)
        result = storage.get_translation("greeting", "common", "zh-CN")
        assert result is not None
        assert result["value"] == "你好"

    def test_get_translation_not_found(self, storage):
        result = storage.get_translation("nonexistent", "common", "zh-CN")
        assert result is None

    def test_list_translations_by_module(self, storage):
        from odap.biz.platform.i18n.models.translation import Translation
        storage.save_translation(Translation(key="k1", module="common", locale="zh-CN", value="v1"))
        storage.save_translation(Translation(key="k2", module="common", locale="zh-CN", value="v2"))
        storage.save_translation(Translation(key="k3", module="admin", locale="zh-CN", value="v3"))
        result = storage.list_translations(module="common")
        assert result["total"] == 2
        assert all(t["module"] == "common" for t in result["translations"])

    def test_list_translations_by_locale(self, storage):
        from odap.biz.platform.i18n.models.translation import Translation
        storage.save_translation(Translation(key="k1", module="common", locale="zh-CN", value="你好"))
        storage.save_translation(Translation(key="k1", module="common", locale="en-US", value="Hello"))
        result = storage.list_translations(locale="en-US")
        assert result["total"] == 1
        assert result["translations"][0]["locale"] == "en-US"

    def test_delete_translation(self, storage):
        from odap.biz.platform.i18n.models.translation import Translation
        storage.save_translation(Translation(key="k1", module="common", locale="zh-CN", value="v1"))
        deleted = storage.delete_translation("k1", "common", "zh-CN")
        assert deleted is True
        assert storage.get_translation("k1", "common", "zh-CN") is None

    def test_delete_translation_not_found(self, storage):
        deleted = storage.delete_translation("nonexistent", "common", "zh-CN")
        assert deleted is False

    def test_list_modules(self, storage):
        from odap.biz.platform.i18n.models.translation import Translation
        storage.save_translation(Translation(key="k1", module="common", locale="zh-CN", value="v1"))
        storage.save_translation(Translation(key="k2", module="admin", locale="zh-CN", value="v2"))
        modules = storage.list_modules()
        assert "common" in modules
        assert "admin" in modules

    def test_list_locales(self, storage):
        from odap.biz.platform.i18n.models.translation import Translation
        storage.save_translation(Translation(key="k1", module="common", locale="zh-CN", value="v1"))
        storage.save_translation(Translation(key="k2", module="common", locale="en-US", value="v2"))
        locales = storage.list_locales()
        assert "zh-CN" in locales
        assert "en-US" in locales

    def test_save_translation_upsert(self, storage):
        from odap.biz.platform.i18n.models.translation import Translation
        storage.save_translation(Translation(key="k1", module="common", locale="zh-CN", value="旧值"))
        storage.save_translation(Translation(key="k1", module="common", locale="zh-CN", value="新值"))
        result = storage.get_translation("k1", "common", "zh-CN")
        assert result["value"] == "新值"


class TestI18nService:
    @pytest.fixture
    def service(self, tmp_path):
        from odap.biz.platform.i18n.storage.sqlite_i18n_storage import SQLiteI18nStorage
        from odap.biz.platform.i18n.services.i18n_service import I18nService
        I18nService._instance = None
        svc = I18nService.__new__(I18nService)
        svc._storage = SQLiteI18nStorage(db_path=str(tmp_path / "i18n_svc_test.db"))
        svc._initialized = True
        I18nService._instance = svc
        return svc

    def test_save_translation(self, service):
        result = service.save_translation("greeting", "common", "zh-CN", "你好")
        assert result["key"] == "greeting"
        assert result["value"] == "你好"

    def test_get_translations(self, service):
        service.save_translation("k1", "common", "zh-CN", "v1")
        service.save_translation("k2", "common", "zh-CN", "v2")
        result = service.get_translations(module="common")
        assert result["total"] == 2

    def test_list_modules(self, service):
        service.save_translation("k1", "common", "zh-CN", "v1")
        service.save_translation("k2", "admin", "zh-CN", "v2")
        result = service.list_modules()
        assert result["status"] == "success"
        assert "common" in result["modules"]
        assert "admin" in result["modules"]

    def test_list_locales(self, service):
        service.save_translation("k1", "common", "zh-CN", "v1")
        result = service.list_locales()
        assert result["status"] == "success"
        locale_codes = [loc["code"] for loc in result["locales"]]
        assert "zh-CN" in locale_codes

    def test_auto_translate_no_source(self, service):
        result = service.auto_translate("nonexistent", "zh-CN", "en-US")
        assert result.get("status") == "error"

    @patch.object(
        __import__("odap.biz.platform.i18n.services.i18n_service", fromlist=["I18nService"]).I18nService,
        "_call_llm_translate",
        return_value="Hello",
    )
    def test_auto_translate_with_mock_llm(self, mock_translate, service):
        service.save_translation("greeting", "common", "zh-CN", "你好")
        result = service.auto_translate("common", "zh-CN", "en-US")
        assert result["status"] == "success"
        assert result["translated_count"] >= 1

    def test_translation_model(self):
        from odap.biz.platform.i18n.models.translation import Translation
        t = Translation(key="k", module="m", locale="zh-CN", value="v")
        assert t.key == "k"
        assert t.module == "m"
        assert t.locale == "zh-CN"
        assert t.value == "v"
        assert t.updated_at is not None
