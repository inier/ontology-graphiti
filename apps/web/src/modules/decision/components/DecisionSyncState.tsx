/**
 * 同步窗口状态块（E41）—— 详情页专用，**不进台账列表**
 *
 * 场景：`decision.status === 'executing'`，但执行侧的结果没有回写到决策流程状态。
 * 这时把界面渲染成「执行中」是在替执行层下一个我们看不到的结论。
 *
 * 三条硬规则（全部落在 `toSyncState` 这一个纯函数里）：
 * 1. 不渲染「执行中」，渲染「状态同步中」；
 * 2. 自带期限（`SYNC_STALE_MINUTES`，按 `updated_at` 计时），超时升级为
 *    「状态可能未同步」并给出核对入口，绝不出现无限期「同步中」；
 * 3. 文案含可核对信息：等了多久、决策状态最后一次更新在什么时候、去哪核对。
 *
 * 色系只用既有 token：`syncing` 走 info，`stale` 走 warning，**不新增色系**。
 */
import React, { useState } from 'react';
import { Button, Typography } from 'antd';
import { ClockCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { ExecutionRecordDrawer } from './ExecutionRecordDrawer';
import { toSyncState } from '../utils/displayStatus';
import type { DecisionStatus } from '../types';

const { Text } = Typography;

interface Props {
  status: DecisionStatus;
  /** 决策状态最后一次更新时间 —— 同步窗口的计时基准 */
  updatedAt?: string | null;
  /** 关联的执行记录 id（用于核对入口） */
  actionRecordId?: string | null;
  /** 已确认执行侧终态（例如刚发起执行的响应里执行记录已结束） */
  actionTerminal?: boolean;
  /** 便于测试注入固定时刻 */
  now?: number;
}

export function DecisionSyncState({
  status,
  updatedAt,
  actionRecordId,
  actionTerminal,
  now,
}: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const sync = toSyncState({ status, updatedAt, actionTerminal, now });

  // 非 executing 状态与本机制无关，整块不渲染（不占位、不留空壳）
  if (!sync) return null;

  const stale = sync.kind === 'stale';
  const tone = stale ? 'var(--odap-color-warning)' : 'var(--odap-color-info)';

  return (
    <div
      role="status"
      data-sync-state={sync.kind}
      style={{
        border: `1px solid ${tone}`,
        borderRadius: 'var(--odap-radius-md)',
        padding: 'var(--odap-spacing-sm) var(--odap-spacing-md)',
        marginBottom: 'var(--odap-spacing-md)',
        background: 'var(--odap-color-bg-primary)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {stale ? (
          <WarningOutlined style={{ fontSize: 16, color: tone }} />
        ) : (
          <ClockCircleOutlined style={{ fontSize: 16, color: tone }} />
        )}
        <Text strong style={{ color: tone }}>
          {sync.label}
        </Text>
        {actionRecordId && (
          <Button type="link" size="small" onClick={() => setDrawerOpen(true)}>
            查看执行记录
          </Button>
        )}
      </div>
      <div style={{ marginTop: 4 }}>
        <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-sm)' }}>
          {sync.detail}
        </Text>
      </div>
      {stale && actionRecordId && (
        <div style={{ marginTop: 4 }}>
          <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
            {`执行记录：${actionRecordId}（点「查看执行记录」核对，或复制该 ID 交给运维排查）`}
          </Text>
        </div>
      )}
      {/* 超时但没有关联执行记录：核对入口不存在，必须换一句可执行的话，不能静默留白 */}
      {stale && !actionRecordId && (
        <div style={{ marginTop: 4 }}>
          <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
            该决策没有关联执行记录，无法在系统内核对。请联系管理员按决策 ID 排查执行侧是否已派发。
          </Text>
        </div>
      )}

      <ExecutionRecordDrawer
        open={drawerOpen}
        actionRecordId={actionRecordId ?? null}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}

export default DecisionSyncState;
