/**
 * 决策模块界面常量（一处集中，禁止散落在组件里）
 *
 * `SYNC_STALE_MINUTES` 是 E41 的硬要求：**同步态必须自带期限**，
 * 否则「状态同步中」会变成没有终点的等待，用户永远不知道要不要去核对执行记录。
 * 计时基准是 `decision.updated_at`（决策状态最后一次变化的时刻），
 * **不是** `sla_state`、也不是 `waited_minutes` —— 后两者服务的是「等了多久没人处理」，
 * 与「状态回写卡了多久」是两件不同的事，混用会把 5 分钟的同步延迟显示成 3 天的等待。
 */

const DEFAULT_SYNC_STALE_MINUTES = 10;

function readOverride(): number {
  const raw = import.meta.env.VITE_DECISION_SYNC_STALE_MINUTES;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_SYNC_STALE_MINUTES;
}

/** 超过该分钟数仍未回写 → 从「状态同步中」升级为「状态可能未同步」 */
export const SYNC_STALE_MINUTES = readOverride();
