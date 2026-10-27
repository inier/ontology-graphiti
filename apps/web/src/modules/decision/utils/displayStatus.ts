/**
 * 决策状态展示映射 —— **全模块唯一实现点**
 *
 * 硬约束（uiux §5.1.1 / §11 第 7 条）：
 * - 映射函数签名必须是 `toDisplayLabel(status, outcome)`。`status` 六值**不含**
 *   `partial_success`，只吃 `status` 会把「部分成功」这个 PRD 明确要求的标签丢掉。
 * - 台账 / 队列 / 详情 / 队列卡片四处共用本文件，任何组件内不得再写
 *   `status === 'executed' && outcome === 'partial_success'` 之类的判断（那是第二个真相源）。
 */
import type {
  DecisionEntrySource,
  DecisionOperation,
  DecisionOutcome,
  DecisionRecord,
  DecisionSlaState,
  DecisionStatus,
  PendingDecisionItem,
  Resolution,
} from '../types';
import { ENTRY_SOURCE_OPTIONS } from '../types';
import { SYNC_STALE_MINUTES } from '../constants/decisionConfig';

/** 界面只有 5 类标签 / 4 个色系（success / warning / error / 中性） */
export type DisplayTone = 'success' | 'partial' | 'failure' | 'pending' | 'rejected' | 'unknown';

export interface DisplayLabel {
  tone: DisplayTone;
  label: string;
}

/**
 * `status` × `outcome` → 界面标签（双参，缺一不可）
 * 历史数据（`status` 缺失 / `status_assumed`）由 `status_assumed` 单独标注，
 * 标签本身仍走「待定」，见 uiux §5.1.5。
 */
export function toDisplayLabel(
  status: DecisionStatus | null | undefined,
  outcome?: DecisionOutcome | null,
): DisplayLabel {
  switch (status) {
    case 'pending':
      return { tone: 'pending', label: '待定（待裁定）' };
    case 'decided':
      return { tone: 'pending', label: '待定（待执行确认）' };
    case 'executing':
      return { tone: 'pending', label: '待定（待执行确认）' };
    case 'executed':
      // 唯一需要 outcome 参与的一支：`status` 只有 executed，没有 partial_success
      return outcome === 'partial_success'
        ? { tone: 'partial', label: '部分成功' }
        : { tone: 'success', label: '执行成功' };
    case 'failed':
      return { tone: 'failure', label: '执行失败' };
    case 'rejected':
      return { tone: 'rejected', label: '已驳回' };
    default:
      // 未知枚举值：显示「状态未知」中性色，不抛错不空白（uiux §7.4）
      return { tone: 'unknown', label: '状态未知' };
  }
}

/**
 * `status` 与 `outcome` 互相矛盾时追加提示（不新增状态、不静默吞掉）
 * 结果列仍以 `status` 为准。
 */
export function isStatusOutcomeConflict(
  status: DecisionStatus | null | undefined,
  outcome?: DecisionOutcome | null,
): boolean {
  if (!status || !outcome) return false;
  if (status === 'executed') return outcome !== 'success' && outcome !== 'partial_success';
  if (status === 'failed') return outcome === 'success';
  return false;
}

/** 台账「执行状态」4 档（uiux §4.6）。精确 8 态只在详情页，且需 `ActionRecord` */
export type ExecutionTier = 'none' | 'not_started' | 'running' | 'done' | 'failed';

export interface ExecutionTierMeta {
  tier: ExecutionTier;
  label: string;
  /** 无关联动作 = 从没派发过执行，与「未开始」是两件事 */
  muted: boolean;
}

/**
 * 4 档归并的唯一实现。
 *
 * 说明：`DecisionRecord` 不携带 `ActionRecord.status`（列表端点不返回），因此 4 档由
 * 「是否有 action_record_id」+ 决策 `status` 派生 —— 只用契约里真实存在的字段，
 * 不臆造 `action_status`。精确 8 态待契约补字段后再上（P1），当前不做假字段。
 */
export function toExecutionTier(record: Pick<DecisionRecord, 'status' | 'action_record_id'>): ExecutionTierMeta {
  if (!record.action_record_id) {
    return { tier: 'none', label: '无动作', muted: true };
  }
  switch (record.status) {
    case 'executing':
      return { tier: 'running', label: '进行中', muted: false };
    case 'executed':
      return { tier: 'done', label: '已完成', muted: false };
    case 'failed':
    case 'rejected':
      return { tier: 'failed', label: '失败或已回滚', muted: false };
    default:
      return { tier: 'not_started', label: '未开始', muted: false };
  }
}

/** 来源入口展示（7 值 + 未知兜底）。未知值 `console.warn` 一次，不猜成最接近的已知值 */
const ENTRY_SOURCE_LABEL = new Map<string, string>(
  ENTRY_SOURCE_OPTIONS.map((o) => [o.value, o.label]),
);
const warnedEntrySources = new Set<string>();

export function toEntrySourceLabel(source: DecisionEntrySource | string | null | undefined): {
  label: string;
  muted: boolean;
} {
  if (!source) return { label: '来源未标注', muted: true };
  const known = ENTRY_SOURCE_LABEL.get(source);
  if (known) return { label: known, muted: source === 'legacy' };
  if (!warnedEntrySources.has(source)) {
    warnedEntrySources.add(source);
    console.warn(`[decision] 未知的 entry_source: ${source}，已按「来源未标注」渲染`);
  }
  return { label: '来源未标注', muted: true };
}

/** 裁决人四种取值（uiux §4.8）：系统门禁 / 人工 / 未处理 / 历史数据 */
export type ActorKind = 'system' | 'user' | 'unhandled' | 'legacy';

export interface ActorDisplay {
  kind: ActorKind;
  text: string;
  muted: boolean;
}

function formatShortTime(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function toActorDisplay(
  record: Pick<DecisionRecord, 'status' | 'status_assumed'>,
  resolution?: Resolution | null,
): ActorDisplay {
  if (record.status_assumed) {
    // 历史数据用「—」而不是「未处理」：后者暗示还在等人处理，会误导用户去催
    return { kind: 'legacy', text: '—', muted: true };
  }
  if (resolution) {
    if (resolution.actor_type === 'system' || resolution.by === 'system') {
      return { kind: 'system', text: '系统（策略门禁）', muted: false };
    }
    const time = formatShortTime(resolution.at);
    return {
      kind: 'user',
      text: resolution.by ? (time ? `${resolution.by} · ${time}` : resolution.by) : '已处理',
      muted: false,
    };
  }
  if (record.status === 'pending') {
    return { kind: 'unhandled', text: '未处理', muted: true };
  }
  return { kind: 'unhandled', text: '未处理', muted: true };
}

/** 队列 SLA 标记（三档全部由后端 `sla_state` 给，前端不自算阈值） */
export interface SlaBadge {
  text: string;
  tone: 'warning' | 'breached';
}

export function toSlaBadge(
  slaState: DecisionSlaState | null | undefined,
  status: DecisionStatus,
): SlaBadge | null {
  if (!slaState || slaState === 'ok') return null;
  // executing 段不显示 SLA（正在跑，催无意义）
  if (status === 'executing') return null;
  if (status === 'decided') {
    // 数字由卡片 meta 区的 `decided_waited_minutes` 单独显示（`toWaitMinutes`），
    // 徽标只表达「久了」这一档，不重复拼数字，也不拿 `waited_minutes` 顶替
    return {
      text: slaState === 'breached' ? '裁决后长时间未执行' : '裁决后等待较久',
      tone: slaState === 'breached' ? 'breached' : 'warning',
    };
  }
  return {
    text: slaState === 'breached' ? '已超时' : '等待较久',
    tone: slaState === 'breached' ? 'breached' : 'warning',
  };
}

/** 等待时长展示：粒度到小时，不用相对时间自动刷新 */
export function formatWaiting(minutes?: number | null): string {
  if (minutes === undefined || minutes === null || Number.isNaN(minutes)) return '—';
  const hours = Math.floor(minutes / 60);
  if (hours > 999) return '超过 41 天';
  return `${hours} 小时`;
}

/** 分钟级时长（同步态要精确到分钟，`formatWaiting` 会把 5 分钟显示成「0 小时」） */
export function formatDuration(minutes?: number | null): string {
  if (minutes === undefined || minutes === null || Number.isNaN(minutes)) return '未知';
  if (minutes < 1) return '不到 1 分钟';
  if (minutes < 60) return `${Math.round(minutes)} 分钟`;
  return formatWaiting(minutes);
}

function minutesSince(iso: string | null | undefined, now: number): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.floor((now - t) / 60000));
}

/**
 * 队列条目的等待时长：**按 `group` 取字段，两者不可互相顶替**。
 * `to_resolve` → `waited_minutes`（自 createdAt）
 * `to_execute` → `decided_waited_minutes`（自 resolution.at）
 * 差一整个待裁定周期：拿 `waited_minutes` 顶替会把「昨天裁决的」显示成「等了 5 天」。
 */
export function toWaitMinutes(
  item: Pick<PendingDecisionItem, 'group' | 'waited_minutes' | 'decided_waited_minutes'>,
): number | null {
  if (item.group === 'to_execute') return item.decided_waited_minutes ?? null;
  return item.waited_minutes ?? null;
}

/* ------------------------------------------------------------------ *
 * E41 同步窗口：决策状态说「执行中」，但执行侧结果没回写
 * ------------------------------------------------------------------ */

export type SyncStateKind = 'syncing' | 'stale';

export interface SyncState {
  kind: SyncStateKind;
  /** 主文案：「状态同步中」/「状态可能未同步」 */
  label: string;
  /** 必须含可核对信息（等了多久 / 去哪核对），不能只有「同步中…」 */
  detail: string;
  tone: 'info' | 'warning';
}

/**
 * `status=executing` 时的残留态判定（唯一实现点）。
 *
 * 三条硬规则：
 * 1. **不得把残留态渲染成「执行中」** —— 「执行中」是对执行层的断言，而我们看不到执行层。
 * 2. **必须自带期限**：超过 `SYNC_STALE_MINUTES`（按 `updated_at` 计时）升级为
 *    「状态可能未同步」，并给出核对入口。永不出现无限期「同步中」。
 * 3. **不得与执行记录矛盾**：调用方若已知执行侧已终态（`actionTerminal`），
 *    文案明确说「执行侧已结束」，而不是继续暗示还在跑。
 *
 * `status !== 'executing'` 返回 `null`（其它状态与本机制无关）。
 */
export function toSyncState(input: {
  status: DecisionStatus;
  updatedAt?: string | null;
  /** 执行侧已确认终态（如刚发起执行的响应里 `action_record` 已结束） */
  actionTerminal?: boolean;
  /** 便于测试注入 */
  now?: number;
}): SyncState | null {
  if (input.status !== 'executing') return null;

  const elapsed = minutesSince(input.updatedAt, input.now ?? Date.now());
  const waited = elapsed === null ? '时长未知' : formatDuration(elapsed);
  const since = input.updatedAt ? `（决策状态自 ${formatShortTime(input.updatedAt)} 起未更新）` : '';

  if (elapsed !== null && elapsed >= SYNC_STALE_MINUTES) {
    return {
      kind: 'stale',
      tone: 'warning',
      label: '状态可能未同步',
      detail: `决策状态停在「执行中」已 ${waited}${since}，超过 ${SYNC_STALE_MINUTES} 分钟未回写。执行可能早已结束，也可能是回写失败——请核对执行记录后再判断这条决策是否完成。`,
    };
  }

  return {
    kind: 'syncing',
    tone: 'info',
    label: '状态同步中',
    detail: input.actionTerminal
      ? `执行侧已结束，决策状态尚未回写，已等待 ${waited}${since}。超过 ${SYNC_STALE_MINUTES} 分钟仍未回写将提示你核对执行记录。`
      : `决策状态为「执行中」，执行侧结果尚未回写，已等待 ${waited}${since}。超过 ${SYNC_STALE_MINUTES} 分钟仍未回写将提示你核对执行记录。`,
  };
}

/** 队列可用操作 → 界面按钮语义（数组为空则整组不渲染） */
export function hasOperation(operations: DecisionOperation[] | undefined, op: DecisionOperation): boolean {
  return Array.isArray(operations) && operations.includes(op);
}
