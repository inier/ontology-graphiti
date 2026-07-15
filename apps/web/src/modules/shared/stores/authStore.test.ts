import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAuthStore } from './authStore';

vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from '../services/apiClient';

describe('authStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    useAuthStore.setState({
      token: null,
      refreshToken: null,
      user: null,
      loading: false,
      error: null,
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('initial state', () => {
    it('has correct default values when no stored data', () => {
      const state = useAuthStore.getState();
      expect(state.token).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.user).toBeNull();
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('login', () => {
    it('logs in successfully and stores token and user', async () => {
      const loginResponse = {
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        user: {
          id: 'user-1',
          username: 'admin',
          global_role: 'admin',
          role_id: '1',
        },
      };
      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue(loginResponse);

      await useAuthStore.getState().login('admin', 'admin123');

      expect(apiClient.post).toHaveBeenCalledWith('/api/auth/login', { username: 'admin', password: 'admin123' }, { skipAuth: true });
      expect(useAuthStore.getState().token).toBe('test-access-token');
      expect(useAuthStore.getState().refreshToken).toBe('test-refresh-token');
      expect(useAuthStore.getState().user?.username).toBe('admin');
      expect(useAuthStore.getState().user?.global_role).toBe('admin');
      expect(useAuthStore.getState().user?.role_id).toBe('1');
      expect(useAuthStore.getState().loading).toBe(false);
      expect(useAuthStore.getState().error).toBeNull();

      expect(localStorage.getItem('token')).toBe('test-access-token');
      expect(localStorage.getItem('refresh_token')).toBe('test-refresh-token');
      expect(localStorage.getItem('currentRoleId')).toBe('1');
    });

    it('maps global_role to role_id when role_id is not provided', async () => {
      const loginResponse = {
        access_token: 'token',
        refresh_token: 'refresh',
        user: { id: 'u1', username: 'analyst', global_role: 'analyst' },
      };
      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue(loginResponse);

      await useAuthStore.getState().login('analyst', 'pass');

      expect(useAuthStore.getState().user?.role_id).toBe('3');
      expect(localStorage.getItem('currentRoleId')).toBe('3');
    });

    it('defaults to observer role_id for unknown roles', async () => {
      const loginResponse = {
        access_token: 'token',
        refresh_token: 'refresh',
        user: { id: 'u1', username: 'unknown', global_role: 'custom_role' },
      };
      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue(loginResponse);

      await useAuthStore.getState().login('unknown', 'pass');

      expect(useAuthStore.getState().user?.role_id).toBe('5');
    });

    it('handles login error', async () => {
      (apiClient.post as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Invalid credentials'));

      await useAuthStore.getState().login('admin', 'wrong');

      expect(useAuthStore.getState().error).toBe('Invalid credentials');
      expect(useAuthStore.getState().loading).toBe(false);
      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
    });

    it('sets loading to true during login', async () => {
      let resolveLogin: (value: unknown) => void;
      const loginPromise = new Promise((resolve) => { resolveLogin = resolve; });
      (apiClient.post as ReturnType<typeof vi.fn>).mockReturnValue(loginPromise);

      const actionPromise = useAuthStore.getState().login('admin', 'pass');
      expect(useAuthStore.getState().loading).toBe(true);

      resolveLogin!({ access_token: 't', refresh_token: 'r', user: {} });
      await actionPromise;
      expect(useAuthStore.getState().loading).toBe(false);
    });
  });

  describe('loginSSO', () => {
    it('logs in via SSO and loads user', async () => {
      const ssoResponse = {
        access_token: 'sso-token',
        refresh_token: 'sso-refresh',
      };
      const meResponse = {
        id: 'u1',
        username: 'sso-user',
        global_role: 'commander',
        role_id: '2',
      };
      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce(ssoResponse);
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue(meResponse);

      await useAuthStore.getState().loginSSO('github', 'code-123', 'state-456');

      expect(apiClient.post).toHaveBeenCalledWith('/api/auth/sso/github', { provider: 'github', code: 'code-123', state: 'state-456' }, { skipAuth: true });
      expect(useAuthStore.getState().token).toBe('sso-token');
      expect(useAuthStore.getState().user?.username).toBe('sso-user');
      expect(useAuthStore.getState().loading).toBe(false);
    });

    it('handles SSO login error', async () => {
      (apiClient.post as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('SSO failed'));

      await useAuthStore.getState().loginSSO('github', 'bad-code', 'bad-state');

      expect(useAuthStore.getState().error).toBe('SSO failed');
      expect(useAuthStore.getState().loading).toBe(false);
    });
  });

  describe('refreshTokenAction', () => {
    it('refreshes token successfully', async () => {
      useAuthStore.setState({ refreshToken: 'old-refresh' });
      localStorage.setItem('refresh_token', 'old-refresh');

      const refreshResponse = {
        access_token: 'new-access',
        refresh_token: 'new-refresh',
      };
      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue(refreshResponse);

      await useAuthStore.getState().refreshTokenAction();

      expect(apiClient.post).toHaveBeenCalledWith('/api/auth/refresh', { refresh_token: 'old-refresh' }, { skipAuth: true, skipAuthError: true });
      expect(useAuthStore.getState().token).toBe('new-access');
      expect(useAuthStore.getState().refreshToken).toBe('new-refresh');
      expect(localStorage.getItem('token')).toBe('new-access');
    });

    it('falls back to localStorage for refresh token', async () => {
      useAuthStore.setState({ refreshToken: null });
      localStorage.setItem('refresh_token', 'stored-refresh');

      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue({
        access_token: 'new-token',
        refresh_token: 'new-refresh',
      });

      await useAuthStore.getState().refreshTokenAction();
      expect(apiClient.post).toHaveBeenCalledWith('/api/auth/refresh', { refresh_token: 'stored-refresh' }, { skipAuth: true, skipAuthError: true });
    });

    it('does nothing when no refresh token available', async () => {
      useAuthStore.setState({ refreshToken: null });

      await useAuthStore.getState().refreshTokenAction();

      expect(apiClient.post).not.toHaveBeenCalled();
    });

    it('calls logout on refresh failure', async () => {
      useAuthStore.setState({ refreshToken: 'bad-refresh', token: 'old-token', user: { id: '1', username: 'test', global_role: 'admin', role_id: '1' } });
      (apiClient.post as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Refresh failed'));

      await useAuthStore.getState().refreshTokenAction();

      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
    });
  });

  describe('logoutAction', () => {
    it('calls logout API and clears state', async () => {
      useAuthStore.setState({ refreshToken: 'refresh-token' });
      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue({});

      await useAuthStore.getState().logoutAction();

      expect(apiClient.post).toHaveBeenCalledWith('/api/auth/logout', { refresh_token: 'refresh-token' });
      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
    });

    it('still clears state even if API call fails', async () => {
      useAuthStore.setState({ refreshToken: 'refresh-token', token: 'token', user: { id: '1', username: 'test', global_role: 'admin', role_id: '1' } });
      (apiClient.post as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Logout API failed'));

      await useAuthStore.getState().logoutAction();

      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
    });
  });

  describe('logout', () => {
    it('clears all auth state and localStorage', () => {
      localStorage.setItem('token', 'some-token');
      localStorage.setItem('refresh_token', 'some-refresh');
      localStorage.setItem('user', JSON.stringify({ id: '1', username: 'test' }));
      localStorage.setItem('currentRoleId', '1');

      useAuthStore.setState({
        token: 'some-token',
        refreshToken: 'some-refresh',
        user: { id: '1', username: 'test', global_role: 'admin', role_id: '1' },
      });

      useAuthStore.getState().logout();

      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().refreshToken).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
      expect(useAuthStore.getState().error).toBeNull();
      expect(localStorage.getItem('token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
      expect(localStorage.getItem('user')).toBeNull();
      expect(localStorage.getItem('currentRoleId')).toBeNull();
    });
  });

  describe('loadUser', () => {
    it('loads user profile from API', async () => {
      useAuthStore.setState({ token: 'valid-token' });
      const meResponse = {
        id: 'u1',
        username: 'admin',
        global_role: 'admin',
        role_id: '1',
        ws_id: 'ws-1',
        ws_role: 'owner',
      };
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue(meResponse);

      await useAuthStore.getState().loadUser();

      expect(useAuthStore.getState().user?.username).toBe('admin');
      expect(useAuthStore.getState().user?.ws_id).toBe('ws-1');
      expect(useAuthStore.getState().user?.ws_role).toBe('owner');
      expect(useAuthStore.getState().loading).toBe(false);
    });

    it('does nothing when no token available', async () => {
      useAuthStore.setState({ token: null });
      localStorage.removeItem('token');

      await useAuthStore.getState().loadUser();

      expect(apiClient.get).not.toHaveBeenCalled();
    });

    it('handles loadUser error', async () => {
      useAuthStore.setState({ token: 'bad-token' });
      (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Unauthorized'));

      await useAuthStore.getState().loadUser();

      expect(useAuthStore.getState().error).toBe('Unauthorized');
      expect(useAuthStore.getState().loading).toBe(false);
    });

    it('maps role from API response when global_role is missing', async () => {
      useAuthStore.setState({ token: 'valid-token' });
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
        id: 'u1',
        username: 'user',
        role: 'analyst',
      });

      await useAuthStore.getState().loadUser();

      expect(useAuthStore.getState().user?.global_role).toBe('analyst');
    });
  });

  describe('setCurrentRole', () => {
    it('updates current role in state and localStorage', () => {
      useAuthStore.setState({
        user: { id: '1', username: 'admin', global_role: 'admin', role_id: '1' },
      });

      useAuthStore.getState().setCurrentRole('3');

      expect(useAuthStore.getState().user?.role_id).toBe('3');
      expect(localStorage.getItem('currentRoleId')).toBe('3');
    });

    it('does nothing when user is null', () => {
      useAuthStore.setState({ user: null });
      useAuthStore.getState().setCurrentRole('2');
      expect(useAuthStore.getState().user).toBeNull();
    });
  });

  describe('getCurrentRoleId', () => {
    it('returns stored currentRoleId from localStorage', () => {
      localStorage.setItem('currentRoleId', '2');
      expect(useAuthStore.getState().getCurrentRoleId()).toBe('2');
    });

    it('falls back to user role_id when localStorage is empty', () => {
      useAuthStore.setState({
        user: { id: '1', username: 'admin', global_role: 'admin', role_id: '1' },
      });
      expect(useAuthStore.getState().getCurrentRoleId()).toBe('1');
    });

    it('returns default observer role_id when nothing is available', () => {
      useAuthStore.setState({ user: null });
      expect(useAuthStore.getState().getCurrentRoleId()).toBe('5');
    });
  });
});
