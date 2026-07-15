/**
 * ODAP 前端测试工具集 - 统一导出
 *
 * 从此处导入所有测试辅助工具，避免记忆多个文件路径。
 *
 * @example
 * ```ts
 * // API mock 工具
 * import { createMockFetch, mockApiEndpoint, authMocks } from '@/test/helpers';
 *
 * // Store 测试工具
 * import { createTestStore, resetStore, createAuthenticatedStore } from '@/test/helpers';
 *
 * // 组件渲染工具
 * import { renderWithProviders, renderWithRouter, cleanupAuthState } from '@/test/helpers';
 * ```
 */

// ─── API Mock 工具 ───
export {
  // 核心函数
  createMockFetch,
  createSuccessResponse,
  createErrorResponse,
  mockApiEndpoint,
  createEndpointMockFetch,
  clearEndpointMocks,

  // ODAP 场景快捷 mock
  authMocks,
  workspaceMocks,
  healthMocks,
} from './apiMock';

// API Mock 类型
export type {
  ApiSuccessResponse,
  ApiErrorResponse,
  ApiResponse,
  MockResponseOverrides,
  EndpointKey,
  EndpointMockMap,
  MockEndpointConfig,
} from './apiMock';

// ─── Zustand Store 测试工具 ───
export {
  // 核心函数
  createTestStore,
  resetStore,
  getStoreSnapshot,
  expectStoreState,
  subscribeToStore,

  // ODAP 场景快捷工厂
  createAuthenticatedStore,
} from './storeTestUtils';

// Store 测试类型
export type {
  StoreCreator,
  StoreSetter,
  StoreGetter,
  ExtractStoreState,
} from './storeTestUtils';

// ─── 组件渲染工具 ───
export {
  // 核心函数
  renderWithProviders,
  renderWithRouter,

  // 环境管理
  cleanupAuthState,
  setupAuthState,
} from './renderWithProviders';

// 渲染工具类型
export type {
  CustomRenderOptions,
} from './renderWithProviders';
