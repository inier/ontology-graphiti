/**
 * Zustand Store 测试工具集
 *
 * 为 ODAP 前端 Zustand 5 store 提供隔离测试能力。
 * 核心思路：利用 Zustand 的 `create` 工厂函数特性，
 * 在测试中创建独立的 store 实例，避免测试间状态泄漏。
 *
 * @example
 * ```ts
 * import { createTestStore } from '@/test/helpers';
 * import { useAuthStore } from '@/modules/shared/stores/authStore';
 *
 * const store = createTestStore(useAuthStore);
 * store.getState().login('admin', 'password');
 * expect(store.getState().token).toBe('test-token');
 * ```
 */

import { createStore } from 'zustand/vanilla';
import type { StoreApi } from 'zustand';

// ─── 类型定义 ───

/**
 * Zustand store 的创建函数签名
 *
 * 与 `create<T>((set, get) => ({...}))` 中传入的工厂函数一致
 */
export type StoreCreator<T> = (set: StoreSetter<T>, get: StoreGetter<T>) => T;

/** Zustand set 函数签名 */
export type StoreSetter<T> = (
  partial: T | Partial<T> | ((state: T) => T | Partial<T>),
  replace?: boolean | undefined,
) => void;

/** Zustand get 函数签名 */
export type StoreGetter<T> = () => T;

/**
 * 从 useStore hook 中提取 store 状态类型
 *
 * @example
 * ```ts
 * type AuthState = ExtractStoreState<typeof useAuthStore>;
 * ```
 */
export type ExtractStoreState<T> = T extends (selector: (state: infer S) => infer R) => R
  ? S
  : T extends { getState: () => infer S }
    ? S
    : never;

// ─── 核心工具函数 ───

/**
 * 创建一个隔离的 Zustand store 实例用于测试
 *
 * 使用 `createStore` (vanilla API) 创建独立实例，
 * 不会影响全局的 `useXxxStore` hook。
 *
 * @param storeCreator - Zustand store 的创建函数（即传给 `create()` 的参数）
 * @returns 独立的 StoreApi 实例
 *
 * @example
 * ```ts
 * // 方式1：直接传入创建函数
 * const store = createTestStore((set, get) => ({
 *   count: 0,
 *   increment: () => set({ count: get().count + 1 }),
 * }));
 * store.getState().increment();
 * expect(store.getState().count).toBe(1);
 *
 * // 方式2：从现有 store 提取创建函数
 * // 注意：需要 store 模块导出创建函数，而非仅导出 hook
 * ```
 */
export function createTestStore<T>(storeCreator: StoreCreator<T>): StoreApi<T> {
  return createStore<T>(storeCreator);
}

/**
 * 将 store 重置为初始状态
 *
 * 通过调用 store 的内部 `_reset` 方法（如果存在），
 * 或者手动设置初始状态来重置。
 *
 * 注意：Zustand 原生不支持重置，需要 store 自行实现。
 * ODAP 中的 store 如果需要可重置，应在创建时添加 `_reset` 方法。
 *
 * @param store - 要重置的 store 实例
 * @param initialState - 可选的初始状态，用于覆盖重置
 *
 * @example
 * ```ts
 * const store = createTestStore((set) => ({
 *   count: 0,
 *   name: 'test',
 *   increment: () => set((s) => ({ count: s.count + 1 })),
 *   _reset: () => set({ count: 0, name: 'test' }),
 * }));
 *
 * store.getState().increment();
 * resetStore(store);
 * expect(store.getState().count).toBe(0);
 * ```
 */
export function resetStore<T extends Record<string, unknown>>(
  store: StoreApi<T>,
  initialState?: Partial<T>,
): void {
  const state = store.getState();

  // 优先使用 store 自定义的 _reset 方法
  if (typeof (state as Record<string, unknown>)._reset === 'function') {
    (state as Record<string, unknown>)._reset as () => void)();
    return;
  }

  // 如果提供了初始状态，用它来重置
  if (initialState) {
    store.setState(initialState as Partial<T>, true);
    return;
  }

  // 最后手段：尝试将所有非函数属性设为 undefined
  // 这不是理想的重置方式，仅作为兜底
  const resetState: Record<string, unknown> = {};
  for (const key of Object.keys(state)) {
    if (typeof (state as Record<string, unknown>)[key] !== 'function') {
      resetState[key] = undefined;
    }
  }
  store.setState(resetState as Partial<T>, true);
}

// ─── Store 断言工具 ───

/**
 * 获取 store 当前状态的快照
 *
 * 返回状态的深拷贝，避免测试中断言修改原状态。
 *
 * @param store - Zustand store 实例
 * @returns 状态的深拷贝
 */
export function getStoreSnapshot<T>(store: StoreApi<T>): T {
  return JSON.parse(JSON.stringify(store.getState()));
}

/**
 * 断言 store 状态中特定字段的值
 *
 * @param store - Zustand store 实例
 * @param selector - 状态选择器
 * @param expected - 期望值
 *
 * @example
 * ```ts
 * expectStoreState(authStore, (s) => s.token, 'test-token');
 * expectStoreState(authStore, (s) => s.loading, false);
 * ```
 */
export function expectStoreState<T, R>(
  store: StoreApi<T>,
  selector: (state: T) => R,
  expected: R,
): void {
  const actual = selector(store.getState());
  if (typeof expected === 'object' && expected !== null) {
    expect(actual).toEqual(expected);
  } else {
    expect(actual).toBe(expected);
  }
}

/**
 * 订阅 store 变化并收集所有状态变更
 *
 * 用于测试 store 的状态流转过程。
 * 返回一个取消订阅函数和已收集的状态列表。
 *
 * @param store - Zustand store 实例
 * @returns `{ unsubscribe, states }` - 取消订阅函数和状态历史
 *
 * @example
 * ```ts
 * const { unsubscribe, states } = subscribeToStore(authStore);
 * authStore.getState().login('admin', 'password');
 * // states 包含所有中间状态
 * unsubscribe();
 * ```
 */
export function subscribeToStore<T>(store: StoreApi<T>): {
  unsubscribe: () => void;
  states: T[];
} {
  const states: T[] = [store.getState()];
  const unsubscribe = store.subscribe((state) => {
    states.push(state);
  });
  return { unsubscribe, states };
}

// ─── ODAP 特定 Store 的测试工厂 ───

/**
 * 创建一个带有认证状态的测试 store
 *
 * 模拟已登录用户的 authStore 状态，用于需要认证的组件测试。
 *
 * @param overrides - 可选的状态覆盖
 * @returns 包含已认证状态的 store 实例
 *
 * @example
 * ```ts
 * const authStore = createAuthenticatedStore({
 *   user: { username: 'analyst', global_role: 'analyst' },
 * });
 * ```
 */
export function createAuthenticatedStore(overrides?: {
  token?: string;
  user?: Record<string, unknown>;
}): StoreApi<{
  token: string | null;
  refreshToken: string | null;
  user: Record<string, unknown> | null;
  loading: boolean;
  error: string | null;
}> {
  return createTestStore((set) => ({
    token: overrides?.token ?? 'test-access-token',
    refreshToken: 'test-refresh-token',
    user: overrides?.user ?? {
      id: 'user-1',
      username: 'admin',
      global_role: 'admin',
      role_id: '1',
    },
    loading: false,
    error: null,
    logout: () =>
      set({
        token: null,
        refreshToken: null,
        user: null,
        error: null,
      }),
    _reset: () =>
      set({
        token: overrides?.token ?? 'test-access-token',
        refreshToken: 'test-refresh-token',
        user: overrides?.user ?? {
          id: 'user-1',
          username: 'admin',
          global_role: 'admin',
          role_id: '1',
        },
        loading: false,
        error: null,
      }),
  }));
}
