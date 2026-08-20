/**
 * 决策影响分析面板（ADR-076 §8 前端块 3）
 * 下游决策 / 目标对象变化 / 协同证据决策，含完整性标注
 */
import React from 'react';
import { Alert, Card, Empty, List, Space, Tag, Typography } from 'antd';
import type { DecisionImpact } from '../types';

const { Text } = Typography;

interface Props {
  impact: DecisionImpact | null;
  onSelectDecision?: (decisionId: string) => void;
}

const COMPLETENESS_META: Record<string, { label: string; type: 'success' | 'warning' | 'info' }> = {
  full: { label: '分析完整', type: 'success' },
  degraded_target_resolution: { label: '目标解析降级（部分数据不可用）', type: 'warning' },
  partial: { label: '部分维度缺失', type: 'warning' },
};

export function ImpactPanel({ impact, onSelectDecision }: Props) {
  if (!impact) {
    return (
      <Card title="影响分析" size="small">
        <Empty description="查看因果链后自动加载影响分析" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const meta = COMPLETENESS_META[impact.impact_completeness] || COMPLETENESS_META.partial;

  return (
    <Card title="影响分析" size="small">
      <Alert type={meta.type} message={meta.label} showIcon style={{ marginBottom: 12 }} />

      <Text strong>下游决策（{impact.derived_decisions.length}）</Text>
      <List
        size="small"
        dataSource={impact.derived_decisions}
        locale={{ emptyText: '无下游决策' }}
        renderItem={(d: any) => (
          <List.Item
            style={{ cursor: 'pointer', padding: '6px 0' }}
            onClick={() => d.decision_id && onSelectDecision?.(d.decision_id)}
          >
            <Space size={8}>
              <Text>{d.recommended_option || d.name || d.decision_id || d.uuid}</Text>
              {d.outcome && <Tag>{d.outcome}</Tag>}
            </Space>
          </List.Item>
        )}
      />

      <Text strong>目标对象变化（{impact.target_changes.length}）</Text>
      <List
        size="small"
        dataSource={impact.target_changes}
        locale={{ emptyText: '无目标对象变化记录' }}
        renderItem={(c: any, i) => (
          <List.Item style={{ padding: '6px 0' }}>
            <Text type="secondary">
              {c.type === 'edge_invalidated'
                ? `边失效: ${c.from_uuid} -[${c.edge_type}]-> ${c.to_uuid}`
                : `动作: ${c.action_type_id || c.action_record_id || `记录 ${i + 1}`} → ${c.target_object_id || ''}（${c.status || '未知状态'}）`}
            </Text>
          </List.Item>
        )}
      />

      <Text strong>协同证据决策（{impact.co_evidence_decisions.length}）</Text>
      <List
        size="small"
        dataSource={impact.co_evidence_decisions}
        locale={{ emptyText: '无共享证据的其他决策' }}
        renderItem={(d: any) => (
          <List.Item
            style={{ cursor: 'pointer', padding: '6px 0' }}
            onClick={() => (d.decision_id || d.uuid) && onSelectDecision?.(d.decision_id || d.uuid)}
          >
            <Text>{d.recommended_option || d.name || d.decision_id || d.uuid}</Text>
          </List.Item>
        )}
      />
    </Card>
  );
}
