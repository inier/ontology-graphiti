import { create } from 'zustand';
import { i18nApi } from '../services/i18nApi';
import type { TranslationEntry, I18nModule, LocaleInfo, ScanMissingResult } from '../services/i18nApi';

interface I18nAdminState {
  translations: TranslationEntry[];
  modules: I18nModule[];
  locales: LocaleInfo[];
  currentLocale: string;
  total: number;
  loading: boolean;
  error: string | null;

  loadTranslations: (params?: { module?: string; locale?: string; page?: number; page_size?: number }) => Promise<void>;
  saveTranslation: (data: { key: string; module: string; locale: string; value: string }) => Promise<void>;
  saveTranslationsBulk: (items: Array<{ key: string; module: string; locale: string; value: string }>) => Promise<number>;
  deleteTranslation: (data: { key: string; module: string; locale: string }) => Promise<void>;
  autoTranslate: (module: string, sourceLocale: string, targetLocale: string) => Promise<void>;
  scanMissing: (module: string, locale: string) => Promise<ScanMissingResult | null>;
  loadModules: () => Promise<void>;
  loadLocales: () => Promise<void>;
  addLocale: (data: { code: string; name: string; native_name: string; is_active?: boolean }) => Promise<boolean>;
  removeLocale: (code: string, deleteTranslations?: boolean) => Promise<boolean>;
  setCurrentLocale: (locale: string) => void;
  clearError: () => void;
}

export const useI18nAdminStore = create<I18nAdminState>((set, get) => ({
  translations: [],
  modules: [],
  locales: [],
  currentLocale: 'zh-CN',
  total: 0,
  loading: false,
  error: null,

  loadTranslations: async (params) => {
    set({ loading: true, error: null });
    try {
      const data = await i18nApi.listTranslations(params);
      set({
        translations: data.translations || [],
        total: data.total || 0,
        loading: false,
      });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  saveTranslation: async (data) => {
    set({ loading: true, error: null });
    try {
      const updated = await i18nApi.saveTranslation(data);
      set((state) => ({
        translations: state.translations.map((t) =>
          t.key === data.key && t.module === data.module && t.locale === data.locale
            ? updated
            : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  saveTranslationsBulk: async (items) => {
    set({ loading: true, error: null });
    try {
      const result = await i18nApi.saveTranslationsBulk(items);
      set({ loading: false });
      return result.count;
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
      return 0;
    }
  },

  deleteTranslation: async (data) => {
    set({ loading: true, error: null });
    try {
      await i18nApi.deleteTranslation(data);
      set((state) => ({
        translations: state.translations.filter(
          (t) => !(t.key === data.key && t.module === data.module && t.locale === data.locale)
        ),
        total: Math.max(0, state.total - 1),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  autoTranslate: async (module, sourceLocale, targetLocale) => {
    set({ loading: true, error: null });
    try {
      await i18nApi.autoTranslate({ module, source_locale: sourceLocale, target_locale: targetLocale });
      await get().loadTranslations({ module, locale: targetLocale });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  scanMissing: async (module, locale) => {
    set({ loading: true, error: null });
    try {
      const result = await i18nApi.scanMissing({ module, locale });
      set({ loading: false });
      return result;
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
      return null;
    }
  },

  loadModules: async () => {
    try {
      const data = await i18nApi.listModules();
      set({ modules: data.modules || [] });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  loadLocales: async () => {
    try {
      const data = await i18nApi.listLocales();
      set({ locales: data.locales || [] });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  addLocale: async (data) => {
    set({ loading: true, error: null });
    try {
      await i18nApi.addLocale(data);
      await get().loadLocales();
      set({ loading: false });
      return true;
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
      return false;
    }
  },

  removeLocale: async (code, deleteTranslations = false) => {
    set({ loading: true, error: null });
    try {
      await i18nApi.removeLocale(code, deleteTranslations);
      await get().loadLocales();
      set({ loading: false });
      return true;
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
      return false;
    }
  },

  setCurrentLocale: (locale) => set({ currentLocale: locale }),
  clearError: () => set({ error: null }),
}));
