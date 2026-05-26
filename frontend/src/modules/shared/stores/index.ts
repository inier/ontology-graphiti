import { create } from 'zustand';
import { API_BASE } from '../../../config';
import { api } from '../services/api';
import type { Workspace as ApiWorkspace, AuditEvent as ApiAuditEvent } from '../services/api';

export interface User {
  id: string;
  username: string;
  name: string;
  roles: string[];
}

export type Workspace = ApiWorkspace;

export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
  timestamp: string;
  read?: boolean;
}

export type AuditEvent = ApiAuditEvent;

interface AuditFilters {
  start_time?: string;
  end_time?: string;
  event_type?: string;
  severity?: string;
  actor_id?: string;
}

interface AppState {
  user: User | null;
  token: string | null;
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  notifications: Notification[];
  loading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loadWorkspaces: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => Promise<void>;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearError: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  user: null,
  token: null,
  currentWorkspace: null,
  workspaces: [],
  notifications: [],
  loading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ loading: true, error: null });
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        throw new Error(`Login failed: ${response.status}`);
      }

      const data = await response.json();
      const user: User = {
        id: data.user?.id || data.user_id || 'user-1',
        username: data.user?.username || username,
        name: data.user?.name || username,
        roles: data.user?.roles || ['user'],
      };
      const token = data.token || data.access_token || '';

      set({
        user,
        token,
        loading: false,
      });

      get().addNotification({
        type: 'success',
        message: `Welcome, ${username}!`,
      });

      await get().loadWorkspaces();
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Login failed',
        loading: false,
      });
    }
  },

  logout: () => {
    set({
      user: null,
      token: null,
      currentWorkspace: null,
      workspaces: [],
      notifications: [],
    });
    get().addNotification({
      type: 'info',
      message: 'You have been logged out',
    });
  },

  loadWorkspaces: async () => {
    set({ loading: true, error: null });
    try {
      const workspaces = await api.listWorkspaces();

      set({
        workspaces,
        currentWorkspace: workspaces[0] || null,
        loading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load workspaces',
        loading: false,
      });
    }
  },

  switchWorkspace: async (workspaceId: string) => {
    const { workspaces } = get();
    const workspace = workspaces.find((w) => w.workspace_id === workspaceId);

    if (workspace) {
      set({ currentWorkspace: workspace });
      get().addNotification({
        type: 'info',
        message: `Switched to workspace: ${workspace.name}`,
      });
    }
  },

  addNotification: (notification) => {
    const newNotification: Notification = {
      ...notification,
      id: `notif-${Date.now()}`,
      timestamp: new Date().toISOString(),
    };
    set((state) => ({
      notifications: [newNotification, ...state.notifications].slice(0, 50),
    }));
  },

  removeNotification: (id: string) => {
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    }));
  },

  clearError: () => {
    set({ error: null });
  },
}));

interface AuditState {
  events: AuditEvent[];
  total: number;
  loading: boolean;
  filters: AuditFilters;

  loadEvents: (filters?: AuditFilters) => Promise<void>;
  setFilter: (key: string, value: string | undefined) => void;
  clearFilters: () => void;
}

export const useAuditStore = create<AuditState>((set, get) => ({
  events: [],
  total: 0,
  loading: false,
  filters: {},

  loadEvents: async (filters) => {
    set({ loading: true });
    try {
      const params = new URLSearchParams();
      const currentFilters = filters || get().filters;

      Object.entries(currentFilters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });

      const response = await fetch(`${API_BASE}/api/audit/events?${params}`);
      const data = await response.json();

      set({
        events: data.events || [],
        total: data.total || 0,
        loading: false,
      });
    } catch (error) {
      console.error('Failed to load audit events:', error);
      set({ loading: false });
    }
  },

  setFilter: (key: string, value: string | undefined) => {
    set((state) => ({
      filters: { ...state.filters, [key]: value },
    }));
  },

  clearFilters: () => {
    set({ filters: {} });
  },
}));