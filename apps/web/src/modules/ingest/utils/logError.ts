/**
 * 从进程日志中提取错误原因。
 *
 * 后端有两个来源：ProcessLog.error_message（顶层字段）与 details.error（异常字符串），
 * 两者可能只有其一存在，这里统一兜底，确保失败原因不丢失。
 *
 * 单独成文件的原因：IngestPanel 必须保持「只导出组件」，
 * 工具函数混在同一模块会让 react-refresh 退化为整页刷新。
 */
export interface LogErrorSource {
  error_message?: string;
  /**
   * 各阶段日志的 details 由后端 JSONB 原样透传：
   * 除 `error` 外还可能带任意业务字段（如 `input`），故这里保留开放键。
   */
  details?: { error?: unknown } & Record<string, unknown>;
}

export function getLogError(log: LogErrorSource): string | undefined {
  const fromDetails = log.details && typeof log.details.error === 'string' ? log.details.error : undefined;
  const raw = log.error_message || fromDetails;
  return raw ? String(raw) : undefined;
}
