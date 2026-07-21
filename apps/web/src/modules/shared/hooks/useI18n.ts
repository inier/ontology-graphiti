import { useTranslation } from 'react-i18next';
import { setLocale, getCurrentLocale, type Locale } from '../stores/i18nStore';

export function useI18n(namespace?: string) {
  const { t, i18n: instance } = useTranslation(namespace);

  const changeLocale = (locale: Locale) => {
    setLocale(locale);
  };

  const currentLocale = (instance.language as Locale) || 'zh-CN';

  return {
    t,
    locale: currentLocale,
    changeLocale,
    isZh: currentLocale === 'zh-CN',
    isEn: currentLocale === 'en-US',
    isJa: currentLocale === 'ja-JP',
    instance,
  };
}
