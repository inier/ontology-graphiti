import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/i18n`;

export interface TranslationEntry {
  key: string;
  module: string;
  locale: string;
  value: string;
  status: 'draft' | 'reviewed' | 'approved';
  updated_at: string;
  updated_by: string;
}

export interface I18nModule {
  name: string;
  key_count: number;
  locale_count: number;
  locales: string[];
}

export interface LocaleInfo {
  code: string;
  name: string;
  native_name: string;
  is_active: boolean;
  created_at: string;
}

export interface ScanMissingResult {
  status: string;
  module: string;
  locale: string;
  total: number;
  missing: number;
  missing_keys: string[];
}

export const i18nApi = {
  listTranslations: (params?: { module?: string; locale?: string; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.module) searchParams.set('module', params.module);
    if (params?.locale) searchParams.set('locale', params.locale);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    const qs = searchParams.toString();
    return fetchJson<{ translations: TranslationEntry[]; total: number }>(`${BASE}/translations${qs ? '?' + qs : ''}`);
  },

  saveTranslation: (data: { key: string; module: string; locale: string; value: string }) =>
    fetchJson<TranslationEntry>(`${BASE}/translations`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  saveTranslationsBulk: (items: Array<{ key: string; module: string; locale: string; value: string }>) =>
    fetchJson<{ status: string; count: number }>(`${BASE}/translations/bulk`, {
      method: 'PUT',
      body: JSON.stringify({ items }),
    }),

  deleteTranslation: (data: { key: string; module: string; locale: string }) =>
    fetchJson<void>(`${BASE}/translations`, {
      method: 'DELETE',
      body: JSON.stringify(data),
    }),

  reviewTranslation: (key: string, module: string, locale: string, approved: boolean) =>
    fetchJson<void>(`${BASE}/translations/review`, {
      method: 'POST',
      body: JSON.stringify({ key, module, locale, approved }),
    }),

  autoTranslate: (data: { module: string; source_locale: string; target_locale: string }) =>
    fetchJson<{ translated_count: number; total_count: number; skipped: number }>(`${BASE}/auto-translate`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listModules: () =>
    fetchJson<{ modules: I18nModule[]; count: number }>(`${BASE}/modules`),

  listLocales: () =>
    fetchJson<{ locales: LocaleInfo[]; count: number }>(`${BASE}/locales`),

  addLocale: (data: { code: string; name: string; native_name: string; is_active?: boolean }) =>
    fetchJson<{ status: string; locale: LocaleInfo }>(`${BASE}/locales`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  removeLocale: (code: string, deleteTranslations = false) =>
    fetchJson<{ status: string; code: string; deactivated: boolean }>(
      `${BASE}/locales/${encodeURIComponent(code)}?delete_translations=${deleteTranslations}`,
      { method: 'DELETE' },
    ),

  getBundle: (namespace: string, locale: string) =>
    fetchJson<{ status: string; namespace: string; locale: string; bundle: Record<string, string> }>(
      `${BASE}/bundles/${encodeURIComponent(namespace)}/${encodeURIComponent(locale)}`,
    ),

  scanMissing: (data: { module: string; locale: string }) =>
    fetchJson<ScanMissingResult>(`${BASE}/scan-missing`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
