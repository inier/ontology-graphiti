/**
 * 统一错误契约的前端投影（SPEC §5「错误契约（全局统一）」）
 *
 * 后端返回：{ error_code, message, detail, trace_id }
 * 用户明确要求"可诊断"：界面必须展示 error_code 与 message，禁止"加载失败"式模糊文案。
 */

export interface ApiErrorPayload {
  error_code: string;
  message: string;
  detail: Record<string, unknown> | null;
  trace_id: string;
}

/** 前端不可恢复/未知错误的兜底码（仍具体，不含"操作异常"式模糊措辞） */
export const FALLBACK_ERROR_CODE = 'WIKI_CLIENT_NETWORK_ERROR';

export class WikiApiError extends Error {
  readonly errorCode: string;
  readonly detail: Record<string, unknown> | null;
  readonly traceId: string;
  readonly status: number;

  constructor(payload: ApiErrorPayload, status = 0) {
    super(payload.message);
    this.name = 'WikiApiError';
    this.errorCode = payload.error_code;
    this.detail = payload.detail;
    this.traceId = payload.trace_id;
    this.status = status;
  }
}

/** 界面展示用的错误视图模型（不含堆栈，仅可诊断信息） */
export interface WikiErrorInfo {
  errorCode: string;
  message: string;
  traceId: string;
  status: number;
  /** 可选的冲突条目 id（AC-04）、冲突版本（AC-08）等业务定位信息 */
  conflictingId?: string;
}

export function toErrorInfo(err: unknown): WikiErrorInfo {
  if (err instanceof WikiApiError) {
    const conflicting = err.detail?.conflicting_entry_id ?? err.detail?.current_version;
    return {
      errorCode: err.errorCode,
      message: err.message,
      traceId: err.traceId,
      status: err.status,
      conflictingId: typeof conflicting === 'string' ? conflicting : undefined,
    };
  }
  const message = err instanceof Error ? err.message : String(err);
  return {
    errorCode: FALLBACK_ERROR_CODE,
    message,
    traceId: '',
    status: 0,
  };
}
