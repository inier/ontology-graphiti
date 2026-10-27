/**
 * 详情页整页空态（404 / 403）
 *
 * 404 覆盖「不存在」与「跨工作空间」两种情形，**用同一套文案不区分措辞**：
 * 一旦区分，就泄露了「这条决策存在、只是不属于你」，配合 48 位 ID 枚举即攻击面。
 */
import React from 'react';
import { Button, Typography } from 'antd';
import { LockOutlined, PartitionOutlined } from '@ant-design/icons';
import { describeError } from '../services/decisionRequest';

const { Title, Text } = Typography;

interface Props {
  kind: 'not-found' | 'forbidden';
  status?: number;
  error?: unknown;
  onBack: () => void;
}

export function DecisionErrorState({ kind, status, error, onBack }: Props) {
  const notFound = kind === 'not-found';
  return (
    <div
      role="alert"
      style={{ padding: 'var(--odap-spacing-xl)', textAlign: 'center', maxWidth: 520, margin: '0 auto' }}
    >
      {notFound ? (
        <PartitionOutlined style={{ fontSize: 24, color: 'var(--odap-color-text-tertiary)' }} />
      ) : (
        <LockOutlined style={{ fontSize: 24, color: 'var(--odap-color-text-secondary)' }} />
      )}
      <Title level={5} style={{ marginTop: 8 }}>
        {notFound ? '决策不存在或无权访问' : '你没有查看这条决策的权限'}
      </Title>
      <Text type="secondary">
        {notFound
          ? '它可能属于其他工作空间，或已被删除。'
          : '请联系当前工作空间的管理员开通查看权限。'}
      </Text>
      {status ? (
        <div style={{ marginTop: 4 }}>
          <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
            {`HTTP ${status}${error ? ` · ${describeError(error)}` : ''}`}
          </Text>
        </div>
      ) : null}
      <div style={{ marginTop: 16 }}>
        <Button type="primary" onClick={onBack}>
          返回决策台账
        </Button>
      </div>
    </div>
  );
}

export default DecisionErrorState;
