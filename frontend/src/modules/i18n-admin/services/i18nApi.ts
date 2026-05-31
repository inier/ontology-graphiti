import { fetchJson } from '../../shared/services/apiClient';
import { API_BASE } from '../../../config';

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
  locales: string[];
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
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  autoTranslate: (data: { module: string; source_locale: string; target_locale: string }) =>
    fetchJson<{ translated_count: number }>(`${BASE}/auto-translate`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listModules: () =>
    fetchJson<{ modules: I18nModule[] }>(`${BASE}/modules`),

  listLocales: () =>
    fetchJson<{ locales: string[] }>(`${BASE}/locales`),

  reviewTranslation: (key: string, module: string, locale: string, approved: boolean) =>
    fetchJson<void>(`${BASE}/translations/review`, {
      method: 'POST',
      body: JSON.stringify({ key, module, locale, approved }),
    }),
};
