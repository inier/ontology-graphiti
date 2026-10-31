/**
 * 测试用 Provider 包装组件（从 renderWithProviders 拆出）
 *
 * 单独成文件的原因：react-refresh 要求「一个模块只导出组件」。
 * 本文件仅导出 `AllProviders` 组件；测试 i18n 实例在此内部维护。
 */

import React from 'react';
import { MemoryRouter, type RouteObject } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from 'i18next';
import type { i18n as I18nInstance } from 'i18next';
import { initReactI18next } from 'react-i18next';

// ─── 测试用 i18n 实例 ───

let testI18nInstance: I18nInstance | null = null;

/**
 * 获取/创建测试专用的 i18n 实例
 *
 * 与生产 i18n 实例隔离，避免测试修改影响全局状态。
 * 使用最小化的翻译资源，仅提供测试所需的 key。
 */
function getTestI18nInstance(): I18nInstance {
  if (testI18nInstance) return testI18nInstance;

  testI18nInstance = i18n.createInstance();
  testI18nInstance.use(initReactI18next).init({
    resources: {
      'zh-CN': {
        common: {
          'app.title': 'ODAP',
          'button.save': '保存',
          'button.cancel': '取消',
          'button.delete': '删除',
          'button.edit': '编辑',
          'button.create': '创建',
          'button.search': '搜索',
          'button.confirm': '确认',
          'label.name': '名称',
          'label.description': '描述',
          'label.status': '状态',
          'label.type': '类型',
          'label.action': '操作',
          'message.loading': '加载中...',
          'message.success': '操作成功',
          'message.error': '操作失败',
          'message.confirm_delete': '确认删除？',
          'message.no_data': '暂无数据',
        },
        messages: {
          'login.success': '登录成功',
          'login.failed': '登录失败',
          'logout.success': '已退出登录',
        },
      },
      'en-US': {
        common: {
          'app.title': 'ODAP',
          'button.save': 'Save',
          'button.cancel': 'Cancel',
          'button.delete': 'Delete',
          'button.edit': 'Edit',
          'button.create': 'Create',
          'button.search': 'Search',
          'button.confirm': 'Confirm',
          'label.name': 'Name',
          'label.description': 'Description',
          'label.status': 'Status',
          'label.type': 'Type',
          'label.action': 'Action',
          'message.loading': 'Loading...',
          'message.success': 'Success',
          'message.error': 'Error',
          'message.confirm_delete': 'Confirm delete?',
          'message.no_data': 'No data',
        },
        messages: {
          'login.success': 'Login successful',
          'login.failed': 'Login failed',
          'logout.success': 'Logged out',
        },
      },
    },
    fallbackLng: 'zh-CN',
    ns: ['common', 'messages'],
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
    lng: 'zh-CN',
  });

  return testI18nInstance;
}

// ─── Provider 组件 ───

/** AllProviders 的 props */
interface AllProvidersProps {
  children: React.ReactNode;
  route?: string;
  routes?: RouteObject[];
  locale?: string;
  withAuth?: boolean;
  authToken?: string;
  userData?: Record<string, unknown>;
}

/**
 * 全量 Provider 包装组件
 *
 * 包含：MemoryRouter + I18nextProvider + localStorage 认证状态
 */
export function AllProviders({
  children,
  route = '/',
  locale = 'zh-CN',
  withAuth = true,
  authToken = 'test-access-token',
  userData,
}: AllProvidersProps): React.ReactElement {
  // 设置认证状态到 localStorage
  if (withAuth) {
    if (!localStorage.getItem('token')) {
      localStorage.setItem('token', authToken);
    }
    if (!localStorage.getItem('refresh_token')) {
      localStorage.setItem('refresh_token', 'test-refresh-token');
    }
    if (!localStorage.getItem('user') && !userData) {
      localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'user-1',
          username: 'admin',
          global_role: 'admin',
          role_id: '1',
        }),
      );
    }
    if (userData && !localStorage.getItem('user')) {
      localStorage.setItem('user', JSON.stringify(userData));
    }
  }

  // 设置 i18n 语言
  const i18nInstance = getTestI18nInstance();
  if (i18nInstance.language !== locale) {
    i18nInstance.changeLanguage(locale);
  }

  return (
    <MemoryRouter initialEntries={[route]} initialIndex={0}>
      <I18nextProvider i18n={i18nInstance}>
        {children}
      </I18nextProvider>
    </MemoryRouter>
  );
}
