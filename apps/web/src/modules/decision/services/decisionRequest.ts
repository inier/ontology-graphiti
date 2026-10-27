/**
 * 决策模块专用请求层 —— 错误体解析的**唯一实现点**（AC-17）
 *
 * ## 为什么不用 `modules/shared/services/apiClient`
 * 1. `apiClient` 对 401/403 一律 `window.location.href = '/login'` 并抛「登录已过期」。
 *    本模块要求「同空间无权限 → 按钮禁用 + Tooltip，**不整页 403**」，一旦走 apiClient，
 *    403 会被当成登录失效，整页跳走，违反 PRD §5.6。
 * 2. `apiClient` 只抛 `HTTP 404: Not Found`，丢掉了后端给的具体原因（PRD 要求列表失败必须
 *    暴露 HTTP 状态 + 后端 detail），且详情页要靠 404/403 区分两种空态。
 *
 * ## 错误体形状：真实链路有三种（这是 E42 曾经等于没做的原因）
 * - **A（主形状）** `APIError` 家族信封 —— 决策模块全部客户端可见错误走这条：
 *   `{"error": {type, code, message, request_id, path, details?}}`
 *   （见 `infra/middleware/exception_handler.py`，409 的 `handler_name` 落在 `details` 里）
 * - **B（框架 422）** Starlette 参数校验，无法改造：
 *   `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` —— **`detail` 是数组**
 * - **C（遗留扁平体）** 契约文档里写的 `{"detail": "...", "reason_code": ..., "handler_name": ...}`，
 *   由 `HTTPException` 放行产生。AC-17 已要求决策模块不再用它，但读取端保留兜底，
 *   否则线上出现一条老响应就又变回「HTTP 409」泛化文案。
 *
 * 读取顺序固定：`error.code`/`error.message` → `detail`（字符串或数组都处理）→ `statusText`。
 *
 * `workspace_id` 一律不传 —— 后端从 JWT 声明解析（ADR-076 §7 信任模型）。
 */
import { API_BASE } from '@/config';

const AUTH_HEADER = 'Authorization';

/** `APIError` 信封内容（形状 A） */
export interface ApiErrorEnvelope {
  type?: string;
  code?: string;
  message?: string;
  request_id?: string;
  path?: string;
  details?: unknown;
}

/** 三种形状的并集。字段全部可选：任何一条缺失都不能让解析抛错 */
export interface DecisionErrorPayload {
  error?: ApiErrorEnvelope;
  /** 可能是字符串（形状 C），也可能是数组（形状 B，422 参数校验） */
  detail?: unknown;
  /** 形状 C 顶层字段 */
  reason_code?: string;
  handler_name?: string | null;
  current_status?: string;
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

/**
 * 形状 B：`detail` 是数组时**绝不能**直接塞进模板字符串 —— 会渲染出 `[object Object]`。
 * 逐条抽 `msg`，带 `loc` 时拼出字段名（去掉 `body`/`query` 这类无信息量前缀）。
 */
function describeDetailList(list: unknown[]): string | undefined {
  const messages = list
    .map((item) => {
      if (typeof item === 'string') return asString(item);
      const entry = asRecord(item);
      if (!entry) return undefined;
      const msg = asString(entry.msg);
      if (!msg) return undefined;
      const field = Array.isArray(entry.loc)
        ? entry.loc.filter((p) => typeof p === 'string' && p !== 'body' && p !== 'query').join('.')
        : '';
      return field ? `${field}：${msg}` : msg;
    })
    .filter((v): v is string => Boolean(v));
  if (messages.length === 0) return undefined;
  return messages.length === 1 ? messages[0] : `${messages[0]}（共 ${messages.length} 处）`;
}

/** 已知 `code` 的定稿文案。按 code 判断，**不匹配文案**（文案会变，code 是契约） */
const CODE_MESSAGE: Record<string, string> = {
  illegal_transition: '该决策已被他人处理，请刷新后查看最新状态',
  execute_in_progress: '该决策正在执行中，请稍候再试',
  concurrent_append_conflict: '推理步骤写入冲突，请重试，已存在的步骤不会丢失',
  step_limit_reached: '该决策的推理步骤已达上限（200 条），无法继续追加',
};

const STATUS_MESSAGE: Record<number, string> = {
  401: '登录状态已失效，请重新登录',
  403: '需要决策审批权限',
  404: '决策不存在或无权访问',
  409: '该决策已被他人处理，请刷新后查看最新状态',
};

interface NormalizedError {
  code?: string;
  handlerName?: string | null;
  currentStatus?: string;
  requestId?: string;
  /** 后端给的原始说明（可能是形状 B 拼出来的），用于诊断展示 */
  raw: string;
  /** 说明是否由「参数校验数组」展平而来 —— 只有这类才该说「请求参数不合法」 */
  fromValidationList: boolean;
}

function normalize(payload: DecisionErrorPayload | string): NormalizedError {
  if (typeof payload === 'string') {
    return { raw: payload, fromValidationList: false };
  }
  const envelope = asRecord(payload.error);
  // 形状 C 的危险变体：`HTTPException(409, detail=<dict>)` 会被 FastAPI 再包一层
  const nested = asRecord(payload.detail);
  const details = asRecord(envelope?.details);

  const listMessage = Array.isArray(payload.detail) ? describeDetailList(payload.detail) : undefined;
  const raw =
    asString(envelope?.message) ??
    listMessage ??
    asString(payload.detail) ??
    asString(nested?.message) ??
    asString(nested?.detail) ??
    '';

  return {
    fromValidationList: Boolean(listMessage),
    code:
      asString(envelope?.code) ??
      asString(payload.reason_code) ??
      asString(nested?.reason_code) ??
      asString(details?.reason_code),
    handlerName:
      asString(details?.handler_name) ??
      asString(payload.handler_name) ??
      asString(nested?.handler_name) ??
      null,
    currentStatus:
      asString(details?.current_status) ??
      asString(payload.current_status) ??
      asString(nested?.current_status),
    requestId: asString(envelope?.request_id),
    raw,
  };
}

/**
 * 面向用户的动作失败文案（采纳/驳回/执行）：**不带 HTTP 前缀**。
 * 文案优先级：已知 `code` → 状态码兜底 → 后端原文。
 */
function resolveUserMessage(status: number, info: NormalizedError): string {
  const byCode = info.code ? CODE_MESSAGE[info.code] : undefined;
  if (byCode) {
    // 409 illegal_transition 且后端给了处理人：把「他人」换成具体姓名，能省用户一次追问
    if (info.code === 'illegal_transition' && info.handlerName) {
      return `该决策已被${info.handlerName}处理，请刷新后查看最新状态`;
    }
    return byCode;
  }
  if (status === 422) {
    // 只有「参数校验数组」才加这个前缀。像 `JWT 缺少 workspace 声明` 这类 422
    // 不是用户填错了字段，硬套「请求参数不合法」会把认证问题说成填表问题
    if (info.fromValidationList) return `请求参数不合法：${info.raw}`;
    return info.raw || '请求未被接受，请检查后重试';
  }
  // 用 `||` 而不是 `??`：空字符串也是「没信息」，必须继续回落
  return STATUS_MESSAGE[status] || info.raw || `HTTP ${status}`;
}

export class DecisionApiError extends Error {
  status: number;
  /** 契约 `error.code`（优先）或 `reason_code`（兜底） */
  code?: string;
  /** @deprecated 契约旧名，等同 `code`；保留只为不改动既有调用点 */
  reasonCode?: string;
  handlerName?: string | null;
  currentStatus?: string;
  requestId?: string;
  /** 后端原始说明，已规整为字符串（数组已展平），可直接进模板 */
  detail: string;
  /** 面向用户的一句话，动作失败时直接用这个，不要自己拼 HTTP 状态 */
  userMessage: string;

  constructor(status: number, payload: DecisionErrorPayload | string) {
    const info = normalize(payload);
    super(resolveUserMessage(status, info));
    this.name = 'DecisionApiError';
    this.status = status;
    this.code = info.code;
    this.reasonCode = info.code;
    this.handlerName = info.handlerName ?? null;
    this.currentStatus = info.currentStatus;
    this.requestId = info.requestId;
    this.detail = info.raw || `HTTP ${status}`;
    this.userMessage = resolveUserMessage(status, info);
  }
}

/** 加载失败用：暴露 HTTP 状态 + 具体原因（PRD 要求，不能只说「加载失败」） */
export function describeError(error: unknown): string {
  if (error instanceof DecisionApiError) {
    return `HTTP ${error.status} · ${error.userMessage}`;
  }
  if (error instanceof Error) return error.message.slice(0, 120);
  return String(error).slice(0, 120);
}

/** 动作失败用：只给用户那句话，不暴露 HTTP 状态码 */
export function describeActionError(error: unknown): string {
  if (error instanceof DecisionApiError) return error.userMessage;
  if (error instanceof Error) return error.message.slice(0, 120);
  return '操作失败，请稍后重试';
}

export function errorStatus(error: unknown): number | undefined {
  return error instanceof DecisionApiError ? error.status : undefined;
}

export function errorCode(error: unknown): string | undefined {
  return error instanceof DecisionApiError ? error.code : undefined;
}

function buildUrl(path: string): string {
  return path.startsWith('http') ? path : `${API_BASE}${path}`;
}

async function parseErrorPayload(response: Response): Promise<DecisionErrorPayload | string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === 'object') return data as DecisionErrorPayload;
    return response.statusText;
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

export async function decisionRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init.headers as Record<string, string>) || {}),
  };
  if (token) headers[AUTH_HEADER] = `Bearer ${token}`;

  const response = await fetch(buildUrl(path), { ...init, headers });
  if (!response.ok) {
    throw new DecisionApiError(response.status, await parseErrorPayload(response));
  }
  return (await response.json()) as T;
}
