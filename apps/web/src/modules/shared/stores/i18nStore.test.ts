import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import i18n, { setLocale, getCurrentLocale, bootstrapI18n, getCachedLocales } from './i18nStore';

vi.mock('../services/apiClient', () => ({
  fetchJson: vi.fn(),
}));

import { fetchJson } from '../services/apiClient';

describe('i18nStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setLocale('zh-CN');
  });

  afterEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('has correct default language', () => {
      expect(getCurrentLocale()).toBe('zh-CN');
    });

    it('loads common namespace translations', () => {
      const resources = i18n.getResourceBundle('zh-CN', 'common');
      expect(resources).toBeDefined();
      expect(resources['保存']).toBe('保存');
      expect(resources['取消']).toBe('取消');
    });

    it('loads en-US translations', () => {
      const resources = i18n.getResourceBundle('en-US', 'common');
      expect(resources).toBeDefined();
      expect(resources['保存']).toBe('Save');
      expect(resources['取消']).toBe('Cancel');
    });
  });

  describe('setLocale', () => {
    it('changes locale to en-US', () => {
      setLocale('en-US');
      expect(getCurrentLocale()).toBe('en-US');
    });

    it('changes locale to zh-CN', () => {
      setLocale('en-US');
      setLocale('zh-CN');
      expect(getCurrentLocale()).toBe('zh-CN');
    });

    it('persists locale to localStorage', () => {
      setLocale('en-US');
      expect(localStorage.getItem('odap-locale')).toBe('en-US');
    });
  });

  describe('getCurrentLocale', () => {
    it('returns locale from localStorage', () => {
      setLocale('en-US');
      expect(localStorage.getItem('odap-locale')).toBe('en-US');
      expect(getCurrentLocale()).toBe('en-US');
    });

    it('falls back to zh-CN when localStorage is empty', () => {
      localStorage.removeItem('odap-locale');
      setLocale('zh-CN');
      expect(getCurrentLocale()).toBe('zh-CN');
    });
  });

  describe('bootstrapI18n', () => {
    it('fetches locales from API successfully', async () => {
      const mockLocales = [
        { code: 'zh-CN', name: 'Chinese', native_name: '简体中文', is_active: true },
        { code: 'en-US', name: 'English', native_name: 'English', is_active: true },
      ];
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue({ locales: mockLocales, count: 2 });

      const result = await bootstrapI18n();

      expect(fetchJson).toHaveBeenCalled();
      expect(result).toEqual(mockLocales);
      expect(getCachedLocales()).toEqual(mockLocales);
    });

    it('returns empty array when API fails', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

      const result = await bootstrapI18n();

      expect(result).toEqual([]);
      expect(getCachedLocales()).toEqual([]);
    });
  });

  describe('translation lookup', () => {
    it('returns Chinese text in zh-CN locale', () => {
      setLocale('zh-CN');
      expect(i18n.t('保存')).toBe('保存');
      expect(i18n.t('创建工作空间')).toBe('创建工作空间');
    });

    it('returns English text in en-US locale', () => {
      setLocale('en-US');
      expect(i18n.t('保存')).toBe('Save');
      expect(i18n.t('创建工作空间')).toBe('Create Workspace');
    });

    it('falls back to Chinese key when translation is missing', () => {
      setLocale('en-US');
      const missingKey = '未翻译的文本';
      expect(i18n.t(missingKey)).toBe(missingKey);
    });

    it('supports interpolation', () => {
      setLocale('zh-CN');
      expect(i18n.t('共 {{count}} 条', { count: 10 })).toBe('共 10 条');
      setLocale('en-US');
      expect(i18n.t('共 {{count}} 条', { count: 10 })).toBe('Total 10 items');
    });
  });
});
