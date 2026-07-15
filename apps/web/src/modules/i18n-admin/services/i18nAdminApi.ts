import { i18nApi } from '../services/i18nApi';
import type { LocaleInfo } from '../services/i18nApi';

export interface TranslationEntry {
  key: string;
  module: string;
  locale: string;
  value: string;
  updated_at: string;
}

export interface I18nModule {
  name: string;
  key_count: number;
  locale_count: number;
}

export const i18nAdminApi = {
  // 语言管理
  listLocales: () => i18nApi.listLocales(),
  addLocale: (data: { code: string; name: string; native_name: string; is_active?: boolean }) =>
    i18nApi.addLocale(data),
  removeLocale: (code: string, deleteTranslations = false) =>
    i18nApi.removeLocale(code, deleteTranslations),

  // 翻译管理
  listTranslations: (params?: { module?: string; locale?: string; page?: number; page_size?: number }) =>
    i18nApi.listTranslations(params),
  saveTranslation: (data: { key: string; module: string; locale: string; value: string }) =>
    i18nApi.saveTranslation(data),
  saveTranslationsBulk: (items: Array<{ key: string; module: string; locale: string; value: string }>) =>
    i18nApi.saveTranslationsBulk(items),
  deleteTranslation: (data: { key: string; module: string; locale: string }) =>
    i18nApi.deleteTranslation(data),

  // 模块管理
  listModules: () => i18nApi.listModules(),

  // 动态加载（前端 i18next）
  getBundle: (namespace: string, locale: string) =>
    i18nApi.getBundle(namespace, locale),

  // 自动翻译
  autoTranslate: (data: { module: string; source_locale: string; target_locale: string }) =>
    i18nApi.autoTranslate(data),

  // 扫描缺失
  scanMissing: (data: { module: string; locale: string }) =>
    i18nApi.scanMissing(data),
};

export type { LocaleInfo };
