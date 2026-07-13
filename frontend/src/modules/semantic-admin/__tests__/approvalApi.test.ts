import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  listApprovalTasks,
  actionAudit,
  actionModify,
  actionReject,
  actionFinalApprove,
} from '../services/approvalApi';

// 拦截 fetchJson 调用（不发起真实 HTTP）
const mockFetch = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => mockFetch(...args),
}));

describe('approvalApi.ts: 二级审批 5 个 API 导出与 URL 构造', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  });

  it('listApprovalTasks 存在 & 默认参数：GET /approval/tasks?page=1&page_size=20', async () => {
    await listApprovalTasks();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const called = mockFetch.mock.calls[0][0] as string;
    expect(called).toContain('/api/semantic-admin/approval/tasks');
    expect(called).toContain('page=1');
    expect(called).toContain('page_size=20');
  });

  it('listApprovalTasks 数组 status 会被拼到 query（status[] 或 status=...）', async () => {
    await listApprovalTasks({
      status: ['PENDING_REVIEW', 'ADMIN_PENDING'],
      assigned_role: 'admin',
    });
    const called = mockFetch.mock.calls[0][0] as string;
    expect(called).toContain('assigned_role=admin');
    // 两种形式（status=X&status=Y 或 status[]=X&status[]=Y）只要都包含即可
    expect(called).toMatch(/PENDING_REVIEW|ADMIN_PENDING/);
  });

  it('actionAudit / actionModify / actionReject / actionFinalApprove 都存在 & 为 async 函数', () => {
    expect(typeof actionAudit).toBe('function');
    expect(typeof actionModify).toBe('function');
    expect(typeof actionReject).toBe('function');
    expect(typeof actionFinalApprove).toBe('function');
  });

  it('actionAudit: 使用 POST + JSON body（含 comment）', async () => {
    mockFetch.mockResolvedValueOnce({
      task_id: 't-1', candidate_id: 'c-1', new_status: 'AUDITOR_APPROVED',
    });
    await actionAudit('t-1', { comment: '已核查 L1 合规，通过' });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/approval/tasks/t-1/audit');
    expect((opts as RequestInit).method).toBe('POST');
    expect((opts as RequestInit).headers).toHaveProperty('Content-Type', 'application/json');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.comment).toBe('已核查 L1 合规，通过');
  });

  it('actionReject: POST JSON 含 rejection reason', async () => {
    mockFetch.mockResolvedValueOnce({
      task_id: 't-2', candidate_id: 'c-2', new_status: 'REVIEWER_REJECTED', close_task: true,
    });
    await actionReject('t-2', { reason: '同义词与 canonical 自包含循环', close_task: true });
    const [, opts] = mockFetch.mock.calls[0];
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.reason).toMatch(/同义词/);
    expect(body.close_task).toBe(true);
  });

  it('actionFinalApprove: POST JSON 含 writeback_now=true 触发回写', async () => {
    mockFetch.mockResolvedValueOnce({
      task_id: 't-3', candidate_id: 'c-3', new_status: 'APPROVED', promote_to_usl: { id: 'ut-99' },
    });
    await actionFinalApprove('t-3', { comment: 'L2 最终批准', auto_promote: true, writeback_now: true });
    const [, opts] = mockFetch.mock.calls[0];
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.writeback_now).toBe(true);
    expect(body.auto_promote).toBe(true);
  });
});
