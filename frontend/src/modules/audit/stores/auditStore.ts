import { create } from 'zustand';
import { apiClient } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

interface Policy {
  policy_id: string;
  name: string;
  description: string;
  category: string;
  compile_status: string;
  version: number;
  markdown_content?: string;
  rego_text?: string;
  created_at?: string;
  updated_at?: string;
  compile_errors?: string[];
}

interface PolicyVersion {
  id: string;
  policy_id: string;
  version: number;
  status: string;
  created_at: string;
  compiled_at?: string;
}

interface AuditLog {
  id: string;
  timestamp: string;
  level: string;
  type: string;
  action: string;
  user: string;
  resource: string;
  result_status: string;
  details?: Record<string, unknown>;
}

interface AuditState {
  policies: Policy[];
  auditLogs: AuditLog[];
  policyVersions: PolicyVersion[];
  compileStatus: Record<string, { status: string; errors?: string[] }>;
  loading: boolean;
  error: string | null;

  loadPolicies: () => Promise<void>;
  loadPolicyVersions: (policyId: string) => Promise<void>;
  savePolicy: (data: { name: string; description: string; markdown_content: string; category: string }) => Promise<Policy | null>;
  compilePolicy: (policyId: string) => Promise<void>;
  hotUpdate: (policyId: string, markdownContent: string) => Promise<void>;
  loadAuditLogs: (params?: { actor?: string; action?: string; result?: string; page?: number; page_size?: number }) => Promise<void>;
  getCompileStatus: (policyId: string) => Promise<void>;
}

export const useAuditStore = create<AuditState>((set, get) => ({
  policies: [],
  auditLogs: [],
  policyVersions: [],
  compileStatus: {},
  loading: false,
  error: null,

  loadPolicies: async () => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<{ policies: Policy[] }>(`${API_BASE}/api/policies?limit=100`);
      set({ policies: data.policies || [], loading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '加载策略失败', loading: false });
    }
  },

  loadPolicyVersions: async (policyId: string) => {
    try {
      const data = await apiClient.get<{ versions: PolicyVersion[] }>(`${API_BASE}/api/policy/markdown/${policyId}/versions`);
      set({ policyVersions: data.versions || [] });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '加载版本历史失败' });
    }
  },

  savePolicy: async (data) => {
    set({ loading: true, error: null });
    try {
      const result = await apiClient.post<Policy>(`${API_BASE}/api/policy/markdown`, data);
      await get().loadPolicies();
      set({ loading: false });
      return result;
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '保存策略失败', loading: false });
      return null;
    }
  },

  compilePolicy: async (policyId: string) => {
    try {
      const result = await apiClient.post<{ compile_status: string; errors?: string[]; rego_text?: string }>(`${API_BASE}/api/policy/markdown/${policyId}/compile`);
      set((state) => ({
        compileStatus: {
          ...state.compileStatus,
          [policyId]: { status: result.compile_status, errors: result.errors },
        },
      }));
    } catch (error) {
      set((state) => ({
        compileStatus: {
          ...state.compileStatus,
          [policyId]: { status: 'error', errors: [error instanceof Error ? error.message : '编译失败'] },
        },
      }));
    }
  },

  hotUpdate: async (policyId: string, markdownContent: string) => {
    set({ loading: true, error: null });
    try {
      await apiClient.put(`${API_BASE}/api/policy/markdown/${policyId}`, {
        markdown_content: markdownContent,
      });
      await get().loadPolicies();
      await get().getCompileStatus(policyId);
      set({ loading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '热更新失败', loading: false });
    }
  },

  loadAuditLogs: async (params) => {
    set({ loading: true, error: null });
    try {
      const searchParams = new URLSearchParams();
      if (params?.actor) searchParams.set('actor', params.actor);
      if (params?.action) searchParams.set('action', params.action);
      if (params?.result) searchParams.set('result', params.result);
      if (params?.page) searchParams.set('page', String(params.page));
      if (params?.page_size) searchParams.set('page_size', String(params.page_size));
      const data = await apiClient.get<{ items: AuditLog[]; total: number }>(`${API_BASE}/api/audit/logs?${searchParams.toString()}`);
      set({ auditLogs: data.items || [], loading: false });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '加载审计日志失败', loading: false });
    }
  },

  getCompileStatus: async (policyId: string) => {
    try {
      const result = await apiClient.get<{ compile_status: string; validation: { valid: boolean; errors: string[] } }>(`${API_BASE}/api/policy/markdown/${policyId}/status`);
      set((state) => ({
        compileStatus: {
          ...state.compileStatus,
          [policyId]: { status: result.compile_status, errors: result.validation?.errors },
        },
      }));
    } catch (error) {
      set((state) => ({
        compileStatus: {
          ...state.compileStatus,
          [policyId]: { status: 'error', errors: [error instanceof Error ? error.message : '获取状态失败'] },
        },
      }));
    }
  },
}));
