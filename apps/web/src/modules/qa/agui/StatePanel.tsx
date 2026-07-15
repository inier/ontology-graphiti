/**
 * State Panel — Shared State 显示面板
 *
 * 监听 STATE_SNAPSHOT / STATE_DELTA 事件
 * 展示当前 memory、active_skills、recent_sessions
 */

import React, { useEffect, useState } from 'react';
import { List, Tag, Typography } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { useAGUIContext } from './AGUIProvider';
import type { StateDeltaEvent, StateSnapshotEvent } from './agui_types';

const { Text } = Typography;

export interface StatePanelProps {
  /** 仅显示特定路径（默认 /memory/facts） */
  watchPath?: string;
}

export function StatePanel({ watchPath = '/memory/facts' }: StatePanelProps) {
  const { events } = useAGUIContext();
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);
  const [deltas, setDeltas] = useState<StateDeltaEvent[]>([]);

  useEffect(() => {
    for (const event of events) {
      if (event.type === 'STATE_SNAPSHOT') {
        setSnapshot(event.snapshot);
      } else if (event.type === 'STATE_DELTA') {
        setDeltas((prev) => [...prev, event]);
      }
    }
  }, [events]);

  // 简单解析：从 snapshot / delta 提取 watchPath
  const extractValue = () => {
    if (!snapshot) return null;
    if (!watchPath.startsWith('/')) return null;
    const path = watchPath.slice(1).split('/');
    let cur: unknown = snapshot;
    for (const p of path) {
      if (cur && typeof cur === 'object' && p in (cur as Record<string, unknown>)) {
        cur = (cur as Record<string, unknown>)[p];
      } else {
        return null;
      }
    }
    return cur;
  };

  const value = extractValue();

  return (
    <Card title="📊 Shared State" size="small" style={{ width: 280 }}>
      <Text type="secondary" style={{ fontSize: 12 }}>
        监听路径: <code>{watchPath}</code>
      </Text>
      {value === null || value === undefined ? (
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          (无数据)
        </Text>
      ) : Array.isArray(value) ? (
        <List
          size="small"
          dataSource={value}
          renderItem={(item) => (
            <List.Item>
              <Tag>{typeof item === 'string' ? item : JSON.stringify(item)}</Tag>
            </List.Item>
          )}
        />
      ) : (
        <pre style={{ fontSize: 12, marginTop: 8, maxHeight: 200, overflow: 'auto' }}>
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
      {deltas.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            增量事件: {deltas.length} 个
          </Text>
        </div>
      )}
    </Card>
  );
}
