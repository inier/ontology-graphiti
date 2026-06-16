/**
 * 查询计划可视化 - 展示五阶段管线的理解和计划
 */
import React from 'react';
import { Card, Tag, Space, Typography, Descriptions, Collapse } from 'antd';
import {
  BulbOutlined,
  ScheduleOutlined,
  FormOutlined,
} from '@ant-design/icons';
import type { QueryUnderstanding, QueryPlan, SubQuery } from '../services/nlQueryApi';

const { Text, Paragraph } = Typography;

const INTENT_LABELS: Record<string, { label: string; color: string }> = {
  keyword_lookup: { label: '关键词查找', color: 'blue' },
  semantic_search: { label: '语义搜索', color: 'green' },
  graph_traverse: { label: '图遍历', color: 'orange' },
  complex_analysis: { label: '复杂分析', color: 'purple' },
  temporal_query: { label: '时态查询', color: 'cyan' },
  action: { label: '执行动作', color: 'red' },
};

const PILLAR_COLORS: Record<string, string> = {
  bm25: '#1890ff',
  vector: '#52c41a',
  graph: '#fa8c16',
};

interface QueryPlanViewerProps {
  understanding?: QueryUnderstanding;
  plan?: QueryPlan;
  explanation?: string;
  loading?: boolean;
}

export function QueryPlanViewer({ understanding, plan, explanation, loading }: QueryPlanViewerProps) {
  if (!understanding && !plan && !explanation) {
    return null;
  }

  const intentInfo = understanding
    ? INTENT_LABELS[understanding.intent] || { label: understanding.intent, color: 'default' }
    : null;

  const renderSubQuery = (sq: SubQuery, idx: number) => (
    <div
      key={idx}
      style={{
        padding: '6px 10px',
        marginBottom: 4,
        borderRadius: 6,
        borderLeft: `3px solid ${PILLAR_COLORS[sq.pillar] || '#999'}`,
        background: '#fafafa',
      }}
    >
      <Space size={6}>
        <Tag color={sq.pillar === 'bm25' ? 'blue' : sq.pillar === 'vector' ? 'green' : 'orange'} style={{ margin: 0 }}>
          {sq.pillar.toUpperCase()}
        </Tag>
        <Text style={{ fontSize: 12 }}>{sq.query}</Text>
        {sq.mode && <Tag style={{ fontSize: 11 }}>{sq.mode}</Tag>}
      </Space>
    </div>
  );

  const items = [
    {
      key: 'understanding',
      label: (
        <Space>
          <BulbOutlined />
          <span>查询理解</span>
          {intentInfo && <Tag color={intentInfo.color}>{intentInfo.label}</Tag>}
          {understanding?.needs_clarification && <Tag color="warning">需澄清</Tag>}
        </Space>
      ),
      children: understanding ? (
        <Descriptions size="small" column={1} variant="bordered">
          <Descriptions.Item label="原始查询">{understanding.original_query}</Descriptions.Item>
          <Descriptions.Item label="意图">
            <Tag color={intentInfo?.color}>{intentInfo?.label}</Tag>
            <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              置信度 {(understanding.confidence * 100).toFixed(0)}%
            </Text>
          </Descriptions.Item>
          {understanding.extracted_entities.length > 0 && (
            <Descriptions.Item label="提取实体">
              {understanding.extracted_entities.map((e, i) => (
                <Tag key={i} color="processing" style={{ marginBottom: 2 }}>{e}</Tag>
              ))}
            </Descriptions.Item>
          )}
          {understanding.rewritten_queries.length > 0 && (
            <Descriptions.Item label="改写查询">
              {understanding.rewritten_queries.map((q, i) => (
                <div key={i} style={{ fontSize: 12, color: '#666', marginBottom: 2 }}>{q}</div>
              ))}
            </Descriptions.Item>
          )}
          {understanding.needs_clarification && (
            <Descriptions.Item label="澄清原因">
              <Text type="warning">{understanding.clarification_reason}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      ) : (
        <Text type="secondary">暂无理解结果</Text>
      ),
    },
    {
      key: 'plan',
      label: (
        <Space>
          <ScheduleOutlined />
          <span>查询计划</span>
          {plan && (
            <Tag color="geekblue">{plan.fusion_strategy.toUpperCase()}</Tag>
          )}
        </Space>
      ),
      children: plan ? (
        <div>
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              选用支柱: {plan.pillars.map((p) => (
                <Tag key={p} color={p === 'bm25' ? 'blue' : p === 'vector' ? 'green' : 'orange'} style={{ fontSize: 11 }}>
                  {p.toUpperCase()}
                </Tag>
              ))}
              <span style={{ marginLeft: 8 }}>Top-K: {plan.top_k}</span>
            </Text>
          </div>
          {plan.sub_queries.map(renderSubQuery)}
        </div>
      ) : (
        <Text type="secondary">暂无计划</Text>
      ),
    },
    ...(explanation ? [{
      key: 'explanation',
      label: (
        <Space>
          <FormOutlined />
          <span>解释说明</span>
        </Space>
      ),
      children: <Paragraph style={{ fontSize: 13, margin: 0 }}>{explanation}</Paragraph>,
    }] : []),
  ];

  return (
    <Card
      size="small"
      title="查询分析与计划"
      loading={loading}
      style={{ marginBottom: 12 }}
    >
      <Collapse items={items} defaultActiveKey={['understanding', 'plan']} size="small" />
    </Card>
  );
}
