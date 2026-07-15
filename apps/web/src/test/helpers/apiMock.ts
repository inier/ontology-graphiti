/**
 * API Mock 工具集
 *
 * 为 ODAP 前端测试提供类型安全的 API mock 工具。
 * 基于 vitest vi.fn() + globalThis.fetch mock 模式，
 * 与 setup.ts 中 `globalThis.fetch = vi.fn()` 的初始化方式一致。
 *
 * @example
 * ```ts
 * import { createMockFetch, mockApiEndpoint } from '@/test/helpers';
 *
 * // 方式1：创建通用 mock fetch
 * const mockFetch = createMockFetch({ workspaces: [] });
 *
 * // 方式2：精确 mock 某个端点
 * mockApiEndpoint('GET', '/api/workspaces', { workspaces: [], total: 0 });
 * ```
 */

import { vi } from 'vitest';

// ─── 类型定义 ───

/** API 成功响应的标准包装格式 */
export interface ApiSuccessResponse<T = unknown> {
  status: 'success';
  data: T;
  message?: string;
}

/** API 错误响应的标准包装格式 */
export interface ApiErrorResponse {
  status: 'error';
  message: string;
  detail?: string;
  code?: string;
}

/** API 响应联合类型 */
export type ApiResponse<T = unknown> = ApiSuccessResponse<T> | ApiErrorResponse;

/** Mock fetch 的可配置响应映射：URL path → 响应数据 */
export type MockResponseOverrides = Record<string, unknown>;

/** 端点 Mock 的键格式：`METHOD /path` */
export type EndpointKey = `${string} ${string}`;

/** 端点 Mock 映射表 */
export type EndpointMockMap = Map<EndpointKey, MockEndpointConfig>;

/** 端点 Mock 配置 */
export interface MockEndpointConfig {
  /** HTTP 状态码，默认 200 */
  status?: number;
  /** 响应体数据 */
  data: unknown;
  /** 响应头 */
  headers?: Record<string, string>;
  /** 是否抛出网络错误（模拟断网） */
  networkError?: boolean;
  /** 延迟毫秒数（模拟慢速网络） */
  delay?: number;
}

// ─── 核心工具函数 ───

/**
 * 创建成功的 API 响应包装
 *
 * @param data - 响应数据
 * @param message - 可选消息
 * @returns 标准成功响应对象
 *
 * @example
 * ```ts
 * const response = createSuccessResponse({ workspaces: [], total: 0 });
 * // => { status: 'success', data: { workspaces: [], total: 0 } }
 * ```
 */
export function createSuccessResponse<T>(data: T, message?: string): ApiSuccessResponse<T> {
  return {
    status: 'success',
    data,
    ...(message !== undefined && { message }),
  };
}

/**
 * 创建错误的 API 响应
 *
 * @param message - 错误消息
 * @param status - HTTP 状态码，默认 500
 * @param detail - 可选详细错误信息
 * @returns 标准错误响应对象
 *
 * @example
 * ```ts
 * const error = createErrorResponse('Workspace not found', 404);
 * // => { status: 'error', message: 'Workspace not found' }
 * ```
 */
export function createErrorResponse(message: string, status: number = 500, detail?: string): ApiErrorResponse {
  return {
    status: 'error',
    message,
    ...(detail !== undefined && { detail }),
  };
}

/**
 * 创建一个 mock fetch 函数，对所有请求返回统一响应
 *
 * 适用于不需要区分端点的简单测试场景。
 * 内部会根据请求 URL 和 method 自动匹配 overrides 中的 key。
 *
 * @param overrides - URL path 到响应数据的映射；未匹配时返回默认空对象
 * @returns vitest mock fn，可直接赋值给 globalThis.fetch
 *
 * @example
 * ```ts
 * const mockFetch = createMockFetch({
 *   '/api/workspaces': { workspaces: [], total: 0 },
 *   '/api/health': { status: 'ok' },
 * });
 * globalThis.fetch = mockFetch;
 * ```
 */
export function createMockFetch(overrides: MockResponseOverrides = {}): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const path = extractPath(url);

    // 在 overrides 中查找匹配的路径
    let data: unknown = {};
    for (const [key, value] of Object.entries(overrides)) {
      if (path.includes(key) || key === path) {
        data = value;
        break;
      }
    }

    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as unknown as typeof fetch;
}

// ─── 端点级 Mock 系统 ───

/** 全局端点 mock 注册表 */
const endpointMocks: EndpointMockMap = new Map();

/**
 * 注册一个端点 mock
 *
 * @param method - HTTP 方法 (GET, POST, PUT, DELETE 等)
 * @param path - API 路径 (如 /api/workspaces)
 * @param response - 响应数据或完整配置
 *
 * @example
 * ```ts
 * // 简单用法：直接传响应数据
 * mockApiEndpoint('GET', '/api/workspaces', { workspaces: [], total: 0 });
 *
 * // 完整配置：控制状态码、延迟、网络错误
 * mockApiEndpoint('POST', '/api/auth/login', {
 *   status: 401,
 *   data: { status: 'error', message: 'Invalid credentials' },
 *   delay: 100,
 * });
 * ```
 */
export function mockApiEndpoint(
  method: string,
  path: string,
  response: unknown | MockEndpointConfig,
): void {
  const key: EndpointKey = `${method.toUpperCase()} ${path}`;
  const config: MockEndpointConfig =
    response !== null &&
    typeof response === 'object' &&
    'data' in (response as Record<string, unknown>) &&
    !Array.isArray(response)
      ? (response as MockEndpointConfig)
      : { data: response };

  endpointMocks.set(key, config);
}

/**
 * 创建支持端点匹配的 mock fetch
 *
 * 与 mockApiEndpoint 配合使用。先注册端点，再创建 fetch mock。
 * 未匹配的请求返回 200 + 空对象。
 *
 * @returns vitest mock fn
 *
 * @example
 * ```ts
 * mockApiEndpoint('GET', '/api/workspaces', { workspaces: [] });
 * mockApiEndpoint('POST', '/api/auth/login', {
 *   status: 401,
 *   data: { message: 'Unauthorized' },
 * });
 * globalThis.fetch = createEndpointMockFetch();
 * ```
 */
export function createEndpointMockFetch(): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const path = extractPath(url);
    const method = (init?.method || 'GET').toUpperCase();

    // 精确匹配 METHOD + path
    const exactKey: EndpointKey = `${method} ${path}`;
    const exactMatch = endpointMocks.get(exactKey);
    if (exactMatch) {
      return buildMockResponse(exactMatch);
    }

    // 模糊匹配：遍历查找 path 部分匹配
    for (const [key, config] of endpointMocks.entries()) {
      const [keyMethod, keyPath] = splitEndpointKey(key);
      if (keyMethod === method && path.includes(keyPath)) {
        return buildMockResponse(config);
      }
    }

    // 未匹配：返回空 200 响应
    return new Response(JSON.stringify({}), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as unknown as typeof fetch;
}

/**
 * 清除所有已注册的端点 mock
 *
 * 通常在 beforeEach 中调用
 */
export function clearEndpointMocks(): void {
  endpointMocks.clear();
}

// ─── ODAP 特定场景的快捷 mock ───

/** 认证相关 mock */
export const authMocks = {
  /** mock 成功登录 */
  loginSuccess: (overrides?: Record<string, unknown>): void => {
    mockApiEndpoint('POST', '/api/auth/login', {
      data: {
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        user: {
          id: 'user-1',
          username: 'admin',
          global_role: 'admin',
          role_id: '1',
        },
        ...overrides,
      },
    });
  },

  /** mock 登录失败 */
  loginFailure: (message = 'Invalid credentials'): void => {
    mockApiEndpoint('POST', '/api/auth/login', {
      status: 401,
      data: { status: 'error', message },
    });
  },

  /** mock 获取当前用户信息 */
  currentUser: (overrides?: Record<string, unknown>): void => {
    mockApiEndpoint('GET', '/api/auth/me', {
      data: {
        id: 'user-1',
        username: 'admin',
        global_role: 'admin',
        role_id: '1',
        ...overrides,
      },
    });
  },
};

/** 工作空间相关 mock */
export const workspaceMocks = {
  /** mock 工作空间列表 */
  listWorkspaces: (workspaces?: Record<string, unknown>[]): void => {
    mockApiEndpoint('GET', '/api/workspaces', {
      data: {
        workspaces: workspaces || [
          { workspace_id: 'ws-1', name: 'Test Workspace', description: '', type: 'default', status: 'active', owner: 'admin' },
        ],
        total: workspaces?.length || 1,
      },
    });
  },

  /** mock 创建工作空间 */
  createWorkspace: (overrides?: Record<string, unknown>): void => {
    mockApiEndpoint('POST', '/api/workspaces', {
      data: {
        workspace_id: 'ws-new',
        name: 'New Workspace',
        description: '',
        type: 'default',
        status: 'active',
        owner: 'admin',
        ...overrides,
      },
    });
  },
};

/** 健康检查 mock */
export const healthMocks = {
  /** mock 健康检查通过 */
  healthy: (): void => {
    mockApiEndpoint('GET', '/health', { data: { status: 'ok' } });
  },
};

// ─── 内部工具函数 ───

/** 从完整 URL 中提取路径部分 */
function extractPath(url: string): string {
  try {
    const parsed = new URL(url, 'http://localhost');
    return parsed.pathname;
  } catch {
    // 如果 URL 解析失败，直接返回原始字符串
    return url;
  }
}

/** 将端点键拆分为 method 和 path */
function splitEndpointKey(key: EndpointKey): [string, string] {
  const spaceIndex = key.indexOf(' ');
  if (spaceIndex === -1) return ['GET', key];
  return [key.slice(0, spaceIndex), key.slice(spaceIndex + 1)];
}

/** 根据 MockEndpointConfig 构建 Response */
async function buildMockResponse(config: MockEndpointConfig): Promise<Response> {
  // 模拟网络延迟
  if (config.delay && config.delay > 0) {
    await new Promise((resolve) => setTimeout(resolve, config.delay));
  }

  // 模拟网络错误
  if (config.networkError) {
    throw new TypeError('Failed to fetch');
  }

  const status = config.status || 200;
  const headers = {
    'Content-Type': 'application/json',
    ...config.headers,
  };

  return new Response(JSON.stringify(config.data), { status, headers });
}
