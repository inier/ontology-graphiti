import { useEffect, useState, useCallback } from 'react';
import { Select, Tooltip } from 'antd';
import { GlobalOutlined } from '@ant-design/icons';
import {
  setLocale,
  getCurrentLocale,
  bootstrapI18n,
  getCachedLocales,
} from '../stores/i18nStore';
import type { LocaleInfo } from '@/modules/i18n-admin/services/i18nApi';

interface LanguageSwitcherProps {
  size?: 'small' | 'middle' | 'large';
  showIcon?: boolean;
}

/**
 * 全局语言切换器
 *
 * - 从后端 /api/i18n/locales 拉取可用语言列表
 * - 切换语言时同步调用 setLocale() 加载新语言的所有 bundle
 * - App 挂载时会自动 bootstrap 一次
 */
export function LanguageSwitcher({
  size = 'middle',
  showIcon = true,
}: LanguageSwitcherProps) {
  const [locales, setLocales] = useState<LocaleInfo[]>([]);
  const [current, setCurrent] = useState<string>(getCurrentLocale());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    void (async () => {
      try {
        setLoading(true);
        await bootstrapI18n();
        if (!mounted) return;
        const cached = getCachedLocales();
        setLocales(cached);
        setCurrent(getCurrentLocale());
      } catch (e) {
        console.warn('LanguageSwitcher: bootstrap failed', e);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const handleChange = useCallback((value: string) => {
    setLocale(value);
    setCurrent(value);
  }, []);

  // 兜底：locales 列表为空时至少提供内置语言
  const options = (
    locales.length > 0
      ? locales
      : [
          { code: 'zh-CN', name: 'Chinese', native_name: '简体中文' },
          { code: 'en-US', name: 'English', native_name: 'English' },
          { code: 'ja-JP', name: 'Japanese', native_name: '日本語' },
        ]
  ).map((loc) => ({
    value: loc.code,
    label: `${loc.native_name || loc.name} (${loc.code})`,
  }));

  return (
    <Tooltip title="切换语言">
      <Select
        value={current}
        onChange={handleChange}
        size={size}
        style={{ minWidth: 150 }}
        loading={loading}
        options={options}
        suffixIcon={showIcon ? <GlobalOutlined /> : undefined}
        data-testid="language-switcher"
      />
    </Tooltip>
  );
}

export default LanguageSwitcher;
