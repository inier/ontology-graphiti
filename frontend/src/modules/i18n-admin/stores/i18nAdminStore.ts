import { create } from 'zustand';
import { i18nApi } from '../services/i18nApi';
import type { TranslationEntry, I18nModule } from '../services/i18nApi';

interface I18nAdminState {
  translations: TranslationEntry[];
  modules: I18nModule[];
  locales: string[];
  currentLocale: string;
  total: number;
  loading: boolean;
  error: string | null;

  loadTranslations: (params?: { module?: string; locale?: string; page?: number; page_size?: number }) => Promise<void>;
  saveTranslation: (data: { key: string; module: string; locale: string; value: string }) => Promise<void>;
  autoTranslate: (module: string, sourceLocale: string, targetLocale: string) => Promise<void>;
  loadModules: () => Promise<void>;
  loadLocales: () => Promise<void>;
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

  autoTranslate: async (module, sourceLocale, targetLocale) => {
    set({ loading: true, error: null });
    try {
      await i18nApi.autoTranslate({ module, source_locale: sourceLocale, target_locale: targetLocale });
      await get().loadTranslations({ module, locale: targetLocale });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
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

  setCurrentLocale: (locale) => set({ currentLocale: locale }),
  clearError: () => set({ error: null }),
}));
