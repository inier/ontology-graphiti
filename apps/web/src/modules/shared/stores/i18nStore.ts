import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import { fetchJson } from '../services/apiClient';
import { API_BASE } from '@/config';
import type { LocaleInfo } from '@/modules/i18n-admin/services/i18nApi';

const STORAGE_KEY = 'odap-locale';

const localeModules = import.meta.glob('/src/modules/**/locales/**/*.json', { eager: true });

type LocaleResources = Record<string, Record<string, Record<string, unknown>>>;

const resources: LocaleResources = {};
const namespaces: string[] = [];

function flattenObject(obj: Record<string, unknown>, prefix: string = ''): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const newKey = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      Object.assign(result, flattenObject(value as Record<string, unknown>, newKey));
    } else {
      result[newKey] = value;
    }
  }
  return result;
}

function invertLocale(zhData: Record<string, unknown>, enData: Record<string, unknown>): {
  zhResources: Record<string, unknown>;
  enResources: Record<string, unknown>;
} {
  const zhFlat = flattenObject(zhData);
  const enFlat = flattenObject(enData);

  const zhResources: Record<string, unknown> = {};
  const enResources: Record<string, unknown> = {};

  for (const [oldKey, zhValue] of Object.entries(zhFlat)) {
    if (typeof zhValue === 'string') {
      const newKey = zhValue;
      zhResources[newKey] = newKey;
      const enValue = enFlat[oldKey];
      if (typeof enValue === 'string') {
        enResources[newKey] = enValue;
      }
    }
  }

  return { zhResources, enResources };
}

const skipInvertNamespaces = new Set(['menu-names', 'messages', 'common', 'i18n-admin']);

Object.entries(localeModules).forEach(([path, module]) => {
  const match = path.match(/\/src\/modules\/([^/]+)\/locales\/([^/]+)\/([^/]+)\.json/);
  if (match) {
    const [, moduleName, lang, namespace] = match;
    const data = (module as { default: Record<string, unknown> }).default;

    if (!resources[lang]) {
      resources[lang] = {};
    }

    if (skipInvertNamespaces.has(namespace)) {
      resources[lang][namespace] = data;
    } else {
      const zhPath = `/src/modules/${moduleName}/locales/zh-CN/${namespace}.json`;
      const enPath = `/src/modules/${moduleName}/locales/en-US/${namespace}.json`;

      if (lang === 'zh-CN' && localeModules[enPath]) {
        const enModule = localeModules[enPath] as { default: Record<string, unknown> };
        const { zhResources } = invertLocale(data, enModule.default);
        resources[lang][namespace] = zhResources;
      } else if (lang === 'en-US' && localeModules[zhPath]) {
        const zhModule = localeModules[zhPath] as { default: Record<string, unknown> };
        const { enResources } = invertLocale(zhModule.default, data);
        resources[lang][namespace] = enResources;
      } else {
        resources[lang][namespace] = data;
      }
    }

    if (!namespaces.includes(namespace)) {
      namespaces.push(namespace);
    }
  }
});

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'zh-CN',
    ns: namespaces,
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: STORAGE_KEY,
      caches: ['localStorage'],
    },
    returnEmptyString: false,
    parseMissingKeyHandler: (key) => key,
    missingKeyHandler: (_lng, _ns, key) => {
      console.warn(`[i18n] Missing translation key: ${key}`);
    },
  });

export default i18n;

export type Locale = 'zh-CN' | 'en-US' | 'ja-JP';

export function setLocale(locale: Locale): void {
  i18n.changeLanguage(locale);
}

export function getCurrentLocale(): Locale {
  return (i18n.language as Locale) || 'zh-CN';
}

let cachedLocales: LocaleInfo[] = [];
let bootstrapPromise: Promise<LocaleInfo[]> | null = null;

export async function bootstrapI18n(): Promise<LocaleInfo[]> {
  if (bootstrapPromise) return bootstrapPromise;

  bootstrapPromise = (async () => {
    try {
      const data = await fetchJson<{ locales: LocaleInfo[]; count: number }>(
        `${API_BASE}/api/i18n/locales`,
      );
      cachedLocales = (data?.locales ?? []).filter((l) => l.is_active);
    } catch (e) {
      console.warn('bootstrapI18n: failed to fetch locales', e);
      cachedLocales = [];
    }
    return cachedLocales;
  })();

  try {
    return await bootstrapPromise;
  } finally {
    bootstrapPromise = null;
  }
}

export function getCachedLocales(): LocaleInfo[] {
  return cachedLocales;
}