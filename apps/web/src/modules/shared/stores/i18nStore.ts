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

Object.entries(localeModules).forEach(([path, module]) => {
  const match = path.match(/\/src\/modules\/([^/]+)\/locales\/([^/]+)\/([^/]+)\.json/);
  if (match) {
    const [, , lang, namespace] = match;
    const data = (module as { default: Record<string, unknown> }).default;

    if (!resources[lang]) {
      resources[lang] = {};
    }

    resources[lang][namespace] = data;

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
    // 缺失的键先到 common 命名空间找一次：`common.*` 是跨模块共用词表
    // （按钮/标签/提示），各模块直接写 t('状态') 即可解析，
    // 不必把同一批文案复制进每个模块的语言包。
    fallbackNS: 'common',
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