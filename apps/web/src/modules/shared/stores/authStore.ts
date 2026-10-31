import { create } from 'zustand';
import { apiClient } from '../services/apiClient';

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: {
    id: string;
    username: string;
    global_role: string;
    role_id: string;
    ws_id?: string;
    ws_role?: string;
  } | null;
  loading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  loginSSO: (provider: string, code: string, state: string) => Promise<void>;
  refreshTokenAction: () => Promise<void>;
  logoutAction: () => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
  setCurrentRole: (roleId: string) => void;
  getCurrentRoleId: () => string;
}

/**
 * 用户字段：`/api/auth/me` 与 `login` 响应里的 `user` 共用同一批键，
 * 且后端同时存在 `id` / `user_id`、`global_role` / `role` 两种历史键名。
 */
interface AuthUserFields {
  id?: string;
  user_id?: string;
  username?: string;
  global_role?: string;
  role?: string;
  role_id?: string;
  ws_id?: string;
  ws_role?: string;
}

/** `POST /api/auth/login`、`/sso/:provider`、`/refresh` 的返回体 */
interface AuthTokenResponse {
  access_token?: string;
  token?: string;
  refresh_token?: string;
  user?: AuthUserFields;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token'),
  refreshToken: localStorage.getItem('refresh_token'),
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  loading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.post<AuthTokenResponse>(
        '/api/auth/login',
        { username, password },
        { skipAuth: true },
      );
      const token = data.access_token || data.token || '';
      const refreshToken = data.refresh_token || '';
      const userData = data.user || {};
      const globalRole = userData.global_role || 'observer';
      const user = {
        id: userData.id || '',
        username: userData.username || '',
        global_role: globalRole,
        // role_id 与 global_role 恒等（后端 GLOBAL_ROLE_TO_ID 已统一），
        // 菜单权限以 global_role 字符串为键，避免历史数字 id（"1".."5"）不一致。
        role_id: userData.role_id || globalRole,
      };

      localStorage.setItem('token', token);
      localStorage.setItem('refresh_token', refreshToken);
      localStorage.setItem('user', JSON.stringify(user));
      localStorage.setItem('currentRoleId', user.role_id);

      set({ token, refreshToken, user, loading: false });
    } catch (error) {
      const errMessage = error instanceof Error ? error.message : String(error);
      set({
        error: error instanceof Error ? errMessage : 'Login failed',
        loading: false,
      });
    }
  },

  loginSSO: async (provider: string, code: string, state: string) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.post<AuthTokenResponse>(
        `/api/auth/sso/${provider}`,
        { provider, code, state },
        { skipAuth: true },
      );
      const token = data.access_token || '';
      const refreshToken = data.refresh_token || '';

      localStorage.setItem('token', token);
      localStorage.setItem('refresh_token', refreshToken);

      set({ token, refreshToken, loading: false });
      await get().loadUser();
    } catch (error) {
      const errMessage = error instanceof Error ? error.message : String(error);
      set({
        error: error instanceof Error ? errMessage : 'SSO login failed',
        loading: false,
      });
    }
  },

  refreshTokenAction: async () => {
    const currentRefreshToken = get().refreshToken || localStorage.getItem('refresh_token');
    if (!currentRefreshToken) return;

    try {
      const data = await apiClient.post<AuthTokenResponse>(
        '/api/auth/refresh',
        { refresh_token: currentRefreshToken },
        { skipAuth: true, skipAuthError: true },
      );
      const token = data.access_token || '';
      const refreshToken = data.refresh_token || '';

      localStorage.setItem('token', token);
      localStorage.setItem('refresh_token', refreshToken);

      set({ token, refreshToken });
    } catch {
      get().logout();
    }
  },

  logoutAction: async () => {
    const currentRefreshToken = get().refreshToken || localStorage.getItem('refresh_token');
    if (currentRefreshToken) {
      try {
        await apiClient.post('/api/auth/logout', { refresh_token: currentRefreshToken });
      } catch { /* 忽略：失败时保持当前状态 */ 
        // Ignore logout API errors
      }
    }
    get().logout();
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    localStorage.removeItem('currentRoleId');
    set({
      token: null,
      refreshToken: null,
      user: null,
      error: null,
    });
  },

  loadUser: async () => {
    const token = get().token || localStorage.getItem('token');
    if (!token) return;

    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<AuthUserFields>('/api/auth/me');
      const globalRole = data.global_role || data.role || 'observer';
      const user = {
        id: data.id || data.user_id || '',
        username: data.username || '',
        global_role: globalRole,
        role_id: data.role_id || globalRole,
        ws_id: data.ws_id,
        ws_role: data.ws_role,
      };

      localStorage.setItem('user', JSON.stringify(user));
      set({ user, loading: false });
    } catch (error) {
      const errMessage = error instanceof Error ? error.message : String(error);
      set({
        error: error instanceof Error ? errMessage : 'Failed to load user',
        loading: false,
      });
    }
  },

  setCurrentRole: (roleId: string) => {
    localStorage.setItem('currentRoleId', roleId);
    const user = get().user;
    if (user) {
      const updated = { ...user, role_id: roleId };
      localStorage.setItem('user', JSON.stringify(updated));
      set({ user: updated });
    }
  },

  getCurrentRoleId: () => {
    const stored = localStorage.getItem('currentRoleId');
    if (stored) return stored;
    const user = get().user;
    if (user?.role_id) return user.role_id;
    return 'observer';
  },
}));

const initToken = localStorage.getItem('token');
if (initToken) {
  useAuthStore.getState().loadUser();
}
