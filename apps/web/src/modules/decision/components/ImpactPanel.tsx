/**
 * 决策影响分析面板
 *
 * 本期修复（uiux §6.3 / §9.2 第 7 条）：
 * 1. `impact_completeness` 是**三态**（`full` / `degraded_target_resolution` / `partial`），
 *    三态文案不得合并 —— 前者的用户行动是「去查本体数据」，后者是「等 ADR-074 落地」。
 * 2. 影响分析单独失败不再静默 `setImpact(null)`（旧实现把「加载失败」伪装成「还没加载」），
 *    改为卡片内局部 Alert + 局部重试，不阻断因果链与详情。
 */
import React from 'react';
import { Alert, Button, Card, Empty, List, Space, Tag, Typography } from 'antd';
import { CloseCircleOutlined } from '@ant-design/icons';
import type { DecisionImpact } from '../types';
import { describeError } from '../services/decisionRequest';

const { Text } = Typography;

interface Props {
  impact: DecisionImpact | null;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  onSelectDecision?: (decisionId: string) => void;
}

const COMPLETENESS_META: Record<
  DecisionImpact['impact_completeness'],
  { type: 'success' | 'warning'; title: string; description: string }
> = {
  full: {
    type: 'success',
    title: '影响分析完整',
    description: '强影响与弱影响维度均已覆盖。',
  },
  degraded_target_resolution: {
    type: 'warning',
    title: '目标解析降级，部分影响未纳入',
    description:
      '有执行动作的目标实体未能解析到图谱中，相关目标变更可能缺失。可核对执行动作的目标对象是否已入本体。',
  },
  partial: {
    type: 'warning',
    title: '影响分析不完整',
    description:
      // 最后一句是设计的关键：下游决策 0 条极易被误读为「这件事没有影响」，必须显式否定
      '当前仅覆盖弱影响三类（下游决策、目标对象变化、协同证据决策）。强影响维度（事实失效清单、失效边遍历）依赖 ADR-074 落地，尚未纳入。下游决策数为 0 不代表没有下游决策。',
  },
};

export function ImpactPanel({ impact, loading = false, error, onRetry, onSelectDecision }: Props) {
  if (error) {
    return (
      <Card title="影响分析" size="small">
        <Alert
          type="warning"
          showIcon
          icon={<CloseCircleOutlined />}
          message="影响分析加载失败，可单独重试"
          description={describeError(error)}
          action={
            onRetry ? (
              <Button size="small" onClick={onRetry}>
                重试
              </Button>
            ) : null
          }
        />
      </Card>
    );
  }

  if (!impact) {
    return (
      <Card title="影响分析" size="small" loading={loading}>
        {!loading && (
          <Empty description="暂无可分析的下游影响" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>
    );
  }

  const meta = COMPLETENESS_META[impact.impact_completeness] ?? COMPLETENESS_META.partial;

  return (
    <Card title="影响分析" size="small">
      <Alert
        type={meta.type}
        message={meta.title}
        description={meta.description}
        showIcon
        style={{ marginBottom: 12 }}
      />

      <Text strong>下游决策（{impact.derived_decisions.length}）</Text>
      <List
        size="small"
        dataSource={impact.derived_decisions}
        locale={{ emptyText: '无下游决策' }}
        renderItem={(d: Record<string, unknown>) => (
          <List.Item
            style={{ cursor: 'pointer', padding: '6px 0' }}
            onClick={() => d.decision_id && onSelectDecision?.(String(d.decision_id))}
          >
            <Space size={8}>
              <Text>
                {String(d.recommended_option || d.name || d.decision_id || d.uuid || '未命名决策')}
              </Text>
              {d.outcome ? <Tag>{String(d.outcome)}</Tag> : null}
            </Space>
          </List.Item>
        )}
      />

      <Text strong>目标对象变化（{impact.target_changes.length}）</Text>
      <List
        size="small"
        dataSource={impact.target_changes}
        locale={{ emptyText: '无目标对象变化记录' }}
        renderItem={(c: Record<string, unknown>, i) => (
          <List.Item style={{ padding: '6px 0' }}>
            <Text type="secondary">
              {c.type === 'edge_invalidated'
                ? `边失效: ${c.from_uuid} -[${c.edge_type}]-> ${c.to_uuid}`
                : `动作: ${c.action_type_id || c.action_record_id || `记录 ${i + 1}`} → ${c.target_object_id || ''}（${c.status || '未记录状态'}）`}
            </Text>
          </List.Item>
        )}
      />

      <Text strong>协同证据决策（{impact.co_evidence_decisions.length}）</Text>
      <List
        size="small"
        dataSource={impact.co_evidence_decisions}
        locale={{ emptyText: '无共享证据的其他决策' }}
        renderItem={(d: Record<string, unknown>) => (
          <List.Item
            style={{ cursor: 'pointer', padding: '6px 0' }}
            onClick={() => {
              const id = d.decision_id || d.uuid;
              if (id) onSelectDecision?.(String(id));
            }}
          >
            <Text>{String(d.recommended_option || d.name || d.decision_id || d.uuid || '未命名决策')}</Text>
          </List.Item>
        )}
      />
    </Card>
  );
}

export default ImpactPanel;
