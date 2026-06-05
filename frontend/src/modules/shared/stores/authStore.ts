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

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token'),
  refreshToken: localStorage.getItem('refresh_token'),
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  loading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.post('/api/auth/login', { username, password }, { skipAuth: true });
      const token = data.access_token || data.token || '';
      const refreshToken = data.refresh_token || '';
      const userData = data.user || {};
      const globalRole = userData.global_role || 'observer';
      const ROLE_TO_ID: Record<string, string> = {
        admin: '1', commander: '2', analyst: '3', operator: '4', observer: '5',
      };
      const user = {
        id: userData.id || '',
        username: userData.username || '',
        global_role: globalRole,
        role_id: userData.role_id || ROLE_TO_ID[globalRole] || '5',
      };

      localStorage.setItem('token', token);
      localStorage.setItem('refresh_token', refreshToken);
      localStorage.setItem('user', JSON.stringify(user));
      localStorage.setItem('currentRoleId', user.role_id);

      set({ token, refreshToken, user, loading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Login failed',
        loading: false,
      });
    }
  },

  loginSSO: async (provider: string, code: string, state: string) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.post(`/api/auth/sso/${provider}`, { provider, code, state }, { skipAuth: true });
      const token = data.access_token || '';
      const refreshToken = data.refresh_token || '';

      localStorage.setItem('token', token);
      localStorage.setItem('refresh_token', refreshToken);

      set({ token, refreshToken, loading: false });
      await get().loadUser();
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'SSO login failed',
        loading: false,
      });
    }
  },

  refreshTokenAction: async () => {
    const currentRefreshToken = get().refreshToken || localStorage.getItem('refresh_token');
    if (!currentRefreshToken) return;

    try {
      const data = await apiClient.post('/api/auth/refresh', { refresh_token: currentRefreshToken }, { skipAuth: true, skipAuthError: true });
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
      } catch {
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
      const data = await apiClient.get('/api/auth/me');
      const globalRole = data.global_role || data.role || 'observer';
      const ROLE_TO_ID: Record<string, string> = {
        admin: '1', commander: '2', analyst: '3', operator: '4', observer: '5',
      };
      const user = {
        id: data.id || data.user_id || '',
        username: data.username || '',
        global_role: globalRole,
        role_id: data.role_id || ROLE_TO_ID[globalRole] || '5',
        ws_id: data.ws_id,
        ws_role: data.ws_role,
      };

      localStorage.setItem('user', JSON.stringify(user));
      set({ user, loading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load user',
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
    return '5';
  },
}));

const initToken = localStorage.getItem('token');
if (initToken) {
  useAuthStore.getState().loadUser();
}
