/**
 * 组件渲染工具集
 *
 * 为 ODAP 前端组件测试提供统一的 render 包装函数。
 * 自动注入 i18n、Router、Auth 等必要的 Context Provider，
 * 避免每个测试文件重复编写 Provider 包装代码。
 *
 * @example
 * ```tsx
 * import { renderWithProviders, renderWithRouter } from '@/test/helpers';
 *
 * // 带所有 Provider 的渲染
 * const { container } = renderWithProviders(<MyComponent />);
 *
 * // 带路由的渲染（指定初始路径）
 * const { getByText } = renderWithRouter(<MyComponent />, '/workspace');
 * ```
 */

import React from 'react';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import { MemoryRouter, type RouteObject } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// ─── 类型定义 ───

/** renderWithProviders 的额外配置选项 */
export interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  /** 初始路由路径，默认 '/' */
  route?: string;
  /** 路由配置（用于测试特定路由匹配） */
  routes?: RouteObject[];
  /** i18n 语言，默认 'zh-CN' */
  locale?: string;
  /** 是否注入认证 token 到 localStorage，默认 true */
  withAuth?: boolean;
  /** 自定义认证 token 值 */
  authToken?: string;
  /** 自定义用户数据写入 localStorage */
  userData?: Record<string, unknown>;
}

// ─── 测试用 i18n 实例 ───

let testI18nInstance: i18n.i18n | null = null;

/**
 * 获取/创建测试专用的 i18n 实例
 *
 * 与生产 i18n 实例隔离，避免测试修改影响全局状态。
 * 使用最小化的翻译资源，仅提供测试所需的 key。
 */
function getTestI18nInstance(): i18n.i18n {
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
function AllProviders({
  children,
  route = '/',
  routes,
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

// ─── 核心渲染函数 ───

/**
 * 带全量 Provider 的组件渲染
 *
 * 自动包装 MemoryRouter + I18nextProvider，并可选注入认证状态。
 * 这是 ODAP 前端组件测试的推荐渲染方式。
 *
 * @param ui - 要渲染的 React 元素
 * @param options - 渲染选项
 * @returns @testing-library/react 的 RenderResult
 *
 * @example
 * ```tsx
 * // 基础用法
 * const { getByText } = renderWithProviders(<MyComponent />);
 *
 * // 带路由和认证
 * const { container } = renderWithProviders(<WorkspacePage />, {
 *   route: '/workspace',
 *   withAuth: true,
 * });
 *
 * // 不带认证（测试未登录状态）
 * const { getByText } = renderWithProviders(<LoginPage />, {
 *   withAuth: false,
 * });
 *
 * // 指定语言
 * const { getByText } = renderWithProviders(<MyComponent />, {
 *   locale: 'en-US',
 * });
 * ```
 */
export function renderWithProviders(
  ui: React.ReactElement,
  options: CustomRenderOptions = {},
): RenderResult {
  const {
    route,
    routes,
    locale,
    withAuth,
    authToken,
    userData,
    ...renderOptions
  } = options;

  // 清理认证状态（如果不需要认证）
  if (!withAuth) {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    localStorage.removeItem('currentRoleId');
  }

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <AllProviders
      route={route}
      routes={routes}
      locale={locale}
      withAuth={withAuth}
      authToken={authToken}
      userData={userData}
    >
      {children}
    </AllProviders>
  );

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

/**
 * 带路由的组件渲染
 *
 * renderWithProviders 的路由特化版本，更简洁的 API。
 * 默认注入认证状态。
 *
 * @param ui - 要渲染的 React 元素
 * @param route - 初始路由路径，默认 '/'
 * @returns RenderResult
 *
 * @example
 * ```tsx
 * const { getByText } = renderWithRouter(<MyComponent />, '/workspace');
 * ```
 */
export function renderWithRouter(
  ui: React.ReactElement,
  route: string = '/',
): RenderResult {
  return renderWithProviders(ui, { route, withAuth: true });
}

// ─── 测试清理 ───

/**
 * 清理测试环境中的认证状态
 *
 * 在 afterEach 中调用，确保测试间状态隔离。
 *
 * @example
 * ```ts
 * afterEach(() => {
 *   cleanupAuthState();
 * });
 * ```
 */
export function cleanupAuthState(): void {
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  localStorage.removeItem('currentRoleId');
}

/**
 * 设置认证状态（用于需要认证的测试）
 *
 * @param token - JWT token
 * @param user - 用户数据
 *
 * @example
 * ```ts
 * setupAuthState('my-token', { username: 'analyst', global_role: 'analyst' });
 * ```
 */
export function setupAuthState(
  token: string = 'test-access-token',
  user?: Record<string, unknown>,
): void {
  localStorage.setItem('token', token);
  localStorage.setItem('refresh_token', 'test-refresh-token');
  localStorage.setItem(
    'user',
    JSON.stringify(
      user || {
        id: 'user-1',
        username: 'admin',
        global_role: 'admin',
        role_id: '1',
      },
    ),
  );
  localStorage.setItem('currentRoleId', (user?.role_id as string) || '1');
}
