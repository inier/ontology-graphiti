/**
 * HITL Panel — Human-in-the-Loop Interrupt 处理面板
 *
 * 当 useAGUI 收到 RunFinished.interrupts 时，此面板渲染对应卡片
 * 点击按钮触发 resume()
 */

import React from 'react';
import { Button, Card, Space, Typography } from 'antd';
import { useAGUIContext } from './AGUIProvider';
import { CardRenderer } from './CardRegistry';
import type { Interrupt } from './agui_types';

const { Text } = Typography;

export interface HITLPanelProps {
  /** 覆盖默认的 resume 行为 */
  onConfirm?: (interrupt: Interrupt, approved: boolean, editedArgs?: Record<string, unknown>) => void;
}

export function HITLPanel({ onConfirm }: HITLPanelProps) {
  const { pendingInterrupts, resume } = useAGUIContext();

  if (pendingInterrupts.length === 0) return null;

  return (
    <Card
      title="⚠️ 需要您的确认"
      size="small"
      style={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        width: 360,
        zIndex: 1000,
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {pendingInterrupts.map((interrupt) => (
          <Card key={interrupt.id} size="small" type="inner">
            <Text strong>{interrupt.message}</Text>
            <div style={{ marginTop: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                类型: {interrupt.reason}
                {interrupt.toolCallId && ` · 工具: ${interrupt.toolCallId}`}
              </Text>
            </div>
            <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
              <Button
                type="primary"
                size="small"
                onClick={() => {
                  if (onConfirm) {
                    onConfirm(interrupt, true);
                  } else {
                    resume(interrupt.id, { approved: true });
                  }
                }}
              >
                ✓ 确认
              </Button>
              <Button
                size="small"
                onClick={() => {
                  if (onConfirm) {
                    onConfirm(interrupt, false);
                  } else {
                    resume(interrupt.id, { approved: false });
                  }
                }}
              >
                ✗ 拒绝
              </Button>
            </div>
          </Card>
        ))}
      </Space>
    </Card>
  );
}
