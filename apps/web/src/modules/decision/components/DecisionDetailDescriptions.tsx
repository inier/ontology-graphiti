/**
 * 详情页字段区（原 10 项 + 本期新增）
 *
 * 三条「整行不渲染」规则（不是显示「—」）：
 * - 驳回理由：仅「已驳回」状态渲染该行
 * - 关联任务 ID：仅 `entry_source = agent` 渲染
 * - 推理摘要：有内容才渲染
 * 门禁拒绝与人工驳回用**同一位置、同一字号、同一层级**，只在标签前缀区分，
 * 不给门禁摘要单独底色 —— 它是同一字段的另一种来源，不是另一种卡片。
 */
import React from 'react';
import { Descriptions, Space, Tag, Typography } from 'antd';
import { CopyOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import type { DecisionRecord } from '../types';
import { DecisionStatusTag } from './DecisionStatusTag';
import { EvidenceCount } from './EvidenceCount';
import { toActorDisplay, toEntrySourceLabel, toExecutionTier } from '../utils/displayStatus';

const { Text, Paragraph } = Typography;

interface Props {
  decision: DecisionRecord;
  onCopyId?: (id: string) => void;
}

function formatDateTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

export function DecisionDetailDescriptions({ decision, onCopyId }: Props) {
  const actor = toActorDisplay(decision, decision.resolution);
  const source = toEntrySourceLabel(decision.entry_source);
  const tier = toExecutionTier(decision);
  const confidence = typeof decision.confidence === 'number' ? decision.confidence : null;
  const lowConfidence = confidence !== null && confidence < 0.6;
  const resolution = decision.resolution;
  const gateRejected = resolution?.actor_type === 'system';

  return (
    <Descriptions size="small" column={2} bordered>
      <Descriptions.Item label="决策 ID">
        <Space size={4}>
          <Text style={{ fontFamily: 'var(--odap-font-family-mono)' }}>{decision.decision_id}</Text>
          <CopyOutlined
            style={{ fontSize: 16, cursor: 'pointer' }}
            aria-label="复制决策 ID"
            onClick={() => onCopyId?.(decision.decision_id)}
          />
        </Space>
      </Descriptions.Item>

      <Descriptions.Item label="可见状态">
        <DecisionStatusTag
          status={decision.status}
          outcome={decision.outcome}
          statusAssumed={decision.status_assumed}
        />
      </Descriptions.Item>

      <Descriptions.Item label="推荐方案" span={2}>
        {decision.recommended_option || <Text type="secondary">未给出方案</Text>}
      </Descriptions.Item>

      <Descriptions.Item label="置信度">
        {confidence === null ? (
          <Text type="secondary">未评估</Text>
        ) : (
          <Text
            style={{
              fontVariantNumeric: 'tabular-nums',
              color: lowConfidence ? 'var(--odap-color-warning)' : undefined,
            }}
          >
            {lowConfidence
              ? `${Math.round(confidence * 100)}% 低`
              : `${Math.round(confidence * 100)}%`}
          </Text>
        )}
      </Descriptions.Item>

      <Descriptions.Item label="证据数">
        <EvidenceCount
          entityCount={decision.evidence_entity_ids?.length}
          episodeCount={decision.evidence_episode_ids?.length}
          variant="detailed"
        />
      </Descriptions.Item>

      <Descriptions.Item label="来源入口">
        {source.muted ? <Text type="secondary">{source.label}</Text> : source.label}
      </Descriptions.Item>

      <Descriptions.Item label="决策方法">{decision.decision_method || '未标注'}</Descriptions.Item>

      <Descriptions.Item label="裁决人 / 时间">
        {actor.kind === 'system' ? (
          <Space size={4}>
            <SafetyCertificateOutlined
              style={{ fontSize: 16, color: 'var(--odap-color-text-secondary)' }}
            />
            <Text>{actor.text}</Text>
          </Space>
        ) : actor.muted ? (
          <Text type="secondary">{actor.text}</Text>
        ) : (
          <Text>{actor.text}</Text>
        )}
      </Descriptions.Item>

      <Descriptions.Item label="创建时间">{formatDateTime(decision.created_at)}</Descriptions.Item>

      {/* 仅「已驳回」渲染该行；门禁拒绝与人工驳回只看前缀区分 */}
      {decision.status === 'rejected' && (
        <Descriptions.Item label="驳回理由" span={2}>
          <Text strong style={{ marginRight: 8 }}>
            {gateRejected ? '门禁判定：' : '驳回理由：'}
          </Text>
          {resolution?.reason ? (
            <Text>{resolution.reason}</Text>
          ) : gateRejected ? (
            <Text type="secondary">门禁未返回原因，请查看执行动作详情</Text>
          ) : (
            <Text type="secondary">未填写驳回理由</Text>
          )}
        </Descriptions.Item>
      )}

      <Descriptions.Item label="执行动作" span={2}>
        {decision.action_record_id ? (
          <Space size={8}>
            <Text style={{ fontFamily: 'var(--odap-font-family-mono)' }}>
              {decision.action_record_id}
            </Text>
            <Tag
              style={{ background: 'var(--odap-color-bg-tertiary)', borderColor: 'var(--odap-color-border)' }}
            >
              {tier.label}
            </Tag>
          </Space>
        ) : (
          <Space orientation="vertical" size={0}>
            <Text>无关联执行动作</Text>
            <Text type="secondary" style={{ fontSize: 'var(--odap-font-size-xs)' }}>
              该决策尚未派发执行
            </Text>
          </Space>
        )}
      </Descriptions.Item>

      {/* Agent 来源独有：`DecisionRecord` 只有 `agent_id`，没有 `task_id`，
          因此不渲染「关联任务 ID」行（缺字段就不给空壳），只展示真实存在的 agent_id */}
      {decision.entry_source === 'agent' && (
        <Descriptions.Item label="关联 Agent">
          {decision.agent_id ? (
            <Text style={{ fontFamily: 'var(--odap-font-family-mono)' }}>{decision.agent_id}</Text>
          ) : (
            <Text type="secondary">未回填 agent_id</Text>
          )}
        </Descriptions.Item>
      )}

      {decision.reasoning && (
        <Descriptions.Item label="推理摘要" span={2}>
          <Paragraph ellipsis={{ rows: 3, expandable: true, symbol: '展开' }} style={{ marginBottom: 0 }}>
            {decision.reasoning}
          </Paragraph>
        </Descriptions.Item>
      )}
    </Descriptions>
  );
}

export default DecisionDetailDescriptions;
