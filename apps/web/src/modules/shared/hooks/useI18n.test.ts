import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useI18n } from './useI18n';

vi.mock('../stores/i18nStore', () => ({
  setLocale: vi.fn(),
  getCurrentLocale: vi.fn(),
}));

import { setLocale } from '../stores/i18nStore';

describe('useI18n Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('returns translation function and locale info', () => {
    const { result } = renderHook(() => useI18n());

    expect(result.current.t).toBeDefined();
    expect(result.current.locale).toBeDefined();
    expect(result.current.changeLocale).toBeDefined();
    expect(result.current.isZh).toBeDefined();
    expect(result.current.isEn).toBeDefined();
    expect(result.current.instance).toBeDefined();
  });

  it('returns correct isZh and isEn flags based on locale', () => {
    const { result } = renderHook(() => useI18n());

    if (result.current.locale === 'zh-CN') {
      expect(result.current.isZh).toBe(true);
      expect(result.current.isEn).toBe(false);
    } else {
      expect(result.current.isZh).toBe(false);
      expect(result.current.isEn).toBe(true);
    }
  });

  it('calls setLocale when changeLocale is invoked', () => {
    const { result } = renderHook(() => useI18n());

    act(() => {
      result.current.changeLocale('en-US');
    });

    expect(setLocale).toHaveBeenCalledWith('en-US');
  });

  it('works with custom namespace', () => {
    const { result } = renderHook(() => useI18n('menu-names'));

    expect(result.current.t).toBeDefined();
    expect(result.current.locale).toBeDefined();
  });
});
