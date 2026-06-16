import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuditStore } from './auditStore';

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

import { apiClient } from '@/modules/shared/services/apiClient';

const mockPolicy = {
  policy_id: 'pol-1',
  name: 'Test Policy',
  description: 'A test policy',
  category: 'access',
  compile_status: 'compiled',
  version: 1,
  markdown_content: '# Test',
  rego_text: 'package test',
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
};

const mockPolicyVersion = {
  id: 'pv-1',
  policy_id: 'pol-1',
  version: 1,
  status: 'active',
  created_at: '2026-01-01T00:00:00',
};

const mockAuditLog = {
  id: 'log-1',
  timestamp: '2026-01-01T00:00:00',
  level: 'info',
  type: 'access',
  action: 'read',
  user: 'admin',
  resource: 'ontology',
  result_status: 'success',
};

describe('auditStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuditStore.setState({
      policies: [],
      auditLogs: [],
      policyVersions: [],
      compileStatus: {},
      loading: false,
      error: null,
    });
  });

  describe('initial state', () => {
    it('has correct default values', () => {
      const state = useAuditStore.getState();
      expect(state.policies).toEqual([]);
      expect(state.auditLogs).toEqual([]);
      expect(state.policyVersions).toEqual([]);
      expect(state.compileStatus).toEqual({});
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('loadPolicies', () => {
    it('loads policies successfully', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({ policies: [mockPolicy] });
      await useAuditStore.getState().loadPolicies();
      expect(useAuditStore.getState().policies).toHaveLength(1);
      expect(useAuditStore.getState().policies[0].policy_id).toBe('pol-1');
      expect(useAuditStore.getState().loading).toBe(false);
    });

    it('handles loadPolicies error', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));
      await useAuditStore.getState().loadPolicies();
      expect(useAuditStore.getState().error).toBe('Network error');
      expect(useAuditStore.getState().loading).toBe(false);
    });

    it('handles missing policies array gracefully', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({});
      await useAuditStore.getState().loadPolicies();
      expect(useAuditStore.getState().policies).toEqual([]);
    });
  });

  describe('loadPolicyVersions', () => {
    it('loads policy versions successfully', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({ versions: [mockPolicyVersion] });
      await useAuditStore.getState().loadPolicyVersions('pol-1');
      expect(useAuditStore.getState().policyVersions).toHaveLength(1);
      expect(useAuditStore.getState().policyVersions[0].id).toBe('pv-1');
    });

    it('handles loadPolicyVersions error', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Version load failed'));
      await useAuditStore.getState().loadPolicyVersions('pol-1');
      expect(useAuditStore.getState().error).toBe('Version load failed');
    });
  });

  describe('savePolicy', () => {
    it('saves a policy and reloads list', async () => {
      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue(mockPolicy);
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({ policies: [mockPolicy] });
      const result = await useAuditStore.getState().savePolicy({
        name: 'Test Policy',
        description: 'A test policy',
        markdown_content: '# Test',
        category: 'access',
      });
      expect(result).toEqual(mockPolicy);
      expect(apiClient.post).toHaveBeenCalled();
      expect(useAuditStore.getState().loading).toBe(false);
    });

    it('returns null on save error', async () => {
      (apiClient.post as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Save failed'));
      const result = await useAuditStore.getState().savePolicy({
        name: 'Bad',
        description: '',
        markdown_content: '',
        category: '',
      });
      expect(result).toBeNull();
      expect(useAuditStore.getState().error).toBe('Save failed');
    });
  });

  describe('compilePolicy', () => {
    it('compiles policy and updates compileStatus', async () => {
      (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue({
        compile_status: 'compiled',
        errors: [],
        rego_text: 'package test',
      });
      await useAuditStore.getState().compilePolicy('pol-1');
      expect(useAuditStore.getState().compileStatus['pol-1']).toEqual({
        status: 'compiled',
        errors: [],
      });
    });

    it('handles compile error and sets error status', async () => {
      (apiClient.post as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Compile failed'));
      await useAuditStore.getState().compilePolicy('pol-1');
      expect(useAuditStore.getState().compileStatus['pol-1']).toEqual({
        status: 'error',
        errors: ['Compile failed'],
      });
    });
  });

  describe('hotUpdate', () => {
    it('updates policy and reloads', async () => {
      (apiClient.put as ReturnType<typeof vi.fn>).mockResolvedValue({});
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
        policies: [mockPolicy],
        compile_status: 'compiled',
        validation: { valid: true, errors: [] },
      });
      await useAuditStore.getState().hotUpdate('pol-1', '# Updated');
      expect(apiClient.put).toHaveBeenCalled();
      expect(useAuditStore.getState().loading).toBe(false);
    });

    it('handles hotUpdate error', async () => {
      (apiClient.put as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Hot update failed'));
      await useAuditStore.getState().hotUpdate('pol-1', '# Bad');
      expect(useAuditStore.getState().error).toBe('Hot update failed');
    });
  });

  describe('loadAuditLogs', () => {
    it('loads audit logs with params', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [mockAuditLog], total: 1 });
      await useAuditStore.getState().loadAuditLogs({ actor: 'admin', page: 1, page_size: 10 });
      expect(useAuditStore.getState().auditLogs).toHaveLength(1);
      expect(useAuditStore.getState().loading).toBe(false);
    });

    it('handles loadAuditLogs error', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Logs load failed'));
      await useAuditStore.getState().loadAuditLogs();
      expect(useAuditStore.getState().error).toBe('Logs load failed');
    });
  });

  describe('getCompileStatus', () => {
    it('gets compile status for a policy', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
        compile_status: 'compiled',
        validation: { valid: true, errors: [] },
      });
      await useAuditStore.getState().getCompileStatus('pol-1');
      expect(useAuditStore.getState().compileStatus['pol-1']).toEqual({
        status: 'compiled',
        errors: [],
      });
    });

    it('handles getCompileStatus error', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Status check failed'));
      await useAuditStore.getState().getCompileStatus('pol-1');
      expect(useAuditStore.getState().compileStatus['pol-1']).toEqual({
        status: 'error',
        errors: ['Status check failed'],
      });
    });
  });
});
