/**
 * 错误体解析（AC-17）—— 三种真实形状都必须能读出具体原因
 *
 * 这三条不是「多余的兼容」，是三条真实存在的响应：
 * - A `{"error": {...}}`     ：`APIError` 家族信封（决策模块主形状）
 * - B `{"detail": [ ... ]}`  ：框架 422 参数校验（无法改造，`detail` 是数组）
 * - C `{"detail": "...", "reason_code": ...}` ：`HTTPException` 放行产生的遗留扁平体
 */
import { describe, expect, it, vi } from 'vitest';
import {
  DecisionApiError,
  describeActionError,
  describeError,
  errorCode,
  errorStatus,
  decisionRequest,
} from './decisionRequest';

function fakeResponse(status: number, body: unknown, statusText = ''): Response {
  return {
    ok: false,
    status,
    statusText,
    json: async () => body,
  } as unknown as Response;
}

describe('形状 A：APIError 信封', () => {
  it('409 illegal_transition + details.handler_name → 用户看到姓名，不是「HTTP 409」', () => {
    const error = new DecisionApiError(409, {
      error: {
        type: 'ConflictError',
        code: 'illegal_transition',
        message: 'decision already resolved',
        request_id: 'req-1',
        path: '/api/decisions/dec_1/resolve',
        details: { handler_name: '张三', current_status: 'decided' },
      },
    });

    expect(error.userMessage).toBe('该决策已被张三处理，请刷新后查看最新状态');
    expect(error.code).toBe('illegal_transition');
    expect(error.handlerName).toBe('张三');
    expect(error.currentStatus).toBe('decided');
    // 加载失败用的诊断文案仍带 HTTP 状态，但不再是「HTTP 409 · HTTP 409」
    expect(describeError(error)).toBe('HTTP 409 · 该决策已被张三处理，请刷新后查看最新状态');
  });

  it('409 illegal_transition 无处理人 → 「该决策已被他人处理」', () => {
    const error = new DecisionApiError(409, {
      error: { code: 'illegal_transition', message: 'already resolved' },
    });
    expect(describeActionError(error)).toBe('该决策已被他人处理，请刷新后查看最新状态');
  });

  it('code 优先于状态码：409 execute_in_progress 不会被说成「已被他人处理」', () => {
    const error = new DecisionApiError(409, {
      error: { code: 'execute_in_progress', message: 'lock held' },
    });
    expect(error.code).toBe('execute_in_progress');
    expect(describeActionError(error)).toBe('该决策正在执行中，请稍候再试');
  });

  it('409 无 code（通用 CONFLICT）→ 回落状态码文案，仍不是「HTTP 409」', () => {
    const error = new DecisionApiError(409, { error: { code: 'CONFLICT', message: 'conflict' } });
    expect(describeActionError(error)).toBe('该决策已被他人处理，请刷新后查看最新状态');
  });

  it('404 → 统一「决策不存在或无权访问」，不区分跨空间与不存在', () => {
    const error = new DecisionApiError(404, { error: { code: 'NOT_FOUND', message: 'not found' } });
    expect(describeActionError(error)).toBe('决策不存在或无权访问');
  });
});

describe('形状 B：detail 是数组（框架 422）', () => {
  it('逐条抽 msg 并带字段名，绝不渲染成 [object Object]', () => {
    const error = new DecisionApiError(422, {
      detail: [
        { type: 'string_too_long', loc: ['body', 'context_summary'], msg: '最多 500 字符' },
      ],
    });

    expect(error.userMessage).toBe('请求参数不合法：context_summary：最多 500 字符');
    expect(error.userMessage).not.toContain('[object Object]');
    expect(error.detail).not.toContain('[object Object]');
  });

  it('多条错误给出条数，不丢信息', () => {
    const error = new DecisionApiError(422, {
      detail: [
        { loc: ['body', 'confidence'], msg: '必须在 0 与 1 之间' },
        { loc: ['body', 'recommended_option'], msg: '字段必填' },
      ],
    });

    expect(error.userMessage).toContain('confidence：必须在 0 与 1 之间');
    expect(error.userMessage).toContain('共 2 处');
  });

  it('detail 是纯字符串数组也能读', () => {
    const error = new DecisionApiError(422, { detail: ['请求体不是合法 JSON'] });
    expect(error.userMessage).toBe('请求参数不合法：请求体不是合法 JSON');
  });
});

describe('形状 C：遗留扁平体 / FastAPI 双层包裹', () => {
  it('扁平 reason_code=step_limit_reached → 容量上限文案（不是「你填错了」）', () => {
    const error = new DecisionApiError(422, {
      detail: '该决策推理步骤已满',
      reason_code: 'step_limit_reached',
    });
    expect(error.userMessage).toBe('该决策的推理步骤已达上限（200 条），无法继续追加');
  });

  it('HTTPException(409, detail={reason_code}) 的双层包裹也能读到 reason_code', () => {
    const error = new DecisionApiError(409, {
      detail: { reason_code: 'illegal_transition', handler_name: '李四' },
    });
    expect(error.code).toBe('illegal_transition');
    expect(error.handlerName).toBe('李四');
    expect(describeActionError(error)).toBe('该决策已被李四处理，请刷新后查看最新状态');
  });

  it('只有纯文本时优先用后端原文；完全没有信息才回落 HTTP 状态', () => {
    const withText = new DecisionApiError(500, 'Internal Server Error');
    expect(withText.userMessage).toBe('Internal Server Error');

    const empty = new DecisionApiError(500, {});
    expect(empty.userMessage).toBe('HTTP 500');
    expect(describeActionError(empty)).toBe('HTTP 500');
  });
});

describe('decisionRequest 真实链路', () => {
  it('从 fetch 响应里按错误信封解析（不是只在构造函数里成立）', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        fakeResponse(409, {
          error: { code: 'illegal_transition', message: 'already resolved', details: {} },
        }),
      ),
    );
    localStorage.setItem('token', 't');

    await expect(decisionRequest('/api/decisions/dec_1/resolve', { method: 'POST' })).rejects.toThrow(
      '请刷新后查看最新状态',
    );
    vi.unstubAllGlobals();
  });

  it('detail 为数组时不把数组塞进模板（防 [object Object] 事故）', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        fakeResponse(422, { detail: [{ loc: ['body', 'q'], msg: '最多 100 字符' }] }),
      ),
    );
    localStorage.setItem('token', 't');

    let caught: unknown;
    try {
      await decisionRequest('/api/decisions?q=xxx');
    } catch (e) {
      caught = e;
    }

    expect(errorStatus(caught)).toBe(422);
    expect(errorCode(caught)).toBeUndefined();
    expect(describeActionError(caught)).toContain('q：最多 100 字符');
    expect(describeActionError(caught)).not.toContain('[object Object]');
    vi.unstubAllGlobals();
  });
});
