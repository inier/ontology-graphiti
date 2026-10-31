import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import type {
  ApprovalTask,
  ApprovalAuditPayload,
  ApprovalModifyPayload,
  ApprovalRejectPayload,
  ApprovalFinalApprovePayload,
  ApprovalTaskResponse,
} from '../types';

const URL_PREFIX = `${API_BASE}/api/semantic-admin`;

/**
 * 拼查询串。数组用重复键（status=A&status=B），不加 `[]` 后缀 ——
 * 后端是 FastAPI `Optional[List[str]] = Query(...)`，只认裸键名。
 */
function buildQuery(params: Record<string, unknown>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    if (Array.isArray(v)) {
      v.forEach((val) => q.append(k, String(val)));
    } else {
      q.set(k, String(v));
    }
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

export async function listApprovalTasks(params?: {
  assigned_role?: string;
  status?: string[];
  assignee_user_id?: string;
  domain_id?: string;
  order_by?: string;
  page?: number;
  page_size?: number;
}): Promise<{ items: ApprovalTask[]; total: number; page: number; page_size: number }> {
  try {
    const query = params || {};
    // 一次性拼完，不要先 buildQuery 再手工拼 status：buildQuery 的返回值已经带了
    // 前导 `?`，再套一层 `?${qs}&${statusQS}` 会得到 `??assigned_role=...`，
    // 首个参数名变成 `?assigned_role` 被后端丢弃 —— L1/L2 页签于是显示同一份
    // 未过滤列表，且不报错。
    const fullQS = buildQuery({
      ...query,
      page: query.page ?? 1,
      page_size: query.page_size ?? 20,
    });
    return await fetchJson<{ items: ApprovalTask[]; total: number; page: number; page_size: number }>(
      `${URL_PREFIX}/approval/tasks${fullQS}`,
    );
  } catch (e) {
    const errMessage = e instanceof Error ? e.message : String(e);
    const msg = e instanceof Error ? errMessage : String(e);
    throw new Error(`Failed to list approval tasks: ${msg}`);
  }
}

export async function actionAudit(
  task_id: string,
  payload: ApprovalAuditPayload,
): Promise<ApprovalTaskResponse> {
  try {
    return await fetchJson<ApprovalTaskResponse>(
      `${URL_PREFIX}/approval/tasks/${encodeURIComponent(task_id)}/audit`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );
  } catch (e) {
    const errMessage = e instanceof Error ? e.message : String(e);
    const msg = e instanceof Error ? errMessage : String(e);
    throw new Error(`Failed to audit approval task: ${msg}`);
  }
}

export async function actionModify(
  task_id: string,
  payload: ApprovalModifyPayload,
): Promise<ApprovalTaskResponse> {
  try {
    return await fetchJson<ApprovalTaskResponse>(
      `${URL_PREFIX}/approval/tasks/${encodeURIComponent(task_id)}/modify`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );
  } catch (e) {
    const errMessage = e instanceof Error ? e.message : String(e);
    const msg = e instanceof Error ? errMessage : String(e);
    throw new Error(`Failed to modify approval task: ${msg}`);
  }
}

export async function actionReject(
  task_id: string,
  payload: ApprovalRejectPayload,
): Promise<ApprovalTaskResponse> {
  try {
    return await fetchJson<ApprovalTaskResponse>(
      `${URL_PREFIX}/approval/tasks/${encodeURIComponent(task_id)}/reject`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );
  } catch (e) {
    const errMessage = e instanceof Error ? e.message : String(e);
    const msg = e instanceof Error ? errMessage : String(e);
    throw new Error(`Failed to reject approval task: ${msg}`);
  }
}

export async function actionFinalApprove(
  task_id: string,
  payload: ApprovalFinalApprovePayload,
): Promise<ApprovalTaskResponse> {
  try {
    return await fetchJson<ApprovalTaskResponse>(
      `${URL_PREFIX}/approval/tasks/${encodeURIComponent(task_id)}/final-approve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );
  } catch (e) {
    const errMessage = e instanceof Error ? e.message : String(e);
    const msg = e instanceof Error ? errMessage : String(e);
    throw new Error(`Failed to final approve approval task: ${msg}`);
  }
}
