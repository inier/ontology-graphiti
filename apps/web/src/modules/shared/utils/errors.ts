/**
 * 统一错误信息提取。
 *
 * 后端错误契约：`{ error_code, message, detail, trace_id }`。axios 抛错时
 * 该对象挂在 `error.response.data` 上；网络层错误则没有 response。
 * 这里用 `unknown` + 结构化收窄，避免在 catch 上写 `any`。
 */

export interface ApiErrorPayload {
  error_code?: string;
  message?: string;
  detail?: string;
  trace_id?: string;
}

export function getApiErrorDetail(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null) {
    const response = (error as { response?: { data?: unknown } }).response;
    const data = response?.data;
    if (typeof data === 'object' && data !== null) {
      const payload = data as ApiErrorPayload;
      const text = payload.detail ?? payload.message;
      if (typeof text === 'string' && text) return text;
    }
  }
  return fallback;
}
