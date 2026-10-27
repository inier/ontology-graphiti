/**
 * 台账列定义（uiux §4.2，10 列）
 *
 * 只做「字段 → 单元格」的渲染，不含取数逻辑：取数在 `DecisionLedgerTable`。
 * 所有派生展示一律调用 `utils/displayStatus` 的单点实现，列内不再二次判断状态。
 */
import React from 'react';
import { Button, Space, Tooltip, Typography } from 'antd';
import type { ProColumns } from '@ant-design/pro-components';
import {
  CopyOutlined,
  EyeOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import type { DecisionRecord } from '../types';
import { DecisionStatusTag } from './DecisionStatusTag';
import { EvidenceCount } from './EvidenceCount';
import { toActorDisplay, toEntrySourceLabel, toExecutionTier } from '../utils/displayStatus';

const { Text } = Typography;

function formatDateTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

interface ColumnOptions {
  onOpenDetail: (decisionId: string) => void;
  onCopyId: (decisionId: string) => void;
}

export function buildLedgerColumns({ onOpenDetail, onCopyId }: ColumnOptions): ProColumns<DecisionRecord>[] {
  return [
    {
      title: '决策 ID',
      dataIndex: 'decision_id',
      key: 'decision_id',
      width: 150,
      fixed: 'left',
      render: (_dom: React.ReactNode, record: DecisionRecord) => (
        <Space size={4} style={{ maxWidth: '100%' }}>
          <Text
            style={{
              fontFamily: 'var(--odap-font-family-mono)',
              fontSize: 'var(--odap-font-size-xs)',
              whiteSpace: 'nowrap',
            }}
          >
            {record.decision_id}
          </Text>
          <Tooltip title="复制决策 ID">
            <Button
              type="text"
              size="small"
              aria-label="复制决策 ID"
              icon={<CopyOutlined style={{ fontSize: 16 }} />}
              onClick={(e) => {
                e.stopPropagation();
                onCopyId(record.decision_id);
              }}
            />
          </Tooltip>
          {/* 键盘可达的详情入口：整行 onRow 只响鼠标，不能作为唯一入口（uiux §4.7） */}
          <Button
            type="text"
            size="small"
            tabIndex={0}
            aria-label="查看决策详情"
            icon={<EyeOutlined style={{ fontSize: 16 }} />}
            onClick={(e) => {
              e.stopPropagation();
              onOpenDetail(record.decision_id);
            }}
          />
        </Space>
      ),
    },
    {
      title: '问题',
      dataIndex: 'context_summary',
      key: 'context_summary',
      // 唯一的非结构化长文本列，吃掉剩余宽度给这一列
      minWidth: 260,
      render: (_dom: React.ReactNode, record: DecisionRecord) =>
        record.context_summary ? (
          <Text ellipsis={{ tooltip: record.context_summary }} style={{ maxWidth: '100%' }}>
            {record.context_summary}
          </Text>
        ) : (
          <Text type="secondary">未填写场景描述</Text>
        ),
    },
    {
      title: '推荐方案',
      dataIndex: 'recommended_option',
      key: 'recommended_option',
      minWidth: 160,
      render: (_dom: React.ReactNode, record: DecisionRecord) =>
        record.recommended_option ? (
          <Text ellipsis={{ tooltip: record.recommended_option }} style={{ maxWidth: '100%' }}>
            {record.recommended_option}
          </Text>
        ) : (
          <Text type="secondary">未给出方案</Text>
        ),
    },
    {
      title: '结果',
      dataIndex: 'status',
      key: 'status',
      width: 148,
      render: (_: unknown, record) => (
        <DecisionStatusTag
          status={record.status}
          outcome={record.outcome}
          statusAssumed={record.status_assumed}
        />
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 88,
      align: 'right',
      sorter: true,
      render: (_dom: React.ReactNode, record: DecisionRecord) => {
        const value = record.confidence;
        if (value === undefined || value === null || Number.isNaN(value)) {
          return <Text type="secondary">未评估</Text>;
        }
        const percent = Math.round(value * 100);
        const low = value < 0.6;
        return (
          <Text
            style={{
              fontVariantNumeric: 'tabular-nums',
              color: low ? 'var(--odap-color-warning)' : undefined,
            }}
          >
            {low ? `${percent}% 低` : `${percent}%`}
          </Text>
        );
      },
    },
    {
      // 本期契约 `sort` 枚举只到 [created_at, updated_at, confidence]：
      // 这一列照常显示，但**不加 sorter**，表头也不出排序箭头（渲染一个点了没用的箭头是骗点击）
      title: '证据数',
      key: 'evidence_count',
      width: 132,
      render: (_: unknown, record) => (
        <EvidenceCount
          entityCount={record.evidence_entity_ids?.length}
          episodeCount={record.evidence_episode_ids?.length}
        />
      ),
    },
    {
      // 4 档粗粒度；精确 8 态只在详情页（列表不跨库查动作状态，避免 N+1）
      title: '执行状态',
      key: 'execution_tier',
      width: 88,
      render: (_: unknown, record) => {
        const tier = toExecutionTier(record);
        if (tier.tier === 'none') return <Text type="secondary">{tier.label}</Text>;
        const color =
          tier.tier === 'running'
            ? 'var(--odap-color-info)'
            : tier.tier === 'done'
              ? 'var(--odap-color-success)'
              : tier.tier === 'failed'
                ? 'var(--odap-color-error)'
                : 'var(--odap-color-text-secondary)';
        return <Text style={{ color }}>{tier.label}</Text>;
      },
    },
    {
      title: '裁决人',
      key: 'actor',
      width: 140,
      render: (_: unknown, record) => {
        const actor = toActorDisplay(record, record.resolution);
        if (actor.kind === 'system') {
          return (
            <Space size={4}>
              <SafetyCertificateOutlined
                style={{ fontSize: 16, color: 'var(--odap-color-text-secondary)' }}
              />
              <Text>{actor.text}</Text>
            </Space>
          );
        }
        return actor.muted ? <Text type="secondary">{actor.text}</Text> : <Text>{actor.text}</Text>;
      },
    },
    {
      title: '来源入口',
      dataIndex: 'entry_source',
      key: 'entry_source',
      width: 112,
      render: (_dom: React.ReactNode, record: DecisionRecord) => {
        const source = toEntrySourceLabel(record.entry_source);
        return source.muted ? <Text type="secondary">{source.label}</Text> : <Text>{source.label}</Text>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 148,
      sorter: true,
      render: (_dom: React.ReactNode, record: DecisionRecord) => (
        <Text style={{ fontVariantNumeric: 'tabular-nums' }}>{formatDateTime(record.created_at)}</Text>
      ),
    },
  ];
}
