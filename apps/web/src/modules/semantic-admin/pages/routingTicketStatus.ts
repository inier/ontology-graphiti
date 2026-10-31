/**
 * 路由工单的状态 / 优先级展示元数据。
 *
 * 单独成文件的原因：`RoutingTicketsPage.tsx` 必须保持「只导出组件」，
 * 否则 react-refresh 会退化为整页刷新。详情页也复用这里的映射。
 */
import type { TicketStatus, TicketPriority } from '../services/routingTicketApi';

export const STATUS_META: Record<TicketStatus, { color: string; text: string }> = {
  open: { color: 'default', text: '待处理' },
  assigned: { color: 'blue', text: '已指派' },
  in_progress: { color: 'processing', text: '处理中' },
  resolved: { color: 'success', text: '已解决' },
  rejected: { color: 'error', text: '已驳回' },
  closed: { color: 'default', text: '已关闭' },
};

export const PRIORITY_COLOR: Record<TicketPriority, string> = {
  P0: 'red', P1: 'orange', P2: 'blue', P3: 'default',
};

export const statusMeta = (s: string) =>
  STATUS_META[s as TicketStatus] ?? { color: 'default', text: s };
