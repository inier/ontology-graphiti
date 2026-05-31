import { create } from 'zustand';
import type { BreakpointKey } from '../styles/breakpoints.ts';

type Locale = 'zh-CN' | 'en-US';

interface TranslationEntry {
  [key: string]: string | TranslationEntry;
}

interface I18nState {
  locale: Locale;
  translations: Record<Locale, TranslationEntry>;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string>) => string;
  loadTranslations: (locale: Locale, namespace: string, data: TranslationEntry) => void;
}

const STORAGE_KEY = 'odap-locale';

function getStoredLocale(): Locale {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'zh-CN' || stored === 'en-US') {
    return stored;
  }
  return 'zh-CN';
}

function resolveNestedKey(obj: TranslationEntry, key: string): string {
  const parts = key.split('.');
  let current: any = obj;
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = current[part];
    } else {
      return key;
    }
  }
  return typeof current === 'string' ? current : key;
}

export const useI18nStore = create<I18nState>((set, get) => ({
  locale: getStoredLocale(),
  translations: {
    'zh-CN': {},
    'en-US': {},
  },

  setLocale: (locale: Locale) => {
    localStorage.setItem(STORAGE_KEY, locale);
    set({ locale });
  },

  t: (key: string, params?: Record<string, string>) => {
    const state = get();
    const translations = state.translations[state.locale];
    let value = resolveNestedKey(translations, key);

    if (params) {
      for (const [paramKey, paramValue] of Object.entries(params)) {
        value = value.replace(`{{${paramKey}}}`, paramValue);
      }
    }

    return value;
  },

  loadTranslations: (locale: Locale, namespace: string, data: TranslationEntry) => {
    set((state) => ({
      translations: {
        ...state.translations,
        [locale]: {
          ...state.translations[locale],
          [namespace]: data,
        },
      },
    }));
  },
}));
