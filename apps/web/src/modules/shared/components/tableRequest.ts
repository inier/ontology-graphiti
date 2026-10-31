/**
 * ProTable request 适配工具。
 *
 * 单独成文件的原因：`AdvancedTable.tsx` 必须保持「只导出组件」，
 * 否则 react-refresh 无法对该模块做热替换（会整页刷新）。
 */

/**
 * 将简单的数据获取函数包装为 ProTable request 格式。
 * 各页面只需传入返回 T[] 的异步函数，即可让 ProTable 接管 loading + 刷新。
 */
export function wrapRequest<T>(
  fetcher: () => Promise<T[]>,
): (params: { current?: number; pageSize?: number }, sort: unknown, filter: unknown) => Promise<{ data: T[]; success: boolean; total: number }> {
  return async () => {
    try {
      const data = await fetcher();
      return { data, success: true, total: data.length };
    } catch (error) {
      console.error('[AdvancedTable] request error:', error);
      return { data: [], success: false, total: 0 };
    }
  };
}
